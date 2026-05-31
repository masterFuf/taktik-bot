#!/usr/bin/env python3
"""
Smart Comment Bridge for TAKTIK Desktop
AI-powered comment reply marketing system.

Workflow:
1. Open a target post (competitor)
2. Screenshot the post → fal.ai Vision → understand visual context
3. Extract caption + post metadata
4. Open comments → scrape ALL comments (scroll through entire list)
5. AI Qualifier: filter comments that are relevant prospects
6. AI Reply Generator: generate contextual replies for each qualified comment
7. Reply to comments one by one with human-like delays

Usage:
    python smart_comment_bridge.py <config_file.json>

Config JSON:
{
    "deviceId": "HBEDU19325000489",
    "falApiKey": "...",
    "postUrl": "https://www.instagram.com/p/...",  // optional, if not already on post
    "targetBio": "...",  // bio of the target account (optional, scraped if missing)
    "mode": "scrape" | "qualify" | "reply_all",
    "maxComments": 500,
    "qualificationPrompt": "...",  // custom prompt for qualifying prospects
    "replyPrompt": "...",  // custom prompt/strategy for generating replies
    "replyTone": "casual" | "professional" | "friendly",
    "replyLanguage": "fr",
    "delayBetweenReplies": [30, 90],  // min/max seconds between replies
    "dryRun": false  // if true, generate replies but don't post them
}
"""

import sys
import os
import time
import random
import re
import subprocess
from dataclasses import asdict
from typing import List, Dict, Any
import xml.etree.ElementTree as ET

# Bootstrap: UTF-8 + loguru + sys.path in one call. This implementation is
# one level below the public entrypoint, so resolve back to bot/ explicitly.
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.input.keyboard import KeyboardService
from bridges.common.parsing.counts import parse_count
from bridges.instagram.base import logger, InstagramBridgeBase, send_message as send_event
from bridges.instagram.engagement.runtime.smart_comment_comments import SmartCommentCommentsMixin
from bridges.instagram.engagement.runtime.smart_comment_media import SmartCommentMediaMixin
from bridges.instagram.engagement.runtime.smart_comment_models import (
    PostContext,
    ScrapedComment,
)
from bridges.instagram.engagement.runtime.smart_comment_target import SmartCommentTargetMixin


