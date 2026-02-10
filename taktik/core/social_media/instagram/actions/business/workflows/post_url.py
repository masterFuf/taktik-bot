"""Business logic for Instagram post URL interactions."""

from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
import random
import re
import time

from ._likers_common import LikersWorkflowBase
from ..common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service

class PostUrlBusiness(LikersWorkflowBase):
    
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
            
            effective_config['source'] = post_url
            
            # Shared interaction loop (from LikersWorkflowBase)
            self._interact_with_likers_list(
                stats=stats,
                effective_config=effective_config,
                max_interactions=max_interactions,
                source_type='POST_URL',
                source_name=post_url,
            )
            
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
    

