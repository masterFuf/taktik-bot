"""Deep link navigation via ADB (profile + post URLs)."""

import time
import subprocess
from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import DETECTION_SELECTORS, NAVIGATION_SELECTORS, PROFILE_SELECTORS


class DeepLinkNavigationMixin(BaseAction):
    """Mixin: navigate to profiles and posts via ADB deep links."""

    def _navigate_via_deep_link(self, username: str, max_attempts: int = 3) -> bool:
        device_serial = self._get_device_serial()
        self.logger.debug(f"🔧 Using device: {device_serial}")
        
        for attempt in range(2):
            try:
                self.logger.debug(f"Attempt {attempt + 1}/2 - Deep link to @{username}")
                
                deep_link_url = f"https://www.instagram.com/{username}/"
                
                # Use adbutils instead of subprocess to avoid PATH issues in packaged builds
                try:
                    from adbutils import adb
                    device = adb.device(serial=device_serial)
                    # Execute am start command via adbutils shell
                    result = device.shell(f'am start -W -a android.intent.action.VIEW -d "{deep_link_url}" com.instagram.android')
                    self.logger.debug(f"Deep link result: {result}")
                    
                    if 'Error' not in str(result) and 'Exception' not in str(result):
                        self.logger.debug("Deep link executed successfully")
                        self._human_like_delay('click')  # Minimal — am start -W already waits for activity
                        
                        if self._verify_profile_navigation(username):
                            return True
                    else:
                        self.logger.debug(f"Deep link failed: {result}")
                except ImportError:
                    # Fallback to subprocess if adbutils not available
                    cmd = [
                        'adb', '-s', device_serial, 'shell', 'am', 'start',
                        '-W', '-a', 'android.intent.action.VIEW',
                        '-d', deep_link_url,
                        'com.instagram.android'
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        self.logger.debug("Deep link executed successfully (subprocess)")
                        self._human_like_delay('click')  # Minimal — am start -W already waits for activity
                        if self._verify_profile_navigation(username):
                            return True
                    else:
                        self.logger.debug(f"Deep link failed: {result.stderr}")
                
            except subprocess.TimeoutExpired:
                self.logger.debug("Timeout during deep link execution")
            except Exception as e:
                self.logger.debug(f"Deep link error: {e}")
            
            if attempt < max_attempts - 1:
                self._random_sleep()
        
        return False

    def navigate_to_post_url(self, post_url: str) -> bool:
        """
        Navigate to a specific Instagram post via deep link.
        
        Args:
            post_url: Full Instagram post URL (e.g., https://www.instagram.com/p/ABC123/)
            
        Returns:
            bool: True if navigation successful
        """
        # Delegate to the proper deep link method that specifies Instagram package
        return self.navigate_to_post_via_deep_link(post_url)

    def navigate_to_post_via_deep_link(self, post_url: str) -> bool:
        try:
            from urllib.parse import urlparse
            
            self.logger.info(f"🔗 Navigating to post via deep link: {post_url}")
            
            # Clean URL: remove tracking params (?utm_source=...&igsh=...)
            # The & character causes shell splitting on the device
            parsed = urlparse(post_url)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean_url != post_url:
                self.logger.debug(f"Cleaned URL: {clean_url}")
            
            device_serial = self._get_device_serial()
            
            # Use adbutils (same pattern as navigate_to_profile deep link)
            try:
                from adbutils import adb
                device = adb.device(serial=device_serial)
                result = device.shell(f'am start -W -a android.intent.action.VIEW -d "{clean_url}" com.instagram.android')
                self.logger.debug(f"Deep link result: {result}")
                
                if 'Error' in str(result) or 'Exception' in str(result):
                    self.logger.error(f"❌ ADB error opening post: {result}")
                    return False
            except ImportError:
                # Fallback to subprocess if adbutils not available
                import subprocess
                adb_command = f'adb -s {device_serial} shell am start -W -a android.intent.action.VIEW -d "{clean_url}" com.instagram.android'
                sub_result = subprocess.run(adb_command, shell=True, capture_output=True, text=True, timeout=10)
                if sub_result.returncode != 0:
                    self.logger.error(f"❌ ADB error opening post: {sub_result.stderr}")
                    return False
                
            self._human_like_delay('page_load')
            
            # Check POSITIVE indicators FIRST (Like/Comment buttons = we're on a post)
            # This avoids false positives from broad error selectors matching post captions
            for indicator in self.detection_selectors.post_screen_indicators:
                if self._wait_for_element(indicator, timeout=3, silent=True):
                    self.logger.success(f"✅ Successfully navigated to post")
                    return True
            
            # Only check error indicators if no positive match found
            for selector in self.detection_selectors.post_error_indicators:
                try:
                    if self._wait_for_element(selector, timeout=2, silent=True):
                        self.logger.error(f"❌ Post inaccessible: {post_url}")
                        self._press_back()
                        return False
                except Exception:
                    continue
            
            self.logger.warning(f"⚠️ Navigation to post uncertain: {post_url}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error navigating to post via deep link: {e}")
            return False
