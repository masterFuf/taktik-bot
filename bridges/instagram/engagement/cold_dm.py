#!/usr/bin/env python3
"""
Cold DM Bridge - Interface between Electron and Cold DM Workflow
Sends DMs to a list of recipients (cold outreach)
Supports AI-generated personalized messages via OpenRouter.
"""

import sys

# Bootstrap: UTF-8 + loguru + sys.path in one call
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from bridges.common.runtime.bootstrap import setup_environment
setup_environment(log_level="INFO")

from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import logger
from bridges.instagram.engagement.runtime.cold_dm_messages import choose_cold_dm_message
from bridges.instagram.engagement.runtime.cold_dm_navigation import ColdDMNavigationMixin
from bridges.instagram.engagement.runtime.cold_dm_persistence import (
    record_sent_dm,
)
from bridges.instagram.engagement.runtime.cold_dm_progress import emit_cold_dm_progress
from bridges.instagram.engagement.runtime.cold_dm_recipients import ColdDMRecipientMixin
from bridges.instagram.engagement.runtime.cold_dm_sender import ColdDMSenderMixin
from bridges.instagram.engagement.runtime.cold_dm_timing import wait_before_next_cold_dm


class ColdDMWorkflow(ColdDMRecipientMixin, ColdDMSenderMixin, ColdDMNavigationMixin, InstagramBridgeBase):
    """Cold DM workflow - sends DMs to new users (cold outreach)."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self._init_cold_dm_sender(device_id)
        # Stats
        self.dms_sent = 0
        self.dms_success = 0
        self.dms_failed = 0
        self.private_profiles = 0

    def run(self, recipients: list, messages: list, delay_min: int = 30, delay_max: int = 60, max_dms: int = 50, account_id: int = 1, session_id: str = None, ai_prompt: str = '', openrouter_api_key: str = '') -> dict:
        """Run the cold DM workflow."""
        use_ai = bool(ai_prompt and openrouter_api_key)
        logger.info(f"Starting Cold DM workflow: {len(recipients)} recipients, {len(messages)} messages, AI mode: {use_ai}")

        if not messages and not use_ai:
            return {'success': False, 'error': 'No messages provided and AI mode not configured'}

        if not recipients:
            return {'success': False, 'error': 'No recipients provided'}

        filtered_recipients = self.filter_pending_recipients(recipients, account_id)

        if not filtered_recipients:
            return {'success': True, 'dms_sent': 0, 'dms_success': 0, 'dms_failed': 0, 'error': 'All recipients already received a DM'}

        # Restart Instagram for clean state
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
                # Navigate to search
                if not self.navigate_to_search():
                    logger.warning(f"Could not navigate to search for {recipient}")
                    self.dms_failed += 1
                    # DON'T record - this is a temporary error, we can retry later
                    self.go_home()  # Reset to home before next attempt
                    continue

                # Search for user
                if not self.search_user(recipient):
                    logger.warning(f"Could not find user: {recipient}")
                    self.dms_failed += 1
                    # DON'T record - user might exist, just search failed
                    self.go_home()  # Reset to home
                    continue

                # Open DM from profile
                open_result = self.open_dm_from_profile()
                if open_result == "private":
                    logger.warning(f"Skipping {recipient} - private profile")
                    # Only count as private, NOT as failed (avoid double counting)
                    self.private_profiles += 1
                    # DON'T record - we might want to retry if they become public
                    self.go_home()
                    continue
                elif not open_result:
                    logger.warning(f"Could not open DM for: {recipient}")
                    self.dms_failed += 1
                    # DON'T record - could be temporary UI issue
                    self.go_home()  # Reset to home
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

                # Send message
                send_result = self.send_message(message)

                if send_result == "invite_sent":
                    # Invite was already sent - record as success to avoid retry
                    logger.info(f"Invite already sent to {recipient} - marking as done")
                    record_sent_dm(account_id, recipient, "", True, "Invite already sent", session_id)
                    self.dms_sent += 1
                elif send_result:
                    self.dms_success += 1
                    logger.info(f"Successfully sent DM to {recipient}")
                    # ONLY record successful DMs - these should not be retried
                    record_sent_dm(account_id, recipient, message, True, None, session_id)
                    self.dms_sent += 1
                else:
                    self.dms_failed += 1
                    logger.warning(f"Failed to send DM to {recipient}")
                    # DON'T record failed sends - we can retry later

                # Go back to home before next user (more reliable than go_back twice)
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
                self.go_home()  # Go home to reset state

        return {
            'success': True,
            'dms_sent': self.dms_sent,
            'dms_success': self.dms_success,
            'dms_failed': self.dms_failed,
            'private_profiles': self.private_profiles
        }


def main():
    from bridges.instagram.engagement.runtime.cold_dm_commands import run_cold_dm_cli

    run_cold_dm_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
