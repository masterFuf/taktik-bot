"""For You Feed Workflow for TikTok automation.


Automates the interactions on the For You feed:
- scroll the videos
- like the videos against criteria
- follow the creators against filters
- extract the video information
"""

from typing import Optional, Dict, Any
import time
import random

from taktik.core.social_media.tiktok.services.behavior.watch_time import video_watch_seconds

from taktik.core.shared.telemetry.sink import emit_step

from .._internal import BaseVideoWorkflow, VideoWorkflowStats, FeedInterruptionsMixin
from .models import ForYouConfig


# Backward-compat alias
ForYouStats = VideoWorkflowStats


class ForYouWorkflow(FeedInterruptionsMixin, BaseVideoWorkflow):
    """TikTok For You feed automation workflow.
    
    Ce workflow permet de:
    - navigate to the For You feed
    - scroll the videos with a varying watch time
    - like, follow and favourite against probabilities and filters
    - extract the video information
    - honour the caps and the breaks
    """
    
    def __init__(self, device, config: Optional[ForYouConfig] = None):
        """Initialize the workflow.
        
        Args:
            device: Device facade for UI interactions
            config: Optional configuration, uses defaults if not provided
        """
        super().__init__(device, module_name="tiktok-for-you-workflow")
        self.config = config or ForYouConfig()
        self.stats = VideoWorkflowStats()
    
    def run(self) -> VideoWorkflowStats:
        """Run the For You workflow.
        
        Returns:
            VideoWorkflowStats: Statistics from the workflow run
        """
        self.logger.info("🚀 Starting For You workflow")
        self.logger.info(f"📊 Config: max_videos={self.config.max_videos}, "
                        f"like_prob={self.config.like_probability}, "
                        f"follow_prob={self.config.follow_probability}")
        
        self._running = True
        self.stats = VideoWorkflowStats()
        
        try:
            # Navigate to For You feed
            # Note: TikTok restart is handled by the bridge's tiktok_startup()
            if not self._ensure_on_for_you():
                self.logger.error("❌ Failed to navigate to For You feed")
                return self.stats
            
            # Process videos
            while self._running and self.stats.videos_watched < self.config.max_videos:
                if not self._wait_if_paused():
                    break
                
                # Check and close any popups first
                self._handle_popups()
                
                # Check for comments section accidentally opened
                if self._handle_comments_section():
                    continue
                
                # Check for suggestion page (Follow back / Not interested)
                if self._handle_suggestion_page():
                    continue
                
                # Check limits
                if self._check_limits_reached():
                    self.logger.info("📊 Session limits reached")
                    break
                
                # Get video info immediately for real-time display
                video_info = self.detection.get_video_info()

                # A parsed hierarchy can prove that an earlier gesture opened a creator profile
                # instead of advancing the feed. Do not report @None as a watched video or keep
                # scrolling the profile grid; return through the existing bounded navigation.
                if self._recover_off_video_surface(video_info):
                    continue
                
                # Detect stuck state
                if self._handle_stuck_video(video_info):
                    continue

                # Plan the dwell BEFORE the callback so the front's per-video card shows
                # the watch time (the bot then sleeps exactly this value). Ads are skipped
                # without watching, so they carry no watch_time.
                if not (self.config.skip_ads and video_info.get('is_ad', False)):
                    # Content-driven, session-scaled, bounded by the operator's range. A flat
                    # draw gave a three-word clip the same dwell as an unreadable wall of text.
                    video_info['watch_time'] = round(video_watch_seconds(
                        video_info,
                        minimum=self.config.min_watch_time,
                        maximum=self.config.max_watch_time,
                        reading_scale=self._behavior_reading_scale('tiktok_feed_video'),
                    ), 1)

                # Send video info callback immediately (before any processing)
                if self._on_video_callback:
                    try:
                        self._on_video_callback(video_info)
                    except Exception as e:
                        self.logger.warning(f"Video callback error: {e}")

                # Feed training. Runs BEFORE the engagement decisions and can end the video's
                # turn entirely: rejecting one and then liking it would send two signals that
                # contradict each other, and the reject already advances the feed by itself.
                if self._train_on_video(video_info):
                    continue

                # Check if current video is an ad
                if self.config.skip_ads and video_info.get('is_ad', False):
                    self.logger.info("📺 Skipping advertisement")
                    self.stats.ads_skipped += 1
                    self._send_stats_update()
                    if not self._advance_to_next_video(video_info):
                        self.stats.errors += 1
                    continue
                
                # Process current video (video_info already fetched). Heartbeat: attribute
                # the per-video processing time (watch + decide + act) in the cadence/run log.
                _liked0 = getattr(self.stats, 'videos_liked', 0)
                _follow0 = getattr(self.stats, 'users_followed', 0)
                _fav0 = getattr(self.stats, 'videos_favorited', 0)
                _t0 = time.time()
                emit_step("analysis", action="start", target="for_you")
                self._process_current_video(video_info)
                _acted = (getattr(self.stats, 'videos_liked', 0) > _liked0
                          or getattr(self.stats, 'users_followed', 0) > _follow0
                          or getattr(self.stats, 'videos_favorited', 0) > _fav0)
                emit_step("analysis", action="done",
                          duration_ms=int((time.time() - _t0) * 1000),
                          outcome="interacted" if _acted else "watched")

                # Check for pause
                self._check_pause_needed()
                
                # Scroll to next video
                if not self._advance_to_next_video(video_info):
                    self.logger.warning("❌ Failed to scroll to next video")
                    if self.click.close_system_popup():
                        self.logger.info("✅ System popup was blocking, closed it")
                        time.sleep(0.5)
                        self._advance_to_next_video(video_info)
                    else:
                        self.stats.errors += 1
                        if self.stats.errors > 5:
                            self.logger.error("❌ Too many errors, stopping")
                            break
            
            self.logger.success(f"✅ Workflow completed: {self.stats.to_dict()}")
            
        except Exception as e:
            self.logger.error(f"❌ Workflow error: {e}")
            self.stats.errors += 1
        
        finally:
            self._running = False
        
        return self.stats

    def _advance_to_next_video(self, video_info: Dict[str, Any]) -> bool:
        """Advance with the identity already captured for this video's callback and filters."""
        return self.scroll.scroll_to_next_video(video_info.get('signature'))

    def _recover_off_video_surface(self, video_info: Dict[str, Any]) -> bool:
        """Return to For You when a parsed snapshot proves the feed video is gone."""
        if video_info.get('video_visible') is not False:
            return False

        self.logger.warning("TikTok video surface lost; returning to the For You feed")
        recovered = self._ensure_on_for_you(force_navigation=True)

        # get_video_info shares its observation with the upcoming gesture. Navigation has made
        # that observation stale, whether recovery succeeded or failed.
        snapshot_device = getattr(self.detection, 'device', None)
        clear_snapshot = getattr(snapshot_device, 'clear_video_snapshot', None)
        if callable(clear_snapshot):
            clear_snapshot()

        if not recovered:
            self.stats.errors += 1
            self.logger.error("Failed to recover the For You feed after leaving the video surface")
        return True
    
    def _train_on_video(self, video_info: Dict[str, Any]) -> bool:
        """Send the feed a signal about this video. True when the video's turn is over.

        Returns True only after a REJECT, because that gesture advances the feed on its own --
        measured, the author changed with no swipe. Returning False everywhere else lets the
        normal engagement pass run, which is what "watch" means here: staying on an in-niche
        video is the positive signal, and it costs nothing extra.
        """
        keywords = getattr(self.config, 'training_keywords', None)
        if not keywords:
            return False

        from taktik.core.social_media.tiktok.services.feed.training import training_decision

        rejected = getattr(self.stats, 'videos_rejected', 0)
        if rejected >= getattr(self.config, 'max_rejections_per_session', 20):
            return False

        decision = training_decision(
            [video_info.get('description'), video_info.get('sound'), video_info.get('author')],
            keywords,
            reject_off_niche=getattr(self.config, 'training_reject_off_niche', True),
        )
        if decision != 'reject':
            # `watch` and `skip` both mean "carry on": the dwell already planned is the signal,
            # and there is nothing to tap for either of them.
            return False

        from taktik.core.social_media.tiktok.actions.atomic.interaction.feed_training_actions import (
            FeedTrainingActions,
        )

        try:
            if FeedTrainingActions(self.device).mark_not_interested():
                if hasattr(self.stats, 'videos_rejected'):
                    self.stats.videos_rejected += 1
                return True
        except Exception as exc:
            self.logger.warning(f"Entraînement FYP: rejet impossible ({exc})")
        # The signal did not leave, so the video is still on screen and still off-niche. Falling
        # through lets the ordinary pass swipe past it, which is the weak negative anyway.
        return False

    def _ensure_on_for_you(self, force_navigation: bool = False) -> bool:
        """Ensure we're on the For You feed."""
        self.logger.debug("📱 Ensuring on For You feed")
        
        # FIRST: Close any popups that might be blocking the screen
        self._handle_popups()
        time.sleep(0.3)
        
        # Check if already on For You
        if not force_navigation and self.detection.is_on_for_you_page():
            self.logger.debug("✅ Already on For You")
            return True
        
        # Close popups again in case they appeared
        self._handle_popups()
        
        # Navigate to home
        if not self.navigation.navigate_to_home():
            return False
        
        time.sleep(1)
        
        # Click For You tab if needed
        self.click.click_for_you_tab()
        time.sleep(0.5)
        
        # Close any popups that might have appeared
        self._handle_popups()
        
        return self.detection.is_on_for_you_page()
    
    def _process_current_video(self, video_info: Optional[Dict[str, Any]] = None):
        """Process the current video.
        
        Args:
            video_info: Pre-fetched video info, or None to fetch it now.
        """
        self.logger.debug(f"📹 Processing video #{self.stats.videos_watched + 1}")
        
        # Get video info if not provided
        if video_info is None:
            video_info = self.detection.get_video_info()
            # Send callback if we just fetched it
            if self._on_video_callback:
                try:
                    self._on_video_callback(video_info)
                except Exception as e:
                    self.logger.warning(f"Video callback error: {e}")
        
        self.logger.debug(f"📹 Video: @{video_info.get('author')} - "
                         f"likes: {video_info.get('like_count')}")
        
        # Watch video — honor the dwell planned (and emitted to the front) in the run
        # loop; draw one only if this call fetched its own video_info.
        watch_time = video_info.get('watch_time') or random.uniform(
            self.config.min_watch_time, self.config.max_watch_time)
        self.scroll.watch_video(watch_time)
        
        self.stats.videos_watched += 1
        self._send_stats_update()  # Real-time stats
        
        # Check if should skip
        if self._should_skip_video(video_info):
            self.stats.videos_skipped += 1
            self.logger.debug("⏭️ Skipping video (filters)")
            return
        
        # Decide actions
        self._decide_and_execute_actions(video_info)
    
    def _should_skip_video(self, video_info: Dict[str, Any]) -> bool:
        """Check if video should be skipped based on filters (incl. hashtags)."""
        # Skip if already liked and config says so
        if self.config.skip_already_liked and video_info.get('is_liked'):
            return True
        
        # Check like count filters
        like_count_str = video_info.get('like_count', '')
        if like_count_str:
            like_count = self._parse_count(like_count_str)
            
            if self.config.min_likes and like_count < self.config.min_likes:
                return True
            
            if self.config.max_likes and like_count > self.config.max_likes:
                return True
        
        # Check hashtag filters
        description = video_info.get('description', '') or ''
        
        # Required hashtags
        if self.config.required_hashtags:
            has_required = any(
                f"#{tag.lower()}" in description.lower() 
                for tag in self.config.required_hashtags
            )
            if not has_required:
                return True
        
        # Excluded hashtags
        if self.config.excluded_hashtags:
            has_excluded = any(
                f"#{tag.lower()}" in description.lower() 
                for tag in self.config.excluded_hashtags
            )
            if has_excluded:
                return True
        
        return False
    
    # _handle_suggestion_page and _handle_comments_section are provided
    # by FeedInterruptionsMixin. The mixin reads self.config.follow_back_suggestions
    # automatically (defaults to False if the attribute is absent).
    
