"""Unified profile processing — extract, filter, interact, record.

Eliminates the duplicated "extract → check private → filter → interact → record"
pipeline found in 5+ workflow files.

Each workflow handles navigation TO/FROM the profile itself.
This mixin only handles what happens WHILE on the profile screen.
"""

from typing import Optional, Dict, Any
from loguru import logger


class ProfileProcessingResult:
    """Standardized result from profile processing."""
    __slots__ = (
        'status', 'username', 'profile_data', 'interaction_result',
        'filter_reasons', 'error_message'
    )
    
    # Status constants
    SUCCESS = 'interacted'
    SKIPPED_PROBABILITY = 'skipped_probability'
    FILTERED_PRIVATE = 'filtered_private'
    FILTERED_CRITERIA = 'filtered_criteria'
    ERROR_NO_DATA = 'error_no_data'
    ERROR_EXCEPTION = 'error_exception'
    
    def __init__(self, status: str, username: str):
        self.status = status
        self.username = username
        self.profile_data = None
        self.interaction_result = None
        self.filter_reasons = []
        self.error_message = None
    
    @property
    def actually_interacted(self) -> bool:
        return self.status == self.SUCCESS
    
    @property
    def was_filtered(self) -> bool:
        return self.status in (self.FILTERED_PRIVATE, self.FILTERED_CRITERIA)
    
    @property
    def was_private(self) -> bool:
        return self.status == self.FILTERED_PRIVATE
    
    @property
    def was_error(self) -> bool:
        return self.status in (self.ERROR_NO_DATA, self.ERROR_EXCEPTION)
    
    @property
    def likes(self) -> int:
        return (self.interaction_result or {}).get('likes', 0)
    
    @property
    def follows(self) -> int:
        return (self.interaction_result or {}).get('follows', 0)
    
    @property
    def comments(self) -> int:
        return (self.interaction_result or {}).get('comments', 0)
    
    @property
    def stories(self) -> int:
        return (self.interaction_result or {}).get('stories', 0)
    
    @property
    def stories_liked(self) -> int:
        return (self.interaction_result or {}).get('stories_liked', 0)


class ProfileProcessingMixin:
    """Mixin: unified profile processing while on a profile screen.
    
    Handles: extract info → check private → apply filters → interact → record.
    Does NOT handle navigation to/from the profile — that's the caller's job.
    """

    def _process_profile_on_screen(
        self,
        username: str,
        config: Dict[str, Any],
        source_type: str = 'UNKNOWN',
        source_name: str = '',
        account_id: int = None,
        session_id: int = None,
        navigate_if_needed: bool = False,
    ) -> ProfileProcessingResult:
        """
        Process a profile we are currently viewing (or can navigate to).
        
        This is the SINGLE implementation of the extract→filter→interact pipeline.
        
        Args:
            username: Target username
            config: Workflow config with filter_criteria, like_percentage, etc.
            source_type: 'HASHTAG', 'POST_URL', 'FOLLOWER', 'FEED', 'NOTIFICATIONS'
            source_name: e.g. '#travel', 'https://...', '@target_user', 'feed'
            account_id: For DB recording
            session_id: For DB recording
            navigate_if_needed: If True, navigate to profile first
            
        Returns:
            ProfileProcessingResult with status, profile_data, interaction_result
        """
        result = ProfileProcessingResult('pending', username)
        
        try:
            # === 1. Navigate if needed ===
            if navigate_if_needed:
                if not self.nav_actions.navigate_to_profile(username):
                    result.status = ProfileProcessingResult.ERROR_NO_DATA
                    result.error_message = 'Navigation failed'
                    self.logger.warning(f"Cannot navigate to @{username}")
                    return result
            
            # === 2. Extract profile info ===
            profile_data = self.profile_business.get_complete_profile_info(
                username=username, navigate_if_needed=False
            )
            
            if not profile_data:
                result.status = ProfileProcessingResult.ERROR_NO_DATA
                result.error_message = 'Profile data extraction failed'
                self.logger.warning(f"Could not get profile data for @{username}")
                return result
            
            result.profile_data = profile_data
            
            # === 3. Check private ===
            if profile_data.get('is_private', False):
                result.status = ProfileProcessingResult.FILTERED_PRIVATE
                result.filter_reasons = ['Private profile']
                self.logger.info(f"🔒 Private profile @{username} - skipped")
                self.stats_manager.increment('private_profiles')
                self._record_filtered_in_db(
                    username, 'Private profile', source_type, source_name,
                    account_id, session_id
                )
                return result
            
            # === 4. Apply filters ===
            filter_criteria = config.get('filter_criteria', config.get('filters', {}))
            filter_result = self.filtering_business.apply_comprehensive_filter(
                profile_data, filter_criteria
            )
            
            if not filter_result.get('suitable', False):
                reasons = filter_result.get('reasons', [])
                result.status = ProfileProcessingResult.FILTERED_CRITERIA
                result.filter_reasons = reasons
                self.logger.info(f"🚫 @{username} filtered: {', '.join(reasons)}")
                self.stats_manager.increment('profiles_filtered')
                self._record_filtered_in_db(
                    username, ', '.join(reasons), source_type, source_name,
                    account_id, session_id
                )
                return result
            
            # === 5. Perform interactions ===
            interaction = self._perform_interactions_on_profile(
                username, config, profile_data=profile_data
            )
            result.interaction_result = interaction
            
            if interaction and interaction.get('actually_interacted', False):
                result.status = ProfileProcessingResult.SUCCESS
                self.logger.success(f"✅ Successful interaction with @{username}")
                
                # Record as processed in DB
                from ...business.common.database_helpers import DatabaseHelpers
                DatabaseHelpers.mark_profile_as_processed(
                    username, source_name, account_id, session_id
                )
            else:
                result.status = ProfileProcessingResult.SKIPPED_PROBABILITY
                self.logger.debug(f"@{username} visited but no interaction (probability)")
            
            return result
            
        except Exception as e:
            result.status = ProfileProcessingResult.ERROR_EXCEPTION
            result.error_message = str(e)
            self.logger.error(f"Error processing @{username}: {e}")
            return result

    def _record_filtered_in_db(
        self, username: str, reason: str, source_type: str,
        source_name: str, account_id: int, session_id: int
    ) -> None:
        """Record a filtered profile in the database. Silent on failure."""
        try:
            from ...business.common.database_helpers import DatabaseHelpers
            DatabaseHelpers.record_filtered_profile(
                username=username,
                reason=reason,
                source_type=source_type,
                source_name=source_name,
                account_id=account_id,
                session_id=session_id
            )
        except Exception as e:
            self.logger.debug(f"Error recording filtered profile @{username}: {e}")
