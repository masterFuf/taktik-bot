"""Post type detection, reel handling, grid detection for hashtag workflow."""

import time
from typing import Any, Dict, Optional

from taktik.core.social_media.instagram.ui.extractors import post_signature


class HashtagPostDetectionMixin:
    """Mixin: detect post types (reel/post/carousel), reveal reel UI, check grid presence."""

    def _detect_opened_post_type(self) -> str:
        try:
            reel_player_indicators = self.post_selectors.reel_player_indicators
            
            for indicator in reel_player_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Reel player detected via: {indicator}")
                    return "reel_player"
            
            carousel_indicators = self.post_selectors.carousel_indicators
            
            for indicator in carousel_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Carousel detected via: {indicator}")
                    return "post_detail"
            
            post_detail_indicators = self.post_selectors.post_detail_indicators
            
            for indicator in post_detail_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Post detail detected via: {indicator}")
                    return "post_detail"
            
            self.logger.warning("No post indicator found")
            return "unknown"
            
        except Exception as e:
            self.logger.debug(f"Error detecting post type: {e}")
            return "unknown"
    
    def _reveal_reel_comments_section(self) -> bool:
        try:
            # Humanized controlled scroll to reveal the like/comment row (was a fixed-centre swipe).
            self.logger.debug("Swipe to reveal comments")
            self.device.human_scroll("down", distance_ratio=0.6)
            time.sleep(2)

            if self._are_like_comment_elements_visible():
                self.logger.debug("Like/comment elements detected after 1st swipe")
                return True

            self.logger.debug("Second swipe to finalize opening")
            self.device.human_scroll("down", distance_ratio=0.4)
            time.sleep(2)
            
            result = self._are_like_comment_elements_visible()
            if result:
                self.logger.debug("Like/comment elements detected after 2nd swipe")
            else:
                self.logger.debug("Like/comment elements not detected")
            return result
            
        except Exception as e:
            self.logger.error(f"Error swiping to reveal comments: {e}")
            return False
    
    def _are_like_comment_elements_visible(self) -> bool:
        try:
            like_indicators = self.post_selectors.like_button_indicators
            comment_indicators = self.post_selectors.comment_button_indicators
            
            for selector in like_indicators + comment_indicators:
                try:
                    if self.device.xpath(selector).exists:
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking elements: {e}")
            return False
    
    # Escalating travel for one advance. A post is not a fixed height: a reel fills the
    # screen, a photo with a long caption can exceed it, a short one takes half. Half a
    # screen — the value this used to send blindly — lands back on the SAME post often
    # enough to matter, so each retry pushes further instead of repeating what failed.
    _NEXT_POST_RATIOS = (0.5, 0.8, 1.0)

    def _current_post_signature(self) -> str:
        """Identity of the post on screen — shared convention (`ui.extractors.post_signature`)."""
        try:
            is_reel = self._is_reel_post()
            return post_signature(
                self.ui_extractors.extract_likes_count_from_ui(is_reel=is_reel),
                self.ui_extractors.extract_comments_count_from_ui(is_reel=is_reel),
                is_reel,
            )
        except Exception as e:
            self.logger.debug(f"Error reading post signature: {e}")
            return ""

    def _signature_of(self, metadata: Optional[Dict[str, Any]]) -> Optional[str]:
        """Signature of a post whose counters were JUST read — no second UI dump."""
        if not metadata:
            return None
        return post_signature(
            metadata.get('likes_count'),
            metadata.get('comments_count'),
            metadata.get('is_reel', False),
        )

    def _swipe_to_next_post(self, known_signature: Optional[str] = None) -> bool:
        """Advance to the next post — and CONFIRM the post actually changed.

        This used to be a blind half-screen scroll that logged "swiped to next post"
        whatever happened. When the travel was too short (reels, long captions), the
        caller re-read the SAME post, found it already processed, scrolled again, and
        burned its whole post budget on one post before opening the likers of a post it
        had just rejected. Nothing in the logs said so — the swipe claimed success.

        Returns True only when the post on screen is no longer the one we came from.

        Args:
            known_signature: signature of the current post if the caller already read it
                (saves one UI dump per advance — this runs on every post).
        """
        before = known_signature if known_signature is not None else self._current_post_signature()

        for attempt, ratio in enumerate(self._NEXT_POST_RATIOS, start=1):
            try:
                self.device.human_scroll("down", distance_ratio=ratio)
            except Exception as e:
                self.logger.debug(f"Error swiping to next post: {e}")
                return False

            time.sleep(1.2)
            after = self._current_post_signature()

            # An unreadable screen is not a proven arrival: treat it as "changed" only if
            # we could read it. Otherwise the caller's own extraction decides.
            if after and after != before:
                self.logger.debug(f"📜 Next post reached (attempt {attempt}, ratio {ratio})")
                return True

            self.logger.debug(
                f"📜 Still on the same post after scrolling {ratio} of the screen "
                f"(attempt {attempt}/{len(self._NEXT_POST_RATIOS)})"
            )

        self.logger.warning("⚠️ Could not advance to the next post - end of list, or the viewer is stuck")
        return False
