"""Shared popup handling logic for all TikTok workflows.

Centralises the popup-detection-and-close chain that was duplicated
across ForYouWorkflow, SearchWorkflow, and FollowersWorkflow.
"""

import time
from loguru import logger


class PopupHandler:
    """Stateless helper that closes TikTok popups using click + detection actions.

    Usage::

        handler = PopupHandler(click_actions, detection_actions)
        closed = handler.close_all()   # returns True if something was closed
    """

    def __init__(self, click, detection):
        self.click = click
        self.detection = detection
        self.logger = logger.bind(module="tiktok-popup-handler")

    def close_all(self) -> bool:
        """Run through the full popup chain. Returns True if any popup was closed."""

        # Android system popups (input method selection, etc.)
        if self.click.close_system_popup():
            self.logger.info("✅ System popup closed")
            time.sleep(0.5)
            return True

        # Notification banner (e.g., "X sent you new messages")
        if self.click.dismiss_notification_banner():
            self.logger.info("✅ Notification banner dismissed")
            time.sleep(0.5)
            return True

        # Accidentally on Inbox page
        if self.detection.is_on_inbox_page():
            self.click.escape_inbox_page()
            self.logger.info("✅ Escaped from Inbox page")
            time.sleep(0.5)
            return True

        # "Link email" popup
        if self.detection.has_link_email_popup():
            if self.click.close_link_email_popup():
                self.logger.info("✅ 'Link email' popup closed")
                time.sleep(0.5)
                return True

        # "Follow your friends" popup
        if self.detection.has_follow_friends_popup():
            if self.click.close_follow_friends_popup():
                self.logger.info("✅ 'Follow your friends' popup closed")
                time.sleep(0.5)
                return True

        # Collections popup
        if self.detection.has_collections_popup():
            if self.click.close_collections_popup():
                self.logger.info("✅ Collections popup closed")
                time.sleep(0.5)
                return True

        # Generic popup
        if self.detection.has_popup():
            self.logger.info("🚨 Popup detected, attempting to close")
            if self.click.close_popup():
                self.logger.info("✅ Popup closed")
                time.sleep(0.5)
                return True

        return False
