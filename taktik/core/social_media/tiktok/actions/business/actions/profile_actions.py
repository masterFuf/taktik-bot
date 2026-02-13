"""
TikTok Profile Actions
Actions for interacting with TikTok profiles, including fetching own profile info.
"""

from dataclasses import dataclass
from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction
from ...core.utils import parse_count
from ....ui.selectors import PROFILE_SELECTORS, NAVIGATION_SELECTORS


@dataclass
class TikTokProfileInfo:
    """Information about a TikTok profile."""
    username: str  # @username without the @
    display_name: Optional[str] = None
    following_count: int = 0
    followers_count: int = 0
    likes_count: int = 0
    bio: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'username': self.username,
            'display_name': self.display_name,
            'following_count': self.following_count,
            'followers_count': self.followers_count,
            'likes_count': self.likes_count,
            'bio': self.bio
        }


class ProfileActions(BaseAction):
    """Actions for TikTok profile interactions.
    
    Uses centralized selectors from ui/selectors/ (PROFILE_SELECTORS, NAVIGATION_SELECTORS).
    """
    
    def navigate_to_own_profile(self) -> bool:
        """Navigate to the user's own profile page.
        
        Returns:
            True if successfully navigated to profile, False otherwise.
        """
        logger.info("📱 Navigating to own profile...")
        
        if self._find_and_click(NAVIGATION_SELECTORS.profile_tab, timeout=5.0):
            self._random_sleep(1.5, 2.5)
            
            # Verify we're on profile page by checking for Edit button or username
            try:
                if self._element_exists(PROFILE_SELECTORS.edit_profile_button, timeout=2):
                    logger.info("✅ Successfully navigated to own profile (Edit button found)")
                    return True
                
                if self._element_exists(PROFILE_SELECTORS.username, timeout=2):
                    logger.info("✅ Successfully navigated to profile page (username found)")
                    return True
            except Exception as e:
                logger.debug(f"Verification failed: {e}")
        
        logger.warning("❌ Could not navigate to profile page")
        return False
    
    def get_own_profile_info(self) -> Optional[TikTokProfileInfo]:
        """Get information about the user's own profile.
        
        Must be on the profile page first (call navigate_to_own_profile).
        
        Returns:
            TikTokProfileInfo if successful, None otherwise.
        """
        logger.info("📊 Fetching own profile info...")
        
        username = None
        display_name = None
        following_count = 0
        followers_count = 0
        likes_count = 0
        bio = None
        
        # Get username using centralized selectors
        try:
            text = self._get_element_text(PROFILE_SELECTORS.username, timeout=3)
            if text:
                username = text.lstrip('@').strip()
                logger.debug(f"Found username: @{username}")
        except Exception as e:
            logger.debug(f"Failed to get username: {e}")
        
        if not username:
            logger.warning("❌ Could not find username on profile page")
            return None
        
        # Get display name
        try:
            display_name = self._get_element_text(PROFILE_SELECTORS.display_name, timeout=3)
            if display_name:
                logger.debug(f"Found display name: {display_name}")
        except Exception as e:
            logger.debug(f"Failed to get display name: {e}")
        
        # Get stats (Following, Followers, Likes) - use specific selectors based on UI dump
        # The stats are in a row with value above label
        try:
            # Get all stat values (they share the same resource-id)
            stat_values = self.device.xpath(PROFILE_SELECTORS.stat_value[0]).all()
            stat_labels = self.device.xpath(PROFILE_SELECTORS.stat_label[0]).all()
            
            logger.debug(f"Found {len(stat_values)} stat values and {len(stat_labels)} stat labels")
            
            for i, label_elem in enumerate(stat_labels):
                try:
                    # XMLElement uses .text property, not .get_text() method
                    label_text = label_elem.text or ''
                    label_lower = label_text.lower()
                    
                    if i < len(stat_values):
                        value_text = stat_values[i].text or '0'
                        count = parse_count(value_text)
                        
                        if 'following' in label_lower:
                            following_count = count
                            logger.debug(f"Found following: {count}")
                        elif 'follower' in label_lower:
                            followers_count = count
                            logger.debug(f"Found followers: {count}")
                        elif 'like' in label_lower:
                            likes_count = count
                            logger.debug(f"Found likes: {count}")
                except Exception as e:
                    logger.debug(f"Failed to parse stat {i}: {e}")
        except Exception as e:
            logger.debug(f"Failed to get stats: {e}")
        
        profile_info = TikTokProfileInfo(
            username=username,
            display_name=display_name,
            following_count=following_count,
            followers_count=followers_count,
            likes_count=likes_count,
            bio=bio
        )
        
        logger.info(f"✅ Profile info: @{username} ({display_name}) - {followers_count} followers")
        return profile_info
    
    def navigate_to_home(self) -> bool:
        """Navigate back to the Home/For You page.
        
        Returns:
            True if successfully navigated to home, False otherwise.
        """
        logger.info("🏠 Navigating to Home...")
        
        if self._find_and_click(NAVIGATION_SELECTORS.home_tab, timeout=5.0):
            self._random_sleep(1.5, 2.5)
            logger.info("✅ Successfully navigated to Home")
            return True
        
        logger.warning("❌ Could not navigate to Home page")
        return False
    
    def fetch_own_profile(self) -> Optional[TikTokProfileInfo]:
        """Navigate to own profile, fetch info, then return to Home.
        
        This is a convenience method that combines navigation and fetching.
        
        Returns:
            TikTokProfileInfo if successful, None otherwise.
        """
        if not self.navigate_to_own_profile():
            return None
        
        self._random_sleep(1.0, 1.5)
        profile_info = self.get_own_profile_info()
        
        # Navigate back to Home so the workflow can continue
        if profile_info:
            self._random_sleep(0.5, 1.0)
            self.navigate_to_home()
        
        return profile_info
