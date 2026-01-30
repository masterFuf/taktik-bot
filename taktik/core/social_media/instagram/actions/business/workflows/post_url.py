"""Business logic for Instagram post URL interactions."""

from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
import random
import re
import time

from ...core.base_business_action import BaseBusinessAction
from ..common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service

class PostUrlBusiness(BaseBusinessAction):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "post-url", init_business_modules=True)
        self.default_config = {
            'max_interactions': 20,
            'like_percentage': 70,
            'follow_percentage': 15,
            'comment_percentage': 5,
            'story_watch_percentage': 10,
            'max_likes_per_profile': 3,
            'min_likes_per_profile': 2  # Changed from 1 to 2
        }
    
    def interact_with_post_likers(self, post_url: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        🆕 NOUVEAU WORKFLOW: Navigation directe dans la liste des likers.
        
        Au lieu de scraper tous les likers puis naviguer via deeplink, on:
        1. Ouvre le post via deeplink
        2. Ouvre la popup des likers
        3. Pour chaque liker visible: clic direct → interaction → back
        4. Scroll seulement quand tous les visibles sont traités
        
        Avantages:
        - ❌ Plus de deeplinks pour chaque profil (pattern suspect)
        - ✅ Navigation 100% naturelle par clics
        - ✅ Comportement humain réaliste
        """
        effective_config = {**self.default_config, **(config or {})}
        
        self.logger.info(f"[DEBUG] POST_URL config received: {config}")
        self.logger.info(f"[DEBUG] POST_URL effective config: max_interactions={effective_config.get('max_interactions', 'N/A')}")
        
        max_interactions = effective_config.get('max_interactions_per_session', effective_config.get('max_interactions', 20))
        self.current_max_interactions = max_interactions
        self.logger.info(f"Max interactions target: {max_interactions}")
        
        stats = {
            'post_url': post_url,
            'users_found': 0,
            'users_interacted': 0,
            'likes_made': 0,
            'follows_made': 0,
            'comments_made': 0,
            'stories_watched': 0,
            'stories_liked': 0,
            'profiles_filtered': 0,
            'skipped': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            self.logger.info(f"Starting Post URL workflow (direct navigation): {post_url}")
            self.logger.info(f"Max interactions: {max_interactions}")
            
            if not self._validate_instagram_url(post_url):
                self.logger.error("Invalid Instagram URL")
                stats['errors'] += 1
                return stats
            
            # 1. Naviguer vers le post via deeplink
            if not self.nav_actions.navigate_to_post_via_deep_link(post_url):
                self.logger.error("Failed to navigate to post")
                stats['errors'] += 1
                return stats
            
            time.sleep(2)
            
            # Extraire les métadonnées du post
            post_metadata = {
                'author_username': self._extract_author_username(),
                'likes_count': self.ui_extractors.extract_likes_count_from_ui(),
                'is_reel': self._is_reel_post()
            }
            
            if not post_metadata.get('author_username'):
                self.logger.error("Failed to extract author username")
                stats['errors'] += 1
                return stats
            
            self.logger.info(f"Post from @{post_metadata['author_username']} - {post_metadata['likes_count']} likes")
            
            # Validation des limites
            validation_result = self._validate_interaction_limits(post_metadata, effective_config)
            if not validation_result['valid']:
                self.logger.warning(f"⚠️ {validation_result['warning']}")
                if validation_result.get('suggestion'):
                    self.logger.info(f"💡 Suggestion: {validation_result['suggestion']}")
                if validation_result.get('adjusted_max'):
                    max_interactions = validation_result['adjusted_max']
                    self.current_max_interactions = max_interactions
                    self.logger.info(f"✅ Adjusted max interactions to {max_interactions}")
            
            # 2. Ouvrir la popup des likers
            is_reel = post_metadata.get('is_reel', False)
            if not self._open_likers_popup(is_reel):
                self.logger.error("Failed to open likers popup")
                stats['errors'] += 1
                return stats
            
            # Démarrer la phase d'interaction
            if self.session_manager:
                self.session_manager.start_interaction_phase()
            
            self.logger.info(f"🚀 Starting direct interactions in likers list (target: {max_interactions})")
            
            # Variables pour le suivi
            processed_usernames = set()
            scroll_attempts = 0
            max_scroll_attempts = 50
            account_id = getattr(self.automation, 'active_account_id', None) if self.automation else None
            session_id = getattr(self.automation, 'current_session_id', None) if self.automation else None
            
            effective_config['source'] = post_url
            
            # 3. Boucle principale d'interaction directe
            while stats['users_interacted'] < max_interactions and scroll_attempts < max_scroll_attempts:
                # Vérifier si la session doit continuer
                if self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        break
                
                # Récupérer les likers visibles avec leurs éléments cliquables
                visible_likers = self.detection_actions.get_visible_followers_with_elements()
                
                if not visible_likers:
                    self.logger.debug("No visible likers found on screen")
                    scroll_attempts += 1
                    self._scroll_likers_popup_up()
                    self._human_like_delay('scroll')
                    continue
                
                new_likers_found = False
                
                for liker_data in visible_likers:
                    username = liker_data['username']
                    
                    # Skip si déjà traité dans cette session
                    if username in processed_usernames:
                        continue
                    
                    processed_usernames.add(username)
                    new_likers_found = True
                    stats['users_found'] += 1
                    
                    # Vérifier si déjà traité OU déjà filtré en DB
                    should_skip, skip_reason = DatabaseHelpers.is_profile_skippable(username, account_id, hours_limit=24*60)
                    if should_skip:
                        if skip_reason == "already_processed":
                            self.logger.info(f"🔄 @{username} already processed")
                        elif skip_reason == "already_filtered":
                            self.logger.info(f"🚫 @{username} already filtered")
                            stats['profiles_filtered'] += 1
                        stats['skipped'] += 1
                        self.stats_manager.increment('skipped')
                        continue
                    
                    # Afficher la progression
                    self.logger.info(f"[{stats['users_interacted']}/{max_interactions}] 👆 Clicking on @{username}")
                    
                    # Cliquer sur le profil dans la liste
                    if not self.detection_actions.click_follower_in_list(username):
                        self.logger.warning(f"Could not click on @{username}")
                        stats['errors'] += 1
                        continue
                    
                    self._human_like_delay('navigation')
                    
                    # Vérifier qu'on est bien sur un profil
                    if not self.detection_actions.is_on_profile_screen():
                        self.logger.warning(f"Not on profile screen after clicking @{username}")
                        if not self._ensure_on_likers_popup():
                            self.logger.error("Could not recover to likers popup, stopping")
                            break
                        stats['errors'] += 1
                        continue
                    
                    # Extraire les infos du profil
                    profile_data = self.profile_business.get_complete_profile_info(
                        username=username, 
                        navigate_if_needed=False
                    )
                    
                    if not profile_data:
                        self.logger.warning(f"Could not get profile data for @{username}")
                        if not self._ensure_on_likers_popup(force_back=True):
                            self.logger.error("Could not recover to likers popup, stopping")
                            break
                        stats['errors'] += 1
                        continue
                    
                    # Vérifier si profil privé
                    if profile_data.get('is_private', False):
                        self.logger.info(f"🔒 Private profile @{username} - skipped")
                        stats['skipped'] += 1
                        self.stats_manager.increment('private_profiles')
                        DatabaseHelpers.record_filtered_profile(
                            username=username,
                            reason='Private profile',
                            source_type='POST_URL',
                            source_name=post_url,
                            account_id=account_id,
                            session_id=session_id
                        )
                        if not self._ensure_on_likers_popup(force_back=True):
                            self.logger.error("Could not recover to likers popup, stopping")
                            break
                        continue
                    
                    # Appliquer les filtres
                    filter_criteria = effective_config.get('filter_criteria', {})
                    filter_result = self.filtering_business.apply_comprehensive_filter(
                        profile_data, filter_criteria
                    )
                    
                    if not filter_result.get('suitable', False):
                        reasons = filter_result.get('reasons', [])
                        self.logger.info(f"🚫 @{username} filtered: {', '.join(reasons)}")
                        stats['profiles_filtered'] += 1
                        self.stats_manager.increment('profiles_filtered')
                        DatabaseHelpers.record_filtered_profile(
                            username=username,
                            reason=', '.join(reasons),
                            source_type='POST_URL',
                            source_name=post_url,
                            account_id=account_id,
                            session_id=session_id
                        )
                        if not self._ensure_on_likers_popup(force_back=True):
                            self.logger.error("Could not recover to likers popup, stopping")
                            break
                        continue
                    
                    # === EFFECTUER LES INTERACTIONS ===
                    interaction_result = self._perform_post_url_interactions(
                        username, 
                        effective_config, 
                        profile_data=profile_data
                    )
                    
                    if interaction_result and interaction_result.get('actually_interacted', False):
                        stats['users_interacted'] += 1
                        stats['likes_made'] += interaction_result.get('likes', 0)
                        stats['follows_made'] += interaction_result.get('follows', 0)
                        stats['comments_made'] += interaction_result.get('comments', 0)
                        stats['stories_watched'] += interaction_result.get('stories', 0)
                        stats['stories_liked'] += interaction_result.get('stories_liked', 0)
                        
                        DatabaseHelpers.mark_profile_as_processed(username, post_url, account_id, session_id)
                        
                        self.logger.success(f"✅ Successful interaction with @{username}")
                        self.stats_manager.increment('profiles_visited')
                        self.stats_manager.increment('profiles_interacted')
                        
                        if interaction_result.get('likes', 0) > 0:
                            self.stats_manager.increment('likes', interaction_result['likes'])
                        if interaction_result.get('follows', 0) > 0:
                            self.stats_manager.increment('follows', interaction_result['follows'])
                        if interaction_result.get('stories', 0) > 0:
                            self.stats_manager.increment('stories_watched', interaction_result['stories'])
                        if interaction_result.get('stories_liked', 0) > 0:
                            self.stats_manager.increment('stories_liked', interaction_result['stories_liked'])
                        
                        self.stats_manager.display_stats(current_profile=username)
                    else:
                        self.logger.debug(f"@{username} visited but no interaction (probability)")
                        stats['skipped'] += 1
                    
                    # Retour à la liste des likers
                    if not self._ensure_on_likers_popup(force_back=True):
                        self.logger.error("Could not return to likers popup, stopping")
                        break
                    
                    # Vérifier si on a atteint le max
                    if stats['users_interacted'] >= max_interactions:
                        self.logger.info(f"✅ Reached target of {max_interactions} successful interactions")
                        break
                    
                    self._human_like_delay('interaction_gap')
                
                # Si aucun nouveau liker trouvé, scroller
                if not new_likers_found:
                    scroll_attempts += 1
                    self._scroll_likers_popup_up()
                    self._human_like_delay('scroll')
                else:
                    scroll_attempts = 0
            
            stats['success'] = stats['users_interacted'] > 0
            self.logger.info(f"Workflow completed: {stats['users_interacted']} interactions out of {stats['users_found']} users")
            
            self.stats_manager.display_final_stats(workflow_name="POST_URL")
            
        except Exception as e:
            self.logger.error(f"General error in Post URL workflow: {e}")
            stats['errors'] += 1
            self.stats_manager.add_error(f"General error: {e}")
        real_stats = self.stats_manager.to_dict()
        return {
            'post_url': stats.get('post_url', ''),
            'users_found': stats.get('users_found', 0),
            'users_interacted': real_stats.get('profiles_visited', 0),
            'likes_made': real_stats.get('likes', 0),
            'follows_made': real_stats.get('follows', 0),
            'comments_made': real_stats.get('comments', 0),
            'stories_watched': real_stats.get('stories_watched', 0),
            'skipped': stats.get('skipped', 0),
            'errors': real_stats.get('errors', 0),
            'success': real_stats.get('profiles_visited', 0) > 0
        }
    
    def _validate_instagram_url(self, url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        
        instagram_patterns = [
            r'https?://(www\.)?instagram\.com/p/[A-Za-z0-9_-]+/?',
            r'https?://(www\.)?instagram\.com/reel/[A-Za-z0-9_-]+/?',
            r'https?://(www\.)?instagram\.com/tv/[A-Za-z0-9_-]+/?'
        ]
        
        for pattern in instagram_patterns:
            if re.match(pattern, url.strip()):
                self.logger.debug(f"Valid URL detected: {pattern}")
                return True
        
        self.logger.debug(f"Invalid URL: {url}")
        return False
    
    def _extract_post_metadata_from_url(self, post_url: str) -> Optional[Dict[str, Any]]:
        try:
            self.logger.debug(f"Navigating to post: {post_url}")
            
            if not self.nav_actions.navigate_to_post_via_deep_link(post_url):
                self.logger.error("Failed to navigate to post")
                return None
            
            time.sleep(3)
            
            metadata = {
                'author_username': self._extract_author_username(),
                'likes_count': self.ui_extractors.extract_likes_count_from_ui(),
                'comments_count': self.ui_extractors.extract_comments_count_from_ui(),
                'is_reel': self._is_reel_post()
            }
            
            if not metadata['author_username']:
                self.logger.error("Failed to extract author username")
                return None
            
            self.logger.info(f"Metadata extracted: @{metadata['author_username']}, {metadata['likes_count']} likes, {metadata['comments_count']} comments")
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata: {e}")
            return None
    
    def _extract_author_username(self) -> Optional[str]:
        try:
            import re
            
            # PRIORITY 1: Try extracting from Reel-specific content-desc (e.g., "Reel by username")
            try:
                reel_container = self.device.xpath('//*[contains(@content-desc, "Reel by")]')
                if reel_container.exists:
                    content_desc = reel_container.info.get('contentDescription', '')
                    self.logger.debug(f"Reel container content-desc: '{content_desc}'")
                    username_match = re.search(r'Reel by ([a-zA-Z0-9_.]+)', content_desc)
                    if username_match:
                        username = username_match.group(1)
                        if self._is_valid_username(username):
                            self.logger.debug(f"Username found from Reel content-desc: @{username}")
                            return username
            except Exception as e:
                self.logger.debug(f"Error extracting from Reel content-desc: {e}")
            
            # PRIORITY 2: Try extracting from profile image content-desc (works for both posts and Reels)
            for selector in self.post_selectors.profile_image_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element_info = element.info
                        content_desc = element_info.get('contentDescription', '')
                        self.logger.debug(f"Profile image content-desc: '{content_desc}'")
                        if content_desc:
                            import re
                            # Try French format first
                            username_match = re.search(r'Photo de profil de ([a-zA-Z0-9_.]+)', content_desc)
                            if not username_match:
                                # Try English format (for Reels)
                                username_match = re.search(r'Profile picture of ([a-zA-Z0-9_.]+)', content_desc)
                            if username_match:
                                username = username_match.group(1)
                                self.logger.debug(f"Extracted username from profile image: '{username}'")
                                if self._is_valid_username(username):
                                    self.logger.debug(f"Username found from profile image: @{username}")
                                    return username
                except Exception as e:
                    self.logger.debug(f"Error with profile image selector {selector}: {e}")
                    continue
            
            for selector in self.post_selectors.header_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element_info = element.info
                        content_desc = element_info.get('contentDescription', '')
                        self.logger.debug(f"Header content-desc: '{content_desc}'")
                        if content_desc:
                            import re
                            username_match = re.match(r'^([a-zA-Z0-9_.]+)', content_desc)
                            if username_match:
                                username = username_match.group(1)
                                self.logger.debug(f"Extracted potential username: '{username}'")
                                if self._is_valid_username(username):
                                    self.logger.debug(f"Username found from header: @{username}")
                                    return username
                except Exception as e:
                    self.logger.debug(f"Error with header selector {selector}: {e}")
                    continue
            
            for selector in self.post_selectors.username_extraction_selectors:
                try:
                    text = self._get_text_from_element(selector)
                    if text and self._is_valid_username(text.lstrip('@')):
                        username = text.strip().lstrip('@')
                        self.logger.debug(f"Username found from text: @{username}")
                        return username
                except Exception as e:
                    self.logger.debug(f"Error with text selector {selector}: {e}")
                    continue
            
            self.logger.warning("Author username not found")
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting username: {e}")
            return None
    
    def _is_valid_username(self, username: str) -> bool:
        if not username or len(username) < 1 or len(username) > 30:
            return False
        
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._]*$', username):
            return False
        
        ui_texts = ['j\'aime', 'likes', 'vues', 'views', 'abonné', 'suivre', 'follow']
        if username.lower() in ui_texts:
            return False
        
        return True
    
    
    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return super()._interact_with_user(username, config)
    
    def _get_filter_criteria_from_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return super()._get_filter_criteria_from_config(config)
    
    def _determine_interactions_from_config(self, config: Dict[str, Any]) -> List[str]:
        return super()._determine_interactions_from_config(config)
    
    def _calculate_adaptive_tolerance(self, target_likes: int) -> int:
        """
        Calculate adaptive tolerance based on post popularity.
        
        Strategy:
        - Small posts (<500 likes): ±5 likes tolerance (~1-5%)
        - Medium posts (500-2000): ±15 likes tolerance (~1-3%)
        - Popular posts (2000-10000): ±50 likes tolerance (~0.5-2.5%)
        - Viral posts (10000-50000): ±100 likes tolerance (~0.2-1%)
        - Mega viral (>50000): ±200 likes tolerance (~0.4%)
        
        Args:
            target_likes: Number of likes on the target post
            
        Returns:
            int: Tolerance threshold
        """
        if target_likes < 500:
            return 5
        elif target_likes < 2000:
            return 15
        elif target_likes < 10000:
            return 50
        elif target_likes < 50000:
            return 100
        else:
            return 200
    
    def _find_and_extract_likers_from_profile(self, post_metadata: Dict[str, Any]) -> List[str]:
        try:
            self.logger.info(f"Searching for post with {post_metadata['likes_count']} likes, {post_metadata['comments_count']} comments")
            
            self.logger.debug("Attempting to open first post...")
            if not self._open_first_post_in_grid():
                self.logger.error("Failed to open first post")
                return []
            
            self.logger.debug("First post opened, starting search...")
            
            max_scrolls = 500
            scroll_count = 0
            detected_posts = []
            posts_checked = 0
            duplicate_count = 0
            
            self.logger.debug(f"Starting search loop (max {max_scrolls} scrolls)")
            while scroll_count < max_scrolls and posts_checked < 50:
                # Vérifier si la session doit continuer (durée, limites, etc.)
                if hasattr(self, 'session_manager') and self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        return None
                
                try:
                    self.logger.debug("Extracting current post metadata...")
                    
                    # Try atomic extraction first (prevents timing issues during scroll)
                    stats = self.ui_extractors.extract_post_stats_atomic()
                    
                    if stats:
                        current_likes = stats['likes']
                        current_comments = stats['comments']
                    else:
                        # Fallback to separate extraction
                        current_likes = self.ui_extractors.extract_likes_count_from_ui()
                        current_comments = self.ui_extractors.extract_comments_count_from_ui()
                    
                    post_signature = (current_likes, current_comments)
                    
                    if post_signature in detected_posts:
                        duplicate_count += 1
                        self.logger.debug(f"Duplicate post (scroll #{scroll_count + 1}): {current_likes} likes, {current_comments} comments")
                        if duplicate_count >= 5:
                            self.logger.warning("Too many duplicates, ending search")
                            break
                    else:
                        duplicate_count = 0
                        posts_checked += 1
                        detected_posts.append(post_signature)
                        
                        self.logger.info(f"UNIQUE POST #{posts_checked}: {current_likes} likes, {current_comments} comments | TARGET: {post_metadata['likes_count']} likes, {post_metadata['comments_count']} comments")
                        
                        # Exact match - best case
                        if current_likes == post_metadata['likes_count'] and current_comments == post_metadata['comments_count']:
                            self.logger.success(f"✅ Exact post found (post #{posts_checked})!")
                            return self._extract_likers_from_current_post()
                        
                        # Adaptive tolerance based on post popularity
                        likes_diff = abs(current_likes - post_metadata['likes_count'])
                        adaptive_tolerance = self._calculate_adaptive_tolerance(post_metadata['likes_count'])
                        
                        # Comments must match exactly (they change less frequently)
                        if likes_diff <= adaptive_tolerance and current_comments == post_metadata['comments_count']:
                            self.logger.success(f"✅ Matching post found (likes diff: {likes_diff}/{adaptive_tolerance}, post #{posts_checked})!")
                            return self._extract_likers_from_current_post()
                    
                except Exception as e:
                    self.logger.debug(f"Error checking scroll #{scroll_count + 1}: {e}")
                
                self.logger.debug(f"Vertical scroll #{scroll_count + 1}")
                # Adaptive swipe coordinates
                width, height = self.device.get_screen_size()
                center_x = width // 2
                start_y = int(height * 0.89)  # ~89% of height
                end_y = int(height * 0.16)    # ~16% of height
                self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.7)
                time.sleep(2.5)
                scroll_count += 1
            
            self.logger.warning(f"Matching post not found after {posts_checked} unique posts ({scroll_count} scrolls)")
            return []
            
        except Exception as e:
            self.logger.error(f"Error searching for post: {e}")
            return []
    
    def _open_first_post_in_grid(self) -> bool:
        try:
            first_post = self.device.xpath(self.post_selectors.first_post_grid)
            if first_post.exists:
                self.logger.debug("Opening first post")
                first_post.click()
                time.sleep(3)
                return True
            else:
                self.logger.error("First post not found")
                return False
        except Exception as e:
            self.logger.error(f"Error opening first post: {e}")
            return False
    
    def _extract_likers_from_current_post(self) -> List[str]:
        try:
            if self._is_reel_post():
                self.logger.debug("Reel type post detected")
                return self._extract_likers_from_reel()
            else:
                self.logger.debug("Regular post detected")
                return self._extract_likers_from_regular_post()
                
        except Exception as e:
            self.logger.error(f"Error extracting likers: {e}")
            return []
    
    def _extract_likers_from_regular_post(self) -> List[str]:
        return super()._extract_likers_from_regular_post(max_interactions=None, multiply_by=2)
    
    def _extract_likers_from_reel(self) -> List[str]:
        return super()._extract_likers_from_reel(max_interactions=None, multiply_by=2)
    
    def _find_like_count_element(self):
        return self.ui_extractors.find_like_count_element(logger_instance=self.logger)
    
    def _is_like_count_text(self, text: str) -> bool:
        return self.ui_extractors.is_like_count_text(text)
    
    def _extract_usernames_from_likers_popup(self) -> List[str]:
        max_users = getattr(self, 'current_max_interactions', self.default_config['max_interactions'])
        
        return self.ui_extractors.extract_usernames_from_likers_popup(
            current_max_interactions_attr=max_users,
            automation=self.automation,
            logger_instance=self.logger,
            add_initial_sleep=False
        )
    
    def _extract_visible_usernames(self) -> List[str]:
        return self.ui_extractors.extract_visible_usernames(logger_instance=self.logger)
    
    def _extract_username_from_element(self, element) -> Optional[str]:
        return self.ui_extractors.extract_username_from_element(element, logger_instance=self.logger)
    
    def _scroll_likers_popup_up(self) -> bool:
        return self.ui_extractors.scroll_likers_popup_up(
            logger_instance=self.logger,
            is_likers_popup_open_checker=self._is_likers_popup_open,
            verbose_logs=True
        )
    
    def _get_popup_bounds(self) -> Optional[Dict]:
        try:
            for selector in self.popup_selectors.popup_bounds_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element_info = element.info
                        bounds_data = element_info.get('bounds', '')
                        
                        if bounds_data:
                            import re
                            left, top, right, bottom = None, None, None, None
                            
                            if isinstance(bounds_data, dict):
                                left = bounds_data.get('left', 0)
                                top = bounds_data.get('top', 0)
                                right = bounds_data.get('right', 0)
                                bottom = bounds_data.get('bottom', 0)
                                self.logger.debug(f"Dict format detected for popup")
                            else:
                                bounds_str = str(bounds_data)
                                
                                match1 = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                                if match1:
                                    left, top, right, bottom = map(int, match1.groups())
                                    self.logger.debug(f"[x,y][x,y] format detected for popup")
                                
                                match2 = re.match(r'\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', bounds_str)
                                if match2:
                                    left, top, right, bottom = map(int, match2.groups())
                                    self.logger.debug(f"(x, y, x, y) format detected for popup")
                            
                            if left is not None:
                                popup_bounds = {
                                    'left': left,
                                    'top': top,
                                    'right': right,
                                    'bottom': bottom
                                }
                                self.logger.debug(f"Popup bounds detected with {selector}: {popup_bounds}")
                                return popup_bounds
                                
                except Exception as e:
                    self.logger.debug(f"Error with popup selector {selector}: {e}")
                    continue
            
            self.logger.debug("No popup bounds detected - fallback to fixed coordinates")
            return None
            
        except Exception as e:
            self.logger.debug(f"Error detecting popup bounds: {str(e)}")
            return None
    
    def _validate_interaction_limits(self, post_metadata: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        requested_interactions = config.get('max_interactions', 20)
        available_likes = post_metadata.get('likes_count', 0)
        
        result = {
            'valid': True,
            'warning': None,
            'suggestion': None,
            'adjusted_max': None
        }
        
        if available_likes == 0:
            result['valid'] = False
            result['warning'] = "Post has no likes, cannot extract likers"
            result['suggestion'] = "Choose a post with likes"
            return result
        
        if requested_interactions > available_likes:
            result['valid'] = False
            result['warning'] = f"Requested {requested_interactions} interactions but only {available_likes} likes available"
            result['suggestion'] = f"Automatically adjusting to maximum {available_likes} interactions"
            result['adjusted_max'] = available_likes
        
        return result
    
    def _open_likers_popup(self, is_reel: bool = False) -> bool:
        """Ouvre la popup des likers du post actuel."""
        try:
            like_count_element = self._find_like_count_element()
            
            if not like_count_element:
                self.logger.warning("⚠️ No like counter found - post may not have visible like count")
                return False
            
            like_count_element.click()
            self._human_like_delay('click')
            time.sleep(1.5)
            
            # Check if we accidentally opened comments instead of likers
            if self._is_comments_view_open():
                self.logger.warning("⚠️ Opened comments view instead of likers popup - closing and aborting")
                self._close_comments_view()
                return False
            
            if self._is_likers_popup_open():
                post_type = "reel" if is_reel else "post"
                self.logger.info(f"✅ Likers popup opened ({post_type})")
                return True
            
            self.logger.error("❌ Could not open likers popup")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening likers popup: {e}")
            return False
    
    def _close_comments_view(self) -> bool:
        """Ferme la vue des commentaires si elle est ouverte."""
        try:
            back_selectors = [
                '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
                '//android.widget.ImageView[@content-desc="Retour"]',
                '//android.widget.ImageView[@content-desc="Back"]'
            ]
            for selector in back_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element.click()
                        time.sleep(0.5)
                        if not self._is_comments_view_open():
                            self.logger.debug("✅ Comments view closed")
                            return True
                except:
                    continue
            
            self.device.press('back')
            time.sleep(0.5)
            return not self._is_comments_view_open()
        except Exception as e:
            self.logger.debug(f"Error closing comments view: {e}")
            return False
    
    def _is_comments_view_open(self) -> bool:
        """Vérifie si la vue des commentaires est ouverte."""
        try:
            comments_indicators = [
                '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]',
                '//*[contains(@text, "Ajouter un commentaire")]',
                '//*[contains(@text, "Add a comment")]'
            ]
            for selector in comments_indicators:
                if self.device.xpath(selector).exists:
                    return True
            return False
        except:
            return False
    
    def _ensure_on_likers_popup(self, force_back: bool = False) -> bool:
        """
        S'assure qu'on est sur la popup des likers.
        Essaie plusieurs fois de revenir avec back.
        """
        if not force_back and self._is_likers_popup_open():
            return True
        
        for attempt in range(3):
            self.logger.debug(f"🔙 Back attempt {attempt + 1}/3 to return to likers popup")
            if self._go_back_to_likers_list():
                return True
            time.sleep(0.5)
        
        self.logger.error("❌ Could not return to likers popup after 3 attempts")
        return False
    
    def _go_back_to_likers_list(self) -> bool:
        """Revient à la liste des likers en utilisant le bouton back."""
        try:
            back_selectors = [
                '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
                '//android.widget.ImageView[@content-desc="Retour"]',
                '//android.widget.ImageView[@content-desc="Back"]',
                '//*[@content-desc="Retour"]',
                '//*[@content-desc="Back"]'
            ]
            
            for selector in back_selectors:
                try:
                    back_btn = self.device.xpath(selector)
                    if back_btn.exists:
                        back_btn.click()
                        self._human_like_delay('click')
                        if self._is_likers_popup_open():
                            self.logger.debug("✅ Back to likers popup successful")
                            return True
                except Exception:
                    continue
            
            self.device.press("back")
            self._human_like_delay('click')
            
            if self._is_likers_popup_open():
                self.logger.debug("✅ Back to likers popup via Android back")
                return True
            
            return False
        except Exception as e:
            self.logger.debug(f"Error going back to likers list: {e}")
            return False
    
    def _perform_post_url_interactions(self, username: str, config: Dict[str, Any], 
                                       profile_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Effectue les interactions sur un profil (like, follow, story, comment).
        """
        result = {
            'likes': 0,
            'follows': 0,
            'comments': 0,
            'stories': 0,
            'stories_liked': 0,
            'actually_interacted': False
        }
        
        try:
            interactions_to_do = self._determine_interactions_from_config(config)
            self.logger.debug(f"🎯 Planned interactions for @{username}: {interactions_to_do}")
            
            should_like = 'like' in interactions_to_do
            should_comment = 'comment' in interactions_to_do
            
            if should_like or should_comment:
                likes_result = self.like_business.like_profile_posts(
                    username,
                    max_likes=config.get('max_likes_per_profile', 3),
                    config={'randomize_order': True},
                    should_comment=should_comment,
                    custom_comments=config.get('custom_comments', []),
                    comment_template_category=config.get('comment_template_category', 'generic'),
                    max_comments=config.get('max_comments_per_profile', 1),
                    navigate_to_profile=False,
                    profile_data=profile_data,
                    should_like=should_like
                )
                if likes_result:
                    result['likes'] = likes_result.get('posts_liked', 0)
                    result['comments'] = likes_result.get('posts_commented', 0)
                    if result['likes'] > 0 or result['comments'] > 0:
                        result['actually_interacted'] = True
            
            if 'follow' in interactions_to_do:
                if self.click_actions.click_follow_button():
                    result['follows'] = 1
                    result['actually_interacted'] = True
                    self.logger.info(f"✅ Followed @{username}")
            
            if 'story' in interactions_to_do or 'story_like' in interactions_to_do:
                should_like_story = 'story_like' in interactions_to_do
                story_result = self.story_business.watch_user_stories(
                    username,
                    max_stories=config.get('max_stories_per_profile', 3),
                    should_like=should_like_story,
                    navigate_to_profile=False
                )
                if story_result:
                    result['stories'] = story_result.get('stories_watched', 0)
                    result['stories_liked'] = story_result.get('stories_liked', 0)
                    if result['stories'] > 0:
                        result['actually_interacted'] = True
            
            return result
        except Exception as e:
            self.logger.error(f"Error performing interactions on @{username}: {e}")
            return result

