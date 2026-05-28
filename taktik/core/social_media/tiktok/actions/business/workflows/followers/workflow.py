"""Followers Workflow for TikTok automation.

Dernière mise à jour: 11 janvier 2026
Basé sur les UI dumps réels de TikTok.

Ce workflow permet d'interagir avec les followers d'un utilisateur cible:
1. Rechercher un utilisateur cible
2. Cliquer sur l'onglet Users
3. Ouvrir le profil de l'utilisateur cible
4. Cliquer sur le compteur Followers
5. Pour chaque follower dans la liste:
   a. Cliquer sur le profil du follower (pas le bouton Follow)
   b. Ouvrir un de ses posts
   c. Interagir (like, comment, share, favorite selon config)
   d. Retour au profil
   e. Retour à la liste des followers
   f. Passer au follower suivant
"""

from typing import Optional, Dict, Any, List, Callable, Set
import time
import random

from taktik.core.database.local.service import get_local_database
from taktik.core.social_media.tiktok.services.known_profiles_stop_policy import (
    KnownProfileDecision,
    KnownProfilesStopPolicy,
    normalize_username,
)
from taktik.core.social_media.tiktok.services.followers_list import (
    find_follower_rows,
    tap_follower_username,
)

from .._internal import BaseTikTokWorkflow
from .models import FollowersConfig, FollowersStats
from .page_detection import PageDetectionMixin
from .story_handling import StoryHandlingMixin
from .interaction import VideoInteractionMixin
from .profile_data import ProfileDataMixin
from .navigation import NavigationMixin
from .....ui.selectors import FOLLOWERS_SELECTORS, SEARCH_SELECTORS, VIDEO_SELECTORS