class SmartCommentBridge(
    SmartCommentMediaMixin,
    SmartCommentTargetMixin,
    SmartCommentCommentsMixin,
    InstagramBridgeBase,
):
    """Bridge for AI-powered comment reply marketing."""

    def __init__(self, device_id: str, config: Dict[str, Any], package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self.config = config
        self._keyboard = KeyboardService(device_id)

        # Results
        self.post_context = PostContext()
        self.comments: List[ScrapedComment] = []
        self.qualified_comments: List[ScrapedComment] = []

        # UI state cache
        self._comment_list_bounds = None

    # =========================================================================
    # PHASE 0: TARGET NAVIGATION (uses existing framework classes)
    # =========================================================================

    def restart_instagram(self):
        """Restart Instagram for clean state via AppService."""
        super().restart_instagram()
        logger.info("Instagram restarted successfully")

    # =========================================================================
    # PHASE 1: POST CONTEXT EXTRACTION
    # =========================================================================

    def _expand_caption(self):
        """Click the 'more' button to expand the full caption text.

        Instagram truncates captions and shows a 'more' button. We need to
        click it to get the full text including hashtags.
        """
        try:
            # The "more" button is a child Button inside the IgTextLayoutView
            # with content-desc="more" or text containing "more"/"plus"
            caption_view = self.device(className="com.instagram.ui.widget.textview.IgTextLayoutView")
            if not caption_view.exists:
                return

            # Check if caption text ends with "more" or "plus" (truncated)
            caption_text = caption_view.get_text() or ""
            if not (caption_text.rstrip().endswith('more') or caption_text.rstrip().endswith('plus')):
                logger.debug("Caption does not appear truncated — no 'more' button to click")
                return

            # Find the "more" button by content-desc
            more_btn = self.device(description="more")
            if not more_btn.exists:
                # Try text-based
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

        # Author username — try multiple methods
        author_elem = self.device(resourceId="com.instagram.android:id/row_feed_photo_profile_name")
        if author_elem.exists:
            self.post_context.author_username = author_elem.get_text() or ""
            logger.info(f"Post author (from profile name): {self.post_context.author_username}")

        # Click "more" to expand the full caption BEFORE extracting it
        self._expand_caption()

        # Caption - from IgTextLayoutView (now fully expanded)
        caption_elem = self.device(className="com.instagram.ui.widget.textview.IgTextLayoutView")
        if caption_elem.exists:
            try:
                full_text = caption_elem.get_text() or ""
                # Caption format: "username caption text... [less]"
                # If we don't have the author yet, try to extract from caption prefix
                if not self.post_context.author_username and full_text:
                    # The first word before a space is typically the username
                    first_space = full_text.find(' ')
                    if first_space > 0:
                        candidate = full_text[:first_space].strip()
                        if re.match(r'^[\w][\w.]{0,29}$', candidate):
                            self.post_context.author_username = candidate
                            logger.info(f"Post author (from caption prefix): {self.post_context.author_username}")

                # Remove the username prefix
                if self.post_context.author_username and full_text.startswith(self.post_context.author_username):
                    self.post_context.caption = full_text[len(self.post_context.author_username):].strip()
                else:
                    self.post_context.caption = full_text
                # Remove trailing "more"/"plus"/"less"/"moins"
                self.post_context.caption = re.sub(r'\s+(more|plus|less|moins)\s*$', '', self.post_context.caption)
                logger.info(f"Caption ({len(self.post_context.caption)} chars): {self.post_context.caption[:150]}...")
            except Exception as e:
                logger.warning(f"Error extracting caption: {e}")

        # Post date — from the date TextView (e.g. "June 23, 2025")
        try:
            # The date is a standalone TextView with content-desc matching the date format
            # It appears after the caption in the post layout
            xml = self.device.dump_hierarchy()
            if xml:
                root = ET.fromstring(xml)
                for elem in root.iter():
                    text = (elem.get('text', '') or '').strip()
                    content_desc = (elem.get('content-desc', '') or '').strip()
                    cls = elem.get('class', '') or ''
                    # Date format: "June 23, 2025" or "January 1, 2026" etc.
                    if cls == 'android.widget.TextView' and text and re.match(
                        r'^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}$', text
                    ):
                        self.post_context.post_date = text
                        logger.info(f"Post date: {text}")
                        break
                    # Also check content-desc for the same pattern
                    if not self.post_context.post_date and content_desc and re.match(
                        r'^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}$', content_desc
                    ):
                        self.post_context.post_date = content_desc
                        logger.info(f"Post date (from content-desc): {content_desc}")
                        break
        except Exception as e:
            logger.debug(f"Error extracting post date: {e}")

        # Also try to extract date from row_feed_profile_header content-desc
        # Format: "myboost_off posted a carousel June 23, 2025"
        if not self.post_context.post_date:
            try:
                header = self.device(resourceId="com.instagram.android:id/row_feed_profile_header")
                if header.exists:
                    desc = header.info.get('contentDescription', '') or ''
                    date_match = re.search(
                        r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})', desc
                    )
                    if date_match:
                        self.post_context.post_date = date_match.group(1)
                        logger.info(f"Post date (from header): {self.post_context.post_date}")
            except Exception as e:
                logger.debug(f"Error extracting date from header: {e}")

        # Fallback: try to extract author from carousel/photo content-desc
        if not self.post_context.author_username:
            try:
                for rid in ["com.instagram.android:id/carousel_image", "com.instagram.android:id/row_feed_photo_imageview"]:
                    elem = self.device(resourceId=rid)
                    if elem.exists:
                        desc = elem.info.get('contentDescription', '') or ''
                        # "Photo 1 of 5 by username, 76 likes, 6 comments"
                        by_match = re.search(r'by\s+([\w][\w.]{0,29})', desc)
                        if by_match:
                            self.post_context.author_username = by_match.group(1)
                            logger.info(f"Post author (from content-desc): {self.post_context.author_username}")
                            break
            except Exception as e:
                logger.debug(f"Fallback author extraction: {e}")

        if not self.post_context.author_username:
            logger.warning("Could not detect post author username — author detection will be unreliable")

        # Stats from carousel content-desc or buttons
        # carousel_image content-desc: "Photo 1 of 5 by MyBoost.., 18,585 likes, 424 comments"
        self._extract_post_stats()

        # Target bio (if provided in config)
        self.post_context.target_bio = self.config.get('targetBio', '')

        send_event("post_context", context=asdict(self.post_context))
        return self.post_context

    def _extract_post_stats(self):
        """Extract likes/comments count from post."""
        try:
            # Try carousel content-desc first
            carousel = self.device(resourceId="com.instagram.android:id/carousel_image")
            if carousel.exists:
                desc = carousel.info.get('contentDescription', '')
                # "Photo 1 of 5 by MyBoost.., 18,585 likes, 424 comments"
                likes_match = re.search(r'([\d,]+)\s*likes?', desc)
                comments_match = re.search(r'([\d,]+)\s*comments?', desc)
                if likes_match:
                    self.post_context.likes_count = int(likes_match.group(1).replace(',', ''))
                if comments_match:
                    self.post_context.comments_count = int(comments_match.group(1).replace(',', ''))
                logger.info(f"Stats from carousel: {self.post_context.likes_count} likes, {self.post_context.comments_count} comments")
                return

            # Try from row_feed_photo_imageview content-desc
            photo = self.device(resourceId="com.instagram.android:id/row_feed_photo_imageview")
            if photo.exists:
                desc = photo.info.get('contentDescription', '')
                likes_match = re.search(r'([\d,]+)\s*likes?', desc)
                comments_match = re.search(r'([\d,]+)\s*comments?', desc)
                if likes_match:
                    self.post_context.likes_count = int(likes_match.group(1).replace(',', ''))
                if comments_match:
                    self.post_context.comments_count = int(comments_match.group(1).replace(',', ''))

            # Try from buttons (like count next to like button)
            buttons = self.device(className="android.widget.Button")
            for i in range(buttons.count):
                try:
                    btn = buttons[i]
                    text = btn.get_text() or ""
                    # Parse "18.5K", "424", etc.
                    if text and re.match(r'^[\d,.]+[KMkm]?$', text):
                        count = parse_count(text)
                        # Check what's before this button
                        info = btn.info
                        bounds = info.get('bounds', {})
                        left = bounds.get('left', 0)
                        # Like count is typically first, comment count second
                        if left < 250 and self.post_context.likes_count == 0:
                            self.post_context.likes_count = count
                        elif left < 500 and self.post_context.comments_count == 0:
                            self.post_context.comments_count = count
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Error extracting post stats: {e}")

    def extract_post_url(self) -> str:
        """Extract the current post's URL via Share → Copy Link.

        This is critical for the reply phase: we need to navigate back to the
        exact same post, not just the first post on a profile.

        Returns the post URL (e.g. https://www.instagram.com/p/ABC123/) or empty string.
        """
        logger.info("Extracting post URL via Share → Copy Link...")
        try:
            # Click the Share/Send button
            share_btn = self.device(resourceId="com.instagram.android:id/row_feed_button_share")
            if not share_btn.exists:
                # Fallback: try the send button (reels)
                share_btn = self.device(resourceId="com.instagram.android:id/row_feed_button_send")
            if not share_btn.exists:
                logger.warning("Share button not found")
                return ""

            share_btn.click()
            time.sleep(1.5)

            # Look for "Copy link" / "Copier le lien" button in the share sheet
            copy_link = None
            for label in ["Copy link", "Copier le lien", "Copy Link"]:
                elem = self.device(text=label)
                if elem.exists:
                    copy_link = elem
                    break

            if not copy_link:
                # Try by content-desc
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

            # Read clipboard via adb
            try:
                result = subprocess.run(
                    ['adb', '-s', self.device_id, 'shell', 'am', 'broadcast',
                     '-a', 'clipper.get'],
                    capture_output=True, text=True, timeout=5, encoding='utf-8', errors='replace'
                )
                clipboard = result.stdout.strip()
                # Extract URL from broadcast result
                url_match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel)/[\w-]+/?)', clipboard)
                if url_match:
                    post_url = url_match.group(1)
                    logger.info(f"Post URL from clipboard broadcast: {post_url}")
                    self.post_context.post_url = post_url
                    return post_url
            except Exception as e:
                logger.debug(f"Clipboard broadcast failed: {e}")

            # Fallback: try dumpsys clipboard
            try:
                result = subprocess.run(
                    ['adb', '-s', self.device_id, 'shell', 'dumpsys', 'clipboard'],
                    capture_output=True, text=True, timeout=5, encoding='utf-8', errors='replace'
                )
                url_match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel)/[\w-]+/?)', result.stdout)
                if url_match:
                    post_url = url_match.group(1)
                    logger.info(f"Post URL from dumpsys clipboard: {post_url}")
                    self.post_context.post_url = post_url
                    return post_url
            except Exception as e:
                logger.debug(f"Dumpsys clipboard failed: {e}")

            # Fallback: try service call clipboard
            try:
                result = subprocess.run(
                    ['adb', '-s', self.device_id, 'shell',
                     'content', 'query', '--uri', 'content://clipboard/clip'],
                    capture_output=True, text=True, timeout=5, encoding='utf-8', errors='replace'
                )
                url_match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel)/[\w-]+/?)', result.stdout)
                if url_match:
                    post_url = url_match.group(1)
                    logger.info(f"Post URL from content provider: {post_url}")
                    self.post_context.post_url = post_url
                    return post_url
            except Exception as e:
                logger.debug(f"Content provider clipboard failed: {e}")

            # Last resort: Instagram usually shows a toast "Link copied" —
            # the URL format is predictable if we have the shortcode
            logger.warning("Could not read clipboard — post URL not captured")
            return ""

        except Exception as e:
            logger.error(f"Error extracting post URL: {e}")
            # Make sure we dismiss any share sheet
            try:
                self.device.press("back")
                time.sleep(0.5)
            except Exception:
                pass
            return ""

    # =========================================================================
    # PHASE 2: COMMENT SCRAPING
    # =========================================================================

    # =========================================================================
    # PHASE 3: AI QUALIFICATION & REPLY GENERATION
    # (Called from Electron side via fal.ai - bridge just sends data)
    # =========================================================================

    def get_scrape_results(self) -> Dict[str, Any]:
        """Return all scraped data for AI processing on the Electron/Node side."""
        return {
            "post_context": asdict(self.post_context),
            "comments": [asdict(c) for c in self.comments],
            "total_comments": len(self.comments),
            "unique_users": len(set(c.username for c in self.comments)),
            "author_comments": len([c for c in self.comments if c.is_author]),
            "reply_comments": len([c for c in self.comments if c.is_reply]),
        }

    # =========================================================================
    # PHASE 4: REPLY TO COMMENT
    # =========================================================================

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

        # Step 1: Find the comment by scrolling through the list
        if not self._find_and_click_reply(username, comment_content_prefix):
            logger.error(f"Could not find Reply button for @{username}")
            return False

        time.sleep(random.uniform(0.5, 1.0))

        # Step 2: The input field should now be focused with "@username " pre-filled
        # Verify the input field is active
        input_field = self.device(resourceId="com.instagram.android:id/layout_comment_thread_edittext")
        if not input_field.exists:
            logger.error("Comment input field not found after clicking Reply")
            return False

        # Click the input field explicitly to ensure keyboard focus
        input_field.click()
        time.sleep(0.5)

        # Check if @username is pre-filled
        current_text = input_field.get_text() or ""
        logger.debug(f"Input field text after Reply click: '{current_text}'")

        time.sleep(random.uniform(0.3, 0.6))

        # Step 3: Type the reply — try multiple methods
        typed = False

        # Method 1: Taktik Keyboard (ADB broadcast)
        if self._type_with_taktik_keyboard(reply_text):
            # Verify text was actually inserted
            time.sleep(0.5)
            after_text = input_field.get_text() or ""
            if len(after_text) > len(current_text):
                logger.info(f"Taktik Keyboard success: '{after_text[:40]}...'")
                typed = True
            else:
                logger.warning(f"Taktik Keyboard broadcast OK but text not inserted (field: '{after_text[:40]}')")
        else:
            logger.warning("Taktik Keyboard broadcast failed")

        # Method 2: set_text fallback
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

        # Method 3: send_keys fallback
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

        # Step 4: Find and click the post/send button
        # The post button appears after typing (arrow icon)
        send_btn = self.device(resourceId="com.instagram.android:id/layout_comment_thread_post_button_icon")
        if not send_btn.exists:
            send_btn = self.device(resourceId="com.instagram.android:id/layout_comment_thread_post_button_click_area")
        if not send_btn.exists:
            send_btn = self.device(description="Post")
        if not send_btn.exists:
            send_btn = self.device(description="Publier")
        if not send_btn.exists:
            # Last resort: look for any clickable ImageView near the input field (send arrow)
            send_btn = self.device(resourceId="com.instagram.android:id/layout_comment_thread_post_button_container")

        if send_btn.exists:
            send_btn.click()
            time.sleep(1.5)
            logger.info(f"Reply sent to @{username}")
            send_event("reply_sent", username=username, reply=reply_text, content=comment_content_prefix)
            return True
        else:
            logger.error("Send/Post button not found — dumping UI for debug")
            try:
                xml = self.device.dump_hierarchy()
                # Log elements near the input area
                root = ET.fromstring(xml)
                for elem in root.iter():
                    rid = elem.get('resource-id', '') or ''
                    desc = elem.get('content-desc', '') or ''
                    text = elem.get('text', '') or ''
                    if 'post_button' in rid or 'post' in desc.lower() or 'publier' in desc.lower() or 'send' in desc.lower():
                        logger.debug(f"Potential send button: rid={rid} desc={desc} text={text} bounds={elem.get('bounds', '')}")
            except Exception as e:
                logger.debug(f"UI dump failed: {e}")
            return False

    def _find_and_click_reply(self, username: str, content_prefix: str) -> bool:
        """Scroll through comments to find a specific one and click its Reply button.

        Strategy: Use XML dump to find comment rows. Each comment row is a ViewGroup
        that contains both a ViewGroup with content-desc="username " AND a Button
        with text="Reply"/"Répondre". We scan all ViewGroups in the RecyclerView,
        find the one matching our target username, then click its Reply button.

        Instagram comment row structure (from XML dump):
          <ViewGroup>  (inner comment row)
            <ViewGroup content-desc="username ">
              <Button text="username" />
            </ViewGroup>
            <Button text="Reply" content-desc="Reply" />  ← click this
            <Button text="See translation" />              ← optional
          </ViewGroup>
        """
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

                # Find the RecyclerView (comments list)
                recycler = root
                for elem in root.iter():
                    rid = elem.get('resource-id', '') or ''
                    if 'sticky_header_list' in rid:
                        recycler = elem
                        break

                # Scan all ViewGroups looking for comment rows that contain our target username
                # A comment row's inner ViewGroup has direct children:
                #   - ViewGroup with content-desc="username " (with trailing space)
                #   - Button with text="Reply"
                reply_bounds = None
                found_username = False

                for vg in recycler.iter():
                    if vg.get('class', '') != 'android.view.ViewGroup':
                        continue

                    # Check direct children of this ViewGroup
                    has_target_user = False
                    reply_btn = None

                    for child in vg:
                        child_class = child.get('class', '') or ''
                        child_text = (child.get('text', '') or '').strip().lower()
                        child_desc = (child.get('content-desc', '') or '').strip().lower()

                        # Check if this child is the username ViewGroup or Button
                        if child_text == username_lower or child_desc == username_lower or \
                           child_text == username_lower + ' ' or child_desc == username_lower + ' ':
                            has_target_user = True

                        # Check if this child is a Reply button
                        if child_class == 'android.widget.Button' and child_text in ('reply', 'répondre'):
                            reply_btn = child

                    if has_target_user and reply_btn is not None:
                        reply_bounds = reply_btn.get('bounds', '')
                        found_username = True
                        break
                    elif has_target_user:
                        found_username = True
                        # Username found but Reply not in same ViewGroup — log for debug
                        children_info = []
                        for c in vg:
                            ct = (c.get('text', '') or '').strip()
                            cc = (c.get('class', '') or '').split('.')[-1]
                            cb = c.get('bounds', '')
                            children_info.append(f"{cc}('{ct}' {cb})")
                        logger.debug(f"Scroll {scroll}: found @{username} but no Reply sibling. Children: {children_info}")

                if reply_bounds:
                    # Parse bounds "[x1,y1][x2,y2]"
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', reply_bounds)
                    if match:
                        x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                        logger.info(f"Clicking Reply for @{username} at ({cx}, {cy}) bounds={reply_bounds}")
                        self.device.click(cx, cy)
                        time.sleep(1)
                        return True
                    else:
                        logger.warning(f"Could not parse Reply bounds: {reply_bounds}")

                if found_username:
                    logger.debug(f"Scroll {scroll}: @{username} visible but Reply button not found yet, scrolling...")
                else:
                    # Log visible usernames for debugging
                    visible = []
                    for elem in recycler.iter():
                        cd = (elem.get('content-desc', '') or '').strip()
                        if cd and re.match(r'^[\w][\w.]{0,29}\s*$', cd) and \
                           cd.strip().lower() not in ('like', 'reply', 'répondre'):
                            visible.append(cd.strip())
                    logger.debug(f"Scroll {scroll}: visible usernames = {visible}")

            except Exception as e:
                logger.warning(f"Error finding reply button (scroll {scroll}): {e}")

            # Scroll down to find more comments
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
            bounds = comment_list.info.get('bounds', {})
            top = bounds.get('top', 234)
            bottom = bounds.get('bottom', 738)
            center_x = self.screen_width // 2
            start_y = top + int((bottom - top) * 0.2)
            end_y = top + int((bottom - top) * 0.9)
        except Exception:
            center_x = self.screen_width // 2
            start_y = 200
            end_y = 600

        for i in range(15):
            try:
                self.device.swipe(center_x, start_y, center_x, end_y, duration=0.1)
                time.sleep(0.15)
            except Exception:
                break

    def _type_with_taktik_keyboard(self, text: str) -> bool:
        """Type text using Taktik Keyboard via shared KeyboardService."""
        return self._keyboard.type_text(text)

    # =========================================================================
    # ORCHESTRATION
    # =========================================================================

    def run_scrape(self) -> Dict[str, Any]:
        """Run the scraping phase: extract post context + scrape all comments.

        If targetUsername is provided in config, navigates to the target profile first,
        scrapes profile info, then opens the first post before scraping comments.
        Otherwise, scrapes from whatever post is currently visible on screen.
        """
        target_username = self.config.get('targetUsername', '').strip().lstrip('@')
        target_profile_data = None

        # ===== PHASE 0: Navigate to target (if provided) =====
        if target_username:
            send_event("scrape_status", status="restarting", message="Restarting Instagram...")
            logger.info(f"Dynamic target mode: navigating to @{target_username}")

            # Step 0a: Restart Instagram for clean state (ensures home page)
            self.restart_instagram()

            # Step 0b: Navigate to target profile (deep link or search)
            send_event("scrape_status", status="navigating", message=f"Navigating to @{target_username}...")
            if not self.navigate_to_target_profile(target_username):
                return {"success": False, "error": f"Could not navigate to @{target_username}'s profile"}

            # Step 0c: Scrape target profile info
            send_event("scrape_status", status="scraping_profile", message=f"Scraping @{target_username} profile...")
            target_profile = self.scrape_target_profile()
            target_profile_data = asdict(target_profile)

            # Send profile info to frontend
            send_event("target_profile", profile=target_profile_data)

            # Check if profile is private
            if target_profile.is_private:
                return {"success": False, "error": f"@{target_username} is a private account"}

            # Step 0d: Open first post
            send_event("scrape_status", status="opening_post", message="Opening first post...")
            if not self.open_first_post():
                return {"success": False, "error": f"Could not open first post on @{target_username}'s profile"}

            logger.info(f"Successfully navigated to @{target_username}'s first post")

        # ===== PHASE 1: Extract post context =====
        self.extract_post_context()

        # Enrich post context with target profile data if available
        if target_profile_data:
            self.post_context.target_bio = target_profile_data.get('bio', '')
            self.post_context.target_profile = target_profile_data
            # If author_username wasn't detected from the post, use the target username
            if not self.post_context.author_username and target_username:
                self.post_context.author_username = target_username

        # ===== PHASE 1b: Extract post URL (disabled for now — buggy Share→Copy Link flow) =====
        # TODO: Re-enable when clipboard reading is reliable
        # send_event("scrape_status", status="extracting_url", message="Extracting post URL...")
        # post_url = self.extract_post_url()
        # if post_url:
        #     logger.info(f"Post URL captured: {post_url}")
        # else:
        #     logger.warning("Could not capture post URL — reply phase will use fallback navigation")

        # ===== PHASE 2: Screenshot =====
        screenshot_path = self.take_post_screenshot()

        # ===== PHASE 3: Open comments =====
        if not self.open_comments():
            return {"success": False, "error": "Could not open comments"}

        # Keep default comment sort ("For you") — no filter change needed

        # Dismiss keyboard if visible
        try:
            title = self.device(resourceId="com.instagram.android:id/title_text_view")
            if title.exists:
                title.click()
                logger.info("Tapped comments title to dismiss keyboard")
                time.sleep(1)
            else:
                self.device.click(self.screen_width // 2, 150)
                time.sleep(1)
        except Exception as e:
            logger.debug(f"Keyboard dismiss attempt: {e}")

        # Wait for comments to fully load
        time.sleep(2)

        # ===== PHASE 4: Scrape comments =====
        max_comments = self.config.get('maxComments', 500)
        self.scrape_all_comments(max_comments)

        # ===== PHASE 5: Return results =====
        results = self.get_scrape_results()
        results["success"] = True
        results["screenshot_path"] = screenshot_path
        return results

    def verify_post_fingerprint(self) -> bool:
        """Verify we're on the correct post by checking date and caption prefix.

        Uses post_date and caption prefix from config (saved during scrape) to
        confirm we navigated to the right post. This is a safety check.
        """
        expected_date = self.config.get('postDate', '').strip()
        expected_caption = self.config.get('captionPrefix', '').strip()

        if not expected_date and not expected_caption:
            logger.debug("No post fingerprint in config — skipping verification")
            return True  # Nothing to verify against

        try:
            # Check date from header content-desc
            actual_date = ""
            header = self.device(resourceId="com.instagram.android:id/row_feed_profile_header")
            if header.exists:
                desc = header.info.get('contentDescription', '') or ''
                date_match = re.search(
                    r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})', desc
                )
                if date_match:
                    actual_date = date_match.group(1)

            # Check caption prefix
            actual_caption = ""
            caption_elem = self.device(className="com.instagram.ui.widget.textview.IgTextLayoutView")
            if caption_elem.exists:
                actual_caption = (caption_elem.get_text() or "").strip()
                # The raw caption from IgTextLayoutView starts with "username caption..."
                # but captionPrefix from config was already cleaned of the username during scrape.
                # Strip the username prefix if present.
                author = self.config.get('targetUsername', '').strip().lstrip('@')
                if author and actual_caption.lower().startswith(author.lower()):
                    actual_caption = actual_caption[len(author):].strip()
                # Also strip trailing "more"/"plus"/"less"/"moins"
                actual_caption = re.sub(r'\s+(more|plus|less|moins)\s*$', '', actual_caption)

            # Verify date match
            if expected_date and actual_date:
                if expected_date.lower() != actual_date.lower():
                    logger.warning(f"Post date mismatch! Expected: '{expected_date}', Got: '{actual_date}'")
                    return False
                logger.info(f"Post date verified: {actual_date}")

            # Verify caption prefix match (first 80 chars)
            if expected_caption and actual_caption:
                # Compare first N chars (caption may be truncated on screen)
                prefix_len = min(len(expected_caption), 80)
                expected_prefix = expected_caption[:prefix_len].lower()
                actual_prefix = actual_caption[:prefix_len].lower()
                if expected_prefix != actual_prefix:
                    logger.warning(f"Caption prefix mismatch! Expected: '{expected_prefix[:60]}...', Got: '{actual_prefix[:60]}...'")
                    return False
                logger.info(f"Caption prefix verified ({prefix_len} chars match)")

            return True

        except Exception as e:
            logger.warning(f"Error verifying post fingerprint: {e}")
            return True  # Don't block on verification errors

    def navigate_to_post_url(self, post_url: str) -> bool:
        """Navigate directly to a specific post via its URL using Android deep link.

        This is much more reliable than profile → first post, because it opens
        the exact post regardless of which post was scraped.
        """
        logger.info(f"Navigating to post via URL: {post_url}")
        try:
            # Use am start to open the URL in Instagram
            from taktik.core.clone import get_active_package
            pkg = get_active_package()
            result = subprocess.run(
                ['adb', '-s', self.device_id, 'shell',
                 'am', 'start', '-a', 'android.intent.action.VIEW',
                 '-d', post_url,
                 '-p', pkg],
                capture_output=True, text=True, timeout=10, encoding='utf-8', errors='replace'
            )
            logger.debug(f"am start result: {result.stdout.strip()}")
            time.sleep(4)  # Wait for Instagram to load the post

            # Verify we landed on a post (check for comment button or like button)
            for indicator in [
                "com.instagram.android:id/row_feed_button_comment",
                "com.instagram.android:id/row_feed_button_like",
                "com.instagram.android:id/like_button",
            ]:
                if self.device(resourceId=indicator).exists:
                    logger.info("Successfully navigated to post via URL")
                    return True

            # Sometimes Instagram shows a loading screen, wait more
            time.sleep(3)
            for indicator in [
                "com.instagram.android:id/row_feed_button_comment",
                "com.instagram.android:id/row_feed_button_like",
                "com.instagram.android:id/like_button",
            ]:
                if self.device(resourceId=indicator).exists:
                    logger.info("Successfully navigated to post via URL (after extra wait)")
                    return True

            logger.warning("Post URL navigation: could not verify landing on post")
            return False

        except Exception as e:
            logger.error(f"Error navigating to post URL: {e}")
            return False

    def _navigate_to_comments(self) -> bool:
        """Navigate to the comments of the target post.

        Strategy (in order of preference):
        1. If we have a post_url → deep link directly to the post
        2. If we have a targetUsername → navigate to profile → open first post (legacy fallback)
        3. Fail if neither is available
        """
        # Reset cached UI bounds (stale after restart)
        self._comment_list_bounds = None

        post_url = self.config.get('postUrl', '') or self.post_context.post_url
        target_username = self.config.get('targetUsername', '').strip().lstrip('@')

        if not post_url and not target_username:
            logger.error("No postUrl or targetUsername available for navigation")
            return False

        logger.info("Restarting Instagram for navigation reset...")
        self.restart_instagram()

        if post_url:
            # ===== PREFERRED: Navigate directly to the exact post =====
            logger.info(f"Using post URL for precise navigation: {post_url}")
            if not self.navigate_to_post_url(post_url):
                logger.warning("Post URL navigation failed, trying profile fallback...")
                if target_username:
                    if not self._navigate_via_profile(target_username):
                        return False
                else:
                    logger.error("Post URL navigation failed and no targetUsername for fallback")
                    return False
        elif target_username:
            # ===== FALLBACK: Navigate via profile → first post =====
            logger.warning(f"No post URL available — falling back to @{target_username}'s first post")
            if not self._navigate_via_profile(target_username):
                return False

        if not self.open_comments():
            logger.error("Could not open comments")
            return False

        # Dismiss keyboard if visible
        try:
            title = self.device(resourceId="com.instagram.android:id/title_text_view")
            if title.exists:
                title.click()
                time.sleep(1)
        except Exception:
            pass

        time.sleep(1)
        return True

    def _navigate_via_profile(self, target_username: str) -> bool:
        """Navigate to profile → open first post → scroll through posts to find the right one.

        After opening the first post, Instagram shows a scrollable feed of all
        the profile's posts. We scroll down through them, checking the fingerprint
        (date + caption prefix) on each one until we find a match.
        """
        expected_date = self.config.get('postDate', '').strip()
        expected_caption = self.config.get('captionPrefix', '').strip()
        has_fingerprint = bool(expected_date or expected_caption)

        logger.info(f"Navigating via profile: @{target_username} (fingerprint: {'yes' if has_fingerprint else 'no'})")

        if not self.navigate_to_target_profile(target_username):
            logger.error(f"Could not navigate to @{target_username}")
            return False

        if not self.open_first_post():
            logger.error("Could not open first post")
            return False

        # If no fingerprint data, just use the first post (old behavior)
        if not has_fingerprint:
            logger.info("No fingerprint data — using first post")
            return True

        # Check if the first post already matches
        if self.verify_post_fingerprint():
            logger.info("First post matches fingerprint!")
            return True

        # Scroll through posts to find the matching one
        max_posts_to_check = 12  # Don't scroll forever — check up to ~12 posts
        for i in range(max_posts_to_check):
            logger.info(f"Post {i+2}/{max_posts_to_check+1}: scrolling to next post...")

            # Scroll down to the next post in the feed
            # Instagram's post feed scrolls vertically when viewing from a profile grid
            self.device.swipe(
                self.screen_width // 2,
                int(self.screen_height * 0.8),
                self.screen_width // 2,
                int(self.screen_height * 0.2),
                duration=0.3
            )
            time.sleep(2)

            # Verify we're still on a post (not scrolled past all posts)
            on_post = False
            for indicator in [
                "com.instagram.android:id/row_feed_button_comment",
                "com.instagram.android:id/row_feed_button_like",
                "com.instagram.android:id/like_button",
            ]:
                if self.device(resourceId=indicator).exists:
                    on_post = True
                    break

            if not on_post:
                logger.warning("Scrolled past all visible posts — target post not found")
                break

            # Check fingerprint on this post
            if self.verify_post_fingerprint():
                logger.info(f"Found matching post after scrolling through {i+2} posts!")
                return True

            logger.debug(f"Post {i+2} does not match fingerprint, continuing...")

        logger.error(f"Could not find matching post after checking {max_posts_to_check+1} posts on @{target_username}'s profile")
        return False

    def _dismiss_keyboard_and_scroll_top(self):
        """After sending a reply, dismiss the keyboard and scroll comments back to top.

        This avoids a full Instagram restart between replies.
        """
        try:
            # Click on the comments title to dismiss keyboard (safer than back press)
            title = self.device(resourceId="com.instagram.android:id/title_text_view")
            if title.exists:
                title.click()
                time.sleep(0.5)
            else:
                # Fallback: press back to dismiss keyboard
                self.device.press("back")
                time.sleep(0.5)

                # Verify we're still on the comments page
                title = self.device(resourceId="com.instagram.android:id/title_text_view")
                if not title.exists:
                    # We went back to the post — reopen comments
                    logger.warning("Comments page lost after back press, reopening...")
                    if not self.open_comments():
                        return False
                    time.sleep(1)

            # Reset cached bounds (scroll position changed)
            self._comment_list_bounds = None

            # Scroll comments back to top
            logger.debug("Scrolling comments back to top...")
            self._scroll_comments_to_top()
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(f"Error dismissing keyboard / scrolling to top: {e}")
            return True  # Non-fatal, continue anyway

    def run_reply(self, qualified_comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run the reply phase: reply to pre-qualified comments with AI-generated replies.

        Args:
            qualified_comments: List of dicts with 'username', 'content', 'reply' keys
        """
        delay_range = self.config.get('delayBetweenReplies', [30, 90])
        dry_run = self.config.get('dryRun', False)
        replies_sent = 0
        replies_failed = 0
        replied_usernames = set()  # Track already-replied usernames in this run

        for i, qc in enumerate(qualified_comments):
            username = qc.get('username', '')
            content = qc.get('content', '')
            reply = qc.get('reply', '')

            if not username or not reply:
                continue

            # Skip if we already replied to this username in this run
            if username.lower() in replied_usernames:
                logger.info(f"[{i+1}/{len(qualified_comments)}] Skipping @{username} — already replied in this session")
                continue

            logger.info(f"[{i+1}/{len(qualified_comments)}] Replying to @{username}...")
            send_event("reply_progress",
                       current=i + 1,
                       total=len(qualified_comments),
                       username=username)

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

            # Between replies: wait, then dismiss keyboard and scroll to top
            if i < len(qualified_comments) - 1:
                delay = random.uniform(delay_range[0], delay_range[1])
                logger.info(f"Waiting {delay:.0f}s before next reply...")
                time.sleep(delay)

                # Dismiss keyboard and scroll comments to top (no Instagram restart!)
                self._dismiss_keyboard_and_scroll_top()

        results = {
            "success": True,
            "replies_sent": replies_sent,
            "replies_failed": replies_failed,
            "total": len(qualified_comments),
            "dry_run": dry_run
        }
        send_event("reply_complete", **results)
        return results


def main():
    from bridges.instagram.engagement.runtime.smart_comment_commands import run_smart_comment_cli

    run_smart_comment_cli(sys.argv[1:])


if __name__ == '__main__':
    main()
