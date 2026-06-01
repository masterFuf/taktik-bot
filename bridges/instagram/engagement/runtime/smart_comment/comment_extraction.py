"""Visible comment extraction support for Instagram Smart Comment."""

from __future__ import annotations

import traceback

from bridges.instagram.engagement.runtime.smart_comment.events import emit_comment_scraped
from bridges.instagram.engagement.runtime.smart_comment.models import ScrapedComment
from bridges.instagram.engagement.runtime.smart_comment.parsing import parse_litho_comments
from bridges.instagram.engagement.runtime.smart_comment.visible_usernames import extract_visible_comment_usernames
from bridges.instagram.runtime.ipc import logger
from taktik.core.shared.device.adb import run_adb_shell_process


class SmartCommentCommentExtractionMixin:
    """Extract visible comments from XML and Litho dumpsys output."""

    def _get_visible_usernames(self) -> set:
        """Get usernames currently visible in the comments RecyclerView."""
        visible = set()
        try:
            xml = self.device.dump_hierarchy()
            if not xml:
                return visible

            visible = extract_visible_comment_usernames(xml)
            logger.debug(f"Visible comment usernames from XML ({len(visible)}): {visible}")
        except Exception as e:
            logger.warning(f"Failed to get visible usernames from XML: {e}")

        return visible

    def _get_dumpsys_comments(self) -> str:
        """Get the Litho view hierarchy via adb shell dumpsys activity top."""
        try:
            result = run_adb_shell_process(
                self.device_id,
                ["dumpsys", "activity", "top"],
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            return result.stdout or ""
        except Exception as e:
            logger.error(f"dumpsys activity top failed: {e}")
            return ""

    def _extract_visible_comments_fast(self, seen_keys: set, max_comments: int) -> int:
        """Extract visible comments via dumpsys activity top."""
        count_before = len(self.comments)

        try:
            visible_usernames = self._get_visible_usernames()

            dumpsys = self._get_dumpsys_comments()
            if not dumpsys:
                logger.warning("Empty dumpsys output")
                return 0

            comments_data = parse_litho_comments(dumpsys)
            logger.debug(f"Parsed {len(comments_data)} comments from dumpsys")

            if visible_usernames:
                before_filter = len(comments_data)
                comments_data = [c for c in comments_data if c.get("username", "").lower() in visible_usernames]
                filtered_out = before_filter - len(comments_data)
                if filtered_out > 0:
                    logger.debug(f"Filtered out {filtered_out} ghost/cached comments (not visible on screen)")

            for cdata in comments_data:
                if len(self.comments) >= max_comments:
                    break

                username = cdata.get("username", "")
                comment_text = cdata.get("text", "")
                if not username or not comment_text:
                    continue

                key = (username.lower(), comment_text[:50].lower())
                if key in seen_keys:
                    continue

                is_author = False
                if self.post_context.author_username and username.lower() == self.post_context.author_username.lower():
                    is_author = True

                seen_keys.add(key)
                is_reply = cdata.get("is_reply", False)
                parent_username = cdata.get("parent_username", None)
                comment = ScrapedComment(
                    username=username,
                    content=comment_text,
                    likes=cdata.get("likes", 0),
                    is_author=is_author,
                    is_reply=is_reply,
                    parent_username=parent_username,
                    position_top=cdata.get("position_top", 0),
                )
                self.comments.append(comment)

                reply_info = ""
                if is_reply:
                    reply_info = f" [reply to @{parent_username}]" if parent_username else " [reply]"

                logger.debug(
                    f"Comment #{len(self.comments)}: @{username} "
                    f"({comment.likes} likes)"
                    f"{reply_info}: "
                    f"{comment_text[:60]}..."
                )

                emit_comment_scraped(
                    index=len(self.comments),
                    username=username,
                    content=comment_text[:200],
                    likes=comment.likes,
                    is_author=is_author,
                    is_reply=is_reply,
                    parent_username=parent_username or "",
                )

        except Exception as e:
            logger.error(f"Error in comment extraction: {e}")
            logger.error(traceback.format_exc())

        new_count = len(self.comments) - count_before
        return new_count
