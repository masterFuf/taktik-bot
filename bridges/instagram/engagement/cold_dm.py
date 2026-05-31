#!/usr/bin/env python3
"""
Cold DM Bridge - Interface between Electron and Cold DM Workflow
Sends DMs to a list of recipients (cold outreach)
Supports AI-generated personalized messages via OpenRouter.
"""

import sys
import json
import time
import random

# Bootstrap: UTF-8 + loguru + sys.path in one call
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from bridges.common.runtime.bootstrap import setup_environment
setup_environment(log_level="INFO")

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.base import logger, InstagramBridgeBase
from bridges.instagram.engagement.runtime.cold_dm_ai import generate_ai_message
from bridges.instagram.engagement.runtime.cold_dm_navigation import ColdDMNavigationMixin
from bridges.instagram.engagement.runtime.cold_dm_persistence import (
    check_dm_already_sent,
    record_sent_dm,
)


class ColdDMWorkflow(ColdDMNavigationMixin, InstagramBridgeBase):
    """Cold DM workflow - sends DMs to new users (cold outreach)."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self._keyboard = KeyboardService(device_id)
        # Stats
        self.dms_sent = 0
        self.dms_success = 0
        self.dms_failed = 0
        self.private_profiles = 0

    def send_message(self, message: str) -> bool:
        """Send a message in the current conversation."""
        logger.info("Sending message...")

        # Find message input
        msg_input = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
        if not msg_input.exists:
            msg_input = self.device(className="android.widget.EditText")
        if not msg_input.exists:
            msg_input = self.device(textContains="Message")

        if not msg_input.exists:
            # Check if invite was already sent
            if self.check_invite_already_sent():
                return "invite_sent"  # Special return value
            logger.error("Message input not found")
            return False

        msg_input.click()
        time.sleep(0.5)

        # Simulate typing delay
        typing_time = min(len(message) * random.uniform(0.03, 0.05) + random.uniform(0.5, 1.5), 5.0)
        time.sleep(typing_time)

        # Use Taktik Keyboard for reliable input (supports emojis, special chars, etc.)
        if self._keyboard.type_text(message):
            logger.info("Text set via Taktik Keyboard")
        else:
            # Fallback to set_text or send_keys
            logger.warning("Taktik Keyboard failed, trying fallback methods...")
            try:
                msg_input.set_text(message)
            except Exception as e:
                logger.warning(f"set_text failed: {e}, trying send_keys...")
                try:
                    msg_input.send_keys(message)
                except Exception as e2:
                    logger.error(f"send_keys also failed: {e2}")
                    return False

        time.sleep(0.5)

        # Find and click send button
        send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button_container")
        if not send_btn.exists:
            send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button")
        if not send_btn.exists:
            send_btn = self.device(description="Send")
        if not send_btn.exists:
            send_btn = self.device(description="Envoyer")

        if send_btn.exists:
            send_btn.click()
            time.sleep(1)
            logger.info("Message sent!")
            return True

        logger.error("Send button not found")
        return False

    def check_invite_already_sent(self) -> bool:
        """Check if we're on the 'Invite sent' screen."""
        invite_sent = self.device(textContains="Invite sent")
        if invite_sent.exists:
            logger.info("Invite already sent to this user")
            return True

        # Also check for "You can send more messages after your invite is accepted"
        invite_msg = self.device(textContains="invite is accepted")
        if invite_msg.exists:
            logger.info("Invite already sent (waiting for acceptance)")
            return True

        return False

    def run(self, recipients: list, messages: list, delay_min: int = 30, delay_max: int = 60, max_dms: int = 50, account_id: int = 1, session_id: str = None, ai_prompt: str = '', openrouter_api_key: str = '') -> dict:
        """Run the cold DM workflow."""
        use_ai = bool(ai_prompt and openrouter_api_key)
        logger.info(f"Starting Cold DM workflow: {len(recipients)} recipients, {len(messages)} messages, AI mode: {use_ai}")

        if not messages and not use_ai:
            return {'success': False, 'error': 'No messages provided and AI mode not configured'}

        if not recipients:
            return {'success': False, 'error': 'No recipients provided'}

        # Filter out recipients who already received a DM
        filtered_recipients = []
        skipped_count = 0
        for recipient in recipients:
            if check_dm_already_sent(account_id, recipient):
                logger.info(f"Skipping {recipient} - DM already sent")
                skipped_count += 1
            else:
                filtered_recipients.append(recipient)

        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} recipients (DM already sent)")

        if not filtered_recipients:
            return {'success': True, 'dms_sent': 0, 'dms_success': 0, 'dms_failed': 0, 'error': 'All recipients already received a DM'}

        # Restart Instagram for clean state
        self.restart_instagram()

        for i, recipient in enumerate(filtered_recipients[:max_dms]):
            if self.dms_sent >= max_dms:
                logger.info(f"Reached max DMs limit: {max_dms}")
                break

            logger.info(f"[{i+1}/{min(len(filtered_recipients), max_dms)}] Sending DM to: {recipient}")

            # Emit progress to Electron
            print(json.dumps({
                "type": "progress",
                "current": i + 1,
                "total": min(len(filtered_recipients), max_dms),
                "username": recipient
            }), flush=True)

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

                # Pick a message (AI-generated or random from list)
                if use_ai:
                    message = generate_ai_message(recipient, ai_prompt, openrouter_api_key)
                    if not message:
                        logger.warning(f"AI generation failed for @{recipient}, skipping")
                        self.dms_failed += 1
                        self.go_home()
                        continue
                else:
                    message = random.choice(messages)

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

                # Delay between DMs
                if i < len(filtered_recipients) - 1:
                    delay = random.uniform(delay_min, delay_max)
                    logger.info(f"Waiting {delay:.1f}s before next DM...")
                    time.sleep(delay)

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
