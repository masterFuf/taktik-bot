"""
TikTok Profile Actions
Actions for interacting with TikTok profiles, including fetching own profile info.
"""

import re
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction


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
    """Actions for TikTok profile interactions."""
    
    # UI Selectors for profile page
    PROFILE_TAB_SELECTOR = '//android.widget.FrameLayout[@content-desc="Profile"]'
    PROFILE_TAB_TEXT_SELECTOR = '//android.widget.TextView[@text="Profile"]'
    
    # Profile info selectors
    USERNAME_SELECTOR = '//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/qh5"]'
    DISPLAY_NAME_SELECTOR = '//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/qf8"]'
    
    # Stats selectors - these have the same resource-id but different labels
    STATS_VALUE_SELECTOR = '//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/qfw"]'
    STATS_LABEL_SELECTOR = '//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/qfv"]'
    
    # Edit button (indicates we're on our own profile)
    EDIT_BUTTON_SELECTOR = '//android.widget.Button[@text="Edit"]'
    
    def navigate_to_own_profile(self) -> bool:
        """Navigate to the user's own profile page.
        
        Returns:
            True if successfully navigated to profile, False otherwise.
        """
        logger.info("📱 Navigating to own profile...")
        
        # Try clicking the Profile tab in bottom navigation using _find_and_click from BaseAction
        selectors = [
            self.PROFILE_TAB_SELECTOR,
            self.PROFILE_TAB_TEXT_SELECTOR,
            '//android.widget.TextView[@text="Profile"]',
            '//android.widget.FrameLayout[contains(@content-desc, "Profile")]',
        ]
        
        if self._find_and_click(selectors, timeout=5.0):
            self._random_sleep(1.5, 2.5)
            
            # Verify we're on profile page by checking for Edit button or username
            try:
                edit_elem = self.device.xpath(self.EDIT_BUTTON_SELECTOR)
                if edit_elem.exists:
                    logger.info("✅ Successfully navigated to own profile (Edit button found)")
                    return True
                
                username_elem = self.device.xpath(self.USERNAME_SELECTOR)
                if username_elem.exists:
                    logger.info("✅ Successfully navigated to profile page (username found)")
                    return True
            except Exception as e:
                logger.debug(f"Verification failed: {e}")
        
        logger.warning("❌ Could not navigate to profile page")
        return False
    
    def _parse_count(self, text: str) -> int:
        """Parse a count string like '1,750', '1.2K', '1.5M', '166 K', etc. to an integer.
        
        Handles formats:
        - Plain numbers: '1234', '1,234'
        - K suffix: '1.5K', '1,5K', '166 K', '166K'
        - M suffix: '1.2M', '2 M'
        - B suffix: '1B', '1.5 B'
        """
        if not text:
            return 0
        
        try:
            # Normalize: remove non-breaking spaces and extra whitespace
            text_str = str(text).strip().replace('\xa0', ' ').strip()
            
            multipliers = {
                'K': 1000, 'k': 1000,
                'M': 1000000, 'm': 1000000,
                'B': 1000000000, 'b': 1000000000
            }
            
            # Check for suffix with or without space (e.g., "166K", "166 K", "1.2 M")
            for suffix, multiplier in multipliers.items():
                # Handle "166 K" format (space before suffix)
                if text_str.endswith(f' {suffix}') or text_str.endswith(f' {suffix.lower()}'):
                    try:
                        # Use comma as decimal separator too (European format)
                        number_part = text_str[:-2].strip().replace(',', '.')
                        return int(float(number_part) * multiplier)
                    except (ValueError, AttributeError):
                        continue
                # Handle "166K" format (no space)
                elif text_str.upper().endswith(suffix.upper()):
                    try:
                        number_part = text_str[:-1].strip().replace(',', '.')
                        return int(float(number_part) * multiplier)
                    except (ValueError, AttributeError):
                        continue
            
            # No suffix found - extract digits only
            # Remove spaces and normalize separators
            number_str = text_str.replace(' ', '').replace(',', '')
            
            # Try direct parse
            try:
                return int(number_str)
            except ValueError:
                # Try float then int
                try:
                    return int(float(number_str))
                except ValueError:
                    # Last resort: extract only digits
                    digits_only = ''.join(c for c in text_str if c.isdigit())
                    return int(digits_only) if digits_only else 0
                    
        except (ValueError, AttributeError):
            return 0
    
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
        
        # Get username using xpath
        try:
            username_elem = self.device.xpath(self.USERNAME_SELECTOR)
            if username_elem.exists:
                username_text = username_elem.get_text() or ''
                # Remove @ prefix if present
                username = username_text.lstrip('@').strip()
                logger.debug(f"Found username: @{username}")
        except Exception as e:
            logger.debug(f"Failed to get username: {e}")
        
        if not username:
            logger.warning("❌ Could not find username on profile page")
            return None
        
        # Get display name
        try:
            display_elem = self.device.xpath(self.DISPLAY_NAME_SELECTOR)
            if display_elem.exists:
                display_name = display_elem.get_text()
                logger.debug(f"Found display name: {display_name}")
        except Exception as e:
            logger.debug(f"Failed to get display name: {e}")
        
        # Get stats (Following, Followers, Likes) - use specific selectors based on UI dump
        # The stats are in a row with value above label
        try:
            # Get all stat values (they share the same resource-id)
            stat_values = self.device.xpath(self.STATS_VALUE_SELECTOR).all()
            stat_labels = self.device.xpath(self.STATS_LABEL_SELECTOR).all()
            
            logger.debug(f"Found {len(stat_values)} stat values and {len(stat_labels)} stat labels")
            
            for i, label_elem in enumerate(stat_labels):
                try:
                    # XMLElement uses .text property, not .get_text() method
                    label_text = label_elem.text or ''
                    label_lower = label_text.lower()
                    
                    if i < len(stat_values):
                        value_text = stat_values[i].text or '0'
                        count = self._parse_count(value_text)
                        
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
        
        home_selectors = [
            '//android.widget.FrameLayout[@content-desc="Home"]',
            '//android.widget.TextView[@text="Home"]',
            '//android.widget.FrameLayout[contains(@content-desc, "Home")]',
        ]
        
        if self._find_and_click(home_selectors, timeout=5.0):
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
