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
import json
import os
import time
import random
import re
import subprocess
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import xml.etree.ElementTree as ET

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.keyboard import KeyboardService
from bridges.instagram.base import logger, InstagramBridgeBase, send_message as send_event


@dataclass
class ScrapedComment:
    """A scraped comment from a post."""
    username: str
    content: str
    likes: int = 0
    is_author: bool = False
    is_reply: bool = False
    parent_username: Optional[str] = None
    position_top: int = 0  # Y position for re-finding the comment
    # AI qualification fields
    is_qualified: bool = False
    qualification_reason: str = ""
    # AI reply fields
    generated_reply: str = ""
    reply_sent: bool = False


@dataclass
class TargetProfile:
    """Scraped profile information of the target account."""
    username: str = ""
    full_name: str = ""
    bio: str = ""
    followers: int = 0
    following: int = 0
    posts_count: int = 0
    account_type: str = ""  # e.g. "Social media agency", "Digital creator", etc.
    is_private: bool = False
    is_verified: bool = False


@dataclass
class PostContext:
    """Context about the target post for AI generation."""
    author_username: str = ""
    caption: str = ""
    image_description: str = ""  # From vision AI
    likes_count: int = 0
    comments_count: int = 0
    post_date: str = ""
    target_bio: str = ""  # Bio of the account that posted
    target_profile: Optional[dict] = None  # Full TargetProfile as dict
    post_url: str = ""  # Instagram post URL (e.g. https://www.instagram.com/p/ABC123/)


