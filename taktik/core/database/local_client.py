"""
TAKTIK Local Database Client
Drop-in replacement for TaktikAPIClient that uses local SQLite instead of remote API.
Keeps the same interface for seamless migration.
"""

import os
import requests
from typing import Optional, Dict, Any, Tuple, List
from loguru import logger
from datetime import datetime

from .local_database import get_local_database, LocalDatabaseService

# Import for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .models import InstagramProfile


class LocalDatabaseClient:
    """
    Local database client that mimics TaktikAPIClient interface.
    Uses local SQLite for data storage, only calls remote API for:
    - License verification
    - Action limits check
    - Stats sync (sessions + daily aggregates)
    """
    
    def __init__(self, api_url: str = None, api_key: str = None, config_mode: bool = False):
        """
        Initialize the local database client.
        
        Args:
            api_url: Remote API URL (for license/limits only)
            api_key: API key for remote calls
            config_mode: If True, skip API key requirement
        """
        # Remote API config (for license/limits only)
        if api_url:
            self.api_url = api_url.rstrip('/')
        else:
            from ..config.api_endpoints import get_api_url
            self.api_url = get_api_url()
        
        self.config_mode = config_mode
        self.api_key = api_key if not config_mode else None
        
        # Local database
        self.local_db: LocalDatabaseService = get_local_database()
        
        # HTTP session for remote calls
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            })
        
        logger.info("✅ LocalDatabaseClient initialized (local SQLite + remote API for license)")
    
    def _remote_request(self, method: str, endpoint: str, data: dict = None, 
                        timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Make a request to the remote API (for license/limits only)."""
        if not self.api_key and not self.config_mode:
            logger.warning("No API key for remote request")
            return None
        
        url = f"{self.api_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        try:
            verify_ssl = os.getenv('TAKTIK_DISABLE_SSL_VERIFY', '0').lower() not in ('1', 'true', 'yes')
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout, verify=verify_ssl)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=timeout, verify=verify_ssl)
            else:
                return None
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on remote request {method} {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"Remote request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error during remote request: {e}")
            return None
    
    # ============================================
    # HEALTH & LICENSE (Remote API)
    # ============================================
    
    def health_check(self) -> bool:
        """Check if remote API is healthy."""
        try:
            result = self._remote_request('GET', '/health')
            return result.get('status') == 'healthy' if result else False
        except:
            return False
    
    def check_action_limits(self) -> Dict[str, Any]:
        """Action limits are no longer enforced. Always allow."""
        return {'can_perform_action': True, 'remaining_actions': 999999, 'max_actions_per_day': 999999}
    
    def record_api_action(self, action_type: str = 'UNKNOWN') -> bool:
        """Action recording to remote API is no longer used. No-op."""
        return True
    
    def record_action_usage(self, action_type: str) -> bool:
        """Action recording to remote API is no longer used. No-op."""
        return True
    
    # ============================================
    # ACCOUNTS (Local Database)
    # ============================================
    
    def create_account(self, username: str, is_bot: bool = True) -> Tuple[int, bool]:
        """Create or get an Instagram account."""
        return self.local_db.get_or_create_account(username, is_bot)
    
    def get_or_create_account(self, username: str, is_bot: bool = True) -> Optional[Dict[str, Any]]:
        """Get or create an account, return dict format."""
        account_id, created = self.local_db.get_or_create_account(username, is_bot)
        return {'account_id': account_id, 'created': created}
    
    def get_account_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get account by username."""
        return self.local_db.get_account_by_username(username)
    
    def get_account_stats(self, account_id: int) -> Dict[str, Any]:
        """Get account statistics."""
        return self.local_db.get_account_stats(account_id)
    
    # ============================================
    # PROFILES (Local Database)
    # ============================================
    
    def save_profile(self, profile: 'InstagramProfile') -> Optional[int]:
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
            return self.local_db.save_profile(profile_data)
        except Exception as e:
            logger.error(f"Error saving profile {profile.username}: {e}")
            return None
    
    def get_profile(self, username: str) -> Optional['InstagramProfile']:
        """Get a profile from local database."""
        try:
            profile_data = self.local_db.get_profile_by_username(username)
            if profile_data:
                from .models import InstagramProfile
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
    
    def create_profile(self, profile_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a profile in local database."""
        try:
            profile_id, created = self.local_db.get_or_create_profile(profile_data)
            return {'profile_id': profile_id, 'created': created}
        except Exception as e:
            logger.error(f"Error creating profile: {e}")
            return None
    
    def check_profile_processed(self, account_id: int, username: str, 
                                 hours_limit: int = 24) -> Optional[Dict[str, Any]]:
        """Check if a profile was recently processed."""
        return self.local_db.check_profile_processed(account_id, username, hours_limit)
    
    # ============================================
    # INTERACTIONS (Local Database)
    # ============================================
    
    def record_interaction(self, account_id: int, target_username: str, 
                          interaction_type: str, success: bool = True,
                          content: str = None, session_id: int = None) -> bool:
        """Record an interaction to local database."""
        return self.local_db.record_interaction(
            account_id=account_id,
            target_username=target_username,
            interaction_type=interaction_type,
            success=success,
            content=content,
            session_id=session_id
        )
    
    def log_interaction(self, account_id: int, profile_id: int, interaction_type: str,
                        success: bool = True, content: Optional[str] = None) -> bool:
        """Legacy method - redirects to record_interaction."""
        logger.warning("log_interaction() is deprecated - use record_interaction()")
        # We need the username, but we only have profile_id
        # This is a legacy method, just return True
        return True
    
    def check_recent_interaction(self, target_username: str, days: int = 7) -> bool:
        """Check if there was a recent interaction with a profile."""
        # We need account_id, but this legacy method doesn't have it
        # Return False to allow interaction
        return False
    
    def get_interactions(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get interactions for an account."""
        return self.local_db.get_interactions(account_id, limit)
    
    # ============================================
    # FILTERED PROFILES (Local Database)
    # ============================================
    
    def record_filtered_profile(self, account_id: int, username: str, reason: str,
                                 source_type: str, source_name: str,
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
    
    def is_profile_filtered(self, username: str, account_id: int) -> bool:
        """Check if a profile is filtered."""
        return self.local_db.is_profile_filtered(username, account_id)
    
    def check_filtered_profiles_batch(self, usernames: list, account_id: int) -> list:
        """Check multiple profiles for filtering."""
        return self.local_db.check_filtered_profiles_batch(usernames, account_id)
    
    # ============================================
    # SESSIONS (Local Database + Remote Sync)
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
    
    def update_session(self, session_id: int, update_data: Dict[str, Any]) -> bool:
        """Update a session in local database."""
        return self.local_db.update_session(session_id, **update_data)
    
    def get_session_stats(self, session_id: int) -> Optional[Dict[str, int]]:
        """Get session statistics from local database."""
        return self.local_db.get_session_stats(session_id)
    
    # ============================================
    # SYNC TO REMOTE API
    # ============================================
    
    def sync_to_remote(self) -> Dict[str, Any]:
        """
        Sync local data to remote API.
        Only syncs:
        - Completed sessions (aggregated stats only, no profile data)
        - Daily stats
        
        Returns:
            Dict with sync results
        """
        results = {
            'sessions_synced': 0,
            'daily_stats_synced': 0,
            'errors': []
        }
        
        if not self.api_key:
            results['errors'].append("No API key for sync")
            return results
        
        # Sync sessions
        try:
            unsynced_sessions = self.local_db.get_unsynced_sessions()
            synced_session_ids = []
            
            for session in unsynced_sessions:
                stats = self.local_db.get_session_stats(session['session_id'])
                
                # Send aggregated session data (no profile usernames)
                sync_data = {
                    'session_name': session['session_name'],
                    'target_type': session['target_type'],
                    'target': session['target'],
                    'start_time': session['start_time'],
                    'end_time': session['end_time'],
                    'duration_seconds': session['duration_seconds'],
                    'status': session['status'],
                    'stats': stats
                }
                
                result = self._remote_request('POST', '/desktop/sync/session', sync_data)
                if result and result.get('success'):
                    synced_session_ids.append(session['session_id'])
            
            if synced_session_ids:
                self.local_db.mark_sessions_synced(synced_session_ids)
                results['sessions_synced'] = len(synced_session_ids)
                
        except Exception as e:
            results['errors'].append(f"Session sync error: {e}")
        
        # Sync daily stats
        try:
            unsynced_stats = self.local_db.get_unsynced_daily_stats()
            synced_stat_ids = []
            
            for stat in unsynced_stats:
                sync_data = {
                    'date': stat['date'],
                    'total_likes': stat['total_likes'],
                    'total_follows': stat['total_follows'],
                    'total_unfollows': stat['total_unfollows'],
                    'total_comments': stat['total_comments'],
                    'total_story_views': stat['total_story_views'],
                    'total_story_likes': stat['total_story_likes'],
                    'total_sessions': stat['total_sessions'],
                    'completed_sessions': stat['completed_sessions'],
                    'failed_sessions': stat['failed_sessions'],
                    'total_duration_seconds': stat['total_duration_seconds']
                }
                
                result = self._remote_request('POST', '/desktop/sync/daily-stats', sync_data)
                if result and result.get('success'):
                    synced_stat_ids.append(stat['id'])
            
            if synced_stat_ids:
                self.local_db.mark_daily_stats_synced(synced_stat_ids)
                results['daily_stats_synced'] = len(synced_stat_ids)
                
        except Exception as e:
            results['errors'].append(f"Daily stats sync error: {e}")
        
        if results['sessions_synced'] > 0 or results['daily_stats_synced'] > 0:
            logger.info(f"✅ Synced to remote: {results['sessions_synced']} sessions, {results['daily_stats_synced']} daily stats")
        
        return results


# Factory function to get the database client
def get_database_client(api_url: str = None, api_key: str = None, 
                        config_mode: bool = False, use_local: bool = True):
    """
    Get the local database client (SQLite).
    
    Args:
        api_url: Remote API URL (kept for backward compat, unused)
        api_key: API key (kept for backward compat, unused)
        config_mode: Config mode flag
        use_local: Always True — local SQLite is the only mode now.
    """
    return LocalDatabaseClient(api_url=api_url, api_key=api_key, config_mode=config_mode)
