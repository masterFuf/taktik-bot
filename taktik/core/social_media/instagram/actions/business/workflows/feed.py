"""Business logic for Instagram feed interactions.

Ce workflow permet d'interagir avec les utilisateurs depuis le feed principal.
Utilisations typiques:
- Interagir avec les auteurs des posts dans le feed
- Interagir avec les likers des posts du feed
- Découvrir de nouveaux comptes via le feed
"""

import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ...core.base_business_action import BaseBusinessAction
from ..common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service


class FeedBusiness(BaseBusinessAction):
    """Business logic for interacting with users from the home feed."""
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "feed", init_business_modules=True)
        
        self.default_config = {
            'max_interactions': 20,
            'max_posts_to_check': 30,
            'interaction_delay_range': (20, 40),
            'like_percentage': 70,
            'follow_percentage': 15,
            'comment_percentage': 5,
            'story_watch_percentage': 10,
            'max_likes_per_profile': 3,
            'interact_with_post_author': True,  # Interagir avec l'auteur du post
            'interact_with_post_likers': False,  # Interagir avec les likers du post
            'skip_reels': True,  # Ignorer les reels dans le feed
            'skip_ads': True  # Ignorer les publicités
        }
        
        # Sélecteurs spécifiques au feed
        self._feed_selectors = {
            'feed_post_container': [
                '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"]',
                '//*[@resource-id="com.instagram.android:id/row_feed_profile_header"]'
            ],
            'post_author_username': [
                '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
                '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_username"]'
            ],
            'post_author_avatar': [
                '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_imageview"]'
            ],
            'sponsored_indicators': [
                '//*[contains(@text, "Sponsorisé")]',
                '//*[contains(@text, "Sponsored")]',
                '//*[contains(@text, "Publicité")]',
                '//*[contains(@text, "Ad")]'
            ],
            'reel_indicators': [
                '//*[contains(@content-desc, "Reel")]',
                '//*[@resource-id="com.instagram.android:id/clips_video_container"]'
            ],
            'likes_count_button': [
                '//*[@resource-id="com.instagram.android:id/row_feed_textview_likes"]',
                '//*[contains(@text, "J\'aime")]',
                '//*[contains(@text, "likes")]'
            ]
        }
    
    def interact_with_feed(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Interagir avec les utilisateurs depuis le feed.
        
        Args:
            config: Configuration du workflow
            
        Returns:
            Dict avec les statistiques
        """
        effective_config = {**self.default_config, **(config or {})}
        
        stats = {
            'posts_checked': 0,
            'posts_skipped_reels': 0,
            'posts_skipped_ads': 0,
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
            self.logger.info("📱 Starting feed workflow")
            self.logger.info(f"Max interactions: {effective_config['max_interactions']}")
            self.logger.info(f"Max posts to check: {effective_config['max_posts_to_check']}")
            
            # Naviguer vers le feed (home)
            if not self.nav_actions.navigate_to_home():
                self.logger.error("Failed to navigate to home feed")
                stats['errors'] += 1
                return stats
            
            time.sleep(2)
            
            # Démarrer la phase de scraping
            if self.session_manager:
                self.session_manager.start_scraping_phase()
            
            users_to_interact = []
            seen_users = set()
            posts_checked = 0
            
            # Parcourir le feed et collecter les utilisateurs
            while (len(users_to_interact) < effective_config['max_interactions'] and 
                   posts_checked < effective_config['max_posts_to_check']):
                
                posts_checked += 1
                stats['posts_checked'] += 1
                
                self.logger.debug(f"📱 Checking post {posts_checked}/{effective_config['max_posts_to_check']}")
                
                # Vérifier si c'est une pub
                if effective_config.get('skip_ads', True) and self._is_sponsored_post():
                    self.logger.debug("⏭️ Skipping sponsored post")
                    stats['posts_skipped_ads'] += 1
                    self._scroll_to_next_post()
                    continue
                
                # Vérifier si c'est un reel
                if effective_config.get('skip_reels', True) and self._is_reel_post():
                    self.logger.debug("⏭️ Skipping reel post")
                    stats['posts_skipped_reels'] += 1
                    self._scroll_to_next_post()
                    continue
                
                # Extraire l'auteur du post
                if effective_config.get('interact_with_post_author', True):
                    author = self._get_current_post_author()
                    if author and author not in seen_users:
                        seen_users.add(author)
                        users_to_interact.append({
                            'username': author,
                            'source': 'post_author'
                        })
                        self.logger.debug(f"Found post author: @{author}")
                
                # Extraire les likers du post (optionnel)
                if effective_config.get('interact_with_post_likers', False):
                    likers = self._get_post_likers(max_likers=3)
                    for liker in likers:
                        if liker not in seen_users and len(users_to_interact) < effective_config['max_interactions']:
                            seen_users.add(liker)
                            users_to_interact.append({
                                'username': liker,
                                'source': 'post_liker'
                            })
                
                # Passer au post suivant
                self._scroll_to_next_post()
                time.sleep(random.uniform(1, 2))
            
            stats['users_found'] = len(users_to_interact)
            
            # Terminer le scraping et démarrer les interactions
            if self.session_manager:
                self.session_manager.end_scraping_phase()
                self.session_manager.start_interaction_phase()
            
            if not users_to_interact:
                self.logger.warning("No users found in feed")
                return stats
            
            self.logger.info(f"📋 {len(users_to_interact)} users to process from feed")
            
            effective_config['source'] = "feed"
            
            for i, user_info in enumerate(users_to_interact, 1):
                username = user_info['username']
                self.logger.info(f"[{i}/{len(users_to_interact)}] Processing @{username} ({user_info['source']})")
                
                account_id = getattr(self.automation, 'active_account_id', None) if self.automation else None
                if DatabaseHelpers.is_profile_already_processed(username, account_id):
                    self.logger.info(f"Profile @{username} already processed, skipped")
                    stats['skipped'] += 1
                    self.stats_manager.increment('skipped')
                    continue
                
                interaction_result = self._interact_with_user(username, effective_config)
                
                if interaction_result:
                    stats['users_interacted'] += 1
                    stats['likes_made'] += interaction_result.get('likes', 0)
                    stats['follows_made'] += interaction_result.get('follows', 0)
                    stats['comments_made'] += interaction_result.get('comments', 0)
                    stats['stories_watched'] += interaction_result.get('stories', 0)
                    stats['stories_liked'] += interaction_result.get('stories_liked', 0)
                    
                    self.stats_manager.increment('interactions')
                    self.stats_manager.increment('likes', interaction_result.get('likes', 0))
                    self.stats_manager.increment('follows', interaction_result.get('follows', 0))
                else:
                    stats['profiles_filtered'] += 1
                
                # Délai entre interactions
                delay = random.randint(*effective_config['interaction_delay_range'])
                self.logger.debug(f"⏳ Waiting {delay}s before next interaction")
                time.sleep(delay)
            
            stats['success'] = True
            self.logger.info(f"✅ Feed workflow completed: {stats['users_interacted']} interactions")
            
        except Exception as e:
            self.logger.error(f"Error in feed workflow: {e}")
            stats['errors'] += 1
        
        return stats
    
    def _is_sponsored_post(self) -> bool:
        """Vérifier si le post actuel est sponsorisé."""
        return self._is_element_present(self._feed_selectors['sponsored_indicators'])
    
    def _is_reel_post(self) -> bool:
        """Vérifier si le post actuel est un reel."""
        return self._is_element_present(self._feed_selectors['reel_indicators'])
    
    def _get_current_post_author(self) -> Optional[str]:
        """Récupérer le username de l'auteur du post actuel."""
        try:
            for selector in self._feed_selectors['post_author_username']:
                element = self.device.xpath(selector)
                if element.exists:
                    username = element.get_text()
                    if username:
                        return self._clean_username(username)
            
            # Fallback: essayer via content-desc de l'avatar
            for selector in self._feed_selectors['post_author_avatar']:
                element = self.device.xpath(selector)
                if element.exists:
                    content_desc = element.attrib.get('content-desc', '')
                    if content_desc:
                        # Le content-desc contient souvent "Photo de profil de username"
                        parts = content_desc.split()
                        for part in parts:
                            if self._is_valid_username(part):
                                return self._clean_username(part)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting post author: {e}")
            return None
    
    def _get_post_likers(self, max_likers: int = 5) -> List[str]:
        """
        Récupérer les likers du post actuel.
        
        Args:
            max_likers: Nombre max de likers à récupérer
            
        Returns:
            Liste de usernames
        """
        likers = []
        
        try:
            # Cliquer sur le compteur de likes pour ouvrir la liste
            clicked = False
            for selector in self._feed_selectors['likes_count_button']:
                if self._find_and_click(selector, timeout=2):
                    clicked = True
                    break
            
            if not clicked:
                return likers
            
            time.sleep(1.5)
            
            # Vérifier si la popup des likers est ouverte
            if not self._is_likers_popup_open():
                return likers
            
            # Extraire les usernames
            for selector in self.popup_selectors.username_in_popup_selectors:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all()[:max_likers]:
                        try:
                            username = element.text
                            if username and self._is_valid_username(username):
                                likers.append(self._clean_username(username))
                        except Exception:
                            continue
                    break
            
            # Fermer la popup
            self._close_likers_popup()
            
        except Exception as e:
            self.logger.debug(f"Error getting post likers: {e}")
        
        return likers
    
    def _scroll_to_next_post(self):
        """Scroller vers le post suivant dans le feed."""
        try:
            # Scroll d'environ 70% de l'écran pour passer au post suivant
            screen_height = self.device.info.get('displayHeight', 1920)
            screen_width = self.device.info.get('displayWidth', 1080)
            
            start_y = int(screen_height * 0.7)
            end_y = int(screen_height * 0.2)
            center_x = screen_width // 2
            
            self.device.swipe(center_x, start_y, center_x, end_y, duration=0.3)
            
        except Exception as e:
            self.logger.debug(f"Error scrolling to next post: {e}")
            # Fallback: utiliser scroll_actions
            self.scroll_actions.scroll_down()
    
    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, int]]:
        """
        Interagir avec un utilisateur.
        """
        try:
            # Naviguer vers le profil
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.warning(f"Cannot navigate to @{username}")
                return None
            
            time.sleep(2)
            
            # Vérifier les filtres
            if hasattr(self, 'filtering_business'):
                filter_result = self.filtering_business.should_interact_with_profile(config.get('filter_criteria', {}))
                if not filter_result.get('should_interact', True):
                    self.logger.info(f"Profile @{username} filtered: {filter_result.get('reason', 'unknown')}")
                    self._record_filtered_profile(username, filter_result.get('reason', 'filtered'), config.get('source', 'feed'))
                    return None
            
            result = {
                'likes': 0,
                'follows': 0,
                'comments': 0,
                'stories': 0,
                'stories_liked': 0
            }
            
            # Like posts
            if random.randint(1, 100) <= config.get('like_percentage', 70):
                likes = self._like_user_posts(username, config.get('max_likes_per_profile', 3))
                result['likes'] = likes
            
            # Follow
            if random.randint(1, 100) <= config.get('follow_percentage', 15):
                if self._follow_user(username):
                    result['follows'] = 1
            
            # Watch stories
            if random.randint(1, 100) <= config.get('story_watch_percentage', 10):
                stories_result = self._watch_user_stories(username, config)
                result['stories'] = stories_result.get('watched', 0)
                result['stories_liked'] = stories_result.get('liked', 0)
            
            # Enregistrer l'interaction
            self._record_interaction(username, result, config.get('source', 'feed'))
            
            # Retourner au feed
            self.nav_actions.navigate_to_home()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error interacting with @{username}: {e}")
            return None
    
    def _like_user_posts(self, username: str, max_likes: int) -> int:
        """Liker les posts d'un utilisateur."""
        likes = 0
        try:
            if hasattr(self, 'like_business'):
                likes = self.like_business.like_posts_on_profile(max_likes=max_likes)
                if likes > 0:
                    self._record_action(username, 'LIKE', likes)
        except Exception as e:
            self.logger.debug(f"Error liking posts: {e}")
        return likes
    
    def _follow_user(self, username: str) -> bool:
        """Suivre un utilisateur."""
        try:
            for selector in self.profile_selectors.follow_button:
                if self._find_and_click(selector, timeout=2):
                    self._human_like_delay('click')
                    self._record_action(username, 'FOLLOW', 1)
                    self.logger.info(f"✅ Followed @{username}")
                    
                    # Envoyer l'événement follow en temps réel au frontend
                    try:
                        import json
                        msg = {"type": "follow_event", "username": username, "success": True}
                        print(json.dumps(msg), flush=True)
                    except:
                        pass  # Ignorer les erreurs d'envoi (CLI mode)
                    
                    return True
        except Exception as e:
            self.logger.debug(f"Error following user: {e}")
        return False
    
    def _watch_user_stories(self, username: str, config: Dict[str, Any]) -> Dict[str, int]:
        """Regarder les stories d'un utilisateur."""
        result = {'watched': 0, 'liked': 0}
        try:
            if hasattr(self, 'content_business'):
                stories_result = self.content_business.watch_stories(
                    like_probability=config.get('story_like_percentage', 5)
                )
                result['watched'] = stories_result.get('watched', 0)
                result['liked'] = stories_result.get('liked', 0)
                
                if result['watched'] > 0:
                    self._record_action(username, 'STORY_WATCH', result['watched'])
                if result['liked'] > 0:
                    self._record_action(username, 'STORY_LIKE', result['liked'])
        except Exception as e:
            self.logger.debug(f"Error watching stories: {e}")
        return result
    
    def _record_filtered_profile(self, username: str, reason: str, source: str):
        """Enregistrer un profil filtré."""
        try:
            account_id = self._get_account_id()
            session_id = self._get_session_id()
            
            DatabaseHelpers.record_filtered_profile(
                username=username,
                reason=reason,
                source_type='FEED',
                source_name=source,
                account_id=account_id,
                session_id=session_id
            )
        except Exception as e:
            self.logger.debug(f"Error recording filtered profile: {e}")
    
    def _record_interaction(self, username: str, result: Dict[str, int], source: str):
        """Enregistrer une interaction complète."""
        try:
            account_id = self._get_account_id()
            session_id = self._get_session_id()
            
            DatabaseHelpers.record_profile_interaction(
                username=username,
                source_type='FEED',
                source_name=source,
                likes=result.get('likes', 0),
                follows=result.get('follows', 0),
                comments=result.get('comments', 0),
                stories_watched=result.get('stories', 0),
                stories_liked=result.get('stories_liked', 0),
                account_id=account_id,
                session_id=session_id
            )
        except Exception as e:
            self.logger.debug(f"Error recording interaction: {e}")
