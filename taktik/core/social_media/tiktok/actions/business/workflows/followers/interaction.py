"""Video interaction mixin for the TikTok Followers workflow.

Handles watching videos, liking, favoriting, following,
and recording interactions in the database.
"""

import time
import random


class VideoInteractionMixin:
    """Methods for interacting with videos on a follower's profile."""

    def _interact_with_profile_posts(self):
        """Interact with posts on the current profile.
        
        Flow:
        1. Count available posts on profile (max 9 visible without scroll)
        2. Click on first post to open video feed
        3. Watch video, interact (like/favorite/etc)
        4. Swipe up to next video (instead of going back and clicking next post)
        5. Repeat for min(posts_per_profile, available_posts) times
        6. Press back to return to profile page
        """
        # Count available posts before interacting
        available_posts = self._count_visible_posts()
        
        if available_posts == 0:
            self.logger.info(f"⚠️ No posts to interact with on profile @{self._current_profile_username}")
            self._send_action('no_posts', self._current_profile_username)
            return
        
        # Limit interactions to available posts
        posts_to_interact = min(self.config.posts_per_profile, available_posts)
        self.logger.debug(f"📹 Will interact with {posts_to_interact} posts (available: {available_posts}, config: {self.config.posts_per_profile})")
        
        # Click on first post to enter video feed
        if not self._click_profile_post(0):
            self.logger.debug("Failed to click first post")
            return
        
        self._human_delay()
        
        for i in range(posts_to_interact):
            if not self._running:
                break
            
            if self._check_limits_reached():
                break
            
            # Watch the video
            watch_time = random.uniform(self.config.min_watch_time, self.config.max_watch_time)
            self.logger.debug(f"Watching video {i+1}/{posts_to_interact} for {watch_time:.1f}s")
            time.sleep(watch_time)
            
            self.stats.posts_watched += 1
            
            # Interact with the video
            self._interact_with_current_video()
            
            self._actions_since_pause += 1
            
            # Swipe up to next video (except for last one)
            if i < posts_to_interact - 1:
                self._swipe_to_next_video()
                self._human_delay()
        
        self._send_stats_update()
        
        # Exit video feed back to profile
        self._go_back()
        time.sleep(0.5)
    
    def _swipe_to_next_video(self):
        """Swipe up to go to next video in the feed.
        
        Uses the scroll action for consistent behavior across all screen sizes.
        """
        try:
            self.scroll.scroll_to_next_video()
        except Exception as e:
            self.logger.debug(f"Error swiping to next video: {e}")
    
    def _count_visible_posts(self) -> int:
        """Count the number of visible posts on the current profile.
        
        Returns:
            Number of posts visible in the grid (max 9 without scrolling).
        """
        try:
            posts = self.device.xpath(self.followers_selectors.profile_post_item[0]).all()
            count = len(posts)
            self.logger.debug(f"📊 Found {count} visible posts on profile")
            return count
        except Exception as e:
            self.logger.debug(f"Error counting posts: {e}")
            return 0
    
    def _click_profile_post(self, index: int = 0) -> bool:
        """Click on a post in the profile grid."""
        try:
            posts = self.device.xpath(self.followers_selectors.profile_post_item[0]).all()
            
            if index < len(posts):
                posts[index].click()
                time.sleep(1)  # Wait for video to load
                return True
            
            # Fallback: click first post
            if self.click._find_and_click(self.followers_selectors.first_post, timeout=3):
                time.sleep(1)
                return True
                
        except Exception as e:
            self.logger.debug(f"Error clicking profile post: {e}")
        
        return False
    
    def _interact_with_current_video(self):
        """Interact with the currently playing video (like, comment, share, favorite)."""
        
        # Check if video is already liked
        if self._is_video_already_liked():
            self.logger.debug("Video already liked, skipping like")
            self._send_action('already_liked', self._current_profile_username)
        else:
            # Like - use probability to distribute likes randomly across posts
            if random.random() < self.config.like_probability:
                if self.stats.likes < self.config.max_likes_per_session:
                    if self._try_like_video():
                        self.stats.likes += 1
                        self._send_action('like', self._current_profile_username)
                        self._record_interaction('LIKE', self._current_profile_username)
        
        # Favorite
        if random.random() < self.config.favorite_probability:
            if self._try_favorite_video():
                self.stats.favorites += 1
                self._send_action('favorite', self._current_profile_username)
                self._record_interaction('FAVORITE', self._current_profile_username)
        
        # Comment (less frequent)
        if random.random() < self.config.comment_probability:
            if self.stats.comments < self.config.max_comments_per_session:
                # TODO: Implement commenting
                pass
        
        # Share (rare)
        if random.random() < self.config.share_probability:
            # TODO: Implement sharing
            pass
        
        self._send_stats_update()
    
    def _is_video_already_liked(self) -> bool:
        """Check if the current video is already liked."""
        try:
            for selector in self.video_selectors.video_already_liked:
                elem = self.device.xpath(selector)
                if elem.exists:
                    return True
        except Exception as e:
            self.logger.debug(f"Error checking if video liked: {e}")
        return False
    
    def _try_like_video(self) -> bool:
        """Try to like the current video."""
        try:
            for selector in self.video_selectors.like_button_unliked:
                elem = self.device.xpath(selector)
                if elem.exists:
                    elem.click()
                    self.logger.info("❤️ Liked video")
                    self._human_delay()
                    return True
        except Exception as e:
            self.logger.debug(f"Error liking video: {e}")
        return False
    
    def _try_favorite_video(self) -> bool:
        """Try to favorite/bookmark the current video."""
        try:
            selectors = self.video_selectors.favorite_button
            if self.click._find_and_click(selectors, timeout=2):
                self.logger.info("⭐ Favorited video")
                self._human_delay()
                return True
        except Exception as e:
            self.logger.debug(f"Error favoriting video: {e}")
        return False
    
    def _try_follow_current_profile(self) -> bool:
        """Try to follow the user from their profile page."""
        try:
            # Look for Follow button on profile
            selectors = self.followers_selectors.profile_follow_button
            if self.click._find_and_click(selectors, timeout=2):
                self.stats.follows += 1
                self.logger.info(f"👤 Followed user ({self.stats.follows}/{self.config.max_follows_per_session})")
                self._send_action('follow', self._current_profile_username)
                self._record_interaction('FOLLOW', self._current_profile_username)
                self._human_delay()
                return True
        except Exception as e:
            self.logger.debug(f"Error following user: {e}")
        return False
    
    def _record_interaction(self, interaction_type: str, target_username: str):
        """Record an interaction in the database."""
        if self._account_id and target_username:
            try:
                self._db.record_tiktok_interaction(
                    account_id=self._account_id,
                    target_username=target_username,
                    interaction_type=interaction_type,
                    success=True,
                    session_id=self._session_id
                )
            except Exception as e:
                self.logger.debug(f"Failed to record interaction: {e}")
