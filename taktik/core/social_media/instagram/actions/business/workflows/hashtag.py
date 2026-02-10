"""Business logic for Instagram hashtag interactions."""

import time
import random
import re
from typing import Dict, List, Any, Optional
from loguru import logger

from ._likers_common import LikersWorkflowBase
from ..common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service
from taktik.core.social_media.instagram.ui.extractors import parse_number_from_text


class HashtagBusiness(LikersWorkflowBase):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "hashtag", init_business_modules=True)
        
        from ..common.workflow_defaults import HASHTAG_DEFAULTS
        self.default_config = {**HASHTAG_DEFAULTS}
    
    def interact_with_hashtag_likers(self, hashtag: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        effective_config = {**self.default_config, **(config or {})}
        
        self.logger.info(f"Hashtag config received: {config}")
        self.logger.info(f"Hashtag config effective: max_interactions={effective_config.get('max_interactions', 'N/A')}")
        
        stats = {
            'hashtag': hashtag,
            'posts_analyzed': 0,
            'posts_selected': 0,
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
            self.logger.info(f"Starting hashtag workflow: #{hashtag}")
            self.logger.info(f"Max interactions: {effective_config['max_interactions']}")
            self.logger.info(f"Post criteria: {effective_config['min_likes']}-{effective_config['max_likes']} likes")
            self.logger.info(f"Max likes/profile: {effective_config.get('max_likes_per_profile', 2)}")
            self.logger.info(f"Probabilities: Like {effective_config.get('like_percentage', 0)}%, "
                           f"Follow {effective_config.get('follow_percentage', 0)}%, "
                           f"Story {effective_config.get('story_watch_percentage', 0)}%, "
                           f"Story Like {effective_config.get('story_like_percentage', 0)}%")
            
            filter_crit = effective_config.get('filter_criteria', {})
            self.logger.info(f"Filters: {filter_crit.get('min_followers', 0)}-{filter_crit.get('max_followers', 100000)} followers, "
                           f"min {filter_crit.get('min_posts', 0)} posts")
            
            if not self.nav_actions.navigate_to_hashtag(hashtag):
                self.logger.error("Failed to navigate to hashtag")
                stats['errors'] += 1
                return stats
            
            time.sleep(1.5)
            
            # Récupérer account_id pour la vérification des posts déjà traités
            account_id = getattr(self.automation, 'active_account_id', None) if self.automation else None
            
            # Boucle pour trouver un post non encore traité
            max_posts_to_try = effective_config.get('max_posts_to_analyze', 20)
            posts_tried = 0
            valid_post = None
            post_metadata = None
            need_to_open_post = True  # Flag pour savoir si on doit ouvrir un post depuis la grille
            
            while posts_tried < max_posts_to_try:
                # Ouvrir un post depuis la grille seulement si nécessaire
                if need_to_open_post:
                    valid_post = self._find_first_valid_post(hashtag, effective_config, skip_count=0)
                    
                    if not valid_post:
                        self.logger.warning("No valid post found matching criteria")
                        return stats
                else:
                    # On est déjà sur un post (après swipe), extraire ses métadonnées
                    self.logger.debug("📜 Already on a post after swipe, extracting metadata...")
                    is_reel = self._is_reel_post()
                    likes_count = self.ui_extractors.extract_likes_count_from_ui()
                    comments_count = self.ui_extractors.extract_comments_count_from_ui()
                    valid_post = {
                        'likes_count': likes_count,
                        'comments_count': comments_count,
                        'is_reel': is_reel
                    }
                    # Vérifier si le post correspond aux critères
                    min_likes = effective_config.get('post_criteria', {}).get('min_likes', 100)
                    max_likes = effective_config.get('post_criteria', {}).get('max_likes', 50000)
                    if not (min_likes <= likes_count <= max_likes):
                        self.logger.info(f"⏭️ Post has {likes_count} likes (criteria: {min_likes}-{max_likes}), swiping to next...")
                        self._swipe_to_next_post()
                        time.sleep(1.5)
                        posts_tried += 1
                        continue
                
                posts_tried += 1
                stats['posts_analyzed'] = posts_tried
                
                self.logger.info(f"Post selected: {valid_post['likes_count']} likes, {valid_post['comments_count']} comments")
                
                # Extraire les métadonnées du post pour vérifier s'il a déjà été traité
                is_reel = valid_post.get('is_reel', False)
                post_metadata = self._extract_current_post_metadata(is_reel)
                
                if post_metadata and post_metadata.get('author'):
                    # Envoyer les métadonnées du post au front pour affichage
                    try:
                        from bridges.desktop_bridge import send_current_post
                        send_current_post(
                            author=post_metadata['author'],
                            likes_count=post_metadata.get('likes_count'),
                            comments_count=post_metadata.get('comments_count'),
                            caption=post_metadata.get('caption'),
                            hashtag=hashtag
                        )
                        self.logger.debug(f"📤 Sent current_post to frontend: @{post_metadata['author']}")
                    except Exception as e:
                        self.logger.debug(f"Failed to send current_post: {e}")
                    
                    # Vérifier si ce post a déjà été traité
                    if DatabaseHelpers.is_hashtag_post_processed(
                        hashtag=hashtag,
                        post_author=post_metadata['author'],
                        post_caption_hash=post_metadata.get('caption_hash'),
                        account_id=account_id,
                        hours_limit=168  # 7 jours
                    ):
                        self.logger.info(f"⏭️ Post by @{post_metadata['author']} already processed, swiping to next post...")
                        # Notifier le frontend qu'on skip ce post
                        try:
                            from bridges.desktop_bridge import send_post_skipped
                            send_post_skipped(
                                author=post_metadata['author'],
                                reason="already_processed",
                                hashtag=hashtag
                            )
                        except Exception as e:
                            self.logger.debug(f"Failed to send post_skipped: {e}")
                        # Swiper verticalement pour passer au post suivant
                        self._swipe_to_next_post()
                        time.sleep(1.5)
                        self._human_like_delay('navigation')
                        need_to_open_post = False  # On est déjà sur un post après le swipe
                        continue
                    else:
                        self.logger.info(f"✅ New post by @{post_metadata['author']} - proceeding with interactions")
                        stats['posts_selected'] += 1
                        break
                else:
                    # Si on ne peut pas extraire les métadonnées, on continue quand même
                    self.logger.warning("⚠️ Could not extract post metadata, proceeding anyway")
                    stats['posts_selected'] += 1
                    break
            
            if not valid_post:
                self.logger.warning("No unprocessed post found after trying multiple posts")
                return stats
            
            validation_result = self._validate_hashtag_limits(valid_post, effective_config)
            if not validation_result['valid']:
                self.logger.warning(f"⚠️ {validation_result['warning']}")
                if validation_result.get('suggestion'):
                    self.logger.info(f"💡 Suggestion: {validation_result['suggestion']}")
                if validation_result.get('adjusted_max'):
                    effective_config['max_interactions'] = validation_result['adjusted_max']
                    self.logger.info(f"✅ Adjusted max interactions to {validation_result['adjusted_max']}")
            
            # Ouvrir la liste des likers et interagir directement (comme Target Followers)
            max_interactions_target = effective_config['max_interactions']
            effective_config['source'] = f"#{hashtag}"
            
            # Ouvrir la popup des likers
            if not self._open_likers_popup(is_reel):
                self.logger.error("Failed to open likers popup")
                stats['errors'] += 1
                return stats
            
            # Démarrer la phase d'interaction
            if self.session_manager:
                self.session_manager.start_interaction_phase()
            
            self.logger.info(f"🚀 Starting direct interactions in likers list (target: {max_interactions_target})")
            
            # Shared interaction loop (from LikersWorkflowBase)
            self._interact_with_likers_list(
                stats=stats,
                effective_config=effective_config,
                max_interactions=max_interactions_target,
                source_type='HASHTAG',
                source_name=f"#{hashtag}",
            )
            
            stats['success'] = stats['users_interacted'] > 0
            self.logger.info(f"Workflow completed: {stats['users_interacted']} interactions out of {stats['users_found']} users")
            
            # Enregistrer le post comme traité pour éviter de le retraiter
            if post_metadata and post_metadata.get('author') and account_id:
                DatabaseHelpers.record_hashtag_post_processed(
                    hashtag=hashtag,
                    post_author=post_metadata['author'],
                    post_caption_hash=post_metadata.get('caption_hash'),
                    post_caption_preview=post_metadata.get('caption', '')[:100] if post_metadata.get('caption') else None,
                    likes_count=post_metadata.get('likes_count'),
                    comments_count=post_metadata.get('comments_count'),
                    likers_processed=stats['users_found'],
                    interactions_made=stats['users_interacted'],
                    account_id=account_id
                )
                self.logger.info(f"📋 Post by @{post_metadata['author']} recorded as processed")
            
            self.stats_manager.display_final_stats(workflow_name="HASHTAG")
            
        except Exception as e:
            self.logger.error(f"General hashtag workflow error: {e}")
            stats['errors'] += 1
            self.stats_manager.add_error(f"General error: {e}")
        
        return stats
    
    def _find_first_valid_post(self, hashtag: str, config: Dict[str, Any], skip_count: int = 0) -> Optional[Dict[str, Any]]:
        """
        Trouve le premier post valide selon les critères de likes.
        
        Args:
            hashtag: Le hashtag à analyser
            config: Configuration avec min_likes, max_likes
            skip_count: Nombre de posts valides à sauter (pour trouver le N-ième post valide)
        """
        min_likes = config.get('min_likes', 100)
        max_likes = config.get('max_likes', 50000)
        max_attempts = 20 + skip_count  # Augmenter les tentatives si on doit sauter des posts
        
        try:
            self.logger.info(f"Searching for valid post from #{hashtag} (criteria: {min_likes}-{max_likes} likes, skip_count={skip_count})")
            
            post_open_result = self._open_first_post_in_grid()
            if not post_open_result:
                self.logger.error("Failed to open first post")
                return None
            
            is_reel = post_open_result.get('is_reel', False) if isinstance(post_open_result, dict) else False
            
            posts_tested = 0
            valid_posts_found = 0  # Compteur de posts valides trouvés
            
            while posts_tested < max_attempts:
                # Vérifier si la session doit continuer (durée, limites, etc.)
                if hasattr(self, 'session_manager') and self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        return None
                
                metadata = self._extract_post_metadata()
                
                if metadata:
                    likes_count = metadata.get('likes_count', 0)
                    comments_count = metadata.get('comments_count', 0)
                    
                    if min_likes <= likes_count <= max_likes:
                        valid_posts_found += 1
                        
                        # Si on doit encore sauter des posts valides
                        if valid_posts_found <= skip_count:
                            self.logger.info(f"Valid post #{valid_posts_found} (skipping, need to skip {skip_count}): {likes_count} likes")
                            # Swiper pour passer au suivant
                            posts_tested += 1
                            if posts_tested < max_attempts:
                                width, height = self.device.get_screen_size()
                                center_x = width // 2
                                start_y = int(height * 0.83)
                                end_y = int(height * 0.21)
                                self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.6)
                                time.sleep(3)
                                is_reel = self._is_reel_post()
                            continue
                        
                        self.logger.info(f"Valid post found (#{posts_tested + 1}): {likes_count} likes, {comments_count} comments")
                        return {
                            'index': posts_tested,
                            'likes_count': likes_count,
                            'comments_count': comments_count,
                            'is_reel': is_reel
                        }
                    else:
                        if likes_count < min_likes:
                            reason = f"too few likes ({likes_count} < {min_likes})"
                        elif likes_count > max_likes:
                            reason = f"too many likes ({likes_count} > {max_likes})"
                        else:
                            reason = "criteria not met"
                        
                        self.logger.info(f"Post #{posts_tested + 1}: {likes_count} likes FILTERED ({reason})")
                else:
                    self.logger.debug(f"Post #{posts_tested + 1}: unable to extract metadata")
                
                posts_tested += 1
                
                if posts_tested < max_attempts:
                    # Adaptive swipe coordinates
                    width, height = self.device.get_screen_size()
                    center_x = width // 2
                    start_y = int(height * 0.83)  # ~83% of height
                    end_y = int(height * 0.21)    # ~21% of height
                    self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.6)
                    time.sleep(3)
                    is_reel = self._is_reel_post()
            
            self.logger.warning(f"No valid post found after {max_attempts} attempts")
            return None
            
        except Exception as e:
            self.logger.error(f"Error searching for valid post: {e}")
            return None
    
    def _swipe_to_next_post(self):
        """Swipe vertical pour passer au post suivant."""
        try:
            width, height = self.device.get_screen_size()
            center_x = width // 2
            start_y = int(height * 0.75)
            end_y = int(height * 0.25)
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.4)
            self.logger.debug("📜 Swiped to next post")
        except Exception as e:
            self.logger.debug(f"Error swiping to next post: {e}")
    
    def _is_on_hashtag_grid(self) -> bool:
        """Vérifie si on est sur la grille de posts d'un hashtag."""
        try:
            # Vérifier si on voit des posts dans la grille
            for selector in self.post_selectors.hashtag_post_selectors:
                posts = self.device.xpath(selector).all()
                if posts and len(posts) >= 3:  # Au moins 3 posts visibles = grille
                    self.logger.debug(f"✅ Hashtag grid detected ({len(posts)} posts visible)")
                    return True
            
            # Vérifier si on voit le header du hashtag
            hashtag_header_selectors = [
                '//*[contains(@text, "posts")]',
                '//*[contains(@text, "publications")]',
                '//*[@resource-id="com.instagram.android:id/action_bar_title"]'
            ]
            for selector in hashtag_header_selectors:
                if self.device.xpath(selector).exists:
                    self.logger.debug("✅ Hashtag page header detected")
                    return True
            
            self.logger.debug("❌ Not on hashtag grid")
            return False
        except Exception as e:
            self.logger.debug(f"Error checking hashtag grid: {e}")
            return False
    
    def _open_first_post_in_grid(self):
        max_attempts = 5
        
        for attempt in range(max_attempts):
            try:
                self.logger.debug(f"Attempt {attempt + 1}/{max_attempts} to open a post")
                
                post_selectors = self.post_selectors.hashtag_post_selectors
                
                posts = None
                used_selector = None
                for selector in post_selectors:
                    posts = self.device.xpath(selector).all()
                    if posts:
                        used_selector = selector
                        self.logger.debug(f"{len(posts)} posts found with: {selector}")
                        break
                
                if not posts:
                    self.logger.warning("No posts found in grid with all selectors")
                    return False
                
                self.logger.debug(f"Clicking first post (selector: {used_selector})")
                posts[0].click()
                time.sleep(3)
                
                post_type = self._detect_opened_post_type()
                self.logger.info(f"Post type detected: {post_type}")
                
                if post_type == "reel_player":
                    self.logger.debug("Reel detected - swipe up to reveal likes")
                    if self._reveal_reel_comments_section():
                        self.logger.debug("Reel comments section revealed")
                        return {'success': True, 'is_reel': True}
                    else:
                        self.logger.debug("Unable to reveal reel comments")
                        
                elif post_type == "post_detail":
                    self.logger.debug(f"Post detail opened (attempt {attempt + 1})")
                    return {'success': True, 'is_reel': False}
                    
                else:
                    self.logger.debug(f"Unknown post type or opening failed")
                
                if attempt < max_attempts - 1:
                    self.logger.debug("Back to grid to try another post")
                    self.device.back()
                    time.sleep(1.5)
                    
                    self.logger.debug("Scrolling in grid")
                    screen_info = self.device.info
                    center_x = screen_info.get('displayWidth', 1080) // 2
                    start_y = int(screen_info.get('displayHeight', 1920) * 0.6)
                    end_y = int(screen_info.get('displayHeight', 1920) * 0.4)
                    self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.4)
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.debug(f"Error attempt {attempt + 1}: {e}")
                continue
        
        self.logger.error(f"Failed to open a post after {max_attempts} attempts")
        return False
    
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
            screen_info = self.device.info
            center_x = screen_info.get('displayWidth', 1080) // 2
            
            start_y = int(screen_info.get('displayHeight', 1920) * 0.80)
            end_y = int(screen_info.get('displayHeight', 1920) * 0.20)
            
            self.logger.debug(f"Swipe to reveal comments: ({center_x}, {start_y}) -> ({center_x}, {end_y})")
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.5)
            time.sleep(2)
            
            if self._are_like_comment_elements_visible():
                self.logger.debug("Like/comment elements detected after 1st swipe")
                return True
            
            self.logger.debug("Second swipe to finalize opening")
            start_y = int(screen_info.get('displayHeight', 1920) * 0.70)
            end_y = int(screen_info.get('displayHeight', 1920) * 0.30)
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.5)
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
                except:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking elements: {e}")
            return False
    
    def _extract_post_metadata(self) -> Optional[Dict[str, Any]]:
        try:
            metadata = {
                'likes_count': self.ui_extractors.extract_likes_count_from_ui(),
                'comments_count': self.ui_extractors.extract_comments_count_from_ui(),
                'is_reel': self._is_reel_post()
            }
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata: {e}")
            return None
    
    def _extract_likers_from_selected_posts(self, posts: List[Dict[str, Any]], config: Dict[str, Any]) -> List[str]:
        all_likers = []
        max_interactions = config.get('max_interactions', 30)
        
        selected_posts = [p for p in posts if p.get('selected', False)]
        
        if not selected_posts:
            return []
        
        self.logger.info(f"Extracting likers from {len(selected_posts)} selected posts")
        
        try:
            if not self._open_first_post_in_grid():
                return []
            
            current_index = 0
            
            # Get screen dimensions once for adaptive swipes
            width, height = self.device.get_screen_size()
            center_x = width // 2
            start_y = int(height * 0.83)
            end_y = int(height * 0.21)
            
            for post in posts:
                while current_index < post['index']:
                    self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.6)
                    time.sleep(2)
                    current_index += 1
                
                if post.get('selected', False):
                    self.logger.info(f"Extracting likers from post #{post['index'] + 1} ({post['likes_count']} likes)")
                    
                    post_likers = self._extract_likers_from_current_post()
                    
                    for username in post_likers:
                        if username not in all_likers:
                            all_likers.append(username)
                            
                            if len(all_likers) >= max_interactions * 2:
                                self.logger.info(f"Target reached: {len(all_likers)} likers collected")
                                for _ in range(3):
                                    self.device.back()
                                    time.sleep(1)
                                return all_likers
                    
                    self.logger.info(f"Total likers collected: {len(all_likers)}")
                
                if current_index < len(posts) - 1:
                    current_index += 1
            
            for _ in range(3):
                self.device.back()
                time.sleep(1)
            
            self.logger.info(f"{len(all_likers)} unique likers extracted")
            return all_likers
            
        except Exception as e:
            self.logger.error(f"Error extracting likers: {e}")
            return []
    
    def _extract_likers_from_current_post(self, is_reel: bool = None, max_interactions: int = None) -> List[str]:
        try:
            if is_reel is None:
                is_reel = self._is_reel_post()
            
            if is_reel:
                self.logger.debug("Reel post detected")
                return self._extract_likers_from_reel(max_interactions=max_interactions)
            else:
                self.logger.debug("Regular post detected")
                return self._extract_likers_from_regular_post(max_interactions=max_interactions)
                
        except Exception as e:
            self.logger.error(f"Error extracting likers: {e}")
            return []
    
    def _extract_likers_from_regular_post(self, max_interactions: int = None) -> List[str]:
        return super()._extract_likers_from_regular_post(max_interactions=max_interactions, multiply_by=2)
    
    def _extract_likers_from_reel(self, max_interactions: int = None) -> List[str]:
        return super()._extract_likers_from_reel(max_interactions=max_interactions, multiply_by=2)
    
    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return super()._interact_with_user(username, config)
    
    def _get_filter_criteria_from_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return super()._get_filter_criteria_from_config(config)
    
    def _is_like_count_text(self, text: str) -> bool:
        return self.ui_extractors.is_like_count_text(text)
    
    def _extract_usernames_from_likers_popup(self, max_interactions: int = None) -> List[str]:
        return self.ui_extractors.extract_usernames_from_likers_popup(
            max_interactions=max_interactions,
            automation=self.automation,
            logger_instance=self.logger,
            add_initial_sleep=True
        )
    
    def _extract_visible_usernames(self) -> List[str]:
        return self.ui_extractors.extract_visible_usernames(logger_instance=self.logger)
    
    def _extract_username_from_element(self, element) -> Optional[str]:
        return self.ui_extractors.extract_username_from_element(element, logger_instance=self.logger)
    
    def _is_valid_username(self, username: str) -> bool:
        return self.ui_extractors.is_valid_username(username)
    
    def interact_with_hashtag(self, source: str = None, hashtag: str = None, 
                            max_interactions: int = 30, action_config: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            if source:
                hashtag_name, _ = self._parse_hashtag_source(source)
            elif hashtag:
                hashtag_name = hashtag
            else:
                raise ValueError("Either 'source' or 'hashtag' must be provided")
            
            if action_config:
                post_criteria = action_config.get('post_criteria', {})
                probabilities = action_config.get('probabilities', {})
                filter_criteria = action_config.get('filter_criteria', {})
                
                config = {
                    'max_interactions': action_config.get('max_interactions', 30),
                    'max_likes_per_profile': action_config.get('max_likes_per_profile', 2),
                    'min_likes': post_criteria.get('min_likes', 100),
                    'max_likes': post_criteria.get('max_likes', 50000),
                    'max_posts_to_analyze': 20,
                    'like_percentage': probabilities.get('like_percentage', 80),
                    'follow_percentage': probabilities.get('follow_percentage', 15),
                    'comment_percentage': probabilities.get('comment_percentage', 5),
                    'story_watch_percentage': probabilities.get('story_percentage', 20),
                    'story_like_percentage': probabilities.get('story_like_percentage', 10),
                    'filter_criteria': {
                        'min_followers': filter_criteria.get('min_followers', 10),
                        'max_followers': filter_criteria.get('max_followers', 50000),
                        'min_posts': filter_criteria.get('min_posts', 3),
                        'skip_private': filter_criteria.get('skip_private', True),
                        'skip_business': filter_criteria.get('skip_business', False)
                    },
                    'like_settings': action_config.get('like_settings', {}),
                    'follow_settings': action_config.get('follow_settings', {}),
                    'story_settings': action_config.get('story_settings', {})
                }
            else:
                config = {
                    'max_interactions': max_interactions,
                    'min_likes': 100,
                    'max_likes': 50000,
                    'max_posts_to_analyze': 20,
                    'like_percentage': 80,
                    'follow_percentage': 15,
                    'comment_percentage': 5,
                    'story_watch_percentage': 10,
                    'max_likes_per_profile': 2,
                    'filter_criteria': {
                        'min_followers': 10,
                        'max_followers': 50000,
                        'min_posts': 3,
                        'skip_private': True
                    }
                }
            
            result = self.interact_with_hashtag_likers(hashtag_name, config)
            
            return {
                'users_found': result.get('users_found', 0),
                'users_interacted': result.get('users_interacted', 0),
                'profiles_filtered': result.get('profiles_filtered', 0),
                'likes_made': result.get('likes_made', 0),
                'follows_made': result.get('follows_made', 0),
                'comments_made': result.get('comments_made', 0),
                'stories_watched': result.get('stories_watched', 0),
                'stories_liked': result.get('stories_liked', 0),
                'errors': result.get('errors', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Hashtag workflow error: {e}")
            return {
                'users_found': 0,
                'users_interacted': 0,
                'profiles_filtered': 0,
                'likes_made': 0,
                'follows_made': 0,
                'comments_made': 0,
                'stories_watched': 0,
                'errors': 1
            }
    
    def _parse_hashtag_source(self, source: str) -> tuple:
        if '-' in source:
            parts = source.split('-', 1)
            return parts[0], parts[1]
        return source, 'recent-likers'
    
    def _validate_hashtag_limits(self, post_metadata: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        requested_interactions = config.get('max_interactions', 30)
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
            result['suggestion'] = "Choose a hashtag with posts that have likes"
            return result
        
        if requested_interactions > available_likes:
            result['valid'] = False
            result['warning'] = f"Requested {requested_interactions} interactions but only {available_likes} likes available on selected post"
            result['suggestion'] = f"Automatically adjusting to maximum {available_likes} interactions"
            result['adjusted_max'] = available_likes
        
        return result
    
    # ============================================
    # POST METADATA EXTRACTION
    # ============================================
    
    def _extract_current_post_metadata(self, is_reel: bool = False) -> Optional[Dict[str, Any]]:
        """
        Extrait les métadonnées du post actuellement affiché.
        Utilisé pour identifier de manière unique un post et éviter de le retraiter.
        
        Args:
            is_reel: True si on est sur un Reel, False pour un post classique
            
        Returns:
            Dict avec author, caption, caption_hash, likes_count, comments_count
            ou None si extraction échouée
        """
        try:
            metadata = {
                'author': None,
                'caption': None,
                'caption_hash': None,
                'likes_count': None,
                'comments_count': None,
                'post_date': None
            }
            
            # Détecter si c'est un Reel (plus fiable que le paramètre)
            is_reel_detected = self._is_reel_post()
            self.logger.debug(f"Post type detection: is_reel_param={is_reel}, is_reel_detected={is_reel_detected}")
            is_reel = is_reel or is_reel_detected  # Utiliser True si l'un des deux est True
            
            # Extraire l'auteur
            if is_reel:
                author_selectors = self.post_selectors.reel_author_username_selectors
            else:
                author_selectors = self.post_selectors.post_author_username_selectors
            
            for selector in author_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        # Essayer plusieurs méthodes pour récupérer le texte
                        text = element.get_text()
                        if not text:
                            # Fallback: essayer content-desc
                            info = element.info
                            text = info.get('contentDescription', '') or info.get('text', '')
                        if text:
                            # Nettoyer le username
                            metadata['author'] = text.strip().lstrip('@').lower()
                            self.logger.debug(f"📝 Post author: @{metadata['author']}")
                            break
                except Exception as e:
                    self.logger.debug(f"Author selector {selector} failed: {e}")
                    continue
            
            # Fallback: extraire depuis "Reel by username" dans content-desc
            if not metadata['author'] and is_reel:
                self.logger.debug("Trying fallback: extracting author from 'Reel by' content-desc")
                try:
                    # Chercher l'élément clips_media_component qui contient "Reel by username"
                    reel_element = self.device.xpath('//*[@resource-id="com.instagram.android:id/clips_media_component"]')
                    if reel_element.exists:
                        info = reel_element.info
                        # Essayer plusieurs clés possibles pour content-desc
                        content_desc = info.get('contentDescription') or info.get('content-desc') or info.get('contentDesc') or ''
                        self.logger.debug(f"clips_media_component info keys: {list(info.keys())}")
                        self.logger.debug(f"clips_media_component content-desc: '{content_desc[:100] if content_desc else 'empty'}'")
                        
                        # Format: "Reel by username. Double-tap to play or pause."
                        if 'Reel by ' in content_desc:
                            username = content_desc.split('Reel by ')[1].split('.')[0].strip()
                            if username:
                                metadata['author'] = username.lower()
                                self.logger.debug(f"📝 Post author (from Reel by): @{metadata['author']}")
                    else:
                        self.logger.debug("clips_media_component not found")
                except Exception as e:
                    self.logger.debug(f"Fallback Reel by extraction failed: {e}")
            
            # Extraire la caption (et la date pour les Reels)
            if is_reel:
                caption_selectors = self.post_selectors.reel_caption_selectors
                # Essayer d'abord de récupérer la caption
                for selector in caption_selectors:
                    try:
                        element = self.device.xpath(selector)
                        if element.exists:
                            caption = element.info.get('contentDescription', '') or element.get_text() or ''
                            if caption:
                                # Vérifier si la caption est rétractée (contient "…" ou "...")
                                if '…' in caption or '...' in caption:
                                    self.logger.debug(f"📝 Caption rétractée détectée: {caption[:30]}... - clic pour ouvrir")
                                    try:
                                        element.click()
                                        time.sleep(0.8)  # Attendre l'animation
                                        # Réessayer de récupérer la caption complète
                                        element = self.device.xpath(selector)
                                        if element.exists:
                                            caption = element.info.get('contentDescription', '') or element.get_text() or ''
                                    except Exception:
                                        pass
                                
                                metadata['caption'] = caption.strip()
                                metadata['caption_hash'] = DatabaseHelpers.generate_caption_hash(caption)
                                self.logger.debug(f"📝 Post caption: {caption[:80]}...")
                                break
                    except Exception:
                        continue
                
                # Extraire la date du post (visible après ouverture de la caption)
                try:
                    date_selectors = getattr(self.post_selectors, 'reel_date_selectors', [])
                    for selector in date_selectors:
                        elements = self.device.xpath(selector)
                        if elements.exists:
                            for elem in elements.all() if hasattr(elements, 'all') else [elements]:
                                date_text = elem.info.get('contentDescription', '') or elem.info.get('text', '') or elem.get_text() or ''
                                # Vérifier que c'est une date (contient un mois)
                                months = ['January', 'February', 'March', 'April', 'May', 'June', 
                                         'July', 'August', 'September', 'October', 'November', 'December']
                                if date_text and any(m in date_text for m in months):
                                    metadata['post_date'] = date_text.strip()
                                    self.logger.debug(f"📅 Post date: {metadata['post_date']}")
                                    break
                            if metadata.get('post_date'):
                                break
                except Exception as e:
                    self.logger.debug(f"Date extraction failed: {e}")
            else:
                caption_selectors = self.post_selectors.post_caption_selectors
                for selector in caption_selectors:
                    try:
                        element = self.device.xpath(selector)
                        if element.exists:
                            caption = element.info.get('contentDescription', '') or element.get_text() or ''
                            if caption:
                                metadata['caption'] = caption.strip()
                                metadata['caption_hash'] = DatabaseHelpers.generate_caption_hash(caption)
                                self.logger.debug(f"📝 Post caption preview: {caption[:50]}...")
                                break
                    except Exception:
                        continue
            
            # Extraire le nombre de likes
            for selector in self.post_selectors.post_likes_count_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        # Pour les reels, le format est "The like number is X. View likes."
                        content_desc = element.info.get('contentDescription', '')
                        text = element.get_text() or content_desc
                        
                        if text:
                            likes = parse_number_from_text(text)
                            if likes:
                                metadata['likes_count'] = likes
                                self.logger.debug(f"📝 Post likes: {likes}")
                                break
                except Exception:
                    continue
            
            # Extraire le nombre de commentaires
            for selector in self.post_selectors.post_comments_count_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        content_desc = element.info.get('contentDescription', '')
                        text = element.get_text() or content_desc
                        
                        if text:
                            comments = parse_number_from_text(text)
                            if comments:
                                metadata['comments_count'] = comments
                                self.logger.debug(f"📝 Post comments: {comments}")
                                break
                except Exception:
                    continue
            
            # Vérifier qu'on a au moins l'auteur
            if metadata['author']:
                date_info = f" | date: {metadata['post_date']}" if metadata.get('post_date') else ""
                self.logger.info(f"📋 Post metadata: @{metadata['author']} | {metadata.get('likes_count', '?')} likes | caption_hash: {metadata.get('caption_hash', 'N/A')}{date_info}")
                return metadata
            else:
                self.logger.warning("⚠️ Could not extract post author")
                return None
                
        except Exception as e:
            self.logger.error(f"Error extracting post metadata: {e}")
            return None
    
