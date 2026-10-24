"""Navigation helpers for the Instagram Cold DM workflow."""

from __future__ import annotations

from typing import Any

from loguru import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from taktik.core.social_media.instagram.workflows.cold_dm.recipient_policy import (
    ColdDmRecipientPolicy,
    cold_dm_skip_reason,
)

#: `open_dm_from_profile` outcome when the screen is no profile: nothing was read nor tapped.
NOT_ON_PROFILE = "not_on_profile"

#: How long a profile opened from the search may take to draw, as in the other profile flows.
PROFILE_LOAD_TIMEOUT_S = 8.0


class ColdDMNavigationMixin:
    """Profile and home navigation used by the Cold DM outreach flow."""

    # What the host gives this mixin, like the fields of a TypeScript interface.
    device: Any  # the (clone-aware) uiautomator2 device, behind the facade
    device_manager: Any  # its manager, which the production actions are built on

    def is_private_profile(self) -> bool:
        """Check if the current profile is private."""
        private_state = self.device(resourceId=PROFILE_SELECTORS.private_empty_state_resource_id)
        if private_state.exists:
            logger.info("Detected private profile (empty state)")
            return True

        for text in PROFILE_SELECTORS.private_text_contains:
            private_text = self.device(textContains=text)
            if private_text.exists:
                logger.info("Detected private profile (text)")
                return True

        return False

    def _cold_dm_detection(self):
        """The production profile reader, on this workflow's device (the Lab supplies its own)."""
        from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions

        return DetectionActions(self.device_manager)

    def _cold_dm_navigation(self):
        """The production navigation, on this workflow's device (the Lab supplies its own): its
        profile search is the one every workflow opens a profile with."""
        from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions

        return NavigationActions(self.device_manager)

    def _cold_dm_messaging(self):
        """The production DM sending from a profile (the welcome DM's too), on this workflow's
        device (the Lab supplies its own)."""
        from taktik.core.social_media.instagram.workflows.dm.messaging import MessagingBusiness

        return MessagingBusiness(self.device_manager)

    def open_recipient_profile(self, recipient: str) -> bool:
        """Open the recipient's profile through the production profile search, never a deep link
        (as the cold DM always reached its recipients): the row of that exact handle, or nobody."""
        return self._cold_dm_navigation().navigate_to_profile(recipient, force_search=True)

    def find_message_button(self):
        """The profile's Message button, looked for inside the profile header only, or None: the
        production lookup the conversation opener uses."""
        return self._cold_dm_messaging().find_header_message_button()

    def evaluate_cold_dm_profile(self, policy: ColdDmRecipientPolicy | None = None) -> dict:
        """Read the open profile and decide, without touching the screen.

        Nothing is read unless the production profile detector sees a profile: any screen with
        the tab bar shows the Direct tab, and a notification row has a Message button of its
        own. Off a profile, `on_profile` is False and every read is None.

        The certified badge is read only when the operator asked to skip certified accounts:
        a dump per recipient costs nothing next to the pause between two DMs, but a read nobody
        acts on is still a read. The decision itself is `cold_dm_skip_reason`, in the core.
        """
        policy = policy or ColdDmRecipientPolicy()
        detection = self._cold_dm_detection()
        if not detection.wait_for_profile_screen(timeout=PROFILE_LOAD_TIMEOUT_S):
            logger.warning("Not on a profile screen: no cold DM decision taken")
            return {
                "on_profile": False,
                "skip_reason": None,
                "is_private": None,
                "is_verified": None,
                "has_message_button": None,
                "message_button": None,
            }
        is_private = self.is_private_profile()
        is_verified = bool(policy.skip_verified and detection.is_verified_account())
        msg_btn = self.find_message_button()
        reason = cold_dm_skip_reason(
            policy,
            is_private=is_private,
            is_verified=is_verified,
            has_message_button=msg_btn is not None,
        )
        return {
            "on_profile": True,
            "skip_reason": reason,
            "is_private": is_private,
            "is_verified": is_verified,
            "has_message_button": msg_btn is not None,
            "message_button": msg_btn,
        }

    def open_dm_from_profile(self, policy: ColdDmRecipientPolicy | None = None):
        """Open the DM conversation from a user's profile.

        Returns True once the conversation is open, False when it could not be,
        `NOT_ON_PROFILE` when the screen is no profile (nothing tapped), or the skip reason
        (`recipient_policy.SKIP_*`) when the operator's settings leave this profile alone.
        """
        logger.info("Opening DM from profile...")

        verdict = self.evaluate_cold_dm_profile(policy)
        if not verdict["on_profile"]:
            return NOT_ON_PROFILE
        if verdict["skip_reason"]:
            logger.warning(f"Skipping DM - {verdict['skip_reason']}")
            return verdict["skip_reason"]

        if verdict["is_private"]:
            logger.info("Private profile with a Message button - trying the DM (setting allows it)")
        # Without a Message button the opener goes through the profile's Options sheet, as the
        # welcome DM does; False when that offers no conversation either.
        return self._cold_dm_messaging().open_conversation_from_profile()

    def go_home(self) -> bool:
        """Back to the home feed by the production navigation, between two recipients."""
        logger.info("Navigating to home...")
        return self._cold_dm_navigation().navigate_to_home()
