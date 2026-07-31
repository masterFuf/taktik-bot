"""Business logic for Instagram hashtag interactions."""

import time
import random
import re
from typing import Dict, List, Any, Optional
from loguru import logger

from ..common.likers_base import LikersWorkflowBase
from ....core.stats import create_workflow_stats
from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter
from taktik.core.database.instagram_hashtag_posts import InstagramHashtagPostService
from taktik.core.social_media.instagram.ui.extractors import parse_number_from_text

from .mixins.post_finder import HashtagPostFinderMixin
from .mixins.extractors import HashtagExtractorsMixin


# « Pas de maximum » : une borne haute reste plus simple à lire qu'un `None` à tester dans
# chacune des trois comparaisons. Aucun post Instagram n'approche ce nombre.
NO_LIKES_CEILING = 10 ** 9

# Valeurs historiques du catalogue, appliquées quand personne ne dit rien.
DEFAULT_MIN_POST_LIKES = 100
DEFAULT_MAX_POST_LIKES = 50000


def resolve_post_like_bounds(config: Dict[str, Any]) -> tuple:
    """Les bornes de likes du post retenu, quelle que soit la forme reçue.

    Le critère arrive sous DEUX formes : à plat (`min_likes`, défauts du workflow) et
    imbriqué (`post_criteria`, ce qu'envoient la page Hashtag, le runner et la CLI). Les deux
    moitiés du workflow n'en lisaient pas la même — la recherche du premier post lisait la
    forme plate, la boucle de swipe la forme imbriquée. Tant que l'opérateur ne renseigne
    rien les deux valent 100-50000 et ça ne se voit pas ; dès qu'il fixe un seuil, un post
    accepté par la recherche est rejeté par la boucle, et le workflow tourne en rond.

    `0` = PAS DE BORNE, exactement comme dans le workflow Feed (`min_post_likes` /
    `max_post_likes`, qui ne testent que si la valeur est > 0). Sans cette convention,
    « aucun minimum » serait inexprimable : c'est pourtant ce qu'il faut pour travailler un
    hashtag dont les posts font vingt likes.
    """
    post_criteria = config.get('post_criteria') or {}
    min_likes = post_criteria.get('min_likes', config.get('min_likes', DEFAULT_MIN_POST_LIKES))
    max_likes = post_criteria.get('max_likes', config.get('max_likes', DEFAULT_MAX_POST_LIKES))
    return (
        min_likes if min_likes and min_likes > 0 else 0,
        max_likes if max_likes and max_likes > 0 else NO_LIKES_CEILING,
    )


