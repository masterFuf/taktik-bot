"""
Business logic for Instagram Direct Messaging.
"""

import time
import random
from typing import Optional, Dict, Any
from loguru import logger

from ....core.base_action import BaseAction
from .....ui.selectors import PROFILE_SELECTORS, BUTTON_SELECTORS, NAVIGATION_SELECTORS, DM_SELECTORS


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
                    element.click()
                    self.logger.debug("✅ Clicked Message button")
                    return True
            except Exception:
                continue
        
        return False
    
    def _type_message(self, message: str) -> bool:
        """Type a message in the DM input field."""
        input_selectors = DM_SELECTORS.message_input
        
        for selector in input_selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    time.sleep(0.3)
                    # Use send_keys or type_with_taktik_keyboard
                    self._type_text_human_like(message)
                    self.logger.debug(f"✅ Typed message: {message[:30]}...")
                    return True
            except Exception:
                continue
        
        return False
    
    def _click_send_button(self) -> bool:
        """Click the Send button to send the DM."""
        send_selectors = DM_SELECTORS.send_button
        
        for selector in send_selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    self.logger.debug("✅ Clicked Send button")
                    return True
            except Exception:
                continue
        
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
