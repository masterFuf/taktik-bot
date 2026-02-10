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

from ....core.base_business_action import BaseBusinessAction
from ...common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service


class FeedBusiness(BaseBusinessAction):
    """Business logic for interacting with users from the home feed."""
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "feed", init_business_modules=True)
        
        from ...common.workflow_defaults import FEED_DEFAULTS
        from .....ui.selectors import FEED_SELECTORS
        self.default_config = {**FEED_DEFAULTS}
        
        # Sélecteurs centralisés (depuis selectors.py)
        self._feed_sel = FEED_SELECTORS
        # Backward-compatible dict wrapper for existing code
        self._feed_selectors = {
            'feed_post_container': self._feed_sel.post_container,
            'post_author_username': self._feed_sel.post_author_username,
            'post_author_avatar': self._feed_sel.post_author_avatar,
            'sponsored_indicators': self._feed_sel.sponsored_indicators,
            'reel_indicators': self._feed_sel.reel_indicators,
            'likes_count_button': self._feed_sel.likes_count_button,
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
            
            # Mode simplifié : liker directement les posts dans le feed
            if effective_config.get('like_posts_directly', True):
                self.logger.info("📱 Direct like mode: liking posts in feed")
                
                if self.session_manager:
                    self.session_manager.start_interaction_phase()
                
                posts_liked = 0
                posts_checked = 0
                
                while (posts_liked < effective_config['max_interactions'] and 
                       posts_checked < effective_config['max_posts_to_check']):
                    
                    posts_checked += 1
                    stats['posts_checked'] += 1
                    
                    self.logger.info(f"📱 Post {posts_checked}/{effective_config['max_posts_to_check']} (liked: {posts_liked})")
                    
                    # Vérifier si c'est une pub
                    if effective_config.get('skip_ads', True) and self._is_sponsored_post():
                        self.logger.debug("⏭️ Skipping sponsored post")
                        stats['posts_skipped_ads'] += 1
                        self._scroll_to_next_post()
                        time.sleep(random.uniform(1, 2))
                        continue
                    
                    # Filtrer par nombre de likes si configuré
                    min_likes = effective_config.get('min_post_likes', 0)
                    max_likes = effective_config.get('max_post_likes', 0)
                    
                    self.logger.debug(f"🔍 Filter config: min_likes={min_likes}, max_likes={max_likes}")
                    
                    if min_likes > 0 or max_likes > 0:
                        post_metadata = self._extract_post_metadata()
                        self.logger.debug(f"🔍 Post metadata result: {post_metadata}")
                        
                        if post_metadata:
                            post_likes = post_metadata.get('likes_count', 0) or 0
                            
                            if min_likes > 0 and post_likes < min_likes:
                                self.logger.info(f"⏭️ Skipping post: {post_likes} likes < {min_likes} min")
                                stats['posts_skipped_filter'] = stats.get('posts_skipped_filter', 0) + 1
                                self._scroll_to_next_post()
                                time.sleep(random.uniform(1, 2))
                                continue
                            
                            if max_likes > 0 and post_likes > max_likes:
                                self.logger.info(f"⏭️ Skipping post: {post_likes} likes > {max_likes} max")
                                stats['posts_skipped_filter'] = stats.get('posts_skipped_filter', 0) + 1
                                self._scroll_to_next_post()
                                time.sleep(random.uniform(1, 2))
                                continue
                            
                            self.logger.info(f"✅ Post matches filter: {post_likes} likes (max: {max_likes})")
                        else:
                            self.logger.debug("⚠️ Could not extract post metadata, skipping filter")
                    
                    # Liker le post directement dans le feed
                    liked = False
                    if random.randint(1, 100) <= effective_config.get('like_percentage', 100):
                        if self._like_current_post():
                            posts_liked += 1
                            stats['likes_made'] += 1
                            self.stats_manager.increment('likes')
                            self.logger.info(f"❤️ Post liked ({posts_liked}/{effective_config['max_interactions']})")
                            liked = True
                        else:
                            self.logger.debug("Failed to like post")
                    
                    # Commenter le post (si configuré)
                    if liked and random.randint(1, 100) <= effective_config.get('comment_percentage', 0):
                        if self._comment_current_post(effective_config):
                            stats['comments_made'] += 1
                            self.stats_manager.increment('comments')
                            self.logger.info(f"💬 Comment posted")
                    
                    # Passer au post suivant
                    self._scroll_to_next_post()
                    
                    # Délai court entre les posts
                    delay = random.randint(*effective_config['interaction_delay_range'])
                    time.sleep(delay)
                
                stats['users_interacted'] = posts_liked
                stats['success'] = True
                self.logger.info(f"✅ Feed workflow completed: {posts_liked} posts liked")
                return stats
            
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
    
    def _like_current_post(self) -> bool:
        """Liker le post actuellement visible dans le feed."""
        try:
            like_button_selectors = self._feed_sel.like_button
            
            # D'abord vérifier si le post est déjà liké
            for selector in like_button_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    content_desc = element.attrib.get('content-desc', '').lower()
                    # Vérifier si déjà liké (unlike = déjà liké)
                    if 'unlike' in content_desc or 'ne plus aimer' in content_desc or 'liked' in content_desc:
                        self.logger.debug("⏭️ Post already liked, skipping")
                        return False
                    
                    # Cliquer sur le bouton like
                    element.click()
                    self._human_like_delay('click')
                    return True
            
            # Fallback: vérifier via l'icône du coeur si le post est déjà liké
            # avant de faire un double tap
            already_liked_selectors = self._feed_sel.already_liked_indicators
            
            for selector in already_liked_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.debug("⏭️ Post already liked (detected via unlike button), skipping")
                    return False
            
            # Double tap seulement si on n'a pas trouvé de bouton like ET le post n'est pas déjà liké
            self.logger.debug("Like button not found, trying double tap")
            screen_height = self.device.info.get('displayHeight', 1920)
            screen_width = self.device.info.get('displayWidth', 1080)
            center_x = screen_width // 2
            center_y = int(screen_height * 0.4)  # Milieu du post
            
            self.device.double_click(center_x, center_y)
            self._human_like_delay('click')
            return True
            
        except Exception as e:
            self.logger.debug(f"Error liking post: {e}")
            return False
    
    def _extract_post_metadata(self) -> Optional[Dict[str, Any]]:
        """Extraire les métadonnées du post actuellement visible (likes, commentaires)."""
        try:
            metadata = {
                'likes_count': self.ui_extractors.extract_likes_count_from_ui(),
                'comments_count': self.ui_extractors.extract_comments_count_from_ui(),
                'is_reel': self._is_reel_post()
            }
            
            self.logger.debug(f"📊 Post metadata: {metadata['likes_count']} likes, {metadata['comments_count']} comments")
            return metadata
            
        except Exception as e:
            self.logger.debug(f"Error extracting post metadata: {e}")
            return None
    
    def _is_reel_post(self) -> bool:
        """Vérifier si le post actuel est un Reel."""
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
    
    def _comment_current_post(self, config: Dict[str, Any]) -> bool:
        """Commenter le post actuellement visible dans le feed."""
        try:
            # Récupérer les commentaires personnalisés ou utiliser des commentaires par défaut
            custom_comments = config.get('custom_comments', [])
            if not custom_comments:
                custom_comments = ['👏', '🔥', '💯', '❤️', '👍', '😍', '✨', '🙌']
            
            comment_text = random.choice(custom_comments)
            
            comment_button_selectors = self._feed_sel.comment_button
            
            # Cliquer sur le bouton commentaire
            for selector in comment_button_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    self._human_like_delay('click')
                    break
            else:
                self.logger.debug("Comment button not found")
                return False
            
            time.sleep(1)
            
            comment_input_selectors = self._feed_sel.comment_input
            
            for selector in comment_input_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    time.sleep(0.5)
                    # Use Taktik Keyboard for reliable text input
                    if not self._type_with_taktik_keyboard(comment_text):
                        self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                        element.set_text(comment_text)
                    self._human_like_delay('typing')
                    break
            else:
                self.logger.debug("Comment input not found")
                self.device.press('back')
                return False
            
            send_button_selectors = self._feed_sel.comment_send_button
            
            for selector in send_button_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    self._human_like_delay('click')
                    time.sleep(1)
                    # Retourner au feed
                    self.device.press('back')
                    return True
            
            self.logger.debug("Send button not found")
            self.device.press('back')
            return False
            
        except Exception as e:
            self.logger.debug(f"Error commenting post: {e}")
            try:
                self.device.press('back')
            except:
                pass
            return False
    
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
                        from bridges.instagram.desktop_bridge import send_follow_event
                        send_follow_event(username, success=True)
                    except ImportError:
                        pass  # Bridge not available (CLI mode)
                    except Exception:
                        pass  # Ignore IPC errors
                    
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
