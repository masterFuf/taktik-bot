"""
Business logic for Instagram Direct Messaging.
"""

import time
import random
from typing import Optional, Dict, Any
from loguru import logger

from ....core.base_action import BaseAction
from taktik.core.social_media.instagram.actions.atomic.text import dm_composer
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import (
    BUTTON_SELECTORS,
    NAVIGATION_SELECTORS,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS


class MessagingBusiness(BaseAction):
    """Business logic for sending DMs on Instagram."""
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-messaging")
        self.profile_selectors = PROFILE_SELECTORS
        self.button_selectors = BUTTON_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
    
    def send_dm_from_profile(self, message: str) -> bool:
        """
        Send a DM from the current profile page.
        Assumes we are already on the target user's profile.
        
        Args:
            message: Message text to send
            
        Returns:
            True if DM sent successfully, False otherwise
        """
        try:
            self.logger.info("📨 Attempting to send DM from profile...")
            
            # Click on Message button on profile
            if not self._click_message_button():
                self.logger.warning("Could not find Message button on profile")
                return False
            
            time.sleep(2)
            
            # Type the message
            if not self._type_message(message):
                self.logger.warning("Could not type message")
                return False
            
            time.sleep(0.5)
            
            # Send the message
            if not self._click_send_button():
                self.logger.warning("Could not click Send button")
                return False
            
            time.sleep(1)
            self.logger.info("✅ DM sent successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending DM: {e}")
            return False
    
    def _click_message_button(self) -> bool:
        """Click the Message button on a profile."""
        message_selectors = PROFILE_SELECTORS.message_button
        
        for selector in message_selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    if not self._human_tap_element(element):
                        element.click()
                    self.logger.debug("✅ Clicked Message button")
                    return True
            except Exception:
                continue
        
        return False
    
    def _type_message(self, message: str) -> bool:
        """Type a message in the DM input field — shared composer atomic."""
        if dm_composer.type_message(self.device, None, message, logger=self.logger):
            self.logger.debug(f"✅ Typed message ({len(message)} chars)")
            return True
        return False
    
    def _click_send_button(self) -> bool:
        """Click the Send button to send the DM — shared composer atomic."""
        if dm_composer.click_send_button(self.device, logger=self.logger):
            self.logger.debug("✅ Clicked Send button")
            return True
        return False


def send_dm(device_manager, username: str, message: str, navigate_to_profile: bool = True) -> bool:
    """
    Send a direct message to a user.
    
    This is the main entry point for sending DMs, used by the Cold DM workflow.
    
    Args:
        device_manager: Device manager instance
        username: Target username
        message: Message to send
        navigate_to_profile: Whether to navigate to profile first (default True)
        
    Returns:
        True if DM sent successfully, False otherwise
    """
    try:
        logger.info(f"📨 Sending DM to @{username}")
        
        messaging = MessagingBusiness(device_manager)
        
        if navigate_to_profile:
            from ...atomic.navigation import NavigationActions
            nav = NavigationActions(device_manager)
            if not nav.navigate_to_profile(username):
                logger.warning(f"Could not navigate to @{username}")
                return False
            time.sleep(1.5)
        
        success = messaging.send_dm_from_profile(message)
        
        if success:
            logger.info(f"✅ DM sent to @{username}")
        else:
            logger.warning(f"❌ Failed to send DM to @{username}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error in send_dm: {e}")
        return False
