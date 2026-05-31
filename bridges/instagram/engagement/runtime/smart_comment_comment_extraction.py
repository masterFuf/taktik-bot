"""Visible comment extraction support for Instagram Smart Comment."""

from __future__ import annotations

import re
import subprocess
import traceback
import xml.etree.ElementTree as ET

from bridges.instagram.engagement.runtime.smart_comment_models import ScrapedComment
from bridges.instagram.engagement.runtime.smart_comment_parsing import parse_litho_comments
from bridges.instagram.runtime.ipc import logger, send_message as send_event
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS


class SmartCommentCommentExtractionMixin:
    """Extract visible comments from XML and Litho dumpsys output."""

    def _get_visible_usernames(self) -> set:
        """Get usernames currently visible in the comments RecyclerView."""
        visible = set()
        try:
            xml = self.device.dump_hierarchy()
            if not xml:
                return visible

            root = ET.fromstring(xml)

            recycler = None
            for elem in root.iter():
                rid = elem.get("resource-id", "") or ""
                if POST_COMMENTS_SELECTORS.comments_list_resource_key in rid:
                    recycler = elem
                    break

            if recycler is None:
                logger.debug("RecyclerView not found in XML, falling back to full scan")
                recycler = root

            for elem in recycler.iter():
                tag_class = elem.get("class", "") or ""
                text = (elem.get("text", "") or "").strip()
                content_desc = (elem.get("content-description", "") or "").strip()

                if tag_class == "android.widget.Button" and text:
                    if (
                        re.match(r"^[\w][\w.]{0,29}$", text)
                        and text.lower() not in POST_COMMENTS_SELECTORS.ignored_username_tokens
                    ):
                        visible.add(text.lower())

                for pattern in POST_COMMENTS_SELECTORS.profile_content_description_patterns:
                    match = re.search(pattern, content_desc)
                    if match:
                        visible.add(match.group(1).lower())

            logger.debug(f"Visible comment usernames from XML ({len(visible)}): {visible}")
        except Exception as e:
            logger.warning(f"Failed to get visible usernames from XML: {e}")

        return visible

    def _get_dumpsys_comments(self) -> str:
        """Get the Litho view hierarchy via adb shell dumpsys activity top."""
        try:
            result = subprocess.run(
                ["adb", "-s", self.device_id, "shell", "dumpsys", "activity", "top"],
                capture_output=True,
                text=True,
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

                send_event(
                    "comment_scraped",
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
