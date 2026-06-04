import random
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger


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

        return True, ""

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
        """Return random delay between actions.

        Returns:
            float: Delay in seconds
        """
        delay_config = self.config.get('session_settings', {}).get('delay_between_actions', {'min': 5, 'max': 15})
        return random.uniform(delay_config.get('min', 5), delay_config.get('max', 15))

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
        
        session_settings = self.config.get('session_settings', {})
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
