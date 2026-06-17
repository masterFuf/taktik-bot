"""Reply helpers for the Instagram Smart Comment bridge."""

from __future__ import annotations

import random
import time
from typing import Any

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.engagement.runtime.smart_comment.reply_finder import SmartCommentReplyFinderMixin
from bridges.instagram.engagement.runtime.smart_comment.reply_sender import SmartCommentReplySenderMixin
from bridges.instagram.runtime.ipc import logger, send_message as send_event
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS


class SmartCommentReplyMixin(SmartCommentReplySenderMixin, SmartCommentReplyFinderMixin):
    """Reply finding, typing and batching for Smart Comment."""

    def _init_smart_comment_reply(self, device_id: str) -> None:
        self._keyboard = KeyboardService(device_id)

    def reply_to_comment(self, username: str, comment_content_prefix: str, reply_text: str) -> bool:
        """
        Reply to a specific comment.

        Strategy:
        1. Scroll through comments to find the target comment
        2. Click "Reply" on that comment
        3. Type the reply
        4. Send it
        """
        logger.info(f"Replying to @{username} ({len(reply_text)} chars)")

        if not self._find_and_click_reply(username, comment_content_prefix):
            logger.error(f"Could not find Reply button for @{username}")
            return False

        time.sleep(random.uniform(0.5, 1.0))

        input_field = self.device(resourceId=POST_COMMENTS_SELECTORS.comment_field_resource_id)
        if not input_field.exists:
            logger.error("Comment input field not found after clicking Reply")
            return False

        input_field.click()
        time.sleep(0.5)

        current_text = input_field.get_text() or ""
        logger.debug(f"Input field text after Reply click: '{current_text}'")

        time.sleep(random.uniform(0.3, 0.6))

        if not self._type_reply_text(input_field, current_text, reply_text):
            logger.error("All typing methods failed — could not insert reply text")
            return False

        time.sleep(random.uniform(0.5, 1.0))

        send_btn = self._find_reply_send_button()

        if send_btn and send_btn.exists:
            send_btn.click()
            time.sleep(1.5)
            logger.info(f"Reply sent to @{username}")
            send_event("reply_sent", username=username, reply=reply_text, content=comment_content_prefix)
            return True

        logger.error("Send/Post button not found — dumping UI for debug")
        self._log_potential_send_buttons()
        return False

    def run_reply(self, qualified_comments: list[dict[str, Any]]) -> dict[str, Any]:
        """Run the reply phase against pre-qualified comments."""
        delay_range = self.config.get("delayBetweenReplies", [30, 90])
        dry_run = self.config.get("dryRun", False)
        replies_sent = 0
        replies_failed = 0
        replied_usernames = set()

        for i, qc in enumerate(qualified_comments):
            username = qc.get("username", "")
            content = qc.get("content", "")
            reply = qc.get("reply", "")

            if not username or not reply:
                continue

            if username.lower() in replied_usernames:
                logger.info(f"[{i+1}/{len(qualified_comments)}] Skipping @{username} — already replied in this session")
                continue

            logger.info(f"[{i+1}/{len(qualified_comments)}] Replying to @{username}...")
            send_event(
                "reply_progress",
                current=i + 1,
                total=len(qualified_comments),
                username=username,
            )

            if dry_run:
                logger.info(f"[DRY RUN] Would reply to @{username} ({len(reply)} chars)")
                send_event("reply_dry_run", username=username, reply=reply)
                replies_sent += 1
                replied_usernames.add(username.lower())
                continue

            success = self.reply_to_comment(username, content, reply)
            if success:
                replies_sent += 1
                replied_usernames.add(username.lower())
            else:
                replies_failed += 1
                send_event("reply_failed", username=username, content=content)

            if i < len(qualified_comments) - 1:
                delay = random.uniform(delay_range[0], delay_range[1])
                logger.info(f"Waiting {delay:.0f}s before next reply...")
                time.sleep(delay)

                self._dismiss_keyboard_and_scroll_top()

        results = {
            "success": True,
            "replies_sent": replies_sent,
            "replies_failed": replies_failed,
            "total": len(qualified_comments),
            "dry_run": dry_run,
        }
        send_event("reply_complete", **results)
        return results