class FollowersWorkflow(
    PageDetectionMixin,
    StoryHandlingMixin,
    VideoInteractionMixin,
    ProfileDataMixin,
    NavigationMixin,
    BaseTikTokWorkflow,
):
    """Workflow pour interagir avec les followers d'un utilisateur cible sur TikTok.
    
    Inherits from BaseTikTokWorkflow:
        - atomic actions (click, navigation, scroll, detection)
        - popup handler + _handle_popups
        - lifecycle (stop/pause/resume/_wait_if_paused)
        - _send_stats_update, set_on_stats_callback
        - _check_pause_needed, set_on_pause_callback
    
    Mixins:
        - PageDetectionMixin: _is_on_video_page, _is_on_profile_page, _is_on_story_page, _is_on_followers_list
        - StoryHandlingMixin: _handle_story_view, _try_like_story
        - VideoInteractionMixin: _interact_with_profile_posts, like/favorite/follow actions
        - ProfileDataMixin: _get_current_profile_username, _extract_and_save_profile_data
        - NavigationMixin: _navigate_to_followers_list, _safe_return_to_followers_list, recovery
    """
    
    def __init__(self, device, config: FollowersConfig):
        super().__init__(device, module_name="tiktok-followers-workflow")
        self.config = config
        self.stats = FollowersStats()
        
        # Selectors
        self.followers_selectors = FOLLOWERS_SELECTORS
        self.search_selectors = SEARCH_SELECTORS
        self.video_selectors = VIDEO_SELECTORS
        
        # Followers-specific state
        self._processed_usernames: Set[str] = set()  # Track usernames we've processed in this session
        self._current_profile_username = ""  # Username of the profile we're currently interacting with
        self._target_followers_count: int = 0  # Number of followers the target has
        self._already_visited_count: int = 0  # Number of target's followers we've already visited
        self._known_profiles_policy = KnownProfilesStopPolicy(self.config.max_consecutive_known_usernames)
        self._known_stop_requested = False
        
        # Database
        self._db = get_local_database()
        self._account_id: Optional[int] = None
        self._session_id: Optional[int] = None
        
        # Followers-specific callbacks
        self._on_action_callback: Optional[Callable] = None
        self._on_user_callback: Optional[Callable] = None
    
    def set_on_action_callback(self, callback: Callable):
        """Set callback for action events (like, follow, etc.)."""
        self._on_action_callback = callback
    
    def run(self, bot_username: str = None) -> FollowersStats:
        """Run the Followers workflow.
        
        Args:
            bot_username: Username of the TikTok bot account (for database tracking)
        """
        self._running = True
        self.stats = FollowersStats()
        self._processed_usernames.clear()
        self._known_profiles_policy = KnownProfilesStopPolicy(self.config.max_consecutive_known_usernames)
        self._known_profiles_policy.reset()
        self._known_stop_requested = False
        
        self.logger.info(f"🚀 Starting Followers workflow for: {self.config.search_query}")
        self.logger.info(f"📊 Config: max_followers={self.config.max_followers}, posts_per_profile={self.config.posts_per_profile}")
        
        # Initialize database tracking
        if bot_username:
            try:
                self._account_id, _ = self._db.get_or_create_tiktok_account(bot_username)
                self._session_id = self._db.create_tiktok_session(
                    account_id=self._account_id,
                    session_name=f"Followers @{self.config.search_query}",
                    workflow_type='FOLLOWERS',
                    target=self.config.search_query,
                    config_used=self.config.to_dict() if hasattr(self.config, 'to_dict') else None
                )
                self.logger.info(f"📊 Database session created: {self._session_id}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize database tracking: {e}")
        
        try:
            # Navigate to target user's followers list
            if not self._navigate_to_followers_list():
                self.logger.error("❌ Failed to navigate to followers list")
                self._end_session('ERROR', 'Failed to navigate to followers list', completion_reason='navigation_failed')
                return self.stats
            
            # Process followers one by one
            completion_reason = 'unknown'
            
            while self._running and self.stats.profiles_visited < self.config.max_followers:
                # Check if paused
                while self._paused and self._running:
                    time.sleep(1)
                
                if not self._running:
                    completion_reason = 'stopped_by_user'
                    break
                
                # Handle any popups that might block interaction
                self._handle_popups()
                
                # Check limits
                limit_reached = self._check_limits_reached()
                if limit_reached:
                    completion_reason = limit_reached
                    self.logger.info(f"📊 Session limit reached: {limit_reached}")
                    break
                
                # Find and process next follower
                if not self._process_next_follower():
                    if self._known_stop_requested:
                        completion_reason = 'max_consecutive_known_usernames'
                        self.logger.info(
                            "Stopping target because consecutive known usernames limit was reached"
                        )
                        break

                    # No more followers found - use smart scroll logic
                    max_scroll_attempts = self._calculate_smart_scroll_attempts()
                    scroll_attempts = 0
                    found_new = False
                    consecutive_zero_buttons = 0  # Track consecutive scrolls with 0 buttons
                    
                    while (
                        scroll_attempts < max_scroll_attempts
                        and not found_new
                        and not self._known_stop_requested
                    ):
                        self.logger.debug(f"No new followers found, scrolling... (attempt {scroll_attempts + 1}/{max_scroll_attempts})")
                        self._scroll_followers_list()
                        # No need to clear _processed_usernames - usernames are stable across scrolls
                        time.sleep(1.0)  # Wait for content to load
                        
                        # Check if we can find any follow buttons at all
                        follower_rows = self._find_follower_rows()
                        if len(follower_rows) == 0:
                            consecutive_zero_buttons += 1
                            # If we've had 3+ scrolls with 0 buttons, we might not be on the followers list
                            if consecutive_zero_buttons >= 3:
                                self.logger.warning("⚠️ No follow buttons found after multiple scrolls, checking page state...")
                                if not self._is_on_followers_list():
                                    self.logger.warning("⚠️ Not on followers list! Attempting recovery...")
                                    if self._recover_to_followers_list():
                                        self.logger.info("✅ Recovery successful, continuing workflow")
                                        consecutive_zero_buttons = 0
                                        continue
                                    else:
                                        self.logger.error("❌ Recovery failed")
                                        break
                        else:
                            consecutive_zero_buttons = 0
                        
                        if self._process_next_follower():
                            found_new = True
                            break
                        if self._known_stop_requested:
                            break
                        
                        scroll_attempts += 1
                    
                    if self._known_stop_requested:
                        completion_reason = 'max_consecutive_known_usernames'
                        self.logger.info(
                            "Stopping target because consecutive known usernames limit was reached"
                        )
                        break

                    if not found_new:
                        completion_reason = 'no_more_followers'
                        visited_ratio = self._get_visited_ratio()
                        self.logger.info(f"No more followers to process after {scroll_attempts} scroll attempts (visited {visited_ratio:.0%} of target's followers)")
                        break
                
                # Check if pause needed
                self._check_pause_needed()
            
            # Determine completion reason if not already set
            if completion_reason == 'unknown':
                if self.stats.profiles_visited >= self.config.max_followers:
                    completion_reason = 'max_profiles_reached'
            
            self.logger.info(f"✅ Followers workflow completed: {self.stats.profiles_visited} profiles, {self.stats.likes} likes, {self.stats.follows} follows (reason: {completion_reason})")
            self._end_session('COMPLETED', completion_reason=completion_reason)
            
        except Exception as e:
            self.logger.error(f"❌ Error in Followers workflow: {e}")
            self.stats.errors += 1
            self._end_session('ERROR', str(e))
        
        return self.stats
    
    def _end_session(self, status: str, error_message: str = None, completion_reason: str = None):
        """End the database session with final stats.
        
        Args:
            status: Session status (COMPLETED, ERROR, etc.)
            error_message: Error message if status is ERROR
            completion_reason: Reason for completion (max_profiles_reached, max_likes_reached, etc.)
        """
        # Store completion reason for stats
        self.stats.completion_reason = completion_reason or 'unknown'
        
        if self._session_id and self._account_id:
            try:
                self._db.end_tiktok_session(
                    session_id=self._session_id,
                    status=status,
                    error_message=error_message,
                    stats={
                        'profiles_visited': self.stats.profiles_visited,
                        'posts_watched': self.stats.posts_watched,
                        'likes': self.stats.likes,
                        'follows': self.stats.follows,
                        'favorites': self.stats.favorites,
                        'comments': self.stats.comments,
                        'shares': self.stats.shares,
                        'known_usernames_seen': self.stats.known_usernames_seen,
                        'new_usernames_seen': self.stats.new_usernames_seen,
                        'consecutive_known_usernames': self.stats.consecutive_known_usernames,
                        'errors': self.stats.errors,
                        'completion_reason': completion_reason
                    }
                )
                self.logger.info(f"📊 Database session {self._session_id} ended: {status} (reason: {completion_reason})")
            except Exception as e:
                self.logger.warning(f"Failed to end database session: {e}")

    # ------------------------------------------------------------------
    # Follower processing (core loop body)
    # ------------------------------------------------------------------
    
    def _process_next_follower(self) -> bool:
        """Find and process the next unprocessed follower.
        
        Flow:
        1. Find follower rows in the list
        2. Check if username already processed (in session or in DB)
        3. Click on the profile (the row, not the Follow button)
        4. Open posts and interact
        5. Go back to followers list
        """
        # Find all follower rows
        follower_rows = self._find_follower_rows()
        
        for idx, row_info in enumerate(follower_rows):
            if not self._running:
                return False
            
            username = row_info.get('username', '')
            username_key = normalize_username(username)
            
            # Skip if already processed in this session (by username)
            if username_key and username_key in self._processed_usernames:
                if self._observe_username(username, is_known=True, reason='session_duplicate'):
                    return False
                continue
            
            # Skip if already interacted in database (past 7 days)
            if username and self._account_id:
                if self._db.check_tiktok_recent_interaction(username, self._account_id, hours=168):
                    self.logger.debug(f"Skipping @{username} - already interacted in past 7 days")
                    self._processed_usernames.add(username_key)
                    if self._observe_username(username, is_known=True, reason='recent_interaction'):
                        return False
                    continue
            
            self.stats.followers_seen += 1
            
            # Check if this is a "Friends" account
            status = row_info.get('status', '')
            if status in ['Friends', 'Following'] and not self.config.include_friends:
                self.stats.already_friends += 1
                if username_key:
                    self._processed_usernames.add(username_key)
                    if self._observe_username(username, is_known=True, reason='friends_or_following'):
                        return False
                self._send_stats_update()
                self._send_action('skip_friends', username or 'unknown')
                self.logger.debug(f"Skipping Friends/Following account @{username}")
                continue
            
            # Check if already interacted with this profile in database
            if username and self._account_id:
                try:
                    if self._db.has_tiktok_interaction(self._account_id, username):
                        self.stats.skipped += 1
                        self._processed_usernames.add(username_key)
                        if self._observe_username(username, is_known=True, reason='already_interacted'):
                            return False
                        self._send_stats_update()
                        self._send_action('skip_already_interacted', username)
                        self.logger.debug(f"Skipping already interacted profile @{username}")
                        continue
                except Exception as e:
                    self.logger.debug(f"Error checking interaction history: {e}")
            
            # Mark as processed by username
            if username_key:
                if self._observe_username(username, is_known=False, reason='eligible_profile'):
                    return False
                self._processed_usernames.add(username_key)
            
            # Click on the profile row (not the button)
            if not self._click_follower_profile(row_info):
                self.logger.warning("Failed to click follower profile")
                self.stats.errors += 1
                continue
            
            self._human_delay()
            
            # Now we're on the follower's profile - get username and interact
            self._current_profile_username = self._get_current_profile_username()
            self.stats.profiles_visited += 1
            self._send_stats_update()
            
            # Extract and save profile data (followers, likes, bio, etc.)
            self._extract_and_save_profile_data()
            
            # Send profile visit action for Live Activity
            self._send_action('profile_visit', self._current_profile_username)
            
            self.logger.info(f"👤 Visiting profile @{self._current_profile_username} ({self.stats.profiles_visited}/{self.config.max_followers})")
            
            # Interact with posts on this profile
            self._interact_with_profile_posts()
            
            # Optionally follow this user
            if random.random() < self.config.follow_probability:
                if self.stats.follows < self.config.max_follows_per_session:
                    self._try_follow_current_profile()
            
            # Safe return to followers list with verification
            if not self._safe_return_to_followers_list():
                self.logger.warning("⚠️ Failed to return to followers list, attempting recovery...")
                if not self._recover_to_followers_list():
                    self.logger.error("❌ Recovery failed, ending workflow")
                    return False
            
            self._human_delay()
            
            return True
        
        return False

    def _observe_username(self, username: str, *, is_known: bool, reason: str) -> bool:
        """Update username-based target exhaustion state.

        Returns True when the current target should stop because too many
        already-known usernames were encountered in a row.
        """
        decision = self._known_profiles_policy.observe(username, is_known=is_known)
        self._sync_known_profile_stats(decision)

        if decision.status == "ignored":
            return False

        self.logger.debug(
            "Known username policy: "
            f"@{decision.username} status={decision.status} reason={reason} "
            f"consecutive={decision.consecutive_known_usernames}/"
            f"{decision.max_consecutive_known_usernames}"
        )

        if not decision.should_stop:
            return False

        self._known_stop_requested = True
        self._send_stats_update()
        self.logger.info(
            "Known username limit reached for "
            f"@{self.config.search_query}: "
            f"{decision.consecutive_known_usernames}/"
            f"{decision.max_consecutive_known_usernames}"
        )
        return True

    def _sync_known_profile_stats(self, decision: KnownProfileDecision) -> None:
        self.stats.known_usernames_seen = decision.known_usernames_seen
        self.stats.new_usernames_seen = decision.new_usernames_seen
        self.stats.consecutive_known_usernames = decision.consecutive_known_usernames
    
    def _find_follower_rows(self) -> List[Dict[str, Any]]:
        """Find all follower rows on screen with username extraction."""
        return find_follower_rows(
            self.device,
            self.followers_selectors,
            logger=self.logger,
        )
    
    def _click_follower_profile(self, row_info: Dict[str, Any]) -> bool:
        """Click on a follower's profile (the username text, not the avatar).
        
        IMPORTANT: We click on the USERNAME TEXT area, not the avatar!
        Clicking on the avatar opens the story if the user has one active.
        Clicking on the username text opens the profile directly.
        
        Layout of a follower row:
        [Avatar ~0-120] [Username/Name ~120-350] [Follow Button ~350+]
        """
        try:
            username = row_info.get('username', '')

            if not tap_follower_username(self.device, row_info, logger=self.logger):
                return False

            # Check if we accidentally landed on a story
            if self._is_on_story_page():
                self.logger.info(f"📖 Landed on story for @{username}, handling story first...")
                self._handle_story_view()

            return True

        except Exception as e:
            self.logger.debug(f"Error clicking follower profile: {e}")
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    
    def _check_limits_reached(self) -> str:
        """Check if session limits have been reached.
        
        Returns:
            str: The limit reason if reached, empty string otherwise.
            Possible values: 'max_likes_reached', 'max_follows_reached', ''
        """
        if self.stats.likes >= self.config.max_likes_per_session:
            return 'max_likes_reached'
        if self.stats.follows >= self.config.max_follows_per_session:
            return 'max_follows_reached'
        return ''
    
    def _send_action(self, action: str, target: str = ""):
        """Send action event via callback."""
        if self._on_action_callback:
            try:
                self._on_action_callback({'action': action, 'target': target})
            except Exception as e:
                self.logger.warning(f"Action callback error: {e}")
    
    def _human_delay(self):
        """Add a human-like delay."""
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        time.sleep(delay)
    
    def _calculate_smart_scroll_attempts(self) -> int:
        """Calculate the number of scroll attempts based on visited ratio.
        
        Logic:
        - If we know the target's follower count and how many we've visited,
          we can estimate how many scrolls are needed to find new followers.
        - If we've visited < 50% of followers, scroll more aggressively
        - If we've visited > 80% of followers, we're likely near the end
        - If we don't have total count but have visited count, use heuristics
        
        Returns:
            Number of scroll attempts to make before giving up.
        """
        total_visited = self._already_visited_count + self.stats.profiles_visited
        
        # If we have the target's follower count, use ratio-based logic
        if self._target_followers_count > 0:
            visited_ratio = total_visited / self._target_followers_count
            remaining = self._target_followers_count - total_visited
            
            self.logger.debug(f"📊 Smart scroll: {total_visited}/{self._target_followers_count} visited ({visited_ratio:.0%}), {remaining} remaining")
            
            if visited_ratio >= 0.9:
                # We've visited 90%+ of followers - very few left, minimal scrolling
                return 5
            elif visited_ratio >= 0.7:
                # We've visited 70-90% - some left, moderate scrolling
                return 10
            elif visited_ratio >= 0.5:
                # We've visited 50-70% - many left, more scrolling
                return 15
            else:
                # We've visited < 50% - lots of followers left, scroll aggressively
                return 20
        
        # Fallback: we don't know total count, but we know how many we've visited
        # Use heuristics based on visited count
        if total_visited > 0:
            # If we've visited many profiles, there are likely more to find
            # Scroll more aggressively to find them
            if total_visited < 50:
                scroll_attempts = 15  # We've visited few, likely many more exist
            elif total_visited < 100:
                scroll_attempts = 10  # Moderate visited count
            else:
                scroll_attempts = 5   # We've visited many, might be near the end
            
            self.logger.debug(f"📊 Smart scroll (no total): {total_visited} visited, using {scroll_attempts} scroll attempts")
            return scroll_attempts
        
        # No data at all - use default
        self.logger.debug("📊 Smart scroll: no data, using default 3 attempts")
        return 3
    
    def _get_visited_ratio(self) -> float:
        """Get the ratio of visited followers to total followers.
        
        Returns:
            Ratio between 0.0 and 1.0, or 0.0 if unknown.
        """
        if self._target_followers_count == 0:
            return 0.0
        
        total_visited = self._already_visited_count + self.stats.profiles_visited
        return min(total_visited / self._target_followers_count, 1.0)