class HashtagBusiness(
    HashtagPostFinderMixin,
    HashtagExtractorsMixin,
    LikersWorkflowBase
):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "hashtag", init_business_modules=True)
        
        from ...common.workflow_defaults import HASHTAG_DEFAULTS
        from taktik.core.social_media.instagram.ui.selectors.surfaces.hashtag import HASHTAG_SELECTORS
        self.default_config = {**HASHTAG_DEFAULTS}
        self._hashtag_sel = HASHTAG_SELECTORS
    
    def _interact_with_hashtag_posts(self, hashtag: str, effective_config: Dict[str, Any],
                                     stats: Dict[str, Any], account_id,
                                     finalize: bool = True) -> Dict[str, Any]:
        """Mode 'posts' — engage the POSTS of a hashtag, never a list of people.

        The 'likers' mode opens ONE post and spends the whole run on the people who liked
        it. This one keeps walking the hashtag instead: a post is chosen by the same
        criteria (like bounds, 7-day dedup), liked and/or commented where it stands, and the
        run moves on to the next. Same discovery machinery, different thing engaged — which
        is why it is a mode of this workflow and not a workflow of its own.

        `max_interactions` counts POSTS here: no profile is ever visited, so there is
        nothing else to count. Every action goes through the production atomics
        (`like_business.like_current_post`, `comment_business.comment_on_post`), so smart
        comments, telemetry and daily caps behave exactly as everywhere else.
        """
        max_posts = int(effective_config.get('max_interactions') or 0)
        max_to_examine = int(effective_config.get('max_posts_to_analyze') or 20)
        like_pct = int(effective_config.get('like_percentage') or 0)
        comment_pct = int(effective_config.get('comment_percentage') or 0)
        min_likes, max_likes = effective_config['min_likes'], effective_config['max_likes']

        self.logger.info(
            f"📝 Posts mode on #{hashtag}: up to {max_posts} post(s), "
            f"like {like_pct}%, comment {comment_pct}%"
        )

        if self.session_manager:
            self.session_manager.start_interaction_phase()

        posts_engaged = 0
        examined = 0
        need_to_open_post = True
        stop_reason = ''

        while posts_engaged < max_posts and examined < max_to_examine:
            if need_to_open_post:
                current = self._find_first_valid_post(hashtag, effective_config, skip_count=0)
                if not current:
                    stop_reason = 'no_valid_post'
                    self.logger.warning("No post matching the criteria")
                    break
                need_to_open_post = False
            else:
                is_reel = self._is_reel_post()
                current = {
                    'likes_count': self.ui_extractors.extract_likes_count_from_ui(is_reel=is_reel),
                    'comments_count': self.ui_extractors.extract_comments_count_from_ui(is_reel=is_reel),
                    'is_reel': is_reel,
                }

            examined += 1
            stats['posts_analyzed'] = examined

            likes_count = current.get('likes_count') or 0
            if not (min_likes <= likes_count <= max_likes):
                self.logger.info(
                    f"⏭️ {likes_count} likes outside {min_likes}-{max_likes}, next post"
                )
                stats['already_filtered'] = stats.get('already_filtered', 0) + 1
                if not self._swipe_to_next_post(known_signature=self._signature_of(current)):
                    stop_reason = 'no_new_post'
                    break
                continue

            metadata = self._extract_current_post_metadata(current.get('is_reel', False))
            author = (metadata or {}).get('author')

            if author:
                try:
                    IPCEmitter.emit_current_post(
                        author=author,
                        likes_count=(metadata or {}).get('likes_count'),
                        comments_count=(metadata or {}).get('comments_count'),
                        caption=(metadata or {}).get('caption'),
                        hashtag=hashtag,
                    )
                except Exception as exc:
                    self.logger.debug(f"Failed to send current_post: {exc}")

                # Same 7-day guard as the likers mode: a post we already engaged must not be
                # engaged twice, and re-liking a liked post would UNLIKE it.
                if InstagramHashtagPostService.is_processed(
                    hashtag=hashtag, post_author=author,
                    post_caption_hash=(metadata or {}).get('caption_hash'),
                    account_id=account_id, hours_limit=168,
                ):
                    self.logger.info(f"⏭️ Post by @{author} already processed, next post")
                    stats['already_processed'] = stats.get('already_processed', 0) + 1
                    try:
                        IPCEmitter.emit_post_skipped(
                            author=author, reason="already_processed", hashtag=hashtag,
                        )
                    except Exception as exc:
                        self.logger.debug(f"Failed to send post_skipped: {exc}")
                    if not self._swipe_to_next_post(known_signature=self._signature_of(current)):
                        stop_reason = 'no_new_post'
                        break
                    self._human_like_delay('navigation')
                    continue

            stats['posts_selected'] = stats.get('posts_selected', 0) + 1

            liked = False
            if like_pct > 0 and random.randint(1, 100) <= like_pct:
                if self.like_business.like_current_post():
                    liked = True
                    stats['likes_made'] += 1
                    self.stats_manager.increment('likes')
                    self.logger.info(f"❤️ Post liked (@{author or 'unknown'})")

            commented = False
            if comment_pct > 0 and random.randint(1, 100) <= comment_pct:
                result = self.comment_business.comment_on_post(
                    custom_comments=effective_config.get('custom_comments'),
                    config=effective_config,
                    username=author,
                )
                if result and result.get('commented'):
                    commented = True
                    stats['comments_made'] += 1
                    self.stats_manager.increment('comments')
                    self.logger.info(f"💬 Comment posted (@{author or 'unknown'})")

            if liked or commented:
                posts_engaged += 1
                stats['users_interacted'] = posts_engaged
                if author and account_id:
                    InstagramHashtagPostService.record_processed(
                        hashtag=hashtag, post_author=author,
                        post_caption_hash=(metadata or {}).get('caption_hash'),
                        post_caption_preview=((metadata or {}).get('caption') or '')[:100] or None,
                        likes_count=(metadata or {}).get('likes_count'),
                        comments_count=(metadata or {}).get('comments_count'),
                        likers_processed=0,
                        interactions_made=1,
                        account_id=account_id,
                    )

            # Read the post like a person before moving on (carousel + caption + dwell),
            # the same pause the Feed workflow takes between two posts.
            try:
                self.scroll_actions.human_reading_pause(
                    read_captions=effective_config.get('read_captions', True),
                    browse_carousels=effective_config.get('browse_carousels', True),
                )
            except Exception as exc:
                self.logger.debug(f"Reading pause skipped: {exc}")

            if posts_engaged >= max_posts:
                stop_reason = 'budget_reached'
                break
            if not self._swipe_to_next_post(known_signature=self._signature_of(current)):
                stop_reason = 'no_new_post'
                break

        if not stop_reason and examined >= max_to_examine:
            stop_reason = 'max_posts_examined'

        stats['stop_reason'] = stop_reason or 'budget_reached'
        stats['success'] = posts_engaged > 0
        self.logger.info(
            f"✅ Posts mode finished: {posts_engaged} post(s) engaged "
            f"({stats['likes_made']} like(s), {stats['comments_made']} comment(s)) "
            f"out of {examined} examined — stop={stats['stop_reason']}"
        )
        self.stats_manager.display_final_stats(workflow_name="HASHTAG")

        if finalize and self.automation and hasattr(self.automation, 'helpers'):
            self.automation.helpers.finalize_session(status='COMPLETED', reason=stats['stop_reason'])

        return stats

    def interact_with_hashtag_likers(self, hashtag: str, config: Dict[str, Any] = None,
                                     finalize: bool = True) -> Dict[str, Any]:
        effective_config = {**self.default_config, **(config or {})}

        # Une seule lecture des bornes du post, pour les deux moitiés du workflow (voir
        # `resolve_post_like_bounds`). Écrites à plat : tout le reste lit cette forme.
        effective_config['min_likes'], effective_config['max_likes'] = resolve_post_like_bounds(effective_config)

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

            # Mode 'posts' : on n'ouvre AUCUNE liste de personnes. On enchaîne les posts du
            # hashtag et on les like/commente directement, comme le workflow Feed le fait sur
            # ton propre fil. Chemin séparé de bout en bout : la voie 'likers' ci-dessous est
            # la voie historique, inchangée.
            if str(effective_config.get('interaction_mode') or 'likers').strip().lower() == 'posts':
                return self._interact_with_hashtag_posts(
                    hashtag, effective_config, stats, account_id, finalize=finalize,
                )

            # Boucle pour trouver un post non encore traité
            max_posts_to_try = effective_config.get('max_posts_to_analyze', 20)
            posts_tried = 0
            valid_post = None
            post_metadata = None
            need_to_open_post = True  # Flag pour savoir si on doit ouvrir un post depuis la grille
            # Un post RETENU, pas simplement le dernier examiné. Sans ce drapeau, une boucle
            # qui s'épuise (20 posts tous écartés) laissait `valid_post` renseigné : la garde
            # plus bas ne voyait rien et le workflow ouvrait les likers d'un post qu'il venait
            # de rejeter — celui-là même qu'il avait déjà traité il y a moins de 7 jours.
            post_ready = False

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
                    likes_count = self.ui_extractors.extract_likes_count_from_ui(is_reel=is_reel)
                    comments_count = self.ui_extractors.extract_comments_count_from_ui(is_reel=is_reel)
                    valid_post = {
                        'likes_count': likes_count,
                        'comments_count': comments_count,
                        'is_reel': is_reel
                    }
                    # Critères résolus une seule fois en tête de méthode (plate = source unique).
                    min_likes = effective_config['min_likes']
                    max_likes = effective_config['max_likes']
                    if not (min_likes <= likes_count <= max_likes):
                        self.logger.info(f"⏭️ Post has {likes_count} likes (criteria: {min_likes}-{max_likes}), swiping to next...")
                        posts_tried += 1
                        if not self._swipe_to_next_post(known_signature=self._signature_of(valid_post)):
                            break
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
                        IPCEmitter.emit_current_post(
                            author=post_metadata['author'],
                            likes_count=post_metadata.get('likes_count'),
                            comments_count=post_metadata.get('comments_count'),
                            caption=post_metadata.get('caption'),
                            hashtag=hashtag,
                        )
                        self.logger.debug(f"📤 Sent current_post to frontend: @{post_metadata['author']}")
                    except Exception as e:
                        self.logger.debug(f"Failed to send current_post: {e}")
                    
                    # Vérifier si ce post a déjà été traité
                    if InstagramHashtagPostService.is_processed(
                        hashtag=hashtag,
                        post_author=post_metadata['author'],
                        post_caption_hash=post_metadata.get('caption_hash'),
                        account_id=account_id,
                        hours_limit=168  # 7 jours
                    ):
                        self.logger.info(f"⏭️ Post by @{post_metadata['author']} already processed, swiping to next post...")
                        # Notifier le frontend qu'on skip ce post
                        try:
                            IPCEmitter.emit_post_skipped(
                                author=post_metadata['author'],
                                reason="already_processed",
                                hashtag=hashtag,
                            )
                        except Exception as e:
                            self.logger.debug(f"Failed to send post_skipped: {e}")
                        # Passer au post suivant — et s'arrêter si on n'y arrive pas, plutôt
                        # que de re-lire le même post jusqu'à épuiser le budget.
                        if not self._swipe_to_next_post(known_signature=self._signature_of(valid_post)):
                            break
                        self._human_like_delay('navigation')
                        need_to_open_post = False  # On est déjà sur un post après le swipe
                        continue
                    else:
                        self.logger.info(f"✅ New post by @{post_metadata['author']} - proceeding with interactions")
                        stats['posts_selected'] += 1
                        post_ready = True
                        break
                else:
                    # Si on ne peut pas extraire les métadonnées, on continue quand même
                    self.logger.warning("⚠️ Could not extract post metadata, proceeding anyway")
                    stats['posts_selected'] += 1
                    post_ready = True
                    break

            if not post_ready:
                # `valid_post` peut être renseigné (le dernier post examiné) sans avoir été
                # RETENU : ne pas ouvrir ses likers, c'est justement celui qu'on a écarté.
                self.logger.warning(
                    f"No unprocessed post found for #{hashtag} after {posts_tried} post(s) examined"
                )
                stats['stop_reason'] = 'no_new_post'
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
                InstagramHashtagPostService.record_processed(
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

            # finalize=False: a multi-hashtag run finalises ONCE at the driver level —
            # finalising here would end the session after the first hashtag.
            if finalize and stats.get('stop_reason') and self.automation and hasattr(self.automation, 'helpers'):
                self.automation.helpers.finalize_session(status='COMPLETED', reason=stats['stop_reason'])

        except Exception as e:
            self.logger.error(f"General hashtag workflow error: {e}")
            stats['errors'] += 1
            self.stats_manager.add_error(f"General error: {e}")
        
        return stats
    
