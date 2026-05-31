"""Post context extraction for the Instagram Smart Comment bridge."""

from __future__ import annotations

import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict

from bridges.common.parsing.counts import parse_count
from bridges.instagram.runtime.ipc import logger, send_message as send_event
from bridges.instagram.engagement.runtime.smart_comment_models import PostContext


class SmartCommentPostContextMixin:
    """Caption, date, stats and post URL extraction for Smart Comment."""

    def _expand_caption(self):
        """Click the 'more' button to expand the full caption text."""
        try:
            caption_view = self.device(className="com.instagram.ui.widget.textview.IgTextLayoutView")
            if not caption_view.exists:
                return

            caption_text = caption_view.get_text() or ""
            if not (caption_text.rstrip().endswith("more") or caption_text.rstrip().endswith("plus")):
                logger.debug("Caption does not appear truncated — no 'more' button to click")
                return

            more_btn = self.device(description="more")
            if not more_btn.exists:
                more_btn = self.device(text="more", className="android.widget.Button")
            if not more_btn.exists:
                more_btn = self.device(description="plus")
            if not more_btn.exists:
                more_btn = self.device(text="plus", className="android.widget.Button")

            if more_btn.exists:
                more_btn.click()
                time.sleep(1)
                logger.info("Clicked 'more' to expand caption")
            else:
                logger.debug("'more' button not found — caption may already be fully visible")
        except Exception as e:
            logger.debug(f"Error expanding caption: {e}")

    def extract_post_context(self) -> PostContext:
        """Extract context from the currently visible post."""
        logger.info("Extracting post context...")

        author_elem = self.device(resourceId="com.instagram.android:id/row_feed_photo_profile_name")
        if author_elem.exists:
            self.post_context.author_username = author_elem.get_text() or ""
            logger.info(f"Post author (from profile name): {self.post_context.author_username}")

        self._expand_caption()

        caption_elem = self.device(className="com.instagram.ui.widget.textview.IgTextLayoutView")
        if caption_elem.exists:
            try:
                full_text = caption_elem.get_text() or ""
                if not self.post_context.author_username and full_text:
                    first_space = full_text.find(" ")
                    if first_space > 0:
                        candidate = full_text[:first_space].strip()
                        if re.match(r"^[\w][\w.]{0,29}$", candidate):
                            self.post_context.author_username = candidate
                            logger.info(f"Post author (from caption prefix): {self.post_context.author_username}")

                if self.post_context.author_username and full_text.startswith(self.post_context.author_username):
                    self.post_context.caption = full_text[len(self.post_context.author_username):].strip()
                else:
                    self.post_context.caption = full_text
                self.post_context.caption = re.sub(r"\s+(more|plus|less|moins)\s*$", "", self.post_context.caption)
                logger.info(f"Caption ({len(self.post_context.caption)} chars): {self.post_context.caption[:150]}...")
            except Exception as e:
                logger.warning(f"Error extracting caption: {e}")

        try:
            xml = self.device.dump_hierarchy()
            if xml:
                root = ET.fromstring(xml)
                for elem in root.iter():
                    text = (elem.get("text", "") or "").strip()
                    content_desc = (elem.get("content-desc", "") or "").strip()
                    cls = elem.get("class", "") or ""
                    if cls == "android.widget.TextView" and text and re.match(
                        r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}$",
                        text,
                    ):
                        self.post_context.post_date = text
                        logger.info(f"Post date: {text}")
                        break
                    if not self.post_context.post_date and content_desc and re.match(
                        r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}$",
                        content_desc,
                    ):
                        self.post_context.post_date = content_desc
                        logger.info(f"Post date (from content-desc): {content_desc}")
                        break
        except Exception as e:
            logger.debug(f"Error extracting post date: {e}")

        if not self.post_context.post_date:
            try:
                header = self.device(resourceId="com.instagram.android:id/row_feed_profile_header")
                if header.exists:
                    desc = header.info.get("contentDescription", "") or ""
                    date_match = re.search(
                        r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})",
                        desc,
                    )
                    if date_match:
                        self.post_context.post_date = date_match.group(1)
                        logger.info(f"Post date (from header): {self.post_context.post_date}")
            except Exception as e:
                logger.debug(f"Error extracting date from header: {e}")

        if not self.post_context.author_username:
            try:
                for rid in ["com.instagram.android:id/carousel_image", "com.instagram.android:id/row_feed_photo_imageview"]:
                    elem = self.device(resourceId=rid)
                    if elem.exists:
                        desc = elem.info.get("contentDescription", "") or ""
                        by_match = re.search(r"by\s+([\w][\w.]{0,29})", desc)
                        if by_match:
                            self.post_context.author_username = by_match.group(1)
                            logger.info(f"Post author (from content-desc): {self.post_context.author_username}")
                            break
            except Exception as e:
                logger.debug(f"Fallback author extraction: {e}")

        if not self.post_context.author_username:
            logger.warning("Could not detect post author username — author detection will be unreliable")

        self._extract_post_stats()

        self.post_context.target_bio = self.config.get("targetBio", "")

        send_event("post_context", context=asdict(self.post_context))
        return self.post_context

    def _extract_post_stats(self):
        """Extract likes/comments count from post."""
        try:
            carousel = self.device(resourceId="com.instagram.android:id/carousel_image")
            if carousel.exists:
                desc = carousel.info.get("contentDescription", "")
                likes_match = re.search(r"([\d,]+)\s*likes?", desc)
                comments_match = re.search(r"([\d,]+)\s*comments?", desc)
                if likes_match:
                    self.post_context.likes_count = int(likes_match.group(1).replace(",", ""))
                if comments_match:
                    self.post_context.comments_count = int(comments_match.group(1).replace(",", ""))
                logger.info(f"Stats from carousel: {self.post_context.likes_count} likes, {self.post_context.comments_count} comments")
                return

            photo = self.device(resourceId="com.instagram.android:id/row_feed_photo_imageview")
            if photo.exists:
                desc = photo.info.get("contentDescription", "")
                likes_match = re.search(r"([\d,]+)\s*likes?", desc)
                comments_match = re.search(r"([\d,]+)\s*comments?", desc)
                if likes_match:
                    self.post_context.likes_count = int(likes_match.group(1).replace(",", ""))
                if comments_match:
                    self.post_context.comments_count = int(comments_match.group(1).replace(",", ""))

            buttons = self.device(className="android.widget.Button")
            for i in range(buttons.count):
                try:
                    btn = buttons[i]
                    text = btn.get_text() or ""
                    if text and re.match(r"^[\d,.]+[KMkm]?$", text):
                        count = parse_count(text)
                        info = btn.info
                        bounds = info.get("bounds", {})
                        left = bounds.get("left", 0)
                        if left < 250 and self.post_context.likes_count == 0:
                            self.post_context.likes_count = count
                        elif left < 500 and self.post_context.comments_count == 0:
                            self.post_context.comments_count = count
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Error extracting post stats: {e}")

    def extract_post_url(self) -> str:
        """Extract the current post's URL via Share → Copy Link."""
        logger.info("Extracting post URL via Share → Copy Link...")
        try:
            share_btn = self.device(resourceId="com.instagram.android:id/row_feed_button_share")
            if not share_btn.exists:
                share_btn = self.device(resourceId="com.instagram.android:id/row_feed_button_send")
            if not share_btn.exists:
                logger.warning("Share button not found")
                return ""

            share_btn.click()
            time.sleep(1.5)

            copy_link = None
            for label in ["Copy link", "Copier le lien", "Copy Link"]:
                elem = self.device(text=label)
                if elem.exists:
                    copy_link = elem
                    break

            if not copy_link:
                for label in ["Copy link", "Copier le lien"]:
                    elem = self.device(description=label)
                    if elem.exists:
                        copy_link = elem
                        break

            if not copy_link:
                logger.warning("Copy link button not found in share sheet")
                self.device.press("back")
                time.sleep(0.5)
                return ""

            copy_link.click()
            time.sleep(1)

            for command, label in [
                (["adb", "-s", self.device_id, "shell", "am", "broadcast", "-a", "clipper.get"], "clipboard broadcast"),
                (["adb", "-s", self.device_id, "shell", "dumpsys", "clipboard"], "dumpsys clipboard"),
                (["adb", "-s", self.device_id, "shell", "content", "query", "--uri", "content://clipboard/clip"], "content provider"),
            ]:
                try:
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        encoding="utf-8",
                        errors="replace",
                    )
                    output = result.stdout.strip() if label == "clipboard broadcast" else result.stdout
                    url_match = re.search(r"(https?://(?:www\.)?instagram\.com/(?:p|reel)/[\w-]+/?)", output)
                    if url_match:
                        post_url = url_match.group(1)
                        logger.info(f"Post URL from {label}: {post_url}")
                        self.post_context.post_url = post_url
                        return post_url
                except Exception as e:
                    logger.debug(f"{label.capitalize()} failed: {e}")

            logger.warning("Could not read clipboard — post URL not captured")
            return ""

        except Exception as e:
            logger.error(f"Error extracting post URL: {e}")
            try:
                self.device.press("back")
                time.sleep(0.5)
            except Exception:
                pass
            return ""
