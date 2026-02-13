"""Feed user interactions: navigate to profile, like/follow/story, record to DB."""

import time
import random
from typing import Dict, List, Any, Optional

from ...common.database_helpers import DatabaseHelpers


class FeedUserInteractionsMixin:
    """Mixin: user-level interactions from the feed (profile visit, like, follow, story, DB records)."""

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