class SmartCommentBridge(InstagramBridgeBase):
    """Bridge for AI-powered comment reply marketing."""

    def __init__(self, device_id: str, config: Dict[str, Any]):
        super().__init__(device_id)
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

    def navigate_to_target_profile(self, username: str) -> bool:
        """Navigate to a target user's profile using the framework's NavigationActions.
        
        Uses deep link (90%) or search (10%) — same as all other workflows.
        """
        logger.info(f"Navigating to @{username} profile...")
        try:
            from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
            nav = NavigationActions(self.device_manager)
            return nav.navigate_to_profile(username)
        except Exception as e:
            logger.error(f"Error navigating to profile: {e}")
            return False

    def scrape_target_profile(self) -> TargetProfile:
        """Scrape profile information using the framework's ProfileBusiness.get_complete_profile_info().
        
        This is the same robust method used by Target, Hashtag, and other workflows.
        """
        logger.info("Scraping target profile info via ProfileBusiness...")
        profile = TargetProfile()

        try:
            from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness
            profile_biz = ProfileBusiness(self.device_manager)
            profile_info = profile_biz.get_complete_profile_info(navigate_if_needed=False)

            if profile_info:
                profile.username = profile_info.get('username', '') or ''
                profile.full_name = profile_info.get('full_name', '') or ''
                profile.bio = profile_info.get('biography', '') or ''
                profile.followers = profile_info.get('followers_count', 0) or 0
                profile.following = profile_info.get('following_count', 0) or 0
                profile.posts_count = profile_info.get('posts_count', 0) or 0
                profile.is_private = profile_info.get('is_private', False)
                profile.is_verified = profile_info.get('is_verified', False)
                profile.account_type = profile_info.get('business_category', '') or ''
                if not profile.account_type:
                    profile.account_type = 'Business' if profile_info.get('is_business', False) else ''

                logger.info(f"Profile scraped: @{profile.username} | {profile.full_name} | "
                            f"{profile.followers} followers | {profile.following} following | "
                            f"{profile.posts_count} posts | type: {profile.account_type}")
            else:
                logger.warning("ProfileBusiness returned None, falling back to basic extraction")
                # Minimal fallback: at least get the username from action bar
                title_elem = self.device(resourceId="com.instagram.android:id/action_bar_title")
                if title_elem.exists:
                    profile.username = (title_elem.get_text() or "").strip()

        except Exception as e:
            logger.error(f"Error scraping profile: {e}")

        return profile

    def open_first_post(self) -> bool:
        """Open the first post in the profile grid using the framework's ClickActions.
        
        Uses the proven image_button selector that works across all workflows.
        """
        logger.info("Opening first post via ClickActions...")

        try:
            from taktik.core.social_media.instagram.actions.atomic.click_actions import ClickActions
            click = ClickActions(self.device_manager)

            # Try clicking first post in grid directly
            if click.click_first_post_in_grid():
                time.sleep(2)
                # Verify we landed on a post
                comment_btn = self.device(resourceId="com.instagram.android:id/row_feed_button_comment")
                like_btn = self.device(resourceId="com.instagram.android:id/row_feed_button_like")
                if comment_btn.exists or like_btn.exists:
                    logger.info("Successfully opened first post")
                    return True
                # Also check for reel indicators (post might be a reel)
                for indicator in [
                    "com.instagram.android:id/clips_single_media_component",
                    "com.instagram.android:id/like_button"
                ]:
                    if self.device(resourceId=indicator).exists:
                        logger.info("Successfully opened first post (reel)")
                        return True
                logger.warning("Clicked grid but didn't land on a post, going back to retry")
                self.device.press("back")
                time.sleep(1)

            # Fallback: scroll down slightly to reveal the grid and retry
            logger.info("First attempt failed, scrolling to reveal grid and retrying...")
            self.device.swipe(
                self.screen_width // 2,
                int(self.screen_height * 0.7),
                self.screen_width // 2,
                int(self.screen_height * 0.4),
                duration=0.3
            )
            time.sleep(1)

            if click.click_first_post_in_grid():
                time.sleep(2)
                logger.info("Successfully opened first post after scroll")
                return True

        except Exception as e:
            logger.error(f"Error opening first post: {e}")

        logger.error("Could not find first post to open")
        return False

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
                        count = self._parse_count(text)
                        # Check what's before this button
                        info = btn.info
                        bounds = info.get('bounds', {})
                        left = bounds.get('left', 0)
                        # Like count is typically first, comment count second
                        if left < 250 and self.post_context.likes_count == 0:
                            self.post_context.likes_count = count
                        elif left < 500 and self.post_context.comments_count == 0:
                            self.post_context.comments_count = count
                except:
                    continue

        except Exception as e:
            logger.warning(f"Error extracting post stats: {e}")

    @staticmethod
    def _parse_count(text: str) -> int:
        """Parse count strings like '18.5K', '1.2M', '424'."""
        from bridges.common.utils import parse_count
        return parse_count(text)

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
            except:
                pass
            return ""

    def take_post_screenshot(self) -> Optional[str]:
        """Take a screenshot of the current post for vision AI analysis."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder = os.path.join(os.environ.get('TEMP', '/tmp'), 'taktik_smart_comment')
            os.makedirs(folder, exist_ok=True)
            filepath = os.path.join(folder, f"post_{timestamp}.png")

            screenshot = self.device.screenshot()
            # uiautomator2 screenshot() returns a PIL Image, not bytes
            screenshot.save(filepath, format='PNG')

            logger.info(f"Post screenshot saved: {filepath}")
            send_event("screenshot", path=filepath)
            return filepath
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None

    # =========================================================================
    # PHASE 2: COMMENT SCRAPING
    # =========================================================================

    def open_comments(self) -> bool:
        """Open the comments section of the current post."""
        logger.info("Opening comments...")

        # Method 1: Click comment button
        comment_btn = self.device(resourceId="com.instagram.android:id/row_feed_button_comment")
        if comment_btn.exists:
            # Click the parent ViewGroup which is clickable
            parent = comment_btn.up(className="android.view.ViewGroup", clickable=True)
            if parent and parent.exists:
                parent.click()
            else:
                comment_btn.click()
            time.sleep(2)

            # Verify we're on comments page
            title = self.device(resourceId="com.instagram.android:id/title_text_view")
            if title.exists and title.get_text() == "Comments":
                logger.info("Comments page opened successfully")
                return True

        # Method 2: Click comment count button
        # The comment count is a Button right after the comment icon
        buttons = self.device(className="android.widget.Button")
        for i in range(buttons.count):
            try:
                btn = buttons[i]
                text = btn.get_text() or ""
                if text and text.isdigit() and int(text) > 0:
                    # Check if previous element is the comment button
                    info = btn.info
                    bounds = info.get('bounds', {})
                    left = bounds.get('left', 0)
                    # Comment count is typically around x=348
                    if 300 < left < 500:
                        btn.click()
                        time.sleep(2)
                        title = self.device(resourceId="com.instagram.android:id/title_text_view")
                        if title.exists and title.get_text() == "Comments":
                            logger.info("Comments page opened via count button")
                            return True
            except:
                continue

        logger.error("Could not open comments")
        return False

    def change_comment_sort(self, sort_type: str = "most_recent") -> bool:
        """Change comment sorting. Options: 'for_you', 'most_recent', 'meta_verified'."""
        logger.info(f"Changing comment sort to: {sort_type}")

        sort_btn = self.device(text="For you", className="android.widget.Button")
        if not sort_btn.exists:
            sort_btn = self.device(description="For you")
        if not sort_btn.exists:
            # Try other current sort labels
            for label in ["Most recent", "Les plus récents", "Meta Verified"]:
                sort_btn = self.device(text=label, className="android.widget.Button")
                if sort_btn.exists:
                    break

        if not sort_btn.exists:
            logger.warning("Sort button not found")
            return False

        sort_btn.click()
        time.sleep(1)

        # Select the desired sort
        sort_map = {
            'for_you': ['For you', 'Pour vous'],
            'most_recent': ['Most recent', 'Les plus récents'],
            'meta_verified': ['Meta Verified', 'Meta vérifié']
        }

        targets = sort_map.get(sort_type, sort_map['most_recent'])
        for target in targets:
            option = self.device(text=target)
            if not option.exists:
                option = self.device(description=target)
            if option.exists:
                option.click()
                time.sleep(1)
                logger.info(f"Sorted by: {target}")
                return True

        # Close menu if nothing found
        self.device.press("back")
        logger.warning(f"Sort option '{sort_type}' not found")
        return False

    def scrape_all_comments(self, max_comments: int = 500) -> List[ScrapedComment]:
        """Scrape all comments from the currently open comments page.
        
        Optimized for speed: minimal sleeps, batch UI hierarchy reads,
        real-time event emission per comment found.
        """
        logger.info(f"Scraping comments (max {max_comments})...")

        seen_keys = set()  # Track unique comments by (username, content_prefix)
        scroll_attempts = 0
        no_new_count = 0
        max_no_new = 5  # Stop after 5 consecutive scrolls with no new comments

        # Cache the RecyclerView bounds once
        self._comment_list_bounds = None

        while len(self.comments) < max_comments and no_new_count < max_no_new:
            # Extract comments from current view
            new_found = self._extract_visible_comments_fast(seen_keys, max_comments)

            if new_found == 0:
                no_new_count += 1
            else:
                no_new_count = 0

            # Send progress
            send_event("scrape_progress",
                       current=len(self.comments),
                       total=max_comments,
                       scroll=scroll_attempts)

            if len(self.comments) >= max_comments:
                break

            # Expand "View X more replies" threads (these are ViewGroups, not Buttons!)
            expanded = self._expand_reply_threads()
            if expanded:
                # If we expanded threads, extract again before scrolling
                time.sleep(0.8)
                new_from_expand = self._extract_visible_comments_fast(seen_keys, max_comments)
                if new_from_expand > 0:
                    no_new_count = 0
                    send_event("scrape_progress",
                               current=len(self.comments),
                               total=max_comments,
                               scroll=scroll_attempts)

            if len(self.comments) >= max_comments:
                break

            # Scroll down — fast, like a human flicking through comments
            scroll_attempts += 1
            self._scroll_comments_down()
            time.sleep(0.3)  # Brief pause — human-like reading speed

        logger.info(f"Scraped {len(self.comments)} comments total")
        send_event("scrape_complete", total=len(self.comments))
        return self.comments

    def _get_visible_usernames(self) -> set:
        """Get the set of usernames currently visible in the comments RecyclerView.
        
        uiautomator XML only contains ACTUALLY VISIBLE elements, unlike dumpsys
        which includes cached/recycled Litho views. We use this as a whitelist.
        
        In Instagram's comments view, each comment has this XML structure:
          <ViewGroup>  (comment row)
            <ImageView content-desc="View username's story" or "Go to username's profile" />
            <ViewGroup>
              <ViewGroup content-desc="username ">
                <Button text="username" />   ← this is what we extract
              </ViewGroup>
              <Button text="Reply" />
            </ViewGroup>
          </ViewGroup>
        
        We specifically look for Button elements inside the sticky_header_list
        RecyclerView whose text matches a username pattern.
        """
        visible = set()
        try:
            xml = self.device.dump_hierarchy()
            if not xml:
                return visible
            
            root = ET.fromstring(xml)
            
            # Find the RecyclerView (sticky_header_list)
            recycler = None
            for elem in root.iter():
                rid = elem.get('resource-id', '') or ''
                if 'sticky_header_list' in rid:
                    recycler = elem
                    break
            
            if recycler is None:
                logger.debug("RecyclerView not found in XML, falling back to full scan")
                # Fallback: scan all elements
                recycler = root
            
            # Extract usernames from Button elements inside the RecyclerView
            # Also check content-desc patterns like "View X's story" or "Go to X's profile"
            for elem in recycler.iter():
                tag_class = elem.get('class', '') or ''
                text = (elem.get('text', '') or '').strip()
                content_desc = (elem.get('content-description', '') or '').strip()
                
                # Method 1: Button with username text (most reliable)
                if tag_class == 'android.widget.Button' and text:
                    if re.match(r'^[\w][\w.]{0,29}$', text) and text.lower() not in (
                        'reply', 'like', 'send', 'comments', 'share', 'post',
                        'répondre', 'publier', 'partager', 'envoyer',
                        'for', 'you', 'most', 'recent', 'meta', 'verified'):
                        visible.add(text.lower())
                
                # Method 2: content-desc "View X's story" or "Go to X's profile"
                for pattern in [r"View ([\w][\w.]{0,29})'s story",
                                r"Go to ([\w][\w.]{0,29})'s profile",
                                r"Voir le story de ([\w][\w.]{0,29})",
                                r"Aller au profil de ([\w][\w.]{0,29})"]:
                    m = re.search(pattern, content_desc)
                    if m:
                        visible.add(m.group(1).lower())
            
            logger.debug(f"Visible comment usernames from XML ({len(visible)}): {visible}")
        except Exception as e:
            logger.warning(f"Failed to get visible usernames from XML: {e}")
        
        return visible

    def _get_dumpsys_comments(self) -> str:
        """Get the Litho view hierarchy via adb shell dumpsys activity top.
        
        This is the ONLY reliable way to get Instagram comment text.
        The XML dump (uiautomator) does NOT contain comment text because
        Instagram uses a custom IgTextLayoutView that renders directly
        on the canvas. But dumpsys activity top exposes the internal
        Litho view hierarchy which contains the real text.
        """
        try:
            result = subprocess.run(
                ['adb', '-s', self.device_id, 'shell', 'dumpsys', 'activity', 'top'],
                capture_output=True, text=True, timeout=10, encoding='utf-8', errors='replace'
            )
            return result.stdout or ''
        except Exception as e:
            logger.error(f"dumpsys activity top failed: {e}")
            return ''

    def _extract_visible_comments_fast(self, seen_keys: set, max_comments: int) -> int:
        """Extraire les commentaires visibles via dumpsys activity top.
        
        Instagram utilise Litho (framework UI de Facebook) pour rendre les
        commentaires. Le texte n'apparaît PAS dans le XML dump de uiautomator,
        mais il est exposé dans la view hierarchy interne via dumpsys.
        
        Litho resource-ids clés :
        - row_comment_textview_comment : texte du commentaire
        - row_comment_textview_time_ago : timestamp (1w, 12w, etc.)
        - row_comment_textview_reply_button : bouton Reply
        - row_comment_like_button : bouton Like
        - Username : text="username" props="{"synthetic":true}"
        """
        count_before = len(self.comments)

        try:
            # Get visible usernames from uiautomator XML to filter out
            # ghost/cached comments from dumpsys RecyclerView cache
            visible_usernames = self._get_visible_usernames()

            dumpsys = self._get_dumpsys_comments()
            if not dumpsys:
                logger.warning("Empty dumpsys output")
                return 0

            # Parse comment blocks from the Litho hierarchy
            comments_data = self._parse_litho_comments(dumpsys)
            logger.debug(f"Parsed {len(comments_data)} comments from dumpsys")

            # Filter to only comments whose username is actually visible on screen
            if visible_usernames:
                before_filter = len(comments_data)
                comments_data = [c for c in comments_data if c.get('username', '').lower() in visible_usernames]
                filtered_out = before_filter - len(comments_data)
                if filtered_out > 0:
                    logger.debug(f"Filtered out {filtered_out} ghost/cached comments (not visible on screen)")

            for cdata in comments_data:
                if len(self.comments) >= max_comments:
                    break

                username = cdata.get('username', '')
                comment_text = cdata.get('text', '')
                if not username or not comment_text:
                    continue

                # Déduplication
                key = (username.lower(), comment_text[:50].lower())
                if key in seen_keys:
                    continue

                is_author = False
                if self.post_context.author_username and \
                   username.lower() == self.post_context.author_username.lower():
                    is_author = True

                seen_keys.add(key)
                is_reply = cdata.get('is_reply', False)
                parent_username = cdata.get('parent_username', None)
                comment = ScrapedComment(
                    username=username,
                    content=comment_text,
                    likes=cdata.get('likes', 0),
                    is_author=is_author,
                    is_reply=is_reply,
                    parent_username=parent_username,
                    position_top=cdata.get('position_top', 0)
                )
                self.comments.append(comment)

                reply_info = ''
                if is_reply:
                    reply_info = f' [reply to @{parent_username}]' if parent_username else ' [reply]'

                logger.debug(f"Comment #{len(self.comments)}: @{username} "
                             f"({comment.likes} likes)"
                             f"{reply_info}: "
                             f"{comment_text[:60]}...")

                send_event("comment_scraped",
                           index=len(self.comments),
                           username=username,
                           content=comment_text[:200],
                           likes=comment.likes,
                           is_author=is_author,
                           is_reply=is_reply,
                           parent_username=parent_username or '')

        except Exception as e:
            logger.error(f"Error in comment extraction: {e}")
            import traceback
            logger.error(traceback.format_exc())

        new_count = len(self.comments) - count_before
        return new_count

    def _parse_litho_comments(self, dumpsys_output: str) -> List[Dict[str, Any]]:
        """Parse la sortie de dumpsys activity top pour extraire les commentaires.
        
        La view hierarchy Litho d'Instagram contient ces éléments dans l'ordre :
          username_synthetic → timestamp → comment_text → reply_button → like_count → like_button
        
        On collecte tous ces événements, on les trie par position, puis on
        reconstruit les blocs commentaire séquentiellement.
        
        Détection des réponses :
        - Un commentaire dont le texte commence par @username est une réponse
        - Un commentaire qui apparaît entre un "View N more replies" et le
          prochain commentaire principal est une réponse
        """
        comments = []

        # Patterns pour chaque type d'élément Litho
        patterns = {
            'username': re.compile(
                r'text="([\w][\w.]{0,29})"\s+props="\{"synthetic":true\}"'
            ),
            'comment': re.compile(
                r'row_comment_textview_comment\s+text="([^"]+)"'
            ),
            'likes': re.compile(
                r'row_comment_textview_like_count\s+text="(\d+)"'
            ),
            'like_button': re.compile(
                r'row_comment_like_button'
            ),
            'view_replies': re.compile(
                r'text="(?:View|Voir|Afficher)\s+\d+\s+(?:more\s+)?(?:repl|réponse)'
            ),
        }

        # Collecter tous les événements avec leur position
        events = []
        for name, pattern in patterns.items():
            for m in pattern.finditer(dumpsys_output):
                value = m.group(1) if m.lastindex else ''
                events.append((m.start(), name, value))

        events.sort(key=lambda x: x[0])

        # Compter les éléments utiles pour le log
        n_usernames = sum(1 for _, t, _ in events if t == 'username')
        n_comments = sum(1 for _, t, _ in events if t == 'comment')
        logger.debug(f"Litho parse: {n_usernames} usernames, {n_comments} comment texts")

        if n_comments == 0:
            return comments

        # Reconstruire les blocs commentaire séquentiellement
        # Ordre observé dans le dumpsys Litho :
        #   username → comment_text → like_button → likes_count
        # Le likes_count apparaît APRÈS le like_button, donc on l'associe
        # rétroactivement au dernier commentaire ajouté.
        current_username = None

        for pos, event_type, value in events:
            if event_type == 'username':
                current_username = value

            elif event_type == 'likes':
                # Associer rétroactivement au dernier commentaire
                like_count = int(value) if value else 0
                if comments and like_count > 0:
                    comments[-1]['likes'] = like_count

            elif event_type == 'view_replies':
                pass

            elif event_type == 'comment':
                if not current_username:
                    continue

                comment_text = value.strip()
                if not comment_text:
                    continue

                # Détecter si c'est une réponse
                is_reply = False
                parent_username = None
                if comment_text.startswith('@'):
                    is_reply = True
                    # Extraire le parent username du @mention
                    mention_match = re.match(r'@([\w][\w.]{0,29})', comment_text)
                    if mention_match:
                        parent_username = mention_match.group(1)

                comments.append({
                    'username': current_username,
                    'text': comment_text,
                    'likes': 0,
                    'is_reply': is_reply,
                    'parent_username': parent_username,
                    'position_top': 0,
                })
                # Reset username after pairing — prevents ghost/cached comment texts
                # (from RecyclerView recycled views) from being paired with the wrong user
                current_username = None

            elif event_type == 'like_button':
                pass

        return comments

    def _scroll_comments_down(self):
        """Scroll the comments list down — fast, like a human flicking."""
        try:
            # Use cached bounds if available to avoid extra RPC call
            if not self._comment_list_bounds:
                comment_list = self.device(resourceId="com.instagram.android:id/sticky_header_list")
                if comment_list.exists:
                    self._comment_list_bounds = comment_list.info.get('bounds', {})
                    logger.debug(f"Cached comment list bounds: {self._comment_list_bounds}")

            if self._comment_list_bounds:
                top = self._comment_list_bounds.get('top', 234)
                bottom = self._comment_list_bounds.get('bottom', 1090)
                center_x = self.screen_width // 2
                start_y = top + int((bottom - top) * 0.75)
                end_y = top + int((bottom - top) * 0.25)
                self.device.swipe(center_x, start_y, center_x, end_y, duration=0.15)
            else:
                # Fallback: swipe in the middle area of the comments panel
                # Comments panel typically spans from ~10% to ~85% of screen height
                center_x = self.screen_width // 2
                start_y = int(self.screen_height * 0.65)
                end_y = int(self.screen_height * 0.25)
                logger.debug(f"Fallback scroll: ({center_x}, {start_y}) → ({center_x}, {end_y})")
                self.device.swipe(center_x, start_y, center_x, end_y, duration=0.15)
        except Exception as e:
            logger.warning(f"Scroll error: {e}")

    def _expand_reply_threads(self) -> bool:
        """Click 'View X more replies' buttons to expand reply threads.
        
        IMPORTANT: These are ViewGroup elements (NOT Buttons!) with:
        - text="View 7 more replies"
        - content-desc="View 7 more replies"
        - class="android.view.ViewGroup"
        - clickable="true"
        
        Returns True if any threads were expanded.
        """
        expanded = False
        try:
            # Find all clickable elements with "View" or "Voir" in their text
            for pattern in ["View", "Voir", "Afficher"]:
                view_replies = self.device(textContains=pattern, clickable=True)
                if not view_replies.exists:
                    continue
                for i in range(view_replies.count):
                    try:
                        elem = view_replies[i]
                        elem_text = (elem.info.get('text', '') or '').lower()
                        elem_desc = (elem.info.get('contentDescription', '') or '').lower()
                        combined = elem_text + ' ' + elem_desc

                        if ('repl' in combined or 'réponse' in combined):
                            # Skip "Hide replies" buttons
                            if 'hide' in combined or 'masquer' in combined:
                                continue
                            logger.info(f"Expanding thread: {elem.info.get('text', '')}")
                            elem.click()
                            expanded = True
                            time.sleep(0.5)
                    except:
                        continue

            # Backup: find by descriptionContains
            if not expanded:
                for desc_kw in ["more repl", "more reply", "réponse"]:
                    elems = self.device(descriptionContains=desc_kw, clickable=True)
                    if elems.exists:
                        for i in range(elems.count):
                            try:
                                elem_desc = (elems[i].info.get('contentDescription', '') or '').lower()
                                if 'hide' in elem_desc or 'masquer' in elem_desc:
                                    continue
                                logger.info(f"Expanding thread (desc): {elems[i].info.get('contentDescription', '')}")
                                elems[i].click()
                                expanded = True
                                time.sleep(0.5)
                            except:
                                continue

        except Exception as e:
            logger.debug(f"Expand reply threads error: {e}")

        return expanded

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
        except:
            center_x = self.screen_width // 2
            start_y = 200
            end_y = 600

        for i in range(15):
            try:
                self.device.swipe(center_x, start_y, center_x, end_y, duration=0.1)
                time.sleep(0.15)
            except:
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
            result = subprocess.run(
                ['adb', '-s', self.device_id, 'shell',
                 'am', 'start', '-a', 'android.intent.action.VIEW',
                 '-d', post_url,
                 '-p', 'com.instagram.android'],
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
        except:
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
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No config file provided"}))
        sys.exit(1)

    config_path = sys.argv[1]

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Failed to load config: {e}"}))
        sys.exit(1)

    device_id = config.get('deviceId')
    if not device_id:
        print(json.dumps({"success": False, "error": "No deviceId provided"}))
        sys.exit(1)

    mode = config.get('mode', 'scrape')

    bridge = SmartCommentBridge(device_id, config)

    if not bridge.connect():
        print(json.dumps({"success": False, "error": "Failed to connect to device"}))
        sys.exit(1)

    if mode == 'scrape':
        # Scrape post context + all comments
        result = bridge.run_scrape()
        print(json.dumps(result, ensure_ascii=False))

    elif mode == 'reply_all':
        # Reply to pre-qualified comments (passed in config)
        qualified = config.get('qualifiedComments', [])
        if not qualified:
            print(json.dumps({"success": False, "error": "No qualified comments provided"}))
            sys.exit(1)

        post_url = config.get('postUrl', '').strip()
        target_username = config.get('targetUsername', '').strip().lstrip('@')

        if not post_url and not target_username:
            print(json.dumps({"success": False, "error": "No postUrl or targetUsername provided for reply mode"}))
            sys.exit(1)

        # Navigate to the correct post
        send_event("reply_progress", current=0, total=len(qualified), username="", status="Navigating to post...")
        logger.info(f"Reply mode: navigating to post (url={post_url or 'none'}, target=@{target_username or 'none'})...")

        bridge.restart_instagram()

        navigated = False
        if post_url:
            # PREFERRED: Navigate directly to the exact post via deep link
            logger.info(f"Using post URL for precise navigation: {post_url}")
            if bridge.navigate_to_post_url(post_url):
                navigated = True
            else:
                logger.warning("Post URL navigation failed, trying profile fallback...")

        if not navigated and target_username:
            # Navigate via profile → scroll through posts to find the matching one
            if not bridge._navigate_via_profile(target_username):
                print(json.dumps({"success": False, "error": f"Could not find the target post on @{target_username}'s profile"}))
                sys.exit(1)
            navigated = True

        if not navigated:
            print(json.dumps({"success": False, "error": "Could not navigate to the target post"}))
            sys.exit(1)

        if not bridge.open_comments():
            print(json.dumps({"success": False, "error": "Could not open comments"}))
            sys.exit(1)

        # Dismiss keyboard if visible
        try:
            title = bridge.device(resourceId="com.instagram.android:id/title_text_view")
            if title.exists:
                title.click()
                time.sleep(1)
        except:
            pass

        time.sleep(1)

        result = bridge.run_reply(qualified)
        print(json.dumps(result, ensure_ascii=False))

    else:
        print(json.dumps({"success": False, "error": f"Unknown mode: {mode}"}))
        sys.exit(1)


if __name__ == '__main__':
    main()
