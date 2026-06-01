"""Instagram Cold DM bridge workflow runtime class."""

from __future__ import annotations

from bridges.instagram.engagement.runtime.cold_dm_messages import choose_cold_dm_message
from bridges.instagram.engagement.runtime.cold_dm_navigation import ColdDMNavigationMixin
from bridges.instagram.engagement.runtime.cold_dm_progress import emit_cold_dm_progress
from bridges.instagram.engagement.runtime.cold_dm_recipients import ColdDMRecipientMixin
from bridges.instagram.engagement.runtime.cold_dm_results import apply_cold_dm_send_result
from bridges.instagram.engagement.runtime.cold_dm_search import ColdDMSearchMixin
from bridges.instagram.engagement.runtime.cold_dm_sender import ColdDMSenderMixin
from bridges.instagram.engagement.runtime.cold_dm_timing import wait_before_next_cold_dm
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import logger


class ColdDMWorkflow(
    ColdDMRecipientMixin,
    ColdDMSearchMixin,
    ColdDMSenderMixin,
    ColdDMNavigationMixin,
    InstagramBridgeBase,
):
    """Cold DM workflow - sends DMs to new users (cold outreach)."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self._init_cold_dm_sender(device_id)
        self.dms_sent = 0
        self.dms_success = 0
        self.dms_failed = 0
        self.private_profiles = 0

    def run(
        self,
        recipients: list,
        messages: list,
        delay_min: int = 30,
        delay_max: int = 60,
        max_dms: int = 50,
        account_id: int = 1,
        session_id: str = None,
        ai_prompt: str = "",
        openrouter_api_key: str = "",
    ) -> dict:
        """Run the cold DM workflow."""
        use_ai = bool(ai_prompt and openrouter_api_key)
        logger.info(
            f"Starting Cold DM workflow: {len(recipients)} recipients, "
            f"{len(messages)} messages, AI mode: {use_ai}"
        )

        if not messages and not use_ai:
            return {"success": False, "error": "No messages provided and AI mode not configured"}

        if not recipients:
            return {"success": False, "error": "No recipients provided"}

        filtered_recipients = self.filter_pending_recipients(recipients, account_id)

        if not filtered_recipients:
            return {
                "success": True,
                "dms_sent": 0,
                "dms_success": 0,
                "dms_failed": 0,
                "error": "All recipients already received a DM",
            }

        self.restart_instagram()

        for i, recipient in enumerate(filtered_recipients[:max_dms]):
            if self.dms_sent >= max_dms:
                logger.info(f"Reached max DMs limit: {max_dms}")
                break

            logger.info(f"[{i+1}/{min(len(filtered_recipients), max_dms)}] Sending DM to: {recipient}")

            emit_cold_dm_progress(
                current=i + 1,
                total=min(len(filtered_recipients), max_dms),
                username=recipient,
            )

            try:
                if not self.navigate_to_search():
                    logger.warning(f"Could not navigate to search for {recipient}")
                    self.dms_failed += 1
                    self.go_home()
                    continue

                if not self.search_user(recipient):
                    logger.warning(f"Could not find user: {recipient}")
                    self.dms_failed += 1
                    self.go_home()
                    continue

                open_result = self.open_dm_from_profile()
                if open_result == "private":
                    logger.warning(f"Skipping {recipient} - private profile")
                    self.private_profiles += 1
                    self.go_home()
                    continue
                if not open_result:
                    logger.warning(f"Could not open DM for: {recipient}")
                    self.dms_failed += 1
                    self.go_home()
                    continue

                message = choose_cold_dm_message(
                    recipient=recipient,
                    messages=messages,
                    use_ai=use_ai,
                    ai_prompt=ai_prompt,
                    openrouter_api_key=openrouter_api_key,
                )
                if not message:
                    self.dms_failed += 1
                    self.go_home()
                    continue

                send_result = self.send_message(message)

                apply_cold_dm_send_result(
                    workflow=self,
                    recipient=recipient,
                    message=message,
                    send_result=send_result,
                    account_id=account_id,
                    session_id=session_id,
                )

                self.go_home()

                wait_before_next_cold_dm(
                    index=i,
                    total=len(filtered_recipients),
                    delay_min=delay_min,
                    delay_max=delay_max,
                )

            except Exception as e:
                logger.error(f"Error sending DM to {recipient}: {e}")
                self.dms_failed += 1
                self.go_home()

        return {
            "success": True,
            "dms_sent": self.dms_sent,
            "dms_success": self.dms_success,
            "dms_failed": self.dms_failed,
            "private_profiles": self.private_profiles,
        }


__all__ = ["ColdDMWorkflow"]
