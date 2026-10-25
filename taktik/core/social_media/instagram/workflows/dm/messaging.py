"""
Business logic for Instagram Direct Messaging.
"""

import time
from typing import Optional, Dict, Any, Union
from loguru import logger

from taktik.core.social_media.instagram.actions.base.base_action import BaseAction
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.text import dm_composer
from taktik.core.shared.diagnostics.action_block import look_for_action_block
from taktik.core.shared.diagnostics.foreground_guard import paquet_etranger
from taktik.core.shared.device.wait import find_element, wait_for_any
from taktik.core.social_media.instagram.actions.atomic.navigation.deep_link_navigation import instagram_handle
from taktik.core.social_media.instagram.workflows.dm.navigation import open_dm_inbox
from taktik.core.social_media.instagram.workflows.dm.session import dm_conversation_shown
from taktik.core.social_media.instagram.workflows.dm.reply_check import ConversationBubbles, ReplyOutcome, reply_outcome
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import (
    BUTTON_SELECTORS,
    NAVIGATION_SELECTORS,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS


#: How long a conversation may take to come up after the tap that opens it.
CONVERSATION_OPEN_TIMEOUT_S = 6.0

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
    
    def send_dm_from_profile(self, message: str, *, username: Optional[str] = None,
                             typos: bool = True) -> Union[ReplyOutcome, str]:
        """Send a DM from the profile on screen: open its conversation, then send in it.

        The one way a DM is sent from a profile, for the welcome DM (`send_dm`) and the cold DM.
        `username`: the account of that profile, for the new-message picker when the profile shows
        no Message button. Returns what the send came to (`send_in_open_conversation`), NOT_SENT
        when the conversation did not open.
        """
        self.logger.info("📨 Attempting to send DM from profile...")
        if not self.open_conversation_from_profile(username):
            return ReplyOutcome.NOT_SENT
        return self.send_in_open_conversation(message, typos=typos)

    def find_header_message_button(self):
        """The Message button of the profile on screen, looked for inside its header only, or None:
        the tab bar's Direct tab carries the same label on every screen with the bar."""
        for selector in PROFILE_SELECTORS.header_message_button:
            element = self.device.xpath(selector)
            if element is not None and element.exists:
                return element
        return None

    def open_conversation_from_profile(self, username: Optional[str] = None) -> bool:
        """Open the conversation of the profile on screen: tap its Message button, or, on another
        account's profile that shows none, write to `username` from the inbox's new-message picker.

        An account that follows us and that we do not follow back has no Message button in its
        header, public or private, in Instagram 410 and 447: only "Suivre en retour" (Pixel 6 Pro
        and Pixel 6a, 2026-10-24: the welcome DM, whose normal case it is, failed there; the cold
        DM too). The Options sheet of the profile offers the conversation in 410 only, the
        inbox's "Nouveau message" picker in both. The welcome DM and the cold DM open it here.
        """
        button = self.find_header_message_button()
        if button is not None:
            if not self._human_tap_element(button):
                button.click()
            return self._conversation_opened("Message button")
        if find_element(self.device, [PROFILE_SELECTORS.header_follow_button]) is None:
            self.logger.warning("Could not find Message button on profile (not another account's profile)")
            return False
        handle = instagram_handle(username)
        if handle is None:
            self.logger.warning("No Message button on profile, and no handle to write to from the inbox")
            return False
        self.logger.info(f"No Message button on the profile of @{handle}: writing from the inbox's new message")
        return self._open_conversation_from_new_message(handle)

    def _open_conversation_from_new_message(self, handle: str) -> bool:
        """Home, the inbox (`open_dm_inbox`, the one opener), its "Nouveau message" button, the
        handle typed in the picker, then the row of exactly that handle. A profile without a
        Message button hides the tab bar, hence home first."""
        if not NavigationActions(self.device).navigate_to_home():
            self.logger.warning("New message: could not go back home before the inbox")
            return False
        if not open_dm_inbox(self.device):
            return False
        new_message = find_element(self.device, DM_SELECTORS.new_message_button)
        if new_message is None:
            self.logger.warning("New message: no new-message button in the inbox")
            return False
        if not self._human_tap_element(new_message):
            new_message.click()
        if wait_for_any(self.device, [DM_SELECTORS.new_message_search_field], timeout=5,
                        label="dm-new-message-field") is None:
            self.logger.warning("New message: the recipient picker did not open")
            return False
        # Before the tap: a keyboard switched after it can cost the field its focus.
        self._ensure_taktik_keyboard()
        if not self._find_and_click(DM_SELECTORS.new_message_search_field, timeout=2):
            self.logger.warning("New message: could not focus the recipient field")
            return False
        self._clear_text_with_taktik_keyboard()
        if not self._type_text_checked(handle):
            self.logger.warning("New message: the recipient field does not hold the handle")
            return False
        # The results come 4 to 7 s after the typing (Pixel 6a, 447).
        row_selector = DM_SELECTORS.new_message_recipient_row(handle)
        if wait_for_any(self.device, [row_selector], timeout=12, label="dm-new-message-row") is None:
            self.logger.warning(f"New message: no row of @{handle} in the picker")
            return False
        row = find_element(self.device, [row_selector])
        if row is None:
            self.logger.warning(f"New message: the row of @{handle} went away before the tap")
            return False
        if not self._human_tap_element(row):
            row.click()
        return self._conversation_opened(f"Row of @{handle} in the new-message picker")

    def _conversation_opened(self, tapped: str) -> bool:
        """After the tap on `tapped`, is a conversation on screen (`dm_conversation_shown`)? Its
        composer is looked for only then. False, and why in the log, when none came up."""
        if dm_conversation_shown(self.device, timeout=CONVERSATION_OPEN_TIMEOUT_S):
            self.logger.debug(f"✅ {tapped} tapped: the conversation is open")
            return True
        foreign = paquet_etranger(self.device, "instagram", force=True)
        where = f": {foreign} is on screen" if foreign else ""
        self.logger.warning(f"{tapped} tapped, but no conversation came up{where}: nothing typed")
        return False

    def send_in_open_conversation(self, message: str, *, typos: bool = True) -> Union[ReplyOutcome, str]:
        """Type `message` in the open conversation, send it, and read what it came to.

        What the conversation shows after Send, by the one check of every DM send
        (`reply_check.reply_outcome`, the inbox reply's too): SENT when the message is its newest
        outgoing bubble, PENDING when Instagram shows it waiting to be sent (it leaves by itself:
        never counted as sent, never sent again), NOT_SENT when the composer or the send button is
        missing, the typing did not leave the message, or no bubble of it came;
        `INVITE_ALREADY_SENT` when the conversation has no composer because a message request to
        this account is already waiting.
        """
        composer = dm_composer.find_message_input(self.device, logger=self.logger)
        if composer is None:
            if self.invite_already_sent():
                self.logger.info("Invite already sent to this user")
                return INVITE_ALREADY_SENT
            return ReplyOutcome.NOT_SENT
        if not dm_composer.type_message(self.device, None, message, element=composer,
                                        typos=typos, logger=self.logger):
            self.logger.warning("Could not type message")
            return ReplyOutcome.NOT_SENT
        self.logger.debug(f"✅ Typed message ({len(message)} chars)")
        time.sleep(0.5)
        if not dm_composer.click_send_button(self.device, logger=self.logger):
            self.logger.warning("Could not click Send button")
            return ReplyOutcome.NOT_SENT
        outcome = reply_outcome(self.device, message, ConversationBubbles(self.device)._collect_text_messages)
        if outcome is ReplyOutcome.SENT:
            self.logger.info("✅ DM sent and confirmed in the conversation")
        return outcome

    def invite_already_sent(self) -> bool:
        """The open conversation says a message request to this account is already waiting."""
        return any(self.device.xpath(selector).exists for selector in DM_SELECTORS.invite_sent_indicators)


def send_dm(device_manager, username: str, message: str, navigate_to_profile: bool = True) -> ReplyOutcome:
    """
    Send a direct message to a user.
    
    The welcome DM's way: it opens the profile itself (the production profile search, the deep
    link as its fallback), then sends from it by `MessagingBusiness.send_dm_from_profile`, the
    cold DM's sending too. A request already waiting is not a DM sent: NOT_SENT. A DM Instagram
    shows waiting to be sent is PENDING: not sent, and not to be sent again.
    
    Args:
        device_manager: Device manager instance
        username: Target username
        message: Message to send
        navigate_to_profile: Whether to navigate to profile first (default True)
        
    Returns:
        What the DM came to (`ReplyOutcome`).
    """
    try:
        logger.info(f"📨 Sending DM to @{username}")
        
        messaging = MessagingBusiness(device_manager)
        
        if navigate_to_profile:
            nav = NavigationActions(device_manager)
            if not nav.navigate_to_profile(username):
                logger.warning(f"Could not navigate to @{username}")
                return ReplyOutcome.NOT_SENT
            time.sleep(1.5)
        
        result = messaging.send_dm_from_profile(message, username=username)
        outcome = result if isinstance(result, ReplyOutcome) else ReplyOutcome.NOT_SENT
        # The one look after a write: a refused send is not a sent DM, and the run stops.
        if look_for_action_block(ProblematicPageDetector(device_manager), after='dm', target=username):
            return ReplyOutcome.NOT_SENT
        
        if outcome is ReplyOutcome.SENT:
            logger.info(f"✅ DM sent to @{username}")
        elif outcome is ReplyOutcome.PENDING:
            logger.warning(f"DM to @{username} waiting to be sent: not counted, not sent again")
        else:
            logger.warning(f"❌ Failed to send DM to @{username}")
        
        return outcome
        
    except Exception as e:
        logger.error(f"Error in send_dm: {e}")
        return ReplyOutcome.NOT_SENT
