"""Like orchestration — like_profile_posts, sequential scroll, like_current_post."""

import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ....core.base_business import BaseBusinessAction
from ...management.profile import ProfileBusiness
from .post_navigation import PostNavigationMixin
from taktik.core.shared.behavior.like_method import should_double_tap_like
from taktik.core.shared.behavior.engagement_sequence import plan_engagement_sequence
from taktik.core.shared.behavior.dwell import content_dwell
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.support.debug import DEBUG_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS


class LikeOrchestration(PostNavigationMixin, BaseBusinessAction):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "like")
        self.profile_selectors = PROFILE_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.debug_selectors = DEBUG_SELECTORS
        self.post_selectors = POST_SELECTORS
        
        from .....ui.detectors.problematic_page import ProblematicPageDetector
        self.problematic_page_detector = ProblematicPageDetector(device, debug_mode=False)
        
        self.profile_business = ProfileBusiness(device, session_manager)
        
        self.default_config = {
            'like_delay_range': (2, 5),
            'navigation_delay_range': (1, 3),
            'skip_already_liked': True
        }
    
    def like_profile_posts(self, username: str, max_likes: int = 3, 
                          navigate_to_profile: bool = True,
                          config: dict = None,
                          profile_data: dict = None,
                          should_comment: bool = False,
                          custom_comments: list = None,
                          comment_template_category: str = 'generic',
                          max_comments: int = 1,
                          should_like: bool = True) -> dict:
        config = {**self.default_config, **(config or {})}
        
        stats = {
            'username': username,
            'posts_liked': 0,
            'posts_commented': 0,
            'posts_skipped': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            self.logger.info(f"Starting to like posts from @{username} (max: {max_likes})")
            
            if navigate_to_profile:
                if not self.nav_actions.navigate_to_profile(username):
                    self.logger.error(f"Failed to navigate to @{username}")
                    stats['errors'] += 1
                    return stats
            
            if profile_data:
                profile_info = profile_data
            else:
                profile_info = self.profile_business.get_complete_profile_info(username=username, navigate_if_needed=False)
            
            if not profile_info:
                self.logger.error(f"Failed to get profile info for @{username}")
                stats['errors'] += 1
                return stats
            
            if profile_info.get('is_private', False):
                self.logger.warning(f"@{username} is a private account")
                stats['errors'] += 1
                return stats
            
            sequential_stats = self.like_posts_with_sequential_scroll(
                username, max_likes, config, profile_data=profile_info,
                should_comment=should_comment, custom_comments=custom_comments,
                comment_template_category=comment_template_category, max_comments=max_comments,
                should_like=should_like
            )
            posts_liked = sequential_stats['posts_liked']
            posts_commented = sequential_stats.get('posts_commented', 0)
            stats['posts_liked'] = posts_liked
            stats['posts_commented'] = posts_commented
            stats['posts_seen'] = sequential_stats.get('posts_seen', 0)
            stats['method'] = sequential_stats.get('method', 'sequential_scroll')
            
            # Legacy grid method removed - sequential scroll is now the only method
            
            self.logger.debug(f"Checking session_manager: hasattr={hasattr(self, 'session_manager')}, session_manager={self.session_manager}, posts_liked={posts_liked}")
            if hasattr(self, 'session_manager') and self.session_manager and posts_liked > 0:
                try:
                    for i in range(posts_liked):
                        self.session_manager.record_action('like_posts', success=True, source=username)
                    self.logger.debug(f"Session stats recorded: {posts_liked} individual likes for @{username}")
                except Exception as e:
                    self.logger.error(f"Unable to record likes in session counters")
                    
                    stats['posts_liked'] = 0
                    stats['success'] = False
                    
                    raise Exception(f"Likes cancelled for @{username} - session counter recording failed: {e}")
            else:
                self.logger.warning(f"Stats NOT recorded - Reason: session_manager={self.session_manager}, posts_liked={posts_liked}")
            
            if posts_liked > 0:
                self._record_action(username, 'LIKE', posts_liked)
            
            stats['success'] = stats['posts_liked'] > 0
            self.logger.info(f"Likes completed for @{username}: {stats['posts_liked']} posts liked")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"General error liking @{username}: {e}")
            stats['errors'] += 1
            return stats

    def like_posts_with_sequential_scroll(self, username: str, max_likes: int = 3, config: dict = None, profile_data: dict = None,
                                         should_comment: bool = False, custom_comments: list = None,
                                         comment_template_category: str = 'generic', max_comments: int = 1,
                                         should_like: bool = True) -> dict:
        """Like posts with sequential scroll method.
        
        Args:
            should_like: If False, skip liking posts (only comment if should_comment is True)
        """
        config = {**self.default_config, **(config or {})}
        
        stats = {
            'username': username,
            'posts_liked': 0,
            'posts_commented': 0,
            'posts_seen': 0,
            'success': False,
            'errors': 0,
            'method': 'sequential_scroll'
        }
        
        try:
            self.logger.info(f"Sequential scroll method for @{username}")
            
            if profile_data:
                profile_info = profile_data
            else:
                profile_info = self.profile_business.get_complete_profile_info(username=username, navigate_if_needed=False)
            total_posts_on_profile = profile_info.get('posts_count', 0) if profile_info else 0
            
            if total_posts_on_profile > 0:
                max_posts_to_see = min(total_posts_on_profile, max_likes * 5)
                self.logger.info(f"Profile has {total_posts_on_profile} posts - viewing max {max_posts_to_see}")
            else:
                max_posts_to_see = max_likes * 5
                self.logger.debug(f"Post count unknown - max {max_posts_to_see} by default")
            
            posts_liked = 0
            posts_commented = 0
            posts_seen = 0
            
            if not self._open_entry_post_of_profile(total_posts_on_profile, username=username):
                self.logger.error("Failed to open entry post of profile")
                stats['errors'] += 1
                return stats

            self.logger.success("Entry post opened, starting sequential scroll")

            # A human glances at the first post on arrival; the deliberate description
            # read is handled per-post by the engagement sequence (engagement_sequence).
            time.sleep(content_dwell(0))

            consecutive_identical_posts = 0
            seen_posts_signatures = set()
            unique_posts_seen = 0
            
            while posts_liked < max_likes and posts_seen < max_posts_to_see:
                posts_seen += 1
                stats['posts_seen'] = posts_seen
                
                time.sleep(0.3)
                
                try:
                    is_reel = self._is_current_post_reel()
                    current_likes = self._extract_likes_count_from_ui(is_reel=is_reel)
                    current_comments = self._extract_comments_count_from_ui(is_reel=is_reel)
                    
                    post_signature = f"{current_likes}_{current_comments}_{is_reel}"
                    
                    self.logger.debug(f"Extracted signature: {post_signature} | Already seen: {len(seen_posts_signatures)} posts")
                    
                    is_new_post = post_signature not in seen_posts_signatures
                    
                    if is_new_post:
                        seen_posts_signatures.add(post_signature)
                        unique_posts_seen += 1
                        consecutive_identical_posts = 0
                        
                        post_type = "Reel" if is_reel else "Post"
                        self.logger.info(f"{post_type} #{unique_posts_seen} UNIQUE (scroll #{posts_seen}) - {current_likes} likes, {current_comments} comments - Likes: {posts_liked}/{max_likes}")
                    else:
                        consecutive_identical_posts += 1
                        self.logger.debug(f"Already seen post (signature: {post_signature}) - scroll #{consecutive_identical_posts}/6")
                        
                        if consecutive_identical_posts >= 6:
                            self.logger.warning(f"End of feed detected after {unique_posts_seen} unique posts - stopping scroll")
                            break
                        
                        if posts_seen < max_posts_to_see:
                            if not self._navigate_to_next_post_in_sequence():
                                break
                        continue
                    
                except Exception as e:
                    self.logger.debug(f"Error extracting post metadata #{posts_seen}: {e}")
                    self.logger.info(f"Post #{posts_seen}/{max_posts_to_see} - Metadata unavailable - Likes: {posts_liked}/{max_likes}")
                    consecutive_identical_posts = 0
                
                if posts_liked >= max_likes:
                    self.logger.success(f"Goal reached: {posts_liked}/{max_likes} posts liked - stopping scroll")
                    break
                
                # Decide whether to engage this post (probability gate kept — respects the
                # user's like_probability + a position factor so not every post is liked).
                if should_like:
                    base_probability = 0.70
                    position_factor = 0.8 if unique_posts_seen <= 2 else (1.0 if unique_posts_seen <= 5 else 1.2)
                    final_probability = base_probability * position_factor
                    should_like_this_post = random.random() < final_probability
                    self.logger.debug(f"Post #{posts_seen}: like_probability={final_probability:.2f}")
                else:
                    should_like_this_post = False

                if should_like_this_post and posts_liked < max_likes:
                    if self._is_post_already_liked():
                        self.logger.debug(f"Post #{posts_seen} already liked - skipping to avoid unlike")
                        stats['already_liked'] = stats.get('already_liked', 0) + 1
                    else:
                        do_comment_this = should_comment and posts_commented < max_comments
                        # Vary the choreography: like / read description / comment in a
                        # human, non-fixed order (A: like→read→comment, B: read→like→comment,
                        # C: like+comment no read, D: read→like, …). See engagement_sequence.
                        sequence = plan_engagement_sequence(True, do_comment_this)
                        self.logger.debug(f"Post #{posts_seen}: engagement pattern {sequence}")
                        liked_ok, commented_ok = self._run_engagement_sequence(
                            sequence, username, custom_comments, comment_template_category, config
                        )
                        if liked_ok:
                            posts_liked += 1
                            stats['posts_liked'] = posts_liked
                            self.logger.success(f"Post #{posts_seen} liked ({posts_liked}/{max_likes})")
                        if commented_ok:
                            posts_commented += 1
                            stats['posts_commented'] = posts_commented
                else:
                    self.logger.debug(f"Post #{posts_seen} not engaged")
                
                if posts_seen < max_posts_to_see:
                    scroll_count = 1
                    if posts_seen % 4 == 0:
                        scroll_count = 2
                        self.logger.debug(f"Double scroll at post #{posts_seen} for more variety")
                    
                    success = True
                    for i in range(scroll_count):
                        if not self._navigate_to_next_post_in_sequence():
                            self.logger.warning("Unable to navigate to next post - end of scroll")
                            success = False
                            break
                        if i < scroll_count - 1:
                            time.sleep(0.3)
                    
                    if not success:
                        break
                
                self._human_like_delay('scroll')
            
            self._return_to_profile_from_post()
            
            stats['success'] = posts_liked > 0
            stats['unique_posts_seen'] = unique_posts_seen
            self.logger.success(f"[FINAL] Sequential scroll completed: {posts_liked}/{max_likes} posts liked from {unique_posts_seen} unique posts ({posts_seen} scrolls)")
            return stats
            
        except Exception as e:
            self.logger.error(f"Error in like_posts_with_sequential_scroll: {e}")
            stats['errors'] += 1
            try:
                self._return_to_profile_from_post()
            except Exception:
                pass
            return stats

    def like_current_post(self) -> bool:
        try:
            if not self.detection_actions.is_on_post_screen():
                self.logger.warning("Not on a post screen")
                return False

            if self.detection_actions.is_post_liked():
                self.logger.debug("Post already liked")
                return True

            # Alternate like methods like a human (telemetry showed the profile-posts
            # path always used the button): ~45% an image double-tap, else the button.
            if should_double_tap_like() and self._double_tap_like_image():
                self.logger.debug("Post liked via image double-tap")
                return True

            if self.click_actions.like_post():
                self.logger.debug("Post liked successfully (button)")
                return True
            else:
                self.logger.warning("Failed to like")
                return False

        except Exception as e:
            self.logger.error(f"Error liking current post: {e}")
            return False

    def _current_post_signature(self) -> str:
        """A cheap identity signature of the on-screen post (likes_comments_isreel) — used
        to detect that a description read scrolled the frame onto a DIFFERENT post before we
        act. Empty string if it can't be read."""
        try:
            is_reel = self._is_current_post_reel()
            likes = self._extract_likes_count_from_ui(is_reel=is_reel)
            comments = self._extract_comments_count_from_ui(is_reel=is_reel)
            return f"{likes}_{comments}_{is_reel}"
        except Exception:
            return ""

    def _run_engagement_sequence(self, sequence, username, custom_comments,
                                 comment_template_category, config) -> tuple:
        """Execute the ordered engagement steps (read / like / comment) for one post.

        A failed like aborts the rest. CRUCIALLY: reading a description can scroll the
        frame onto the NEXT post (the reframe is best-effort, see PostReadingMixin), so any
        like/comment that FOLLOWS a read is guarded by a post-identity signature check —
        without it, pattern E (read→comment→like) could post a comment on the wrong post.
        On drift we abort the post's sequence rather than act on the wrong post."""
        liked = commented = False
        sig_before_read = None   # set after a read → the next action must re-verify identity

        for step in sequence:
            if step == 'read':
                sig_before_read = self._current_post_signature()
                self._read_post_description()
            elif step in ('like', 'comment'):
                # If a read just happened, confirm we're still on the same post.
                if sig_before_read is not None:
                    if self._current_post_signature() != sig_before_read:
                        self.logger.warning("Frame drifted after reading the description — "
                                            "aborting this post's sequence (wrong post)")
                        break
                    sig_before_read = None   # confirmed once; our own like changes the count
                if step == 'like':
                    if self.like_current_post():
                        liked = True
                    else:
                        self.logger.warning("Failed to like — aborting this post's sequence")
                        break
                else:  # comment
                    if self._comment_current_post(username, custom_comments,
                                                  comment_template_category, config):
                        commented = True
        return liked, commented

    def _read_post_description(self) -> None:
        """Open + read the post's description like a human (carousel + caption expand +
        content-aware dwell), then reframe the post so the next action (like/comment)
        targets the right screen. Reuses the shared PostReadingMixin via scroll_actions."""
        try:
            self.scroll_actions.human_reading_pause()
        except Exception as e:
            self.logger.debug(f"read description skipped: {e}")

    def _comment_current_post(self, username, custom_comments, comment_template_category, config) -> bool:
        """Post a comment on the current post. Returns True if a comment was posted."""
        try:
            from ..comment import CommentBusiness
            comment_business = CommentBusiness(self.device, self.session_manager, self.automation)
            comment_result = comment_business.comment_on_post(
                custom_comments=custom_comments,
                template_category=comment_template_category,
                config=config,
                username=username,
            )
            if comment_result.get('commented'):
                self.logger.success(f"✅ Comment posted: '{comment_result.get('comment_text')}'")
                return True
            self.logger.debug("Comment not posted")
            return False
        except Exception as e:
            self.logger.error(f"Error commenting: {e}")
            return False

    def _double_tap_like_image(self) -> bool:
        """Double-tap a varied point in the post image band to like it, then confirm the
        like registered (a double-tap can miss). Returns False so the caller falls back
        to the like button if it didn't take."""
        try:
            width, height = self.device.get_screen_size()
            image_region = (
                int(width * 0.30), int(height * 0.30),
                int(width * 0.70), int(height * 0.52),
            )
            self.device.human_double_tap(image_region)
            self._human_like_delay('click')
            return self.detection_actions.is_post_liked()
        except Exception as e:
            self.logger.debug(f"Double-tap like failed: {e}")
            return False
    
    def _is_post_already_liked(self) -> bool:
        try:
            return self.detection_actions.is_post_liked()
        except Exception as e:
            self.logger.debug(f"Error checking if liked: {e}")
            return False
    
    def _extract_likes_count_from_ui(self, is_reel: bool = None) -> int:
        """Delegate to ui_extractors for likes extraction."""
        return self.ui_extractors.extract_likes_count_from_ui(is_reel=is_reel)
    
    def _extract_comments_count_from_ui(self, is_reel: bool = None) -> int:
        """Delegate to ui_extractors for comments extraction."""
        return self.ui_extractors.extract_comments_count_from_ui(is_reel=is_reel)
    
    def _is_current_post_reel(self) -> bool:
        """Delegate to detection_actions for reel detection."""
        return self.detection_actions.is_reel_post()
