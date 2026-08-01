"""Business logic for Instagram hashtag interactions."""

import time
import random
import re
from typing import Dict, List, Any, Optional
from loguru import logger

from ..common.likers_base import LikersWorkflowBase
from ..common.list_sources import resolve_list_source
from .interaction_plan import resolve_interaction_plan
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
    
    def _engage_one_post(self, hashtag: str, plan, effective_config: Dict[str, Any],
                         stats: Dict[str, Any], is_reel: bool, author: Optional[str]) -> bool:
        """Do everything the plan asks of the post currently on screen.

        The three things a post is worth are independent — like/comment it, walk the people
        who liked it, walk the people who wrote under it — and this runs whichever ones are
        enabled, in that order. Each population keeps its OWN per-post budget, because "five
        likers and two commenters" is the sentence operators actually want to write.

        Order matters: engaging the post happens while we are still on it, and each people
        walk ends by closing what it opened, so the next one starts from the post again.

        Returns True when anything at all was done — the caller counts engaged posts, not
        attempts.
        """
        did_something = False

        if plan.engage_posts:
            if self._engage_post_itself(effective_config, stats, author):
                did_something = True

        # A people walk LEAVES the post. Only the populations asked for are opened, and each
        # one is closed again so the loop can advance from a known place.
        for enabled, mode, budget in (
            (plan.walk_likers, 'likers', plan.max_likers_per_post),
            (plan.walk_commenters, 'commenters', plan.max_commenters_per_post),
        ):
            if not enabled:
                continue
            if self._walk_post_people(hashtag, mode, budget, effective_config, stats, is_reel):
                did_something = True

        return did_something

    def _engage_post_itself(self, effective_config: Dict[str, Any], stats: Dict[str, Any],
                            author: Optional[str]) -> bool:
        """Like and/or comment the post on screen, through the production atomics."""
        like_pct = int(effective_config.get('like_percentage') or 0)
        comment_pct = int(effective_config.get('comment_percentage') or 0)
        touched = False

        if like_pct > 0 and random.randint(1, 100) <= like_pct:
            if self.like_business.like_current_post():
                stats['likes_made'] += 1
                self.stats_manager.increment('likes')
                self.logger.info(f"❤️ Post liked (@{author or 'unknown'})")
                touched = True

        if comment_pct > 0 and random.randint(1, 100) <= comment_pct:
            result = self.comment_business.comment_on_post(
                custom_comments=effective_config.get('custom_comments'),
                config=effective_config,
                username=author,
            )
            if result and result.get('commented'):
                stats['comments_made'] += 1
                self.stats_manager.increment('comments')
                self.logger.info(f"💬 Comment posted (@{author or 'unknown'})")
                touched = True

        return touched

    def _walk_post_people(self, hashtag: str, mode: str, budget: int,
                          effective_config: Dict[str, Any], stats: Dict[str, Any],
                          is_reel: bool) -> bool:
        """Open one population of the post and walk it, then close it again.

        Same shared loop as post_url and target (`_interact_with_likers_list`); only the row
        plumbing differs, which is what `resolve_list_source` decides.
        """
        try:
            if mode == 'commenters':
                opened = self._open_comments_view()
            else:
                opened = self._open_likers_popup(is_reel)
            if not opened:
                self.logger.warning(f"Could not open the {mode} of this post")
                return False

            before = stats.get('users_interacted', 0)
            self.logger.info(f"🚀 Walking the {mode} of this post (up to {budget})")
            self._interact_with_likers_list(
                stats=stats,
                effective_config={**effective_config, 'source': f"#{hashtag}"},
                max_interactions=budget,
                source_type='HASHTAG',
                source_name=f"#{hashtag}",
                list_source=resolve_list_source(self, mode),
            )
            return stats.get('users_interacted', 0) > before
        except Exception as exc:
            self.logger.error(f"Error while walking the {mode}: {exc}")
            stats['errors'] += 1
            return False
        finally:
            # Whatever happened, come back to the post: the next population — and the next
            # advance — both assume we are standing on it.
            try:
                if mode == 'commenters':
                    self._close_comments_view()
                else:
                    self._close_likers_popup()
            except Exception as exc:
                self.logger.debug(f"Could not close the {mode} view: {exc}")

    def _run_interaction_plan(self, hashtag: str, plan, effective_config: Dict[str, Any],
                              stats: Dict[str, Any], account_id,
                              finalize: bool = True) -> Dict[str, Any]:
        """Walk the posts of a hashtag and do whatever the plan asks of each one.

        ONE loop for every mode. There used to be two — one that opened a single post and
        spent the run on its likers, one that walked many posts and engaged none of their
        people — which is why the two could never be combined. The post is the unit here,
        and `_engage_one_post` decides what it is worth.

        A legacy `likers` run resolves to max_posts=1 plus a likers walk, so it opens one
        post and walks it exactly as before. That equivalence is the whole safety argument
        for unifying the two loops, and it is pinned by tests.
        """
        max_posts = plan.max_posts
        max_to_examine = int(effective_config.get('max_posts_to_analyze') or 20)
        min_likes, max_likes = effective_config['min_likes'], effective_config['max_likes']

        self.logger.info(f"📋 Plan on #{hashtag}: {plan.describe()}")
        if plan.is_noop:
            self.logger.warning("Nothing enabled in the plan — no post would be engaged")
            stats['stop_reason'] = 'empty_plan'
            return stats

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
            stats['posts_engaged'] = stats.get('posts_engaged', 0)

            # Tout ce que le plan demande de ce post : l'engager, parcourir ses likers,
            # parcourir ses commentateurs — chacun avec son propre budget par post.
            engaged = self._engage_one_post(
                hashtag, plan, effective_config, stats, current.get('is_reel', False), author,
            )

            if engaged:
                posts_engaged += 1
                stats['posts_engaged'] = posts_engaged
                # Compteur partage : c'est lui qui remonte au panneau en direct et a la
                # session. Sans ca un plan « posts seuls » ne produit rien de mesurable.
                self.stats_manager.increment('posts_engaged')
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

            # UNE seule voie desormais. Le plan dit ce que vaut chaque post — l'engager,
            # parcourir ses likers, parcourir ses commentateurs — et la boucle marche les
            # posts. Les trois anciens modes sont des cas particuliers de ce plan, traduits
            # litteralement pour qu'une config enregistree se comporte comme avant.
            plan = resolve_interaction_plan(effective_config)
            effective_config['source'] = f"#{hashtag}"
            # Ce qui a REELLEMENT tourne, pour que la session puisse le dire.
            stats['interaction_plan'] = plan.as_record()
            stats['interaction_plan_label'] = plan.describe()

            if self.session_manager:
                self.session_manager.start_interaction_phase()

            result = self._run_interaction_plan(
                hashtag, plan, effective_config, stats, account_id, finalize=finalize,
            )
            return result

        except Exception as e:
            self.logger.error(f"General hashtag workflow error: {e}")
            stats['errors'] += 1
            self.stats_manager.add_error(f"General error: {e}")
        
        return stats
    
