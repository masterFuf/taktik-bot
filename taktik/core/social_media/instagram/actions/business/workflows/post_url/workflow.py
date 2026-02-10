"""Business logic for Instagram post URL interactions."""

from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
import random
import re
import time

from .._likers_common import LikersWorkflowBase
from ...common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service

from .url_handling import PostUrlHandlingMixin
from .extractors import PostUrlExtractorsMixin


class PostUrlBusiness(
    PostUrlHandlingMixin,
    PostUrlExtractorsMixin,
    LikersWorkflowBase
):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "post-url", init_business_modules=True)
        from ...common.workflow_defaults import POST_URL_DEFAULTS
        from .....ui.selectors import HASHTAG_SELECTORS
        self.default_config = {**POST_URL_DEFAULTS}
        self._hashtag_sel = HASHTAG_SELECTORS
    
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
