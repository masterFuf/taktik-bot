"""Comment scraping helpers for the Instagram Smart Comment bridge."""

from __future__ import annotations

import re
import subprocess
import time
import traceback
import xml.etree.ElementTree as ET

from bridges.instagram.runtime.ipc import logger, send_message as send_event
from bridges.instagram.engagement.runtime.smart_comment_models import ScrapedComment
from bridges.instagram.engagement.runtime.smart_comment_parsing import parse_litho_comments
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS


class SmartCommentCommentsMixin:
    """Open, sort and scrape Instagram comments for Smart Comment."""

    def open_comments(self) -> bool:
        """Open the comments section of the current post."""
        logger.info("Opening comments...")

        comment_btn = self.device(resourceId=POST_COMMENTS_SELECTORS.comment_button_resource_id)
        if comment_btn.exists:
            parent = comment_btn.up(className="android.view.ViewGroup", clickable=True)
            if parent and parent.exists:
                parent.click()
            else:
                comment_btn.click()
            time.sleep(2)

            title = self.device(resourceId=POST_COMMENTS_SELECTORS.comment_title_resource_id)
            if title.exists and title.get_text() in POST_COMMENTS_SELECTORS.comment_title_texts:
                logger.info("Comments page opened successfully")
                return True

        buttons = self.device(className="android.widget.Button")
        for i in range(buttons.count):
            try:
                btn = buttons[i]
                text = btn.get_text() or ""
                if text and text.isdigit() and int(text) > 0:
                    info = btn.info
                    bounds = info.get("bounds", {})
                    left = bounds.get("left", 0)
                    if 300 < left < 500:
                        btn.click()
                        time.sleep(2)
                        title = self.device(resourceId=POST_COMMENTS_SELECTORS.comment_title_resource_id)
                        if title.exists and title.get_text() in POST_COMMENTS_SELECTORS.comment_title_texts:
                            logger.info("Comments page opened via count button")
                            return True
            except Exception:
                continue

        logger.error("Could not open comments")
        return False

    def change_comment_sort(self, sort_type: str = "most_recent") -> bool:
        """Change comment sorting. Options: 'for_you', 'most_recent', 'meta_verified'."""
        logger.info(f"Changing comment sort to: {sort_type}")

        sort_btn = self.device(text=POST_COMMENTS_SELECTORS.default_sort_label, className="android.widget.Button")
        if not sort_btn.exists:
            sort_btn = self.device(description=POST_COMMENTS_SELECTORS.default_sort_label)
        if not sort_btn.exists:
            for label in POST_COMMENTS_SELECTORS.sort_button_labels:
                sort_btn = self.device(text=label, className="android.widget.Button")
                if sort_btn.exists:
                    break

        if not sort_btn.exists:
            logger.warning("Sort button not found")
            return False

        sort_btn.click()
        time.sleep(1)

        targets = POST_COMMENTS_SELECTORS.sort_options.get(
            sort_type,
            POST_COMMENTS_SELECTORS.sort_options["most_recent"],
        )
        for target in targets:
            option = self.device(text=target)
            if not option.exists:
                option = self.device(description=target)
            if option.exists:
                option.click()
                time.sleep(1)
                logger.info(f"Sorted by: {target}")
                return True

        self.device.press("back")
        logger.warning(f"Sort option '{sort_type}' not found")
        return False

    def scrape_all_comments(self, max_comments: int = 500) -> list[ScrapedComment]:
        """Scrape all comments from the currently open comments page."""
        logger.info(f"Scraping comments (max {max_comments})...")

        seen_keys = set()
        scroll_attempts = 0
        no_new_count = 0
        max_no_new = 5

        self._comment_list_bounds = None

        while len(self.comments) < max_comments and no_new_count < max_no_new:
            new_found = self._extract_visible_comments_fast(seen_keys, max_comments)

            if new_found == 0:
                no_new_count += 1
            else:
                no_new_count = 0

            send_event(
                "scrape_progress",
                current=len(self.comments),
                total=max_comments,
                scroll=scroll_attempts,
            )

            if len(self.comments) >= max_comments:
                break

            expanded = self._expand_reply_threads()
            if expanded:
                time.sleep(0.8)
                new_from_expand = self._extract_visible_comments_fast(seen_keys, max_comments)
                if new_from_expand > 0:
                    no_new_count = 0
                    send_event(
                        "scrape_progress",
                        current=len(self.comments),
                        total=max_comments,
                        scroll=scroll_attempts,
                    )

            if len(self.comments) >= max_comments:
                break

            scroll_attempts += 1
            self._scroll_comments_down()
            time.sleep(0.3)

        logger.info(f"Scraped {len(self.comments)} comments total")
        send_event("scrape_complete", total=len(self.comments))
        return self.comments

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
                    if re.match(r"^[\w][\w.]{0,29}$", text) and text.lower() not in (
                        POST_COMMENTS_SELECTORS.ignored_username_tokens
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

    def _scroll_comments_down(self):
        """Scroll the comments list down quickly."""
        try:
            if not self._comment_list_bounds:
                comment_list = self.device(resourceId=POST_COMMENTS_SELECTORS.comments_list_resource_id)
                if comment_list.exists:
                    self._comment_list_bounds = comment_list.info.get("bounds", {})
                    logger.debug(f"Cached comment list bounds: {self._comment_list_bounds}")

            if self._comment_list_bounds:
                top = self._comment_list_bounds.get("top", 234)
                bottom = self._comment_list_bounds.get("bottom", 1090)
                center_x = self.screen_width // 2
                start_y = top + int((bottom - top) * 0.75)
                end_y = top + int((bottom - top) * 0.25)
                self.device.swipe(center_x, start_y, center_x, end_y, duration=0.15)
            else:
                center_x = self.screen_width // 2
                start_y = int(self.screen_height * 0.65)
                end_y = int(self.screen_height * 0.25)
                logger.debug(f"Fallback scroll: ({center_x}, {start_y}) → ({center_x}, {end_y})")
                self.device.swipe(center_x, start_y, center_x, end_y, duration=0.15)
        except Exception as e:
            logger.warning(f"Scroll error: {e}")

    def _expand_reply_threads(self) -> bool:
        """Click 'View X more replies' buttons to expand reply threads."""
        expanded = False
        try:
            for pattern in POST_COMMENTS_SELECTORS.expand_replies_text_contains:
                view_replies = self.device(textContains=pattern, clickable=True)
                if not view_replies.exists:
                    continue
                for i in range(view_replies.count):
                    try:
                        elem = view_replies[i]
                        elem_text = (elem.info.get("text", "") or "").lower()
                        elem_desc = (elem.info.get("contentDescription", "") or "").lower()
                        combined = elem_text + " " + elem_desc

                        if any(token in combined for token in POST_COMMENTS_SELECTORS.expand_replies_positive_tokens):
                            if any(token in combined for token in POST_COMMENTS_SELECTORS.expand_replies_hidden_tokens):
                                continue
                            logger.info(f"Expanding thread: {elem.info.get('text', '')}")
                            elem.click()
                            expanded = True
                            time.sleep(0.5)
                    except Exception:
                        continue

            if not expanded:
                for desc_kw in POST_COMMENTS_SELECTORS.expand_replies_description_contains:
                    elems = self.device(descriptionContains=desc_kw, clickable=True)
                    if elems.exists:
                        for i in range(elems.count):
                            try:
                                elem_desc = (elems[i].info.get("contentDescription", "") or "").lower()
                                if any(token in elem_desc for token in POST_COMMENTS_SELECTORS.expand_replies_hidden_tokens):
                                    continue
                                logger.info(f"Expanding thread (desc): {elems[i].info.get('contentDescription', '')}")
                                elems[i].click()
                                expanded = True
                                time.sleep(0.5)
                            except Exception:
                                continue

        except Exception as e:
            logger.debug(f"Expand reply threads error: {e}")

        return expanded
