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
from dataclasses import dataclass, field
from loguru import logger
import time
import random

from taktik.core.database.local.service import get_local_database

from ...atomic.click_actions import ClickActions
from ...atomic.navigation_actions import NavigationActions
from ...atomic.scroll_actions import ScrollActions
from ._popup_handler import PopupHandler
from ...atomic.detection_actions import DetectionActions
from ....ui.selectors import FOLLOWERS_SELECTORS, SEARCH_SELECTORS, VIDEO_SELECTORS


@dataclass
class FollowersConfig:
    """Configuration pour le workflow Followers."""
    
    # Search query (required) - username to search for
    search_query: str = ""
    
    # Nombre de followers à traiter
    max_followers: int = 50
    
    # Nombre de posts à voir par profil
    posts_per_profile: int = 2
    
    # Watch time per video (seconds)
    min_watch_time: float = 5.0
    max_watch_time: float = 15.0
    
    # Probabilités d'interaction (0.0 à 1.0)
    like_probability: float = 0.7
    comment_probability: float = 0.1
    share_probability: float = 0.05
    favorite_probability: float = 0.3
    follow_probability: float = 0.5
    story_like_probability: float = 0.5  # Probability to like stories when encountered
    
    # Limites de session
    max_likes_per_session: int = 50
    max_follows_per_session: int = 30
    max_comments_per_session: int = 10
    
    # Délai entre les actions (secondes)
    min_delay: float = 1.0
    max_delay: float = 3.0
    
    # Pauses
    pause_after_actions: int = 10
    pause_duration_min: float = 30.0
    pause_duration_max: float = 60.0
    
    # Comportement
    include_friends: bool = False  # Inclure les comptes "Friends" (déjà amis)
    skip_private_accounts: bool = False


@dataclass
class FollowersStats:
    """Statistiques du workflow Followers."""
    
    followers_seen: int = 0
    profiles_visited: int = 0
    posts_watched: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    favorites: int = 0
    follows: int = 0
    already_friends: int = 0
    skipped: int = 0
    errors: int = 0
    completion_reason: str = ''
    
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        elapsed = time.time() - self.start_time
        return {
            'followers_seen': self.followers_seen,
            'profiles_visited': self.profiles_visited,
            'posts_watched': self.posts_watched,
            'likes': self.likes,
            'comments': self.comments,
            'shares': self.shares,
            'favorites': self.favorites,
            'follows': self.follows,
            'already_friends': self.already_friends,
            'skipped': self.skipped,
            'errors': self.errors,
            'completion_reason': self.completion_reason,
            'elapsed_seconds': elapsed,
            'elapsed_formatted': f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
        }


