import random
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger


class SessionManager:
    """Manages automation sessions with limits and action probabilities."""

    def __init__(self, config: Dict):
        """Initialize session manager with configuration.

        Args:
            config: Configuration dictionary loaded from JSON file
        """
        self.config = config
        self.session_start_time = datetime.now()
        self.counters = {
            'total_interactions': 0,
            'successful_interactions': 0,
            'follows': 0,
            'likes': 0,
            'comments': 0,
            'stories_watched': 0
        }
        self.source_counters = {}
        
        session_settings = self.config.get('session_settings', {})
        duration_minutes = session_settings.get('session_duration_minutes', 60)
        print(f"[DEBUG SessionManager] Configuration received:")
        print(f"[DEBUG SessionManager] - session_duration_minutes: {duration_minutes}")
        print(f"[DEBUG SessionManager] - session_settings: {session_settings}")

    def should_continue(self) -> tuple[bool, str]:
        """Check if session should continue based on defined limits.

        Returns:
            tuple[bool, str]: (should_continue, stop_reason)
        """
        session_duration = datetime.now() - self.session_start_time
        configured_duration = self.config.get('session_settings', {}).get('session_duration_minutes', 60)
        max_duration = timedelta(minutes=configured_duration)
        
        print(f"[DEBUG SessionManager] Duration check:")
        print(f"[DEBUG SessionManager] - Current duration: {session_duration}")
        print(f"[DEBUG SessionManager] - Max configured: {configured_duration} minutes ({max_duration})")
        print(f"[DEBUG SessionManager] - Should stop: {session_duration > max_duration}")
        
        if session_duration > max_duration:
            reason = f"Maximum duration reached ({configured_duration} minutes)"
            print(f"🛑 Session ended: {reason}")
            return False, reason

        session_settings = self.config.get('session_settings', {})
        workflow_type = session_settings.get('workflow_type', 'unknown')
        
        print(f"[DEBUG SessionManager] Limits check (workflow: {workflow_type}):")
        print(f"[DEBUG SessionManager] - Interactions: {self.counters['total_interactions']}/{session_settings.get('total_interactions_limit', 'infinite')}")
        print(f"[DEBUG SessionManager] - Likes: {self.counters['likes']}/{session_settings.get('total_likes_limit', 'infinite')}")
        print(f"[DEBUG SessionManager] - Follows: {self.counters['follows']}/{session_settings.get('total_follows_limit', 'infinite')}")
        
        interactions_limit = session_settings.get('total_interactions_limit', float('inf'))
        if self.counters['total_interactions'] >= interactions_limit:
            reason = f"Interactions limit reached ({self.counters['total_interactions']}/{interactions_limit})"
            print(f"🛑 Session ended: {reason}")
            return False, reason
        
        if workflow_type in ['target', 'followers', 'target_followers']:
            print(f"[DEBUG SessionManager] Workflow {workflow_type}: checking only interactions + time")
            return True, ""
        
        follows_limit = session_settings.get('total_follows_limit', float('inf'))
        if self.counters['follows'] >= follows_limit:
            reason = f"Follows limit reached ({self.counters['follows']}/{follows_limit})"
            print(f"🛑 Session ended: {reason}")
            return False, reason
            
        likes_limit = session_settings.get('total_likes_limit', float('inf'))
        if self.counters['likes'] >= likes_limit:
            reason = f"Likes limit reached ({self.counters['likes']}/{likes_limit})"
            print(f"🛑 Session ended: {reason}")
            return False, reason

        return True, ""

    def should_perform_action(self, action_type: str, source: Optional[str] = None) -> bool:
        """Determine if action should be performed based on probabilities and limits.

        Args:
            action_type: Action type ('like_posts', 'follow_user', 'watch_stories', 'comment_posts')
            source: Action source (optional, for per-source limits)

        Returns:
            bool: True if action should be performed, False otherwise
        """
        if source:
            if source not in self.source_counters:
                self.source_counters[source] = {
                    'interactions': 0,
                    'follows': 0,
                    'likes': 0,
                    'comments': 0
                }
            
            source_limits = self.config.get('limits_per_source', {})
            source_counter = self.source_counters[source]
            
            if source_counter['interactions'] >= source_limits.get('interactions', float('inf')):
                return False
                
            if action_type == 'follow_user' and source_counter['follows'] >= source_limits.get('follows', float('inf')):
                return False
                
            if action_type in ['like_posts', 'watch_stories'] and source_counter['likes'] >= source_limits.get('likes', float('inf')):
                return False
                
            if action_type == 'comment_posts' and source_counter['comments'] >= source_limits.get('comments', float('inf')):
                return False

        probability = self.config.get('action_probabilities', {}).get(action_type, 0)
        if random.randint(1, 100) > probability:
            return False

        return True

    def record_action(self, action_type: str, success: bool = True, source: Optional[str] = None):
        """Record performed action.

        Args:
            action_type: Action type
            success: Whether action succeeded
            source: Action source (optional)
        """
        self.counters['total_interactions'] += 1
        if success:
            self.counters['successful_interactions'] += 1

        if action_type == 'follow_user' and success:
            self.counters['follows'] += 1
        elif action_type in ['like_posts', 'watch_stories'] and success:
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
                elif action_type in ['like_posts', 'watch_stories']:
                    self.source_counters[source]['likes'] += 1
                elif action_type == 'comment_posts':
                    self.source_counters[source]['comments'] += 1

        if success:
            try:
                from taktik.core.database import get_db_service
                db_service = get_db_service()
                
                api_action_mapping = {
                    'follow_user': 'FOLLOW',
                    'like_posts': 'LIKE',
                    'comment_posts': 'COMMENT',
                    'watch_stories': 'STORY_WATCH'
                }
                
                api_action_type = api_action_mapping.get(action_type)
                if api_action_type and hasattr(db_service, 'api_client'):
                    success_api = db_service.api_client.record_action_usage(api_action_type)
                    if success_api:
                        logger.info(f"✅ Action {api_action_type} recorded in API for quotas (license_usage updated)")
                    else:
                        logger.error(f"🚨 CRITICAL FAILURE: Cannot record action {api_action_type} in API")
                        logger.error(f"🚨 SECURITY: Reverting local counters to prevent quota leaks")
                        self.counters['total_interactions'] -= 1
                        if success:
                            self.counters['successful_interactions'] -= 1
                        
                        if action_type == 'follow_user':
                            self.counters['follows'] -= 1
                        elif action_type in ['like_posts', 'watch_stories']:
                            self.counters['likes'] -= 1
                        elif action_type == 'comment_posts':
                            self.counters['comments'] -= 1
                        elif action_type == 'watch_stories':
                            self.counters['stories_watched'] -= 1
                        
                        if source and source in self.source_counters:
                            self.source_counters[source]['interactions'] -= 1
                            if action_type == 'follow_user':
                                self.source_counters[source]['follows'] -= 1
                            elif action_type in ['like_posts', 'watch_stories']:
                                self.source_counters[source]['likes'] -= 1
                            elif action_type == 'comment_posts':
                                self.source_counters[source]['comments'] -= 1
                        
                        raise Exception(f"API recording failed for action {api_action_type} - quotas not updated")
                        
            except Exception as e:
                logger.error(f"❌ CRITICAL ERROR recording action in API: {e}")
                raise Exception(f"Action {action_type} canceled - cannot update API quotas: {e}")

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
            'duration': str(datetime.now() - self.session_start_time),
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
        print(f"[DEBUG SessionManager] Configuration updated:")
        print(f"[DEBUG SessionManager] - session_duration_minutes: {duration_minutes}")
        print(f"[DEBUG SessionManager] - session_settings: {session_settings}")
