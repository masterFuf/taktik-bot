"""
Business logic for Instagram Direct Messaging.
"""

import time
from typing import Optional, Dict, Any
from loguru import logger

from taktik.core.social_media.instagram.actions.base.base_action import BaseAction
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.text import dm_composer
from taktik.core.shared.diagnostics.action_block import look_for_action_block
from taktik.core.shared.device.wait import find_element, wait_for_any
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import (
    BUTTON_SELECTORS,
    NAVIGATION_SELECTORS,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS


#: `send_dm_from_profile` outcome when the conversation shows a message request already sent.
INVITE_ALREADY_SENT = "invite_sent"


class MessagingBusiness(BaseAction):
    """Business logic for sending DMs on Instagram."""
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-messaging")
        self.profile_selectors = PROFILE_SELECTORS
        self.button_selectors = BUTTON_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
    
    def send_dm_from_profile(self, message: str, *, typos: bool = True):
        """Send a DM from the profile on screen: open its conversation, then send in it.

        The one way a DM is sent from a profile, for the welcome DM (`send_dm`) and the cold DM.
        Returns True once sent, False when a step failed, or `INVITE_ALREADY_SENT` when the
        conversation shows a message request already sent (no composer to type in).
        """
        self.logger.info("📨 Attempting to send DM from profile...")
        if not self.open_conversation_from_profile():
            return False
        return self.send_in_open_conversation(message, typos=typos)

    def find_header_message_button(self):
        """The Message button of the profile on screen, looked for inside its header only, or None:
        the tab bar's Direct tab carries the same label on every screen with the bar."""
        for selector in PROFILE_SELECTORS.header_message_button:
            element = self.device.xpath(selector)
            if element is not None and element.exists:
                return element
        return None

    def open_conversation_from_profile(self) -> bool:
        """Open the conversation of the profile on screen: tap its Message button, or, on a profile
        that shows none, the "Envoyer un message" row of its Options sheet.

        A follower we do not follow back, private, has no Message button in the header of
        Instagram 410, only "Suivre en retour" (Pixel 6 Pro, 2026-10-24: the welcome DM failed
        there); its Options sheet offers the conversation. The welcome DM and the cold DM both
        open it here.
        """
        button = self.find_header_message_button()
        if button is not None:
            if not self._human_tap_element(button):
                button.click()
            self.logger.debug("✅ Clicked Message button")
            time.sleep(2)
            return True
        return self._open_conversation_from_options()

    def _open_conversation_from_options(self) -> bool:
        """No Message button: Options, then the sheet's row that opens the conversation, on another
        account's profile only (its follow button shows it; our own Options open the settings). The
        sheet is closed again when it has no such row."""
        if find_element(self.device, [PROFILE_SELECTORS.header_follow_button]) is None:
            self.logger.warning("Could not find Message button on profile (not another account's profile)")
            return False
        options = find_element(self.device, [PROFILE_SELECTORS.header_options_button])
        if options is None:
            self.logger.warning("Could not find Message button on profile, nor its Options button")
            return False
        if not self._human_tap_element(options):
            options.click()
        found = wait_for_any(self.device, PROFILE_SELECTORS.options_sheet_message_row, timeout=3,
                             label="profile-options-message-row")
        row = find_element(self.device, [found]) if found else None
        if row is None:
            self.logger.warning("No Message button on profile, and no message row in its Options sheet")
            self.device.press_back()
            return False
        if not self._human_tap_element(row):
            row.click()
        self.logger.debug("✅ Opened the conversation from the profile's Options sheet")
        time.sleep(2)
        return True

    def send_in_open_conversation(self, message: str, *, typos: bool = True):
        """Type `message` in the open conversation and send it, through the shared composer.

        True once the send button is pressed on a composer that holds exactly the message; False
        when the composer or the send button is missing, or the typing did not leave the message;
        `INVITE_ALREADY_SENT` when the conversation has no composer because a message request to
        this account is already waiting.
        """
        composer = dm_composer.find_message_input(self.device, logger=self.logger)
        if composer is None:
            if self.invite_already_sent():
                self.logger.info("Invite already sent to this user")
                return INVITE_ALREADY_SENT
            return False
        if not dm_composer.type_message(self.device, None, message, element=composer,
                                        typos=typos, logger=self.logger):
            self.logger.warning("Could not type message")
            return False
        self.logger.debug(f"✅ Typed message ({len(message)} chars)")
        time.sleep(0.5)
        if not dm_composer.click_send_button(self.device, logger=self.logger):
            self.logger.warning("Could not click Send button")
            return False
        time.sleep(1)
        self.logger.info("✅ DM sent successfully")
        return True

    def invite_already_sent(self) -> bool:
        """The open conversation says a message request to this account is already waiting."""
        return any(self.device.xpath(selector).exists for selector in DM_SELECTORS.invite_sent_indicators)


def send_dm(device_manager, username: str, message: str, navigate_to_profile: bool = True) -> bool:
    """
    Send a direct message to a user.
    
    The welcome DM's way: it opens the profile itself (the production profile search, the deep
    link as its fallback), then sends from it by `MessagingBusiness.send_dm_from_profile`, the
    cold DM's sending too. A request already waiting is not a DM sent: False.
    
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
            nav = NavigationActions(device_manager)
            if not nav.navigate_to_profile(username):
                logger.warning(f"Could not navigate to @{username}")
                return False
            time.sleep(1.5)
        
        success = messaging.send_dm_from_profile(message) is True
        # The one look after a write: a refused send is not a sent DM, and the run stops.
        if look_for_action_block(ProblematicPageDetector(device_manager), after='dm', target=username):
            return False
        
        if success:
            logger.info(f"✅ DM sent to @{username}")
        else:
            logger.warning(f"❌ Failed to send DM to @{username}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error in send_dm: {e}")
        return False
