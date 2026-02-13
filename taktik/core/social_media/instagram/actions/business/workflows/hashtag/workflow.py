"""Business logic for Instagram hashtag interactions."""

import time
import random
import re
from typing import Dict, List, Any, Optional
from loguru import logger

from ..common.likers_base import LikersWorkflowBase
from ...common.database_helpers import DatabaseHelpers
from ....core.stats import create_workflow_stats
from taktik.core.database import get_db_service
from taktik.core.social_media.instagram.ui.extractors import parse_number_from_text

from .mixins.post_finder import HashtagPostFinderMixin
from .mixins.extractors import HashtagExtractorsMixin


class HashtagBusiness(
    HashtagPostFinderMixin,
    HashtagExtractorsMixin,
    LikersWorkflowBase
):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "hashtag", init_business_modules=True)
        
        from ...common.workflow_defaults import HASHTAG_DEFAULTS
        from .....ui.selectors import HASHTAG_SELECTORS
        self.default_config = {**HASHTAG_DEFAULTS}
        self._hashtag_sel = HASHTAG_SELECTORS
    
    def interact_with_hashtag_likers(self, hashtag: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        effective_config = {**self.default_config, **(config or {})}
        
        self.logger.info(f"Hashtag config received: {config}")
        self.logger.info(f"Hashtag config effective: max_interactions={effective_config.get('max_interactions', 'N/A')}")
        
        stats = create_workflow_stats('hashtag', source=hashtag)
        
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
    
