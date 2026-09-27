import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from loguru import logger

from taktik.core.shared.behavior.policy import parse_behavior_policy
from taktik.core.shared.behavior.profiles import resolve_pacing_profile
from taktik.core.shared.behavior.sampling import sample_within
from taktik.core.shared.behavior.session_state import BehaviorSessionState

from taktik.core.shared.diagnostics import run_halt
from . import stop_reasons
from .warmup_budget import WarmupBudget


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
            'unfollows': 0,
            'likes': 0,
            'comments': 0,
            # Liking a COMMENT is counted apart from liking a POST so the operator can read
            # what a run actually did. Both feed the same daily like budget (see
            # StatsRepository._INTERACTION_COLUMN_MAP) — same surface, same risk family.
            'comment_likes': 0,
            # No story counter: nothing read it (no cap, story views being passive; no display;
            # the end-of-run figures come from the ledger's STORY_WATCH rows) and no workflow
            # fed it. Removed on 2026-09-25 rather than wired as a second count of those rows.
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

        # Warmup guardrail caps injected by the desktop app (empty in standalone -> no enforcement),
        # counted against the account's day. The same counter as the Taktik Agent's; the workflow,
        # which holds the account, points it at the ledger (`warmup.count_against_account`).
        self.warmup = WarmupBudget(session_settings.get('warmup_policy'))

    def should_continue(self) -> tuple[bool, str]:
        """Check if session should continue based on defined limits.

        Returns:
            tuple[bool, str]: (should_continue, stop_reason). The reason is a
            ``stop_reasons.StopReason``, which IS the English sentence it always was and
            additionally carries the structured code the desktop app reads.
        """
        # Ce que le run ne peut plus faire, avant ce qu'il n'a plus le droit de faire : un run
        # dont le telephone a disparu n'a pas a voir sa duree evaluee. Le verrou est pose par
        # `base_action` quand il constate un lien perdu ou un plantage de l'application cible --
        # deux pannes qui, jusqu'ici, laissaient la boucle tourner jusqu'a son plafond -- et par le
        # detecteur Instagram des qu'il voit « Reessayer plus tard » (2026-09-24).
        arret = run_halt.arret_demande()
        if arret:
            reason = stop_reasons.for_halt(arret)
            log.info(f"🛑 Session ended: {reason}")
            return False, reason

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
            reason = stop_reasons.duration_cap(configured_duration)
            log.info(f"🛑 Session ended: {reason}")
            return False, reason

        session_settings = self.config.get('session_settings', {})
        workflow_type = session_settings.get('workflow_type', 'unknown')
        
        log.debug(f"Limits check ({workflow_type}): profiles={self.counters['profiles_processed']}/{session_settings.get('total_profiles_limit', 'inf')}, likes={self.counters['likes']}/{session_settings.get('total_likes_limit', 'inf')}, follows={self.counters['follows']}/{session_settings.get('total_follows_limit', 'inf')}")
        
        # Check the handled-profiles cap
        profiles_limit = session_settings.get('total_profiles_limit', float('inf'))
        if profiles_limit and profiles_limit != float('inf') and self.counters['profiles_processed'] >= profiles_limit:
            reason = stop_reasons.profiles_cap(self.counters['profiles_processed'], profiles_limit)
            log.info(f"🛑 Session ended: {reason}")
            return False, reason
        
        # The per-type ceilings (follows, likes) are NOT checked here any more. A spent follow
        # budget says nothing about the right to like or watch a story, and ending the run on it
        # was the single biggest waste in a session: `total_follows_limit` is derived as
        # ceil(profiles x follow%), which is the EXPECTED value of the roll, so roughly half the
        # runs reached it -- around profile 26 of 30 on the default settings -- and took the
        # likes and stories down with them.
        #
        # They now disable their own action instead, through `exhausted_intents()`, which the
        # interaction engine reads to drop that intent from each per-profile plan. Same rule the
        # daily sub-quotas already followed; there is now one rule instead of two.

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
        #
        # Not for an unfollow session: an unfollow spends none of this budget (likes, follows,
        # comments), and its own ceilings, the session maximum and the day's unfollow budget,
        # are `unfollow_allowance`. The day's likes used to end an unfollow run before its
        # first unfollow (review of 2026-09-24).
        #
        # Then the written-action cap for THIS session, which spreads the day over several gentle
        # sessions rather than one dump (story views, being passive, do not enter it).
        #
        # Only these global budgets stop the session; the per-type daily sub-quotas disable their
        # own action (`exhausted_intents`). A read error does not kill the session, and a cap that
        # can no longer be READ does not silently become "no cap" either: the budget tolerates
        # isolated failures and stops after a few in a row (`warmup_budget.py`). The day is read
        # once per profile: the read frequency stays negligible.
        stop_reason = self.warmup.stop_reason(self._written_actions(), day_budget=workflow_type != 'unfollow')
        if stop_reason:
            log.info(f"🛑 Session ended: {stop_reason}")
            return False, stop_reason

        return True, ""

    def _written_actions(self) -> int:
        """This session's written actions (likes + follows + comments), the unit of the warmup's
        session cap."""
        return self.counters['likes'] + self.counters['follows'] + self.counters['comments']

    def exhausted_intents(self) -> set:
        """The actions whose budget is spent — SESSION ceilings and DAILY sub-quotas together.

        The caller removes each of these from the per-profile plan, so a run that has used up
        its follows keeps liking and watching stories instead of ending. Returning them from one
        place is the point: a session ceiling and a daily quota mean the same thing to the
        engine — stop doing THAT — and used to be handled by two different mechanisms, one of
        which killed the run.

        Empty in standalone, where no cap is injected, and empty on a read error — fail-open,
        like the rest of the guard.
        """
        spent = set()

        # Session ceilings, derived from the operator's numbers by the config builder.
        session_settings = self.config.get('session_settings', {})
        follows_limit = session_settings.get('total_follows_limit', 0) or 0
        if follows_limit and follows_limit != float('inf') and self.counters['follows'] >= follows_limit:
            spent.add('follow')
        likes_limit = session_settings.get('total_likes_limit', 0) or 0
        if likes_limit and likes_limit != float('inf') and self.counters['likes'] >= likes_limit:
            spent.add('like')

        # Daily sub-quotas, injected by the desktop guard.
        return spent | self.warmup.exhausted_intents()

    def decision_budget_snapshot(self) -> Dict[str, Dict[str, int]]:
        """Return factual live budget state for an injected premium decision provider.

        This exposes no allocation strategy: the public Bot reports the real counters and the
        hard caps already injected by Electron. With no desktop policy/provider every value is
        zero, preserving standalone behavior and preventing a caller from assuming free budget.
        """
        usage = self.warmup.read_daily_usage() or {}
        caps = self.warmup.policy
        session_total = self._written_actions()
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

    def unfollow_allowance(self, session_limit: Any) -> tuple:
        """How many unfollows this session may still make: (room, stop_reason).

        Two ceilings, both counted in unfollows. The session's maximum, the page's "Maximum
        d'unfollows": it used to cap one BATCH, which the session relaunched until its duration
        ran out (164 unfollows in a morning on one account). And the day's unfollow budget of the
        warmup policy, `max_unfollows_per_day`, read from today's totals like the action budget.
        `room` is None when neither ceiling applies; `stop_reason` is set only when room is 0.
        """
        done = int(self.counters.get('unfollows', 0))
        limit = int(session_limit or 0)
        room: Optional[int] = max(limit - done, 0) if limit > 0 else None
        if room == 0:
            return 0, stop_reasons.unfollows_cap(done, limit)
        day_room, day_reason = self.warmup.unfollow_room()
        if day_reason:
            return 0, day_reason
        if day_room is not None:
            room = day_room if room is None else min(room, day_room)
        return room, None

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
        elif action_type == 'unfollow' and success:
            self.counters['unfollows'] += 1
        elif action_type == 'like_posts' and success:
            self.counters['likes'] += 1
        elif action_type == 'comment_posts' and success:
            self.counters['comments'] += 1
        elif action_type == 'like_comment' and success:
            self.counters['comment_likes'] += 1

        if source and source in self.source_counters:
            self.source_counters[source]['interactions'] += 1
            if success:
                if action_type == 'follow_user':
                    self.source_counters[source]['follows'] += 1
                elif action_type == 'like_posts':
                    self.source_counters[source]['likes'] += 1
                elif action_type == 'comment_posts':
                    self.source_counters[source]['comments'] += 1

    def get_delay_between_actions(self) -> float:
        """Return the delay (seconds) between high-level workflow actions.

        An EXPLICIT user delay (`session_settings.delay_between_actions`) still wins for
        back-compat (the UI sends it today); when it's absent — once the UI moves to the
        pacing profile (Lot 4) — the active `PacingProfile` provides the range. Default
        profile 'balanced' = the historical 5-15s, so behaviour is unchanged either way.
        """
        delay_config = self.config.get('session_settings', {}).get('delay_between_actions')
        if isinstance(delay_config, dict) and ('min' in delay_config or 'max' in delay_config):
            low, high = delay_config.get('min', 5), delay_config.get('max', 15)
        else:
            low, high = self.pacing.action_delay_min, self.pacing.action_delay_max

        # Pace floor of the guard: never faster than this minimum, whatever the pacing profile
        # chosen elsewhere. This is the lever that breaks the mechanical regularity observed on
        # a fresh account. Zero or absent means no floor, and standalone is unchanged.
        floor = self.warmup.min_action_gap_seconds()
        if floor <= 0:
            return random.uniform(low, high)
        # A delay under the floor is drawn again. When the whole range sits under it, the delay
        # keeps the range's own spread above the floor: raising every gap to exactly the floor
        # made the cadence a metronome, the very regularity the floor is there to break.
        spread = max(abs(high - low), 0.1 * floor)
        return sample_within(lambda: random.uniform(low, high), floor, float('inf'),
                             edge_band=spread)

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
        self.warmup.set_policy(session_settings.get('warmup_policy'))
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
