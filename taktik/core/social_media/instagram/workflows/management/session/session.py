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
        
        # Séparation des phases : scraping vs interaction
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
        
        # Durée d'interaction (pour info)
        interaction_duration = self.get_interaction_duration()
        
        configured_duration = self.config.get('session_settings', {}).get('session_duration_minutes', 60)
        max_duration = timedelta(minutes=configured_duration)
        
        # Vérifier la durée TOTALE de session (pas seulement l'interaction)
        should_stop_duration = session_duration > max_duration
        
        log.debug(f"Duration check: total={session_duration}, scraping={self.get_scraping_duration()}, interaction={interaction_duration}, max={configured_duration}min, stop={should_stop_duration}")
        
        # Vérifier la durée totale de session
        if should_stop_duration:
            reason = f"Maximum session duration reached ({configured_duration} minutes)"
            log.info(f"🛑 Session ended: {reason}")
            return False, reason

        session_settings = self.config.get('session_settings', {})
        workflow_type = session_settings.get('workflow_type', 'unknown')
        
        log.debug(f"Limits check ({workflow_type}): profiles={self.counters['profiles_processed']}/{session_settings.get('total_profiles_limit', 'inf')}, likes={self.counters['likes']}/{session_settings.get('total_likes_limit', 'inf')}, follows={self.counters['follows']}/{session_settings.get('total_follows_limit', 'inf')}")
        
        # Vérifier la limite de profils traités
        profiles_limit = session_settings.get('total_profiles_limit', float('inf'))
        if profiles_limit and profiles_limit != float('inf') and self.counters['profiles_processed'] >= profiles_limit:
            reason = f"Profiles limit reached ({self.counters['profiles_processed']}/{profiles_limit})"
            log.info(f"🛑 Session ended: {reason}")
            return False, reason
        
        # Vérifier la limite de follows (si configurée et > 0)
        follows_limit = session_settings.get('total_follows_limit', float('inf'))
        if follows_limit and follows_limit != float('inf') and follows_limit > 0 and self.counters['follows'] >= follows_limit:
            reason = f"Follows limit reached ({self.counters['follows']}/{follows_limit})"
            log.info(f"🛑 Session ended: {reason}")
            return False, reason
            
        # Vérifier la limite de likes (si configurée et > 0)
        likes_limit = session_settings.get('total_likes_limit', float('inf'))
        if likes_limit and likes_limit != float('inf') and likes_limit > 0 and self.counters['likes'] >= likes_limit:
            reason = f"Likes limit reached ({self.counters['likes']}/{likes_limit})"
            log.info(f"🛑 Session ended: {reason}")
            return False, reason

        # Garde-fou de montée en charge : plafond du JOUR pour ce compte (toutes sessions confondues).
        #
        # Les limites ci-dessus sont par-session et repartent de zéro à chaque run — c'est
        # précisément ce qui a permis d'empiler sept sessions et de dépasser largement le jour 1.
        # Ici on lit le total réel du jour (daily_stats, que le bot incrémente en direct) et on
        # arrête net quand le budget est atteint. Défense en profondeur : le front bloque déjà le
        # LANCEMENT, mais une seule longue session pourrait à elle seule crever le budget.
        #
        # N'agit que si le desktop a injecté des plafonds ET un fournisseur de totaux : en standalone
        # les deux sont absents, le comportement est inchangé. Un plafond à 0 = pas de limite.
        stop_reason = self._check_daily_budget()
        if stop_reason:
            log.info(f"🛑 Session ended: {stop_reason}")
            return False, stop_reason

        # Plafond d'actions écrites pour CETTE session (injecté par le desktop). Complète le budget
        # du jour : il étale la journée sur plusieurs sessions douces au lieu d'un dump unique. Compte
        # les actions écrites de la session (like/follow/commentaire) — les vues de story, passives,
        # n'entrent pas dans le budget. 0/absent = pas de plafond (standalone inchangé).
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
        """Le budget GLOBAL du jour est-il atteint ? Renvoie la raison d'arrêt, ou '' pour continuer.

        Seul le budget d'actions global arrête la session. Les sous-quotas (suivis, commentaires)
        ne sont PAS un motif d'arrêt : ils désactivent leur propre action pour le reste de la
        journée (voir `exhausted_daily_quotas`). Les arrêter tuait toute la session dès que le
        plafond le moins essentiel était atteint, alors que le budget global laissait encore de
        quoi liker et regarder des stories.

        Best-effort : une erreur de lecture ne doit pas tuer la session (le front reste le garde
        principal). Le fournisseur lit les totaux du jour du compte à chaque appel — should_continue
        n'est consulté qu'une fois par profil, donc la fréquence de lecture reste négligeable.
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
        """Les totaux du jour du compte, ou None quand il n'y a rien à faire respecter."""
        provider = self._daily_usage_provider
        if provider is None or not self._warmup_policy:
            return None
        try:
            return provider() or {}
        except Exception as exc:  # noqa: BLE001 — le garde-fou ne doit jamais faire échouer un run
            log.warning(f"Daily-budget provider failed (continuing without cap): {exc}")
            return None

    def exhausted_daily_quotas(self) -> set:
        """Les sous-quotas épuisés aujourd'hui : {'follow'} / {'comment'} / les deux.

        L'appelant (le moteur d'interaction) retire l'intention correspondante du plan de chaque
        profil, de sorte que la session continue de liker et de regarder les stories alors que les
        commentaires du jour sont consommés. Vide en standalone (aucun plafond injecté) et vide en
        cas d'erreur de lecture — fail-open, comme le reste du garde-fou.
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

        # Plancher de cadence du garde-fou : jamais plus vite que ce minimum, quel que soit le
        # profil de rythme choisi. C'est le levier qui casse la cadence mécanique (hier ~27s soutenu
        # sur un compte neuf). 0/absent (standalone) -> pas de plancher, comportement inchangé.
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
        """Marque le début de la phase de scraping."""
        self.scraping_start_time = datetime.now()
        log.debug(f"🔍 Scraping phase started at {self.scraping_start_time}")
    
    def end_scraping_phase(self):
        """Marque la fin de la phase de scraping."""
        self.scraping_end_time = datetime.now()
        if self.scraping_start_time:
            scraping_duration = self.scraping_end_time - self.scraping_start_time
            log.debug(f"✅ Scraping phase ended - Duration: {scraping_duration}")
        else:
            log.warning("Scraping end called but no start time recorded")
    
    def start_interaction_phase(self):
        """Marque le début de la phase d'interaction (une seule fois par session)."""
        if self.interaction_start_time is None:
            self.interaction_start_time = datetime.now()
            log.debug(f"🎯 Interaction phase started at {self.interaction_start_time}")
        else:
            log.debug(f"Interaction phase already started at {self.interaction_start_time} (not resetting)")
    
    def get_scraping_duration(self) -> timedelta:
        """Retourne la durée de la phase de scraping."""
        if self.scraping_start_time and self.scraping_end_time:
            return self.scraping_end_time - self.scraping_start_time
        return timedelta(0)
    
    def get_interaction_duration(self) -> timedelta:
        """Retourne la durée de la phase d'interaction."""
        if self.interaction_start_time:
            return datetime.now() - self.interaction_start_time
        return timedelta(0)
