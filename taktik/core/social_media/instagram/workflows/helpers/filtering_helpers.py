import time
import random
from typing import Dict, Any
from loguru import logger


class FilteringHelpers:
    
    def __init__(self, automation):
        self.automation = automation
        self.device = automation.device
        self.nav_actions = automation.nav_actions
        self.logger = logger.bind(module="filtering-helpers")
        
    def should_interact_with_user(self, username: str, filters: Dict[str, Any]) -> bool:
        try:
            if hasattr(self.automation, 'processed_users') and username in self.automation.processed_users:
                self.logger.debug(f"@{username} already processed - skipping")
                return False
            
            try:
                if self.nav_actions.navigate_to_profile(username):
                    time.sleep(1)
                    
                    if hasattr(self.automation, 'detection_actions') and self.automation.detection_actions.is_private_account():
                        self.logger.info(f"⏭️ Private profile @{username} - SKIP immediately")
                        self.device.press("back")
                        time.sleep(0.5)
                        return False
                    
                    self.device.press("back")
                    time.sleep(0.5)
                    
            except Exception as check_error:
                self.logger.debug(f"Error checking private profile @{username}: {check_error}")
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Error checking filters for @{username}: {e}")
            return True
    
    def like_current_post(self) -> bool:
        try:
            like_button = self.device(resourceId="com.instagram.android:id/row_feed_button_like")
            if like_button.exists():
                like_button.click()
                time.sleep(random.uniform(0.5, 1.5))
                self.logger.debug("✅ Post liked successfully")
                return True
            
            self.logger.debug("❌ Like button not found")
            return False
            
        except Exception as e:
            self.logger.debug(f"Error liking post: {e}")
            return False
    
    def visit_profile_from_post(self, username: str) -> bool:
        try:
            profile_elements = self.device(resourceId="com.instagram.android:id/row_feed_photo_profile_name")
            if profile_elements.exists():
                profile_elements.click()
                time.sleep(random.uniform(2, 4))
                self.logger.debug(f"✅ Navigated to @{username} profile from post")
                return True
            
            self.logger.debug(f"❌ Profile element not found for @{username}")
            return False
            
        except Exception as e:
            self.logger.debug(f"Error visiting profile @{username}: {e}")
            return False
    
    def follow_user(self, username: str) -> bool:
        try:
            follow_button = self.device(text="Follow")
            if follow_button.exists():
                follow_button.click()
                time.sleep(random.uniform(1, 2))
                self.logger.debug(f"✅ Followed @{username} (EN)")
                return True
            
            follow_button = self.device(text="Suivre")
            if follow_button.exists():
                follow_button.click()
                time.sleep(random.uniform(1, 2))
                self.logger.debug(f"✅ Followed @{username} (FR)")
                return True
            
            self.logger.debug(f"❌ Follow button not found for @{username}")
            return False
            
        except Exception as e:
            self.logger.debug(f"Error following @{username}: {e}")
            return False
