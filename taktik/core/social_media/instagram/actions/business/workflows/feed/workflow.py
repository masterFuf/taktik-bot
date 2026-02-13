"""Feed workflow orchestration.

Internal structure:
- post_actions.py       — Post-level actions (like, comment, detect, scroll, metadata)
- user_interactions.py  — User-level interactions (navigate to profile, like/follow/story, DB records)
"""

import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ....core.base_business_action import BaseBusinessAction
from .post_actions import FeedPostActionsMixin
from .user_interactions import FeedUserInteractionsMixin


class FeedBusiness(FeedPostActionsMixin, FeedUserInteractionsMixin, BaseBusinessAction):
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
