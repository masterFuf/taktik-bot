"""Feed post actions: like, comment, detect, scroll, extract metadata."""

import time
from typing import Dict, List, Any, Optional

from taktik.core.social_media.instagram.services.like.orchestration import FramedLike


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
        """The author of the FRAMED post, the one the Feed likes and comments, read in that
        post's own header (`PostReadingMixin.framed_post_author`), like the like's guards: the
        first handle of its description ("author a publié ..."; a collaboration's first account),
        else of the author line inside that header.

        It read the first author line of the screen: with the framed header just under the top
        of the list, its name line is out of the dump and the line read was the NEXT post's; with
        the post above still under the action bar, that post's. The like, given to the framed
        post, was filed under another account. None when no post is framed (mid-scroll, a
        full-screen Reel) or its header names no handle: the post is then not engaged, it could
        not be filed.
        """
        try:
            author = self.scroll_actions.framed_post_author()
        except Exception as e:
            self.logger.warning(f"Framed post unreadable, author unknown: {e}")
            return None
        if not author:
            self.logger.debug("No framed post with a readable author on screen")
        return author
    
    def _like_budget_spent(self) -> bool:
        """Is `like` among the session's exhausted intents (session ceiling or daily sub-quota)?

        The session re-runs the feed step until its duration and each pass counts its own likes,
        so the run's budget has to be read here, the way the suggestions pass reads `follow`.
        Fail-open on a read error, like the rest of the guard."""
        session = getattr(self, 'session_manager', None)
        if session is None or not hasattr(session, 'exhausted_intents'):
            return False
        try:
            return 'like' in (session.exhausted_intents() or set())
        except Exception as e:
            self.logger.debug(f"Like budget read failed: {e}")
            return False

    def _like_current_post(self, record_as: Optional[str] = None) -> bool:
        """Like the framed feed post, through the like of a list of posts
        (`LikeOrchestration.like_framed_post`), the one a profile's posts and a hashtag's get: a
        double tap on the framed post's own media or a tap on the heart of its own row, alternated
        like a human, then verified on that heart; a short drag first when its row runs under the
        bottom. Never a band of the screen nor the first heart of the screen, which can belong to
        the post above.

        `record_as` is the post author: the like is filed (ledger row and session counter) as soon
        as its heart is seen turned, by `LikeOrchestration.record_post_like`. True only for a like
        given now: an already-liked post returns False here, and nothing is recorded for it."""
        try:
            outcome = self.like_business.like_framed_post(record_as=record_as)
        except Exception as e:
            self.logger.warning(f"Feed like failed: {e}")
            return False
        if outcome is FramedLike.ALREADY_LIKED:
            self.logger.debug("⏭️ Post already liked, skipping")
        return outcome is FramedLike.LIKED

    def _comment_feed_post(self, author: str, config: Dict[str, Any],
                           comment_text: Optional[str] = None) -> Dict[str, Any]:
        """Comment the feed post on screen, filed under its author.

        The production comment (`CommentAction.comment_on_post`, the hashtag posts pass's): it
        files the comment at the send (session counter, ledger row, posted_comments), looks for
        "Try again later" and closes the sheet it opened. The text is `comment_text` when the
        caller has one (the Taktik Agent autopilot's AI), else the AI comment hook's, else one of
        the operator's custom comments. With neither, no comment."""
        return self.comment_business.comment_on_post(
            comment_text=comment_text,
            custom_comments=(config or {}).get('custom_comments'),
            config=config,
            username=author,
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
