"""Profile persistence to local SQLite database."""

from typing import Dict, Any
from loguru import logger
from taktik.core.database import get_db_service


def save_profile_to_database(profile_info: Dict[str, Any], log: logger = None):
    """Save extracted profile info to the local database.
    
    Standalone function (no class needed) — pure I/O, no device interaction.
    """
    _logger = log or logger
    
    try:
        if not profile_info or not profile_info.get('username'):
            return
        
        # Prepare data for API
        profile_data = {
            'username': profile_info['username'],
            'full_name': profile_info.get('full_name', ''),
            'biography': profile_info.get('biography', ''),
            'followers_count': profile_info.get('followers_count', 0),
            'following_count': profile_info.get('following_count', 0),
            'posts_count': profile_info.get('posts_count', 0),
            'is_private': profile_info.get('is_private', False),
            'notes': ''  # Don't auto-populate notes
        }
        
        # Use API to save/update profile
        try:
            db_service = get_db_service()
            from taktik.core.database.models import InstagramProfile
            profile = InstagramProfile(
                username=profile_data['username'],
                full_name=profile_data['full_name'],
                biography=profile_data['biography'],
                followers_count=profile_data['followers_count'],
                following_count=profile_data['following_count'],
                posts_count=profile_data['posts_count'],
                is_private=profile_data['is_private'],
                notes=profile_data['notes']
            )
            
            success = db_service.save_profile(profile)
            if success:
                _logger.debug(f"Profile @{profile_info['username']} saved to DB with actual data")
                _logger.debug(f"  DB: {profile_data['posts_count']} posts, "
                                f"{profile_data['followers_count']} followers, "
                                f"{profile_data['following_count']} following")
            else:
                _logger.warning(f"Failed to save profile @{profile_info['username']}")
        except Exception as db_error:
            _logger.error(f"Database access error: {db_error}")
            
    except Exception as e:
        _logger.error(f"Error saving profile: {e}")
