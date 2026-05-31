"""Reply helpers for the Instagram Smart Comment bridge."""

from __future__ import annotations

import random
import re
import time
import xml.etree.ElementTree as ET
from typing import Any

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.base import logger, send_message as send_event


class SmartCommentReplyMixin:
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
        logger.info(f"Replying to @{username}: {reply_text[:50]}...")

        if not self._find_and_click_reply(username, comment_content_prefix):
            logger.error(f"Could not find Reply button for @{username}")
            return False

        time.sleep(random.uniform(0.5, 1.0))

        input_field = self.device(resourceId="com.instagram.android:id/layout_comment_thread_edittext")
        if not input_field.exists:
            logger.error("Comment input field not found after clicking Reply")
            return False

        input_field.click()
        time.sleep(0.5)

        current_text = input_field.get_text() or ""
        logger.debug(f"Input field text after Reply click: '{current_text}'")

        time.sleep(random.uniform(0.3, 0.6))

        typed = False

        if self._type_with_taktik_keyboard(reply_text):
            time.sleep(0.5)
            after_text = input_field.get_text() or ""
            if len(after_text) > len(current_text):
                logger.info(f"Taktik Keyboard success: '{after_text[:40]}...'")
                typed = True
            else:
                logger.warning(f"Taktik Keyboard broadcast OK but text not inserted (field: '{after_text[:40]}')")
        else:
            logger.warning("Taktik Keyboard broadcast failed")

        if not typed:
            logger.info("Trying set_text fallback...")
            try:
                input_field.set_text(current_text + reply_text)
                time.sleep(0.5)
                after_text = input_field.get_text() or ""
                if len(after_text) > len(current_text):
                    logger.info(f"set_text success: '{after_text[:40]}...'")
                    typed = True
                else:
                    logger.warning("set_text did not insert text")
            except Exception as e:
                logger.warning(f"set_text failed: {e}")

        if not typed:
            logger.info("Trying send_keys fallback...")
            try:
                input_field.click()
                time.sleep(0.3)
                input_field.send_keys(reply_text)
                time.sleep(0.5)
                after_text = input_field.get_text() or ""
                if len(after_text) > len(current_text):
                    logger.info(f"send_keys success: '{after_text[:40]}...'")
                    typed = True
                else:
                    logger.warning("send_keys did not insert text")
            except Exception as e:
                logger.warning(f"send_keys failed: {e}")

        if not typed:
            logger.error("All typing methods failed — could not insert reply text")
            return False

        time.sleep(random.uniform(0.5, 1.0))

        send_btn = self.device(resourceId="com.instagram.android:id/layout_comment_thread_post_button_icon")
        if not send_btn.exists:
            send_btn = self.device(resourceId="com.instagram.android:id/layout_comment_thread_post_button_click_area")
        if not send_btn.exists:
            send_btn = self.device(description="Post")
        if not send_btn.exists:
            send_btn = self.device(description="Publier")
        if not send_btn.exists:
            send_btn = self.device(resourceId="com.instagram.android:id/layout_comment_thread_post_button_container")

        if send_btn.exists:
            send_btn.click()
            time.sleep(1.5)
            logger.info(f"Reply sent to @{username}")
            send_event("reply_sent", username=username, reply=reply_text, content=comment_content_prefix)
            return True

        logger.error("Send/Post button not found — dumping UI for debug")
        try:
            xml = self.device.dump_hierarchy()
            root = ET.fromstring(xml)
            for elem in root.iter():
                rid = elem.get("resource-id", "") or ""
                desc = elem.get("content-desc", "") or ""
                text = elem.get("text", "") or ""
                if "post_button" in rid or "post" in desc.lower() or "publier" in desc.lower() or "send" in desc.lower():
                    logger.debug(f"Potential send button: rid={rid} desc={desc} text={text} bounds={elem.get('bounds', '')}")
        except Exception as e:
            logger.debug(f"UI dump failed: {e}")
        return False

    def _find_and_click_reply(self, username: str, content_prefix: str) -> bool:
        """Scroll through comments to find a specific one and click its Reply button."""
        max_scrolls = 30
        username_lower = username.lower()
        logger.info(f"Searching for @{username} in comments (max {max_scrolls} scrolls)...")

        for scroll in range(max_scrolls):
            try:
                xml = self.device.dump_hierarchy()
                if not xml:
                    logger.warning(f"Scroll {scroll}: empty XML dump")
                    self._scroll_comments_down()
                    time.sleep(0.8)
                    continue

                root = ET.fromstring(xml)

                recycler = root
                for elem in root.iter():
                    rid = elem.get("resource-id", "") or ""
                    if "sticky_header_list" in rid:
                        recycler = elem
                        break

                reply_bounds = None
                found_username = False

                for vg in recycler.iter():
                    if vg.get("class", "") != "android.view.ViewGroup":
                        continue

                    has_target_user = False
                    reply_btn = None

                    for child in vg:
                        child_class = child.get("class", "") or ""
                        child_text = (child.get("text", "") or "").strip().lower()
                        child_desc = (child.get("content-desc", "") or "").strip().lower()

                        if (
                            child_text == username_lower
                            or child_desc == username_lower
                            or child_text == username_lower + " "
                            or child_desc == username_lower + " "
                        ):
                            has_target_user = True

                        if child_class == "android.widget.Button" and child_text in ("reply", "répondre"):
                            reply_btn = child

                    if has_target_user and reply_btn is not None:
                        reply_bounds = reply_btn.get("bounds", "")
                        found_username = True
                        break
                    elif has_target_user:
                        found_username = True
                        children_info = []
                        for c in vg:
                            ct = (c.get("text", "") or "").strip()
                            cc = (c.get("class", "") or "").split(".")[-1]
                            cb = c.get("bounds", "")
                            children_info.append(f"{cc}('{ct}' {cb})")
                        logger.debug(f"Scroll {scroll}: found @{username} but no Reply sibling. Children: {children_info}")

                if reply_bounds:
                    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", reply_bounds)
                    if match:
                        x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                        logger.info(f"Clicking Reply for @{username} at ({cx}, {cy}) bounds={reply_bounds}")
                        self.device.click(cx, cy)
                        time.sleep(1)
                        return True
                    logger.warning(f"Could not parse Reply bounds: {reply_bounds}")

                if found_username:
                    logger.debug(f"Scroll {scroll}: @{username} visible but Reply button not found yet, scrolling...")
                else:
                    visible = []
                    for elem in recycler.iter():
                        cd = (elem.get("content-desc", "") or "").strip()
                        if cd and re.match(r"^[\w][\w.]{0,29}\s*$", cd) and cd.strip().lower() not in ("like", "reply", "répondre"):
                            visible.append(cd.strip())
                    logger.debug(f"Scroll {scroll}: visible usernames = {visible}")

            except Exception as e:
                logger.warning(f"Error finding reply button (scroll {scroll}): {e}")

            self._scroll_comments_down()
            time.sleep(0.8)

        logger.error(f"Could not find @{username} after {max_scrolls} scrolls")
        return False

    def _scroll_comments_to_top(self):
        """Scroll the comments list to the top with fast flick gestures."""
        try:
            comment_list = self.device(resourceId="com.instagram.android:id/sticky_header_list")
            if not comment_list.exists:
                return
            bounds = comment_list.info.get("bounds", {})
            top = bounds.get("top", 234)
            bottom = bounds.get("bottom", 738)
            center_x = self.screen_width // 2
            start_y = top + int((bottom - top) * 0.2)
            end_y = top + int((bottom - top) * 0.9)
        except Exception:
            center_x = self.screen_width // 2
            start_y = 200
            end_y = 600

        for _ in range(15):
            try:
                self.device.swipe(center_x, start_y, center_x, end_y, duration=0.1)
                time.sleep(0.15)
            except Exception:
                break

    def _type_with_taktik_keyboard(self, text: str) -> bool:
        """Type text using Taktik Keyboard via shared KeyboardService."""
        return self._keyboard.type_text(text)

    def _dismiss_keyboard_and_scroll_top(self):
        """After sending a reply, dismiss the keyboard and scroll comments back to top."""
        try:
            title = self.device(resourceId="com.instagram.android:id/title_text_view")
            if title.exists:
                title.click()
                time.sleep(0.5)
            else:
                self.device.press("back")
                time.sleep(0.5)

                title = self.device(resourceId="com.instagram.android:id/title_text_view")
                if not title.exists:
                    logger.warning("Comments page lost after back press, reopening...")
                    if not self.open_comments():
                        return False
                    time.sleep(1)

            self._comment_list_bounds = None

            logger.debug("Scrolling comments back to top...")
            self._scroll_comments_to_top()
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(f"Error dismissing keyboard / scrolling to top: {e}")
            return True

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
                logger.info(f"[DRY RUN] Would reply to @{username}: {reply}")
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
