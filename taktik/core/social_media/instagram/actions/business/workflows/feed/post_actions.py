"""Feed post actions: like, comment, detect, scroll, extract metadata."""

import time
from typing import Dict, List, Any, Optional

# A human doesn't always like the same way: some likes tap the like button, others
# double-tap the image. The choice lives in shared behaviour so the feed and the
# profile-posts (like workflow) paths alternate identically.
from taktik.core.shared.behavior.like_method import should_double_tap_like as _should_double_tap_like
from taktik.core.social_media.instagram.ui.extractors import username_from_author_header


class FeedPostActionsMixin:
    """Mixin: post-level actions in the feed (like, comment, detect, scroll)."""

    def _is_sponsored_post(self) -> bool:
        """Is the current post sponsored?"""
        return self._is_element_present(self._feed_selectors['sponsored_indicators'])
    
    def _is_reel_post(self) -> bool:
        """Is the current post a reel?"""
        try:
            reel_indicators = self._feed_sel.reel_indicators
            
            for selector in reel_indicators:
                element = self.device.xpath(selector)
                if element.exists:
                    return True
            
            return False
        except Exception as e:
            self.logger.debug(f"Error checking if reel: {e}")
            return False
    
    def _get_current_post_author(self) -> Optional[str]:
        """Username of the current post author."""
        try:
            for selector in self._feed_selectors['post_author_username']:
                element = self.device.xpath(selector)
                if element.exists:
                    # A collaboration post names several accounts here ("a et b"): the first
                    # handle, never the line, which the cleaner used to glue into "aetb".
                    username = username_from_author_header(element.get_text())
                    if username:
                        return username
            
            # Fallback: essayer via content-desc de l'avatar
            for selector in self._feed_selectors['post_author_avatar']:
                element = self.device.xpath(selector)
                if element.exists:
                    content_desc = element.attrib.get('content-desc', '')
                    if content_desc:
                        # The content-desc often holds a localized "profile picture of <username>"
                        parts = content_desc.split()
                        for part in parts:
                            if self._is_valid_username(part):
                                return self._clean_username(part)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting post author: {e}")
            return None
    
    def _like_current_post(self, record_as: Optional[str] = None) -> bool:
        """Like the current feed post, alternating like methods like a human would:
        sometimes a tap on the like button, sometimes a double-tap on the image.

        `record_as` is the post author. Given, the like is filed at the gesture -- ledger row
        and session counter -- by `LikeOrchestration.record_post_like`, the function the
        hashtag posts pass files its likes with (`like_current_post(record_as=...)`). The
        gesture stays the feed's: an already-liked post returns False here, and nothing is
        recorded for it."""
        try:
            # Locate the like button and bail out if the post is already liked.
            like_button = None
            for selector in self._feed_sel.like_button:
                element = self.device.xpath(selector)
                if element.exists:
                    content_desc = element.attrib.get('content-desc', '').lower()
                    if any(fragment in content_desc for fragment in self._feed_sel.liked_button_desc_fragments):
                        self.logger.debug("⏭️ Post already liked, skipping")
                        return False
                    like_button = element
                    break

            # Heart-icon fallback check for an already-liked post.
            for selector in self._feed_sel.already_liked_indicators:
                if self.device.xpath(selector).exists:
                    self.logger.debug("⏭️ Post already liked, skipping")
                    return False

            # Pick the method: double-tap by chance, or whenever no like button is visible.
            if like_button is not None and not _should_double_tap_like():
                self.logger.debug("❤️ Liking via the like button")
                if not self._human_tap_element(like_button):
                    like_button.click()  # centre-click fallback
                self._record_feed_like(record_as)
                self._human_like_delay('click')
                return True

            # Image double-tap: a varied point within the post image band (not the fixed
            # centre); fall back to the centre double-tap if sampling fails.
            self.logger.debug("❤️ Liking via image double-tap")
            screen_height = self.device.info.get('displayHeight', 1920)
            screen_width = self.device.info.get('displayWidth', 1080)
            image_region = (
                int(screen_width * 0.30), int(screen_height * 0.30),
                int(screen_width * 0.70), int(screen_height * 0.52),
            )
            if not self.device.human_double_tap(image_region):
                self.device.double_click(screen_width // 2, int(screen_height * 0.4))
            self._record_feed_like(record_as)
            self._human_like_delay('click')
            return True

        except Exception as e:
            self.logger.debug(f"Error liking post: {e}")
            return False

    def _record_feed_like(self, author: Optional[str]) -> None:
        """File a feed like the moment it is given, before the pause that follows it: a run
        stopped during that pause must not leave a like on Instagram with no trace here."""
        if author:
            self.like_business.record_post_like(author)
    
    def _comment_feed_post(self, author: str, config: Dict[str, Any],
                           comment_text: Optional[str] = None) -> Dict[str, Any]:
        """Comment the feed post on screen, filed under its author.

        The production comment (`CommentAction.comment_on_post`, the hashtag posts pass's): it
        files the comment at the send (session counter, ledger row, posted_comments), looks for
        "Try again later" and closes the sheet it opened. The text is `comment_text` when the
        caller has one (the Taktik Agent autopilot's AI), else the AI comment hook's, else one of
        the operator's custom comments. Never a built-in template (`template_fallback=False`):
        with no AI and no custom comment, the Feed does not comment (Kevin, 2026-09-25), the
        same few fixed comments on post after post being a trace of automation."""
        return self.comment_business.comment_on_post(
            comment_text=comment_text,
            custom_comments=(config or {}).get('custom_comments'),
            config=config,
            username=author,
            template_fallback=False,
        ) or {}

    def _extract_post_metadata(self) -> Optional[Dict[str, Any]]:
        """Metadata of the currently visible post (likes, comments)."""
        try:
            is_reel = self._is_reel_post()
            metadata = {
                'likes_count': self.ui_extractors.extract_likes_count_from_ui(is_reel=is_reel),
                'comments_count': self.ui_extractors.extract_comments_count_from_ui(is_reel=is_reel),
                'is_reel': is_reel
            }
            
            self.logger.debug(f"📊 Post metadata: {metadata['likes_count']} likes, {metadata['comments_count']} comments")
            return metadata
            
        except Exception as e:
            self.logger.debug(f"Error extracting post metadata: {e}")
            return None
    
    def _scroll_to_next_post(self):
        """Scroll to the next post and align so the post header is near the top of the screen."""
        try:
            screen_height = self.device.info.get('displayHeight', 1920)

            # Primary scroll ~50% of screen height — humanized controlled (coast=False keeps the
            # travel precise so the header-alignment micro-steps below stay reliable).
            self.device.human_scroll("down", distance_ratio=0.5)
            time.sleep(0.4)

            # Align to the next post header (up to 4 micro-adjustments)
            no_header_streak = 0
            for _ in range(4):
                header_y = self._get_post_header_top_y()

                if header_y is not None and header_y < int(screen_height * 0.35):
                    # Header is already in the upper 35% → good position
                    return

                if header_y is None:
                    no_header_streak += 1
                    if no_header_streak >= 2:
                        # Two consecutive misses → likely in Reel viewer or suggestions section
                        # Stop micro-scrolling to avoid drifting further
                        break
                    # One bigger micro-scroll to skip suggestions / between-post gap (humanized).
                    self.device.human_scroll("down", distance_ratio=0.3)
                else:
                    no_header_streak = 0
                    # Header found but too low on screen → small humanized scroll to bring it up.
                    self.device.human_scroll("down", distance_ratio=0.17)
                time.sleep(0.3)

        except Exception as e:
            self.logger.debug(f"Error scrolling to next post: {e}")
            try:
                self.scroll_actions.scroll_down()
            except Exception:
                pass

    def _get_post_header_top_y(self) -> Optional[int]:
        """Return the top Y pixel of the first visible post author element, or None if not found."""
        try:
            for selector in self._feed_selectors['post_author_username']:
                el = self.device.xpath(selector)
                if el.exists:
                    bounds = el.info.get('bounds', {})
                    top = bounds.get('top')
                    if top is not None:
                        return int(top)
        except Exception:
            pass
        return None
