"""TikTok cold DM outreach workflow."""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Optional

from loguru import logger

from taktik.core.social_media.tiktok import TikTokManager
from taktik.core.social_media.tiktok.actions.atomic.dm_actions import DMActions
from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
from taktik.core.social_media.tiktok.actions.core.base_action import BaseAction
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS


DuplicateChecker = Callable[[int, str, str], bool]
SentDMRecorder = Callable[[int, str, str, bool, Optional[str], Optional[str], str], None]


class TikTokDMOutreachWorkflow:
    """Send cold DMs to TikTok recipients without owning bridge IPC or DB."""

    def __init__(
        self,
        device_id: str,
        *,
        notifier: Any = None,
        duplicate_checker: DuplicateChecker | None = None,
        sent_dm_recorder: SentDMRecorder | None = None,
        manager_factory: Callable[..., Any] = TikTokManager,
        navigation_factory: Callable[[Any], Any] = NavigationActions,
        dm_actions_factory: Callable[[Any], Any] = DMActions,
        base_action_factory: Callable[[Any], Any] = BaseAction,
        rng: Any = random,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.device_id = device_id
        self.notifier = notifier
        self.duplicate_checker = duplicate_checker or _never_duplicate
        self.sent_dm_recorder = sent_dm_recorder or _ignore_sent_dm_record
        self.manager_factory = manager_factory
        self.navigation_factory = navigation_factory
        self.dm_actions_factory = dm_actions_factory
        self.base_action_factory = base_action_factory
        self.rng = rng
        self.sleep = sleeper

        self.device = None
        self.manager = None
        self.navigation = None
        self.dm_actions = None
        self.base_action = None
        self.dms_sent = 0
        self.dms_success = 0
        self.dms_failed = 0
        self.privacy_blocked = 0
        self.not_found = 0

    def connect(self) -> bool:
        """Connect to the device and initialize TikTok actions."""
        logger.info(f"Connecting to device: {self.device_id}")

        try:
            self.manager = self.manager_factory(device_id=self.device_id)
            if not self.manager.device_manager.connect():
                logger.error("Failed to connect to device via device_manager")
                return False

            self.device = self.manager.device_manager.device
            self.navigation = self.navigation_factory(self.device)
            self.dm_actions = self.dm_actions_factory(self.device)
            self.base_action = self.base_action_factory(self.device)

            logger.info("Connected to device successfully")
            return True
        except Exception as exc:
            logger.error(f"Failed to connect: {exc}")
            return False

    def restart_tiktok(self) -> None:
        """Restart TikTok for a clean outreach state."""
        logger.info("Restarting TikTok...")
        _notify(self.notifier, "status", status="restarting", message="Restarting TikTok app")

        if self.manager:
            self.manager.stop()
            self.sleep(1)
            self.manager.launch()
            self.sleep(4)

    def navigate_to_user_profile(self, username: str) -> bool:
        logger.info(f"Navigating to @{username}'s profile")
        return self.navigation.navigate_to_user_profile(username)

    def click_message_button(self) -> bool:
        """Click the Message button on a user's profile."""
        logger.info("Clicking Message button on profile")

        if self.base_action._find_and_click(PROFILE_SELECTORS.message_button, timeout=5):
            self.sleep(2)
            return True

        try:
            raw_device = self.device._device if hasattr(self.device, "_device") else self.device
            message_elem = raw_device(**PROFILE_SELECTORS.message_button_text_selector)
            if message_elem.exists:
                message_elem.click()
                self.sleep(2)
                return True
        except Exception as exc:
            logger.warning(f"Fallback click failed: {exc}")

        logger.warning("Message button not found on profile")
        return False

    def is_privacy_blocked(self) -> bool:
        """Check if the conversation is blocked due to privacy settings."""
        if self.base_action._element_exists(PROFILE_SELECTORS.unable_to_send_message, timeout=2):
            logger.info("Detected privacy blocked conversation (unable to send)")
            return True

        if self.base_action._element_exists(PROFILE_SELECTORS.privacy_blocked_message, timeout=2):
            logger.info("Detected privacy blocked conversation (privacy settings)")
            return True

        return False

    def can_send_message(self) -> bool:
        return self.dm_actions.is_in_conversation()

    def send_dm(self, message: str) -> bool | str:
        """Send a DM in the current conversation."""
        logger.info("Sending DM...")

        if self.is_privacy_blocked():
            logger.warning("Cannot send DM - privacy blocked")
            return "privacy_blocked"

        if not self.can_send_message():
            logger.warning("Message input not found")
            return False

        if self.dm_actions.send_text_message(message):
            logger.info("DM sent successfully")
            return True

        logger.warning("Failed to send DM")
        return False

    def go_home(self) -> None:
        logger.info("Navigating to home...")
        self.navigation.navigate_to_home()
        self.sleep(1)

    def run(
        self,
        recipients: list[str],
        messages: list[str],
        delay_min: int = 30,
        delay_max: int = 60,
        max_dms: int = 50,
        account_id: int = 1,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Run the cold DM outreach workflow."""
        logger.info(
            f"Starting TikTok DM Outreach: {len(recipients)} recipients, {len(messages)} messages"
        )

        if not messages:
            return {"success": False, "error": "No messages provided"}
        if not recipients:
            return {"success": False, "error": "No recipients provided"}

        filtered_recipients = []
        skipped_count = 0
        for recipient in recipients:
            if self.duplicate_checker(account_id, recipient, "tiktok"):
                logger.info(f"Skipping {recipient} - DM already sent")
                skipped_count += 1
            else:
                filtered_recipients.append(recipient)

        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} recipients (DM already sent)")
            _notify(
                self.notifier,
                "status",
                status="filtering",
                message=f"Skipped {skipped_count} already contacted",
            )

        if not filtered_recipients:
            return {
                "success": True,
                "dms_sent": 0,
                "dms_success": 0,
                "dms_failed": 0,
                "error": "All recipients already received a DM",
            }

        self.restart_tiktok()
        total_to_process = min(len(filtered_recipients), max_dms)

        for index, recipient in enumerate(filtered_recipients[:max_dms]):
            if self.dms_sent >= max_dms:
                logger.info(f"Reached max DMs limit: {max_dms}")
                break

            logger.info(f"[{index + 1}/{total_to_process}] Sending DM to: @{recipient}")
            _notify(
                self.notifier,
                "progress",
                current=index + 1,
                total=total_to_process,
                username=recipient,
            )
            _notify(self.notifier, "status", status="processing", message=f"Processing @{recipient}")

            try:
                should_delay = self._process_recipient(recipient, messages, account_id, session_id)
                self._send_stats()
                self.go_home()

                if should_delay and index < total_to_process - 1:
                    delay = self.rng.uniform(delay_min, delay_max)
                    logger.info(f"Waiting {delay:.1f}s before next DM...")
                    _notify(
                        self.notifier,
                        "status",
                        status="waiting",
                        message=f"Waiting {delay:.0f}s...",
                    )
                    self.sleep(delay)
            except Exception as exc:
                logger.error(f"Error sending DM to @{recipient}: {exc}")
                self.dms_failed += 1
                _notify(self.notifier, "dm_result", username=recipient, success=False, error=str(exc))
                self.go_home()

        return {
            "success": True,
            "dms_sent": self.dms_sent,
            "dms_success": self.dms_success,
            "dms_failed": self.dms_failed,
            "privacy_blocked": self.privacy_blocked,
            "not_found": self.not_found,
        }

    def _process_recipient(
        self,
        recipient: str,
        messages: list[str],
        account_id: int,
        session_id: str | None,
    ) -> bool:
        if not self.navigate_to_user_profile(recipient):
            logger.warning(f"Could not find user: @{recipient}")
            self.not_found += 1
            self.dms_failed += 1
            _notify(
                self.notifier,
                "dm_result",
                username=recipient,
                success=False,
                error="User not found",
            )
            return False

        if not self.click_message_button():
            logger.warning(f"Could not click Message button for @{recipient}")
            self.dms_failed += 1
            _notify(
                self.notifier,
                "dm_result",
                username=recipient,
                success=False,
                error="Message button not found",
            )
            return False

        message = self.rng.choice(messages)
        send_result = self.send_dm(message)

        if send_result == "privacy_blocked":
            logger.warning(f"Privacy blocked for @{recipient}")
            self.privacy_blocked += 1
            self.dms_failed += 1
            _notify(
                self.notifier,
                "dm_result",
                username=recipient,
                success=False,
                error="Privacy settings blocked",
            )
            self.sent_dm_recorder(
                account_id, recipient, "", False, "Privacy blocked", session_id, "tiktok"
            )
        elif send_result:
            self.dms_success += 1
            self.dms_sent += 1
            logger.info(f"Successfully sent DM to @{recipient}")
            _notify(self.notifier, "dm_result", username=recipient, success=True, error=None)
            self.sent_dm_recorder(account_id, recipient, message, True, None, session_id, "tiktok")
        else:
            self.dms_failed += 1
            logger.warning(f"Failed to send DM to @{recipient}")
            _notify(self.notifier, "dm_result", username=recipient, success=False, error="Send failed")

        return True

    def _send_stats(self) -> None:
        _notify(
            self.notifier,
            "stats",
            stats={
                "sent": self.dms_sent,
                "success": self.dms_success,
                "failed": self.dms_failed,
                "privacy_blocked": self.privacy_blocked,
                "not_found": self.not_found,
            },
        )


def _notify(notifier: Any, event_type: str, **payload: Any) -> None:
    if notifier is None:
        return
    sender = getattr(notifier, "send", None)
    if callable(sender):
        sender(event_type, **payload)
        return
    method = getattr(notifier, event_type, None)
    if callable(method):
        method(**payload)


def _never_duplicate(account_id: int, recipient: str, platform: str) -> bool:
    return False


def _ignore_sent_dm_record(
    account_id: int,
    recipient: str,
    message: str,
    success: bool,
    error_message: Optional[str],
    session_id: Optional[str],
    platform: str,
) -> None:
    return None
