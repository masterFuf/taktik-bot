"""
TAKTIK Local Database Client
Public interface for all database operations.
All data is stored in local SQLite — no remote API calls.
"""

from typing import Optional, Dict, Any, Tuple, List
from loguru import logger

from .service import get_local_database, LocalDatabaseService

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..models import InstagramProfile


class LocalDatabaseClient:
    """
    Database client for the TAKTIK bot.
    All data is stored locally in SQLite (%APPDATA%/taktik-desktop/taktik-data.db).
    Shared with the Electron app via WAL mode.
    
    This class provides backward-compatible methods that the rest of the codebase
    calls via get_db_service(). It delegates to LocalDatabaseService internally.
    """
    
    def __init__(self, api_key: str = None, **kwargs):
        """Initialize with local SQLite database. Extra kwargs kept for backward compat."""
        self.local_db: LocalDatabaseService = get_local_database()
        logger.info("✅ LocalDatabaseClient initialized (local SQLite)")
    
    # ============================================
    # LEGACY NO-OPS (kept for backward compat)
    # ============================================
    
    def check_action_limits(self) -> Dict[str, Any]:
        """No-op. Action limits are handled by license-service in Electron."""
        return {'can_perform_action': True, 'remaining_actions': 999999, 'max_actions_per_day': 999999}
    
    def record_api_action(self, action_type: str = 'UNKNOWN') -> bool:
        """No-op. Action recording is done locally."""
        return True
    
    def record_action_usage(self, action_type: str) -> bool:
        """No-op. Action recording is done locally."""
        return True
    
    # ============================================
    # ACCOUNTS
    # ============================================
    
    def create_account(self, username: str, is_bot: bool = True) -> Tuple[int, bool]:
        """Create or get an Instagram account. Returns (account_id, created)."""
        return self.local_db.get_or_create_account(username, is_bot)
    
    def get_or_create_account(self, username: str, is_bot: bool = True) -> Tuple[int, bool]:
        """Get or create an account. Returns (account_id, created)."""
        return self.local_db.get_or_create_account(username, is_bot)
    
    def get_account_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get account by username."""
        return self.local_db.get_account_by_username(username)
    
    def get_account_stats(self, account_id: int) -> Dict[str, Any]:
        """Get account statistics."""
        return self.local_db.get_account_stats(account_id)
    
    # ============================================
    # PROFILES
    # ============================================
    
    def save_profile(self, profile: 'InstagramProfile', account_id: int = None) -> bool:
        """Save a profile to local database."""
        try:
            profile_data = {
                'username': profile.username,
                'full_name': profile.full_name,
                'biography': getattr(profile, 'biography', ''),
                'followers_count': profile.followers_count,
                'following_count': profile.following_count,
                'posts_count': profile.posts_count,
                'is_private': profile.is_private,
                'notes': profile.notes
            }
            result = self.local_db.save_profile(profile_data)
            return result is not None
        except Exception as e:
            logger.error(f"Error saving profile {profile.username}: {e}")
            return False
    
    # Alias for callers using the old APIBasedDatabaseService method name
    save_profile_via_api = save_profile
    
    def get_profile(self, username: str) -> Optional['InstagramProfile']:
        """Get a profile from local database."""
        try:
            profile_data = self.local_db.get_profile_by_username(username)
            if profile_data:
                from ..models import InstagramProfile
                return InstagramProfile(
                    id=profile_data.get('profile_id'),
                    username=profile_data.get('username'),
                    full_name=profile_data.get('full_name', ''),
                    followers_count=profile_data.get('followers_count', 0),
                    following_count=profile_data.get('following_count', 0),
                    posts_count=profile_data.get('posts_count', 0),
                    is_private=profile_data.get('is_private', False),
                    biography=profile_data.get('biography', ''),
                    notes=profile_data.get('notes')
                )
            return None
        except Exception as e:
            logger.error(f"Error getting profile {username}: {e}")
            return None
    
    def profile_exists(self, username: str) -> bool:
        """Check if a profile exists in the database."""
        return self.get_profile(username) is not None
    
    def create_profile(self, profile_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a profile in local database."""
        try:
            profile_id, created = self.local_db.get_or_create_profile(profile_data)
            return {'profile_id': profile_id, 'created': created}
        except Exception as e:
            logger.error(f"Error creating profile: {e}")
            return None
    
    def save_profile_and_get_id(self, profile: 'InstagramProfile') -> Optional[int]:
        """Save profile and return its ID."""
        try:
            profile_data = {
                'username': profile.username,
                'full_name': profile.full_name,
                'biography': getattr(profile, 'biography', ''),
                'followers_count': profile.followers_count,
                'following_count': profile.following_count,
                'posts_count': profile.posts_count,
                'is_private': profile.is_private,
                'notes': profile.notes
            }
            result = self.local_db.save_profile(profile_data)
            if result:
                profile.id = result
            return result or 1
        except Exception as e:
            logger.error(f"Error saving profile {profile.username}: {e}")
            return 1
    
    # ============================================
    # INTERACTIONS
    # ============================================
    
    def record_interaction(self, account_id: int, username: str = None,
                          target_username: str = None,
                          interaction_type: str = 'LIKE', success: bool = True,
                          content: str = None, session_id: int = None) -> bool:
        """Record an interaction to local database."""
        target = username or target_username
        if not target:
            logger.error("record_interaction requires username or target_username")
            return False
        return self.local_db.record_interaction(
            account_id=account_id,
            target_username=target,
            interaction_type=interaction_type,
            success=success,
            content=content,
            session_id=session_id
        )
    
    def log_interaction(self, account_id: int, profile_id: int, interaction_type: str,
                        success: bool = True, content: Optional[str] = None) -> bool:
        """Legacy method — no-op, kept for backward compat."""
        return True
    
    def get_interactions(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get interactions for an account."""
        return self.local_db.get_interactions(account_id, limit)
    
    # ============================================
    # PROFILE PROCESSING STATUS
    # ============================================
    
    def is_profile_processed(self, account_id: int, username: str, hours_limit: int = 24) -> bool:
        """Check if a profile was recently processed."""
        try:
            result = self.local_db.check_profile_processed(account_id, username, hours_limit)
            if result is not None:
                return result.get('processed', False)
            return False
        except Exception as e:
            logger.error(f"Error checking profile {username}: {e}")
            return False
    
    def mark_profile_as_processed(self, account_id: int, username: str, 
                                   notes: str = None, session_id: int = None,
                                   interaction_type: str = "PROFILE_VISIT") -> bool:
        """Mark a profile as processed by recording a PROFILE_VISIT interaction."""
        content = notes or f"Profile @{username} processed"
        return self.record_interaction(
            account_id=account_id, username=username,
            interaction_type=interaction_type, success=True,
            content=content, session_id=session_id
        )
    
    # Alias
    mark_as_processed = mark_profile_as_processed
    
    # ============================================
    # FILTERED PROFILES
    # ============================================
    
    def record_filtered_profile(self, account_id: int, username: str, reason: str,
                                 source_type: str = 'GENERAL', source_name: str = 'unknown',
                                 session_id: int = None) -> bool:
        """Record a filtered profile to local database."""
        return self.local_db.record_filtered_profile(
            account_id=account_id,
            username=username,
            reason=reason,
            source_type=source_type,
            source_name=source_name,
            session_id=session_id
        )
    
    # Alias for callers using APIBasedDatabaseService method name
    mark_as_filtered = record_filtered_profile
    
    def is_profile_filtered(self, username: str, account_id: int) -> bool:
        """Check if a profile is filtered."""
        return self.local_db.is_profile_filtered(username, account_id)
    
    def check_filtered_profiles_batch(self, usernames: list, account_id: int) -> list:
        """Check multiple profiles for filtering."""
        return self.local_db.check_filtered_profiles_batch(usernames, account_id)
    
    # ============================================
    # SESSIONS
    # ============================================
    
    def create_session(self, account_id: int, session_name: str, target_type: str,
                       target: str, config_used: Dict[str, Any] = None) -> Optional[int]:
        """Create a session in local database."""
        return self.local_db.create_session(
            account_id=account_id,
            session_name=session_name,
            target_type=target_type,
            target=target,
            config_used=config_used
        )
    
    def update_session(self, session_id: int, update_data: Dict[str, Any] = None, **kwargs) -> bool:
        """Update a session in local database."""
        data = update_data or kwargs
        return self.local_db.update_session(session_id, **data)
    
    def get_session_stats(self, session_id: int) -> Optional[Dict[str, int]]:
        """Get session statistics from local database."""
        return self.local_db.get_session_stats(session_id)


def get_database_client(**kwargs) -> LocalDatabaseClient:
    """Factory function. Returns LocalDatabaseClient (local SQLite)."""
    return LocalDatabaseClient(**kwargs)
