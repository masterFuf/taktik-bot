import random
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional
from loguru import logger

from taktik.core.shared.behavior.policy import parse_behavior_policy
from taktik.core.shared.behavior.profiles import resolve_pacing_profile
from taktik.core.shared.behavior.session_state import BehaviorSessionState


log = logger.bind(module="session-manager")


class SessionManager:
    """Manages automation sessions with limits and action probabilities."""

    def __init__(self, config: Dict):
        """Initialize session manager with configuration.

        Args:
            config: Configuration dictionary loaded from JSON file
        """
        self.config = config
        self.session_start_time = datetime.now()
        # Id of the PERSISTED session, when the caller opened one. The stats mixin already
        # looked it up, but the attribute existed nowhere: every run without the full
        # automation object therefore wrote its interactions with no session id. They
        # existed in the database without ever appearing in a session, so without ever
        # reaching the figures shown.
        #
        self.session_id: Optional[int] = None

        # Phase separation: scraping versus interaction
        self.scraping_start_time = None
        self.scraping_end_time = None
        self.interaction_start_time = None
        
        self.counters = {
            'total_interactions': 0,
            'successful_interactions': 0,
            'profiles_processed': 0,  # Nombre de profils traités (visités)
            'follows': 0,
            'likes': 0,
            'comments': 0,
            # Liking a COMMENT is counted apart from liking a POST so the operator can read
            # what a run actually did. Both feed the same daily like budget (see
            # StatsRepository._INTERACTION_COLUMN_MAP) — same surface, same risk family.
            'comment_likes': 0,
            'stories_watched': 0
        }
        self.source_counters = {}
        
        session_settings = self.config.get('session_settings', {})
        duration_minutes = session_settings.get('session_duration_minutes', 60)
        log.debug(f"Configuration received: duration={duration_minutes}min, settings={session_settings}")

        # Pacing profile (rhythm = a style, not user-set seconds). Default 'balanced' reproduces
        # today's behaviour. Drives the between-actions delay when no explicit user delay is set.
        policy = parse_behavior_policy(self.config)
        self.pacing = resolve_pacing_profile(policy.profile_id if policy else None)
        self.behavior_state = BehaviorSessionState(
            seed=policy.seed if policy else None,
            strict_regression=policy.strict_regression if policy else False,
            profile_id=self.pacing.profile_id,
        )
        if policy:
            log.info(f"Pacing profile: {self.pacing.profile_id}")

        # Warmup guardrail caps injected by the desktop app (empty in standalone -> no enforcement).
        self._warmup_policy = session_settings.get('warmup_policy') or {}
        # Provider of TODAY's totals for this account (daily_stats), injected by the workflow which
        # holds the account_id + DB. Kept as a callable so SessionManager never owns a repository
        # (DI: the DB read is injected, not hidden here). None -> the daily-cap check is skipped.
        self._daily_usage_provider: Optional[Callable[[], Dict[str, int]]] = None

    def should_continue(self) -> tuple[bool, str]:
        """Check if session should continue based on defined limits.

        Returns:
            tuple[bool, str]: (should_continue, stop_reason)
        """
        # Durée totale de session (limite principale)
        session_duration = datetime.now() - self.session_start_time
        
        # Interaction duration, for information
        interaction_duration = self.get_interaction_duration()
        
        configured_duration = self.config.get('session_settings', {}).get('session_duration_minutes', 60)
        max_duration = timedelta(minutes=configured_duration)
        
        # Check the TOTAL session duration, not only the interaction
        should_stop_duration = session_duration > max_duration
        
        log.debug(f"Duration check: total={session_duration}, scraping={self.get_scraping_duration()}, interaction={interaction_duration}, max={configured_duration}min, stop={should_stop_duration}")
        
        # Check the total session duration
        if should_stop_duration:
            reason = f"Maximum session duration reached ({configured_duration} minutes)"
            log.info(f"🛑 Session ended: {reason}")
            return False, reason

        session_settings = self.config.get('session_settings', {})
        workflow_type = session_settings.get('workflow_type', 'unknown')
        
        log.debug(f"Limits check ({workflow_type}): profiles={self.counters['profiles_processed']}/{session_settings.get('total_profiles_limit', 'inf')}, likes={self.counters['likes']}/{session_settings.get('total_likes_limit', 'inf')}, follows={self.counters['follows']}/{session_settings.get('total_follows_limit', 'inf')}")
        
        # Check the handled-profiles cap
        profiles_limit = session_settings.get('total_profiles_limit', float('inf'))
        if profiles_limit and profiles_limit != float('inf') and self.counters['profiles_processed'] >= profiles_limit:
            reason = f"Profiles limit reached ({self.counters['profiles_processed']}/{profiles_limit})"
            log.info(f"🛑 Session ended: {reason}")
            return False, reason
        
        # Check the follow cap, when configured
        follows_limit = session_settings.get('total_follows_limit', float('inf'))
        if follows_limit and follows_limit != float('inf') and follows_limit > 0 and self.counters['follows'] >= follows_limit:
            reason = f"Follows limit reached ({self.counters['follows']}/{follows_limit})"
            log.info(f"🛑 Session ended: {reason}")
            return False, reason
            
        # Check the like cap, when configured
        likes_limit = session_settings.get('total_likes_limit', float('inf'))
        if likes_limit and likes_limit != float('inf') and likes_limit > 0 and self.counters['likes'] >= likes_limit:
            reason = f"Likes limit reached ({self.counters['likes']}/{likes_limit})"
            log.info(f"🛑 Session ended: {reason}")
            return False, reason

        # Ramp-up guard: the DAILY cap for this account, across every session.
        #
        # The caps above are per-session and restart from zero on each run, which is exactly
        # what allowed several sessions to be stacked well past a day's worth.
        # Here the real daily total is read and the session stops when the budget is reached.
        # Defence in depth: the front already blocks the LAUNCH, but one long session could
        # blow the budget on its own.
        #
        # Active only when both the caps and a totals provider were injected; in standalone
        # both are absent and the behaviour is unchanged. A cap of zero means no limit.
        stop_reason = self._check_daily_budget()
        if stop_reason:
            log.info(f"🛑 Session ended: {stop_reason}")
            return False, stop_reason

        # Written-action cap for THIS session. It complements the daily budget by spreading the
        # day over several gentle sessions rather than one dump. It counts the written actions
        # only; story views, being passive, do not enter the budget. Zero or absent means no
        # cap.
        max_per_session = int(self._warmup_policy.get('max_actions_per_session', 0) or 0)
        if max_per_session > 0:
            session_actions = (
                self.counters['likes'] + self.counters['follows'] + self.counters['comments']
            )
            if session_actions >= max_per_session:
                reason = f"Session action cap reached ({session_actions}/{max_per_session})"
                log.info(f"🛑 Session ended: {reason}")
                return False, reason

        return True, ""

    def _check_daily_budget(self) -> str:
        """Is the GLOBAL daily budget reached? Returns the stop reason, or empty to continue.

        Only the global action budget stops the session. The per-type sub-quotas are NOT a stop
        reason: they disable their own action for the rest of the day. Treating them as one
        killed the whole session as soon as the LEAST essential cap was reached, while the
        global budget still left room to like and watch stories.
        

        Best-effort: a read error must not kill the session. The provider reads the account
        daily totals on each call, and this is consulted once per profile, so the read
        frequency stays negligible.
        """
        usage = self._read_daily_usage()
        if usage is None:
            return ""

        max_actions = int(self._warmup_policy.get('max_actions_per_day', 0) or 0)
        total = int(usage.get('total', 0))
        if max_actions > 0 and total >= max_actions:
            return f"Daily action budget reached ({total}/{max_actions})"
        return ""

    def _read_daily_usage(self) -> Optional[Dict[str, int]]:
        """The account daily totals, or None when there is nothing to enforce."""
        provider = self._daily_usage_provider
        if provider is None or not self._warmup_policy:
            return None
        try:
            return provider() or {}
        except Exception as exc:  # noqa: BLE001 — the guard must never fail a run
            log.warning(f"Daily-budget provider failed (continuing without cap): {exc}")
            return None

    def exhausted_daily_quotas(self) -> set:
        """The sub-quotas spent today.

        The caller removes the matching intent from each per-profile plan, so the session keeps
        liking and watching stories while the daily comments are spent. Empty in standalone,
        where no cap is injected, and empty on a read error — fail-open, like the rest of the
        guard.
        """
        usage = self._read_daily_usage()
        if usage is None:
            return set()

        caps = self._warmup_policy
        spent = set()
        max_follows = int(caps.get('max_follows_per_day', 0) or 0)
        if max_follows > 0 and int(usage.get('follows', 0)) >= max_follows:
            spent.add('follow')
        max_comments = int(caps.get('max_comments_per_day', 0) or 0)
        if max_comments > 0 and int(usage.get('comments', 0)) >= max_comments:
            spent.add('comment')
        return spent

    def set_daily_usage_provider(self, provider: Optional[Callable[[], Dict[str, int]]]) -> None:
        """Inject the callable returning TODAY's totals for this account (keys: total/follows/comments).

        Called by the workflow once the account_id is resolved. Without it, the daily-budget check
        is a no-op — which keeps the standalone bot exactly as before.
        """
        self._daily_usage_provider = provider

    def decision_budget_snapshot(self) -> Dict[str, Dict[str, int]]:
        """Return factual live budget state for an injected premium decision provider.

        This exposes no allocation strategy: the public Bot reports the real counters and the
        hard caps already injected by Electron. With no desktop policy/provider every value is
        zero, preserving standalone behavior and preventing a caller from assuming free budget.
        """
        usage = self._read_daily_usage() or {}
        caps = self._warmup_policy
        session_total = (
            int(self.counters.get('likes', 0))
            + int(self.counters.get('follows', 0))
            + int(self.counters.get('comments', 0))
        )
        return {
            'daily': {
                'total': int(usage.get('total', 0) or 0),
                'follows': int(usage.get('follows', 0) or 0),
                'comments': int(usage.get('comments', 0) or 0),
            },
            'session': {
                'total': session_total,
                'likes': int(self.counters.get('likes', 0)),
                'follows': int(self.counters.get('follows', 0)),
                'comments': int(self.counters.get('comments', 0)),
            },
            'caps': {
                'max_actions_per_day': int(caps.get('max_actions_per_day', 0) or 0),
                'max_follows_per_day': int(caps.get('max_follows_per_day', 0) or 0),
                'max_comments_per_day': int(caps.get('max_comments_per_day', 0) or 0),
                'max_actions_per_session': int(caps.get('max_actions_per_session', 0) or 0),
            },
        }

    def record_profile_processed(self):
        """Record that a profile has been processed (visited for interaction).
        
        This should be called once per profile, regardless of how many actions are performed.
        """
        self.counters['profiles_processed'] += 1
        logger.debug(f"📊 Profile processed: {self.counters['profiles_processed']}")
    
    def record_action(self, action_type: str, success: bool = True, source: Optional[str] = None):
        """Record performed action.

        Args:
            action_type: Action type
            success: Whether action succeeded
            source: Action source (optional)
        """
        self.counters['total_interactions'] += 1
        # Remote per-action quotas were removed; action history is local SQLite.
        if success:
            self.counters['successful_interactions'] += 1

        if action_type == 'follow_user' and success:
            self.counters['follows'] += 1
        elif action_type == 'like_posts' and success:
            self.counters['likes'] += 1
        elif action_type == 'comment_posts' and success:
            self.counters['comments'] += 1
        elif action_type == 'like_comment' and success:
            self.counters['comment_likes'] += 1
        elif action_type == 'watch_stories' and success:
            self.counters['stories_watched'] += 1

        if source and source in self.source_counters:
            self.source_counters[source]['interactions'] += 1
            if success:
                if action_type == 'follow_user':
                    self.source_counters[source]['follows'] += 1
                elif action_type == 'like_posts':
                    self.source_counters[source]['likes'] += 1
                elif action_type == 'comment_posts':
                    self.source_counters[source]['comments'] += 1
                elif action_type == 'watch_stories':
                    self.source_counters[source]['stories_watched'] = (
                        self.source_counters[source].get('stories_watched', 0) + 1
                    )

    def get_delay_between_actions(self) -> float:
        """Return the delay (seconds) between high-level workflow actions.

        An EXPLICIT user delay (`session_settings.delay_between_actions`) still wins for
        back-compat (the UI sends it today); when it's absent — once the UI moves to the
        pacing profile (Lot 4) — the active `PacingProfile` provides the range. Default
        profile 'balanced' = the historical 5-15s, so behaviour is unchanged either way.
        """
        delay_config = self.config.get('session_settings', {}).get('delay_between_actions')
        if isinstance(delay_config, dict) and ('min' in delay_config or 'max' in delay_config):
            delay = random.uniform(delay_config.get('min', 5), delay_config.get('max', 15))
        else:
            delay = random.uniform(self.pacing.action_delay_min, self.pacing.action_delay_max)

        # Pace floor of the guard: never faster than this minimum, whatever the pacing profile
        # chosen elsewhere. This is the lever that breaks the mechanical regularity observed on
        # a fresh account. Zero or absent means no floor, and standalone is unchanged.
        floor = float(self._warmup_policy.get('min_action_gap_seconds', 0) or 0)
        return max(delay, floor) if floor > 0 else delay

    def get_session_stats(self) -> Dict:
        """Return current session statistics.

        Returns:
            Dict: Dictionary containing statistics
        """
        return {
            'start_time': self.session_start_time,
            'total_duration': str(datetime.now() - self.session_start_time),
            'scraping_duration': str(self.get_scraping_duration()),
            'interaction_duration': str(self.get_interaction_duration()),
            **self.counters
        }

    def update_config(self, new_config: Dict):
        """Update SessionManager configuration without recreating instance.
        
        Args:
            new_config: New configuration to apply
        """
        self.config = new_config

        # Re-resolve the pacing profile so a mid-session behaviorPolicy change is picked up
        # (update_config is called on every run_workflow); otherwise self.pacing stays stale.
        policy = parse_behavior_policy(self.config)
        self.pacing = resolve_pacing_profile(policy.profile_id if policy else None)
        self.behavior_state.reconfigure(
            seed=policy.seed if policy else None,
            strict_regression=policy.strict_regression if policy else False,
            profile_id=self.pacing.profile_id,
        )

        session_settings = self.config.get('session_settings', {})
        # Same reason as the pacing profile: refresh the warmup caps on a config swap. The injected
        # usage provider is deliberately NOT touched here — it carries the resolved account_id.
        self._warmup_policy = session_settings.get('warmup_policy') or {}
        duration_minutes = session_settings.get('session_duration_minutes', 60)
        log.debug(f"Configuration updated: duration={duration_minutes}min, settings={session_settings}")
    
    def start_scraping_phase(self):
        """Mark the start of the scraping phase."""
        self.scraping_start_time = datetime.now()
        log.debug(f"🔍 Scraping phase started at {self.scraping_start_time}")
    
    def end_scraping_phase(self):
        """Mark the end of the scraping phase."""
        self.scraping_end_time = datetime.now()
        if self.scraping_start_time:
            scraping_duration = self.scraping_end_time - self.scraping_start_time
            log.debug(f"✅ Scraping phase ended - Duration: {scraping_duration}")
        else:
            log.warning("Scraping end called but no start time recorded")
    
    def start_interaction_phase(self):
        """Mark the start of the interaction phase, once per session."""
        if self.interaction_start_time is None:
            self.interaction_start_time = datetime.now()
            log.debug(f"🎯 Interaction phase started at {self.interaction_start_time}")
        else:
            log.debug(f"Interaction phase already started at {self.interaction_start_time} (not resetting)")
    
    def get_scraping_duration(self) -> timedelta:
        """Duration of the scraping phase."""
        if self.scraping_start_time and self.scraping_end_time:
            return self.scraping_end_time - self.scraping_start_time
        return timedelta(0)
    
    def get_interaction_duration(self) -> timedelta:
        """Duration of the interaction phase."""
        if self.interaction_start_time:
            return datetime.now() - self.interaction_start_time
        return timedelta(0)