class FollowersWorkflow:
    """Workflow pour interagir avec les followers d'un utilisateur cible sur TikTok."""
    
    def __init__(self, device, config: FollowersConfig):
        self.device = device
        self.config = config
        self.stats = FollowersStats()
        self.logger = logger.bind(module="tiktok-followers-workflow")
        
        # Actions
        self.click = ClickActions(device)
        self.navigation = NavigationActions(device)
        self.scroll = ScrollActions(device)
        self.detection = DetectionActions(device)
        
        # Shared popup handler
        self._popup_handler = PopupHandler(self.click, self.detection)
        
        # Selectors
        self.followers_selectors = FOLLOWERS_SELECTORS
        self.search_selectors = SEARCH_SELECTORS
        self.video_selectors = VIDEO_SELECTORS
        
        # State
        self._running = False
        self._paused = False
        self._actions_since_pause = 0
        self._processed_usernames: Set[str] = set()  # Track usernames we've processed in this session
        self._current_profile_username = ""  # Username of the profile we're currently interacting with
        self._target_followers_count: int = 0  # Number of followers the target has
        self._already_visited_count: int = 0  # Number of target's followers we've already visited
        
        # Database
        self._db = get_local_database()
        self._account_id: Optional[int] = None
        self._session_id: Optional[int] = None
        
        # Callbacks
        self._on_action_callback: Optional[Callable] = None
        self._on_stats_callback: Optional[Callable] = None
        self._on_pause_callback: Optional[Callable] = None
        self._on_user_callback: Optional[Callable] = None
    
    def set_on_action_callback(self, callback: Callable):
        """Set callback for action events (like, follow, etc.)."""
        self._on_action_callback = callback
    
    def set_on_stats_callback(self, callback: Callable):
        """Set callback for stats updates."""
        self._on_stats_callback = callback
    
    def set_on_pause_callback(self, callback: Callable):
        """Set callback for pause events."""
        self._on_pause_callback = callback
    
    def set_on_user_callback(self, callback: Callable):
        """Set callback for user info events."""
        self._on_user_callback = callback
    
    def stop(self):
        """Stop the workflow."""
        self._running = False
        self.logger.info("🛑 Stopping Followers workflow")
    
    def _handle_popups(self):
        """Check for and close any popups that might block interaction."""
        return self._popup_handler.close_all()
    
    def pause(self):
        """Pause the workflow."""
        self._paused = True
        self.logger.info("⏸️ Pausing Followers workflow")
    
    def resume(self):
        """Resume the workflow."""
        self._paused = False
        self.logger.info("▶️ Resuming Followers workflow")
    
    def run(self, bot_username: str = None) -> FollowersStats:
        """Run the Followers workflow.
        
        Args:
            bot_username: Username of the TikTok bot account (for database tracking)
        """
        self._running = True
        self.stats = FollowersStats()
        self._processed_usernames.clear()
        
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
                    # No more followers found - use smart scroll logic
                    max_scroll_attempts = self._calculate_smart_scroll_attempts()
                    scroll_attempts = 0
                    found_new = False
                    consecutive_zero_buttons = 0  # Track consecutive scrolls with 0 buttons
                    
                    while scroll_attempts < max_scroll_attempts and not found_new:
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
                        
                        scroll_attempts += 1
                    
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
                        'errors': self.stats.errors,
                        'completion_reason': completion_reason
                    }
                )
                self.logger.info(f"📊 Database session {self._session_id} ended: {status} (reason: {completion_reason})")
            except Exception as e:
                self.logger.warning(f"Failed to end database session: {e}")
    
    def _navigate_to_followers_list(self) -> bool:
        """Navigate to the followers list of the target user."""
        self.logger.info(f"🔍 Navigating to followers of: {self.config.search_query}")
        
        try:
            # Open search
            if not self.navigation.open_search():
                self.logger.error("Failed to open search")
                return False
            
            self._human_delay()
            
            # Type search query
            if not self.navigation.search_and_submit(self.config.search_query):
                self.logger.error("Failed to submit search")
                return False
            
            self._human_delay()
            
            # Check if we accidentally landed on Inbox page (notification clicked)
            if self.detection.is_on_inbox_page():
                self.logger.warning("⚠️ Accidentally on Inbox page, going back...")
                self.click.escape_inbox_page()
                time.sleep(1)
                # Try search again
                if not self.navigation.open_search():
                    return False
                self._human_delay()
                if not self.navigation.search_and_submit(self.config.search_query):
                    return False
                self._human_delay()
            
            # Dismiss any notification banner that might interfere
            self.click.dismiss_notification_banner()
            
            # Click on Users tab
            if not self._click_users_tab():
                self.logger.warning("Could not click Users tab, trying to find users anyway")
            
            self._human_delay()
            
            # Click on first user result (the target user)
            if not self._click_first_user():
                self.logger.error("Failed to click on target user")
                return False
            
            self._human_delay()
            
            # Click on Followers counter to open followers list
            if not self._click_followers_counter():
                self.logger.error("Failed to open followers list")
                return False
            
            self._human_delay()
            
            self.logger.success("✅ Navigated to followers list")
            return True
            
        except Exception as e:
            self.logger.error(f"Error navigating to followers list: {e}")
            return False
    
    def _click_users_tab(self) -> bool:
        """Click on the Users tab in search results."""
        self.logger.debug("Clicking Users tab")
        selectors = self.followers_selectors.users_tab
        return self.click._find_and_click(selectors, timeout=5)
    
    def _click_first_user(self) -> bool:
        """Click on the first user in search results."""
        self.logger.debug("Clicking first user result")
        selectors = self.followers_selectors.first_user_result
        if self.click._find_and_click(selectors, timeout=5):
            return True
        selectors = self.followers_selectors.user_search_item
        return self.click._find_and_click(selectors, timeout=5)
    
    def _click_followers_counter(self) -> bool:
        """Click on the Followers counter to open followers list.
        
        Also extracts and stores the followers count for smart scroll logic.
        """
        self.logger.debug("Clicking Followers counter")
        selectors = self.followers_selectors.followers_counter
        
        # Try to extract followers count before clicking
        try:
            for selector in selectors:
                element = self.device.xpath(selector)
                if element and element.exists:
                    # Try to get the text which contains the count
                    text = element.get_text() or ''
                    # Parse count from text like "267 Followers" or "1.2K Followers"
                    count = self._parse_followers_count(text)
                    if count > 0:
                        self._target_followers_count = count
                        self.logger.info(f"📊 Target has {count} followers")
                        break
        except Exception as e:
            self.logger.debug(f"Could not extract followers count: {e}")
        
        # Get count of already visited followers for this target
        if self._account_id and self.config.search_query:
            self._already_visited_count = self._db.count_tiktok_interactions_for_target(
                self._account_id, 
                self.config.search_query,
                hours=168  # 7 days
            )
            self.logger.info(f"📊 Already visited {self._already_visited_count} followers of @{self.config.search_query}")
        
        return self.click._find_and_click(selectors, timeout=5)
    
    def _parse_followers_count(self, text: str) -> int:
        """Parse followers count from text like '267 Followers', '1.2K', '1M'."""
        import re
        if not text:
            return 0
        
        # Remove "Followers" and clean up
        text = text.lower().replace('followers', '').replace('follower', '').strip()
        
        # Handle K (thousands) and M (millions)
        multiplier = 1
        if 'k' in text:
            multiplier = 1000
            text = text.replace('k', '')
        elif 'm' in text:
            multiplier = 1000000
            text = text.replace('m', '')
        
        # Extract number
        match = re.search(r'[\d.]+', text)
        if match:
            try:
                return int(float(match.group()) * multiplier)
            except ValueError:
                pass
        return 0
    
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
            
            # Skip if already processed in this session (by username)
            if username and username in self._processed_usernames:
                continue
            
            # Skip if already interacted in database (past 7 days)
            if username and self._account_id:
                if self._db.check_tiktok_recent_interaction(username, self._account_id, hours=168):
                    self.logger.debug(f"Skipping @{username} - already interacted in past 7 days")
                    self._processed_usernames.add(username)
                    continue
            
            self.stats.followers_seen += 1
            
            # Check if this is a "Friends" account
            status = row_info.get('status', '')
            if status in ['Friends', 'Following'] and not self.config.include_friends:
                self.stats.already_friends += 1
                if username:
                    self._processed_usernames.add(username)
                self._send_stats_update()
                self._send_action('skip_friends', username or 'unknown')
                self.logger.debug(f"Skipping Friends/Following account @{username}")
                continue
            
            # Check if already interacted with this profile in database
            if username and self._account_id:
                try:
                    if self._db.has_tiktok_interaction(self._account_id, username):
                        self.stats.skipped += 1
                        self._processed_usernames.add(username)
                        self._send_stats_update()
                        self._send_action('skip_already_interacted', username)
                        self.logger.debug(f"Skipping already interacted profile @{username}")
                        continue
                except Exception as e:
                    self.logger.debug(f"Error checking interaction history: {e}")
            
            # Mark as processed by username
            if username:
                self._processed_usernames.add(username)
            
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
    
    def _find_follower_rows(self) -> List[Dict[str, Any]]:
        """Find all follower rows on screen with username extraction."""
        rows = []
        
        try:
            # Find all Follow/Friends/Following buttons in the followers list
            buttons = self.device.xpath('//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/rdh"]').all()
            
            self.logger.debug(f"Found {len(buttons)} follow buttons")
            
            for btn in buttons:
                try:
                    status = btn.text or ""
                    btn_info = btn.info
                    bounds = btn_info.get('bounds', {})
                    
                    # Extract username from the same row
                    # Username is in a sibling TextView with resource-id ygv
                    username = None
                    btn_top = bounds.get('top', 0)
                    btn_bottom = bounds.get('bottom', 0)
                    
                    # Find username TextViews and match by vertical position
                    username_elements = self.device.xpath('//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/ygv"]').all()
                    for elem in username_elements:
                        elem_bounds = elem.info.get('bounds', {})
                        elem_top = elem_bounds.get('top', 0)
                        elem_bottom = elem_bounds.get('bottom', 0)
                        
                        # Check if this username is in the same row (overlapping vertical bounds)
                        if elem_top < btn_bottom and elem_bottom > btn_top:
                            username = elem.text
                            break
                    
                    rows.append({
                        'button': btn,
                        'status': status,
                        'bounds': bounds,
                        'username': username,
                    })
                    self.logger.debug(f"Found follower @{username} with status: {status}")
                except Exception as e:
                    self.logger.debug(f"Error processing button: {e}")
                    continue
                    
        except Exception as e:
            self.logger.debug(f"Error finding follower rows: {e}")
        
        return rows
    
    def _click_follower_profile(self, row_info: Dict[str, Any]) -> bool:
        """Click on a follower's profile (the username text, not the avatar).
        
        IMPORTANT: We click on the USERNAME TEXT area, not the avatar!
        Clicking on the avatar opens the story if the user has one active.
        Clicking on the username text opens the profile directly.
        
        Layout of a follower row:
        [Avatar ~0-120] [Username/Name ~120-350] [Follow Button ~350+]
        """
        try:
            bounds = row_info.get('bounds', {})
            username = row_info.get('username', '')
            
            if bounds:
                top = bounds.get('top', 0)
                bottom = bounds.get('bottom', 0)
                
                # Click on the USERNAME area (center of the row, after avatar)
                # Avatar is roughly 0-120px, username text starts around 120-350px
                # We click at x=280 to be safely in the username/display name area
                click_x = 280  # Username text area (avoids avatar which triggers story)
                click_y = (top + bottom) // 2
                
                self.logger.debug(f"Clicking username area at ({click_x}, {click_y}) for @{username}")
                self.device.click(click_x, click_y)
                time.sleep(1.5)  # Wait for profile to load
                
                # Check if we accidentally landed on a story
                if self._is_on_story_page():
                    self.logger.info(f"📖 Landed on story for @{username}, handling story first...")
                    self._handle_story_view()
                
                return True
                
        except Exception as e:
            self.logger.debug(f"Error clicking follower profile: {e}")
        return False
    
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
            # Find posts in the grid - they have resource-id e52 and are clickable
            posts = self.device.xpath('//*[@resource-id="com.zhiliaoapp.musically:id/e52"][@clickable="true"]').all()
            count = len(posts)
            self.logger.debug(f"📊 Found {count} visible posts on profile")
            return count
        except Exception as e:
            self.logger.debug(f"Error counting posts: {e}")
            return 0
    
    def _click_profile_post(self, index: int = 0) -> bool:
        """Click on a post in the profile grid."""
        try:
            # Find posts in the grid
            posts = self.device.xpath('//*[@resource-id="com.zhiliaoapp.musically:id/e52"][@clickable="true"]').all()
            
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
            # Check for "Video liked" content-desc (already liked)
            liked_selectors = [
                '//*[@content-desc="Video liked"]',
                '//*[@resource-id="com.zhiliaoapp.musically:id/f4u"][@selected="true"]',
            ]
            for selector in liked_selectors:
                elem = self.device.xpath(selector)
                if elem.exists:
                    return True
        except Exception as e:
            self.logger.debug(f"Error checking if video liked: {e}")
        return False
    
    def _try_like_video(self) -> bool:
        """Try to like the current video."""
        try:
            # Use selectors that find unliked videos ("Like video" not "Video liked")
            like_selectors = [
                '//*[@content-desc="Like video"]',
                '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like video")]',
            ]
            for selector in like_selectors:
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
    
    def _get_current_profile_username(self) -> str:
        """Extract the username from the current profile page."""
        try:
            # Try to find username element on profile (starts with @)
            # Resource-id for username on profile: qh5
            username_elem = self.device.xpath('//*[@resource-id="com.zhiliaoapp.musically:id/qh5"]')
            if username_elem.exists:
                text = username_elem.get_text()
                if text:
                    # Remove @ prefix if present
                    return text.lstrip('@')
            
            # Fallback: try content-desc
            username_elem = self.device.xpath('//*[contains(@content-desc, "@")]')
            if username_elem.exists:
                desc = username_elem.info.get('contentDescription', '')
                if '@' in desc:
                    # Extract username from content-desc
                    parts = desc.split('@')
                    if len(parts) > 1:
                        return parts[1].split()[0]  # Get first word after @
                        
        except Exception as e:
            self.logger.debug(f"Error getting profile username: {e}")
        
        return "unknown"
    
    def _extract_and_save_profile_data(self):
        """Extract profile data from the current profile page and save to database.
        
        Extracts:
        - Display name (resource-id: qf8)
        - Username (resource-id: qh5)
        - Following count
        - Followers count
        - Likes count
        - Bio (if visible)
        - Videos count (from profile grid)
        """
        if not self._current_profile_username or self._current_profile_username == "unknown":
            return
        
        profile_data = {
            'username': self._current_profile_username,
            'display_name': None,
            'followers_count': 0,
            'following_count': 0,
            'likes_count': 0,
            'videos_count': 0,
            'biography': None,
            'is_private': False,
            'is_verified': False,
        }
        
        try:
            # Get display name (resource-id: qf8)
            display_elem = self.device.xpath('//*[@resource-id="com.zhiliaoapp.musically:id/qf8"]')
            if display_elem.exists:
                profile_data['display_name'] = display_elem.get_text()
            
            # Get stats - values have resource-id qfw, labels have resource-id qfv
            stat_values = self.device.xpath('//*[@resource-id="com.zhiliaoapp.musically:id/qfw"]').all()
            stat_labels = self.device.xpath('//*[@resource-id="com.zhiliaoapp.musically:id/qfv"]').all()
            
            for i, label_elem in enumerate(stat_labels):
                try:
                    label_text = (label_elem.text or '').lower()
                    if i < len(stat_values):
                        value_text = stat_values[i].text or '0'
                        count = self._parse_count_value(value_text)
                        
                        if 'following' in label_text:
                            profile_data['following_count'] = count
                        elif 'follower' in label_text:
                            profile_data['followers_count'] = count
                        elif 'like' in label_text:
                            profile_data['likes_count'] = count
                except Exception as e:
                    self.logger.debug(f"Error parsing stat {i}: {e}")
            
            # Get bio if visible (resource-id: qfx for bio text)
            bio_selectors = [
                '//*[@resource-id="com.zhiliaoapp.musically:id/qfx"]',  # Bio text
            ]
            for selector in bio_selectors:
                bio_elem = self.device.xpath(selector)
                if bio_elem.exists:
                    bio_text = bio_elem.get_text()
                    if bio_text and len(bio_text) > 3:
                        profile_data['biography'] = bio_text
                        break
            
            # Count visible videos in profile grid
            posts = self.device.xpath('//*[@resource-id="com.zhiliaoapp.musically:id/e52"][@clickable="true"]').all()
            if posts:
                profile_data['videos_count'] = len(posts)
            
            # Check for verified badge
            verified_elem = self.device.xpath('//*[contains(@content-desc, "Verified")]')
            if verified_elem.exists:
                profile_data['is_verified'] = True
            
            # Check for private account indicator
            private_elem = self.device.xpath('//*[contains(@text, "private")]')
            if private_elem.exists:
                profile_data['is_private'] = True
            
            # Save to database
            if self._db and self._account_id:
                try:
                    self._db.get_or_create_tiktok_profile(profile_data)
                    self.logger.debug(f"📊 Saved profile data for @{self._current_profile_username}: "
                                     f"{profile_data['followers_count']} followers, "
                                     f"{profile_data['likes_count']} likes")
                except Exception as e:
                    self.logger.debug(f"Error saving profile data: {e}")
                    
        except Exception as e:
            self.logger.debug(f"Error extracting profile data: {e}")
    
    def _parse_count_value(self, text: str) -> int:
        """Parse a count string like '1,750', '1.2K', '1.5M', '166 K' to an integer."""
        if not text:
            return 0
        
        try:
            text_str = str(text).strip().replace('\xa0', ' ').strip()
            
            multipliers = {
                'K': 1000, 'k': 1000,
                'M': 1000000, 'm': 1000000,
                'B': 1000000000, 'b': 1000000000
            }
            
            for suffix, multiplier in multipliers.items():
                if text_str.endswith(f' {suffix}') or text_str.endswith(f' {suffix.lower()}'):
                    number_part = text_str[:-2].strip().replace(',', '.')
                    return int(float(number_part) * multiplier)
                elif text_str.upper().endswith(suffix.upper()):
                    number_part = text_str[:-1].strip().replace(',', '.')
                    return int(float(number_part) * multiplier)
            
            number_str = text_str.replace(' ', '').replace(',', '')
            return int(float(number_str)) if number_str else 0
            
        except (ValueError, AttributeError):
            return 0
    
    def _is_on_video_page(self) -> bool:
        """Check if we're currently on a video playback page.
        
        Unique elements on video page:
        - Like button with content-desc="Video liked" or "Like"
        - resource-id="com.zhiliaoapp.musically:id/long_press_layout" with content-desc="Video"
        - Share button with content-desc containing "Share video"
        """
        try:
            # Check for video-specific elements
            video_selectors = [
                '//*[@resource-id="com.zhiliaoapp.musically:id/long_press_layout"][@content-desc="Video"]',
                '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][@content-desc="Video liked"]',
                '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like")]',
                '//*[contains(@content-desc, "Share video")]',
            ]
            for selector in video_selectors:
                if self.device.xpath(selector).exists:
                    return True
            return False
        except Exception as e:
            self.logger.debug(f"Error checking video page: {e}")
            return False
    
    def _is_on_profile_page(self) -> bool:
        """Check if we're currently on a user profile page.
        
        Unique elements on profile page:
        - Username with resource-id="com.zhiliaoapp.musically:id/qh5" (starts with @)
        - Stats labels (Following/Followers/Likes) with resource-id="com.zhiliaoapp.musically:id/qfv"
        - Follow back / Message buttons
        - Video grid with resource-id="com.zhiliaoapp.musically:id/gxd"
        - "No videos yet" message when profile has no posts
        """
        try:
            profile_selectors = [
                '//*[@resource-id="com.zhiliaoapp.musically:id/qh5"]',  # @username
                '//*[@resource-id="com.zhiliaoapp.musically:id/qfv"][@text="Followers"]',
                '//*[@resource-id="com.zhiliaoapp.musically:id/qfv"][@text="Following"]',
                '//*[@resource-id="com.zhiliaoapp.musically:id/gxd"]',  # Video grid
                '//*[@resource-id="com.zhiliaoapp.musically:id/w4m"][@text="No videos yet"]',  # No videos state
            ]
            for selector in profile_selectors:
                if self.device.xpath(selector).exists:
                    return True
            return False
        except Exception as e:
            self.logger.debug(f"Error checking profile page: {e}")
            return False
    
    def _is_on_story_page(self) -> bool:
        """Check if we're currently viewing a TikTok story.
        
        Story page unique elements:
        - Timestamp like "· 16h ago" with resource-id="com.zhiliaoapp.musically:id/xyx"
        - Close button with content-desc="Close"
        - Follow button with resource-id="com.zhiliaoapp.musically:id/rdo" (different from profile)
        - player_view for story video
        - Message input with text="Message..."
        """
        try:
            story_selectors = [
                '//*[@resource-id="com.zhiliaoapp.musically:id/xyx"]',  # Timestamp "· 16h ago"
                '//*[@content-desc="Close"][@clickable="true"]',  # Close button (X)
                '//*[@resource-id="com.zhiliaoapp.musically:id/rdo"]',  # Story Follow button
                '//*[@resource-id="com.zhiliaoapp.musically:id/qwz"][@text="Message..."]',  # Message input
            ]
            
            # Need at least 2 matches to confirm it's a story page
            matches = 0
            for selector in story_selectors:
                if self.device.xpath(selector).exists:
                    matches += 1
                    if matches >= 2:
                        return True
            
            return False
        except Exception as e:
            self.logger.debug(f"Error checking story page: {e}")
            return False
    
    def _handle_story_view(self):
        """Handle when we accidentally land on a story instead of profile.
        
        Strategy:
        1. Watch the story briefly (simulates human behavior)
        2. Optionally like the story
        3. Click on the username to go to the profile
        
        This turns an "accident" into an opportunity for engagement!
        """
        try:
            self.logger.info("📖 Handling story view...")
            
            # Watch story for a bit (human-like behavior)
            watch_time = random.uniform(3.0, 6.0)
            self.logger.debug(f"Watching story for {watch_time:.1f}s")
            time.sleep(watch_time)
            
            # Optionally like the story (use story_like_probability from config)
            if random.random() < self.config.story_like_probability:
                if self.stats.likes < self.config.max_likes_per_session:
                    if self._try_like_story():
                        self.stats.likes += 1
                        self._send_action('like_story', self._current_profile_username or 'unknown')
                        self._send_stats_update()
            
            # Now click on the username to go to the profile
            # The username/title is clickable and leads to the profile
            username_selectors = [
                '//*[@resource-id="com.zhiliaoapp.musically:id/title"][@clickable="true"]',
                '//*[@resource-id="com.zhiliaoapp.musically:id/s28"]//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/title"]',
            ]
            
            for selector in username_selectors:
                elem = self.device.xpath(selector)
                if elem.exists:
                    self.logger.debug("Clicking username to go to profile from story")
                    elem.click()
                    time.sleep(1.5)  # Wait for profile to load
                    
                    # Verify we're now on the profile
                    if self._is_on_profile_page():
                        self.logger.info("✅ Successfully navigated from story to profile")
                        return
                    break
            
            # Fallback: if clicking username didn't work, close the story
            self.logger.debug("Username click didn't work, closing story...")
            close_btn = self.device.xpath('//*[@content-desc="Close"][@clickable="true"]')
            if close_btn.exists:
                close_btn.click()
                time.sleep(1.0)
            else:
                # Last resort: press back
                self._go_back()
                time.sleep(1.0)
                
        except Exception as e:
            self.logger.debug(f"Error handling story view: {e}")
            # Try to recover by pressing back
            self._go_back()
            time.sleep(1.0)
    
    def _try_like_story(self) -> bool:
        """Try to like the current story."""
        try:
            # Story like button has content-desc containing "Like video"
            like_selectors = [
                '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like video")]',
                '//*[@resource-id="com.zhiliaoapp.musically:id/f4u"][@content-desc="Like"]',
            ]
            
            for selector in like_selectors:
                elem = self.device.xpath(selector)
                if elem.exists:
                    elem.click()
                    self.logger.info("❤️ Liked story")
                    self._human_delay()
                    return True
        except Exception as e:
            self.logger.debug(f"Error liking story: {e}")
        return False
    
    def _is_on_followers_list(self) -> bool:
        """Check if we're currently on the followers list page.
        
        Unique elements on followers list:
        - Tabs: "Following X" / "Followers X" / "Suggested" with selected state
        - RecyclerView with resource-id="com.zhiliaoapp.musically:id/s6p"
        - Follow buttons in the list with resource-id="com.zhiliaoapp.musically:id/rdh"
        - Text "Only X can see all followers"
        
        We need to be careful: profile pages also have some similar elements.
        The key differentiator is the presence of Follow buttons WITH the specific
        resource-id used in the followers list (rdh), not the profile Follow button.
        """
        try:
            # First, make sure we're NOT on a profile page (has @username element)
            # Profile pages have qh5 (the @username) which followers list doesn't have
            if self.device.xpath('//*[@resource-id="com.zhiliaoapp.musically:id/qh5"]').exists:
                return False
            
            # Check for followers list specific elements
            followers_list_selectors = [
                '//*[contains(@content-desc, "Followers")][@selected="true"]',  # Selected Followers tab
                '//*[@resource-id="com.zhiliaoapp.musically:id/s6p"]',  # Followers RecyclerView
            ]
            
            for selector in followers_list_selectors:
                if self.device.xpath(selector).exists:
                    return True
            
            # Also check for Follow buttons with the specific resource-id used in followers list
            # This is different from the profile Follow button which has resource-id eme
            follow_list_buttons = self.device.xpath('//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/rdh"]')
            if follow_list_buttons.exists:
                return True
            
            return False
        except Exception as e:
            self.logger.debug(f"Error checking followers list: {e}")
            return False
    
    def _safe_return_to_followers_list(self) -> bool:
        """Safely return to followers list with page verification.
        
        After interacting with videos, we need to:
        1. Press back to exit video → should land on profile page
        2. Press back again → should land on followers list
        
        Also handles edge cases like being on a story page.
        
        Returns:
            True if successfully returned to followers list, False otherwise.
        """
        max_attempts = 5  # Increased from 3 to handle edge cases
        
        for attempt in range(max_attempts):
            self.logger.debug(f"Return to followers list attempt {attempt + 1}/{max_attempts}")
            time.sleep(0.5)  # Small delay to let UI settle
            
            # Check current page state
            if self._is_on_followers_list():
                self.logger.debug("✅ Already on followers list")
                return True
            
            if self._is_on_story_page():
                # We're on a story page, close it first
                self.logger.debug("📖 On story page, closing story...")
                close_btn = self.device.xpath('//*[@content-desc="Close"][@clickable="true"]')
                if close_btn.exists:
                    close_btn.click()
                    time.sleep(1.0)
                else:
                    self._go_back()
                    time.sleep(1.0)
                continue  # Re-check state after closing story
            
            if self._is_on_video_page():
                # We're on video page, need to go back to profile first
                self.logger.debug("📹 On video page, pressing back to profile...")
                self._go_back()
                time.sleep(1.0)
                continue  # Re-check state after back
            
            if self._is_on_profile_page():
                # We're on profile page, need to go back to followers list
                self.logger.debug("👤 On profile page, pressing back to followers list...")
                self._go_back()
                time.sleep(1.0)
                
                # Verify we landed on followers list
                if self._is_on_followers_list():
                    self.logger.debug("✅ Successfully returned to followers list")
                    return True
                else:
                    self.logger.debug("⚠️ Did not land on followers list after back from profile")
                    continue
            
            # Unknown state, try pressing back
            self.logger.debug("❓ Unknown page state, pressing back...")
            self._go_back()
            time.sleep(1.0)
        
        self.logger.warning("❌ Failed to return to followers list after max attempts")
        return False
    
    def _recover_to_followers_list(self) -> bool:
        """Recovery procedure: restart TikTok and navigate back to followers list.
        
        This is called when normal navigation fails. We:
        1. Restart TikTok app
        2. Navigate to the target user's followers list
        3. Since we skip already-interacted profiles, we'll resume where we left off
        
        Returns:
            True if recovery successful, False otherwise.
        """
        self.logger.info("🔄 Starting recovery procedure...")
        
        try:
            # Restart TikTok
            self.logger.info("🔄 Restarting TikTok...")
            self.device.app_stop('com.zhiliaoapp.musically')
            time.sleep(1)
            self.device.app_start('com.zhiliaoapp.musically')
            time.sleep(4)  # Wait for app to fully load
            
            # Navigate back to followers list
            self.logger.info(f"🔄 Navigating back to followers of: {self.config.search_query}")
            if self._navigate_to_followers_list():
                self.logger.info("✅ Recovery successful - back on followers list")
                return True
            else:
                self.logger.error("❌ Recovery failed - could not navigate to followers list")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Recovery error: {e}")
            return False
    
    def _go_back(self):
        """Press back button to return to previous screen.
        
        Prioritizes in-app back button (for phones without system back button),
        falls back to system back if not found.
        """
        try:
            # In-app back button with content-desc="Back" (most reliable)
            back_selectors = [
                '//android.widget.ImageView[@content-desc="Back"]',
                '//*[@resource-id="com.zhiliaoapp.musically:id/b9b"][@content-desc="Back"]',
                '//*[@content-desc="Back"][@clickable="true"]',
            ]
            
            if self.click._find_and_click(back_selectors, timeout=2):
                time.sleep(0.5)
                return
            
            # Fallback: system back button
            self.device.press("back")
            time.sleep(0.5)
        except Exception as e:
            self.logger.debug(f"Error going back: {e}")
            self.device.press("back")
    
    def _scroll_followers_list(self):
        """Scroll the followers list to load more."""
        self.scroll.scroll_search_results(direction='down')
        time.sleep(0.5)
    
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
    
    def _check_pause_needed(self):
        """Check if a pause is needed and execute it."""
        if self._actions_since_pause >= self.config.pause_after_actions:
            pause_duration = random.uniform(
                self.config.pause_duration_min,
                self.config.pause_duration_max
            )
            
            self.logger.info(f"⏸️ Taking a break for {pause_duration:.0f}s")
            
            if self._on_pause_callback:
                try:
                    self._on_pause_callback(int(pause_duration))
                except Exception as e:
                    self.logger.warning(f"Pause callback error: {e}")
            
            time.sleep(pause_duration)
            self._actions_since_pause = 0
    
    def _send_stats_update(self):
        """Send stats update via callback."""
        if self._on_stats_callback:
            try:
                self._on_stats_callback(self.stats.to_dict())
            except Exception as e:
                self.logger.warning(f"Stats callback error: {e}")
    
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
