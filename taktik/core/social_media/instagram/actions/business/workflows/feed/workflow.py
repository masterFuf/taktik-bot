"""Feed workflow orchestration.

Internal structure:
- post_actions.py         — Post-level actions (like, comment, detect, scroll, metadata)
- suggestions.py          — "Follow suggestions" mode (netego carousel -> Discover people)
- suggestions_parsing.py  — Pure XML-dump parsers for both suggestion surfaces
- user_interactions.py    — User-level interactions (navigate to profile, like/follow/story, DB records)
"""

import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ....core.base_business import BaseBusinessAction
from ....core.stats import create_workflow_stats
from ....core.ipc import IPCEmitter
from .post_actions import FeedPostActionsMixin
from .suggestions import FeedSuggestionsMixin


class FeedBusiness(FeedPostActionsMixin, FeedSuggestionsMixin, BaseBusinessAction):
    """Business logic for interacting with users from the home feed."""

    # Consecutive "filler" advances (only ads/suggestions) before the followed feed is
    # considered exhausted. Mirrors the human crawl's session policy (feed-scroll #25).
    _TAIL_FILLER_RUNS = 2

    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "feed", init_business_modules=True)
        
        from ...common.workflow_defaults import FEED_DEFAULTS
        from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SELECTORS
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
    
    def _advance_to_next_post(self, skip_ads: bool, skip_suggested: bool) -> Dict[str, Any]:
        """One human advance to the next real post via the shared crawl.

        Replaces the old fixed ~50% swipe (`_scroll_to_next_post`): a decisive flick/drag
        that coasts, skips ads/suggestions, stops once the engagement bar is in view and
        frames the post at the top. Returns the scroll result dict (`on_feed`, `filler_run`,
        `ads_skipped`, `suggested_skipped`, ...); on error a safe off-feed result so the
        caller stops cleanly.
        """
        try:
            return self.scroll_actions.scroll_feed_to_next_post(
                skip_ads=skip_ads, skip_suggested=skip_suggested
            )
        except Exception as e:
            self.logger.debug(f"Feed advance error: {e}")
            return {'on_feed': False}

    def interact_with_feed(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Interagir avec les utilisateurs depuis le feed.
        
        Args:
            config: Configuration du workflow
            
        Returns:
            Dict avec les statistiques
        """
        effective_config = {**self.default_config, **(config or {})}
        
        stats = create_workflow_stats('feed')
        
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

            # Run "suggestions seules" : on ne vient PAS engager son fil, on vient
            # chercher le carousel de suggestions. Aucun like, aucun commentaire,
            # aucune story — on scrolle jusqu'a le trouver, on follow, on s'arrete.
            if (effective_config.get('follow_suggestions', False)
                    and effective_config.get('suggestions_only', False)):
                self.logger.info("Suggestions-only run: no feed engagement")
                run_result = self.run_suggestions_only(effective_config)
                stats['suggestion_follows'] = run_result.get('follows', 0)
                stats['follows_made'] = run_result.get('follows', 0)
                stats['users_interacted'] = run_result.get('follows', 0)
                stats['success'] = True
                self.logger.info(
                    f"Suggestions-only run finished: {run_result.get('follows', 0)} follow(s) "
                    f"after {run_result.get('carousel_scrolls', 0)} scroll(s), "
                    f"stop={run_result.get('stop_reason')}"
                )
                return stats

            if effective_config.get('view_feed_stories', False):
                self.logger.info("Viewing friends' stories from feed tray")
                story_result = self.story_business.view_feed_stories({
                    'max_feed_profiles': effective_config.get('max_feed_story_profiles', 5),
                    'max_stories_per_profile': effective_config.get('max_stories_per_profile', 3),
                    'view_duration_range': effective_config.get('story_view_duration_range', (2, 6)),
                    'like_probability': effective_config.get('story_like_percentage', 0) / 100,
                    'reaction_probability': effective_config.get('feed_story_reaction_percentage', 0) / 100,
                    'reaction': effective_config.get('feed_story_reaction', 'laugh'),
                    'reaction_index': effective_config.get('feed_story_reaction_index'),
                })
                stats['stories_watched'] += story_result.get('stories_viewed', 0)
                stats['stories_liked'] += story_result.get('stories_liked', 0)
                stats['story_reactions'] = story_result.get('stories_reacted', 0)
                stats['errors'] += story_result.get('errors', 0)

                if not self.nav_actions.navigate_to_home():
                    self.logger.warning("Could not return to home after feed stories")
                time.sleep(1)
            
            # Mode simplifié : liker directement les posts dans le feed
            if effective_config.get('like_posts_directly', True):
                self.logger.info("📱 Direct like mode: liking posts in feed")
                
                if self.session_manager:
                    self.session_manager.start_interaction_phase()
                
                posts_liked = 0
                posts_checked = 0

                # Human crawl toggles (browse_feed-equivalent, driven here so the workflow
                # keeps its like/comment orchestration). The gesture + content-aware dwell
                # live in the shared/atomic layer; the workflow only consumes them.
                skip_ads = effective_config.get('skip_ads', True)
                skip_suggested = effective_config.get('skip_suggested', True)
                read_captions = effective_config.get('read_captions', True)
                browse_carousels = effective_config.get('browse_carousels', True)
                min_likes = effective_config.get('min_post_likes', 0)
                max_likes = effective_config.get('max_post_likes', 0)
                filler_streak = 0

                # Mode "follow des suggestions" : on surveille l'apparition du carousel
                # netego pendant le scroll pour partir follow en masse depuis Discover
                # people, puis revenir liker le feed.
                follow_suggestions = effective_config.get('follow_suggestions', False)
                suggestion_passes_left = (
                    int(effective_config.get('max_suggestion_passes', 1) or 0)
                    if follow_suggestions else 0
                )
                # Say it out loud. A run log with NO trace of this mode cannot be told apart
                # from one where it was off — that ambiguity cost a QA round.
                self.logger.info(
                    f"Suggestions mode: {'armed' if suggestion_passes_left > 0 else 'off'}"
                    + (f" ({suggestion_passes_left} pass(es), "
                       f"max {effective_config.get('max_suggestion_follows', 0)} follow(s))"
                       if suggestion_passes_left > 0 else "")
                )

                while (posts_liked < effective_config['max_interactions'] and
                       posts_checked < effective_config['max_posts_to_check']):

                    posts_checked += 1
                    stats['posts_checked'] += 1

                    self.logger.info(f"📱 Post {posts_checked}/{effective_config['max_posts_to_check']} (liked: {posts_liked})")

                    # The human crawl already skips ads/suggestions when advancing; this only
                    # guards the very first on-screen post (we navigated home, never crawled to it).
                    process_post = True
                    if skip_ads and self._is_sponsored_post():
                        self.logger.debug("⏭️ Skipping sponsored post")
                        stats['posts_skipped_ads'] += 1
                        process_post = False

                    # Taktik Agent copilot: one feed card per real (non-ad) post.
                    # The branches below set `feed_action` ('like'/'like_comment'/'skip')
                    # and `feed_reason`; the author is best-effort (None if not found).
                    post_author = self._get_current_post_author() if process_post else None
                    feed_action = None
                    feed_reason = None

                    # Filtrer par nombre de likes si configuré
                    if process_post and (min_likes > 0 or max_likes > 0):
                        post_metadata = self._extract_post_metadata()
                        self.logger.debug(f"🔍 Post metadata result: {post_metadata}")

                        if post_metadata:
                            post_likes = post_metadata.get('likes_count', 0) or 0
                            if min_likes > 0 and post_likes < min_likes:
                                self.logger.info(f"⏭️ Skipping post: {post_likes} likes < {min_likes} min")
                                stats['posts_skipped_filter'] = stats.get('posts_skipped_filter', 0) + 1
                                process_post = False
                                feed_action, feed_reason = 'skip', f"{post_likes} likes < min {min_likes}"
                            elif max_likes > 0 and post_likes > max_likes:
                                self.logger.info(f"⏭️ Skipping post: {post_likes} likes > {max_likes} max")
                                stats['posts_skipped_filter'] = stats.get('posts_skipped_filter', 0) + 1
                                process_post = False
                                feed_action, feed_reason = 'skip', f"{post_likes} likes > max {max_likes}"
                            else:
                                self.logger.info(f"✅ Post matches filter: {post_likes} likes (max: {max_likes})")
                        else:
                            self.logger.debug("⚠️ Could not extract post metadata, skipping filter")

                    if process_post:
                        # NB filtres de RELATION (skip qui-nous-suit / qu-on-suit) : NON applicables
                        # ici, par conception. Le workflow Feed engage TON PROPRE fil (like/commentaire
                        # de posts + stories du bandeau) = ton audience deja abonnee. Il ne visite
                        # aucun profil, ne lit aucun bouton d'action, ne follow personne : il n'y a pas
                        # de decision d'ACQUISITION a gater (contrairement a target/hashtag/likers).
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
                        commented = False
                        if liked and random.randint(1, 100) <= effective_config.get('comment_percentage', 0):
                            if self._comment_current_post(effective_config):
                                stats['comments_made'] += 1
                                self.stats_manager.increment('comments')
                                self.logger.info(f"💬 Comment posted")
                                commented = True

                        if liked:
                            feed_action = 'like_comment' if commented else 'like'
                            feed_reason = 'Commenté' if commented else 'Liké'
                        else:
                            feed_action, feed_reason = 'skip', 'Non liké (probabilité)'

                        # Lecture humaine du post (carousel + légende + dwell content-aware)
                        # remplace le sleep fixe : on "passe du temps devant le post".
                        self.scroll_actions.human_reading_pause(
                            read_captions=read_captions, browse_carousels=browse_carousels
                        )

                    # Copilot feed card (skip pure ad-skips, which leave feed_action None).
                    if feed_action is not None:
                        IPCEmitter.emit_feed_decision(post_author, feed_action, reason=feed_reason)

                    # Le carousel de suggestions est arrive a l'ecran : on part follow
                    # en masse, puis on revient poursuivre le feed la ou on en etait.
                    if suggestion_passes_left > 0 and self.has_feed_suggestions_carousel():
                        suggestion_passes_left -= 1
                        pass_result = self.run_feed_suggestions_pass(effective_config)
                        stats['suggestion_follows'] = (
                            stats.get('suggestion_follows', 0) + pass_result.get('follows', 0)
                        )
                        stats['follows_made'] = (
                            stats.get('follows_made', 0) + pass_result.get('follows', 0)
                        )
                        self.logger.info(
                            f"Suggestions pass: {pass_result.get('follows', 0)} follow(s), "
                            f"stop={pass_result.get('stop_reason')}, "
                            f"contacts={pass_result.get('contacts_dialog')}"
                        )
                        if pass_result.get('entered') and not pass_result.get('returned_to_feed'):
                            self.logger.info("Could not get back to the feed - stopping")
                            break

                    # Avance humaine vers le prochain VRAI post (skip pubs/suggestions,
                    # stop-on-metadata, cadrage). Un seul point d'avance pour toute la boucle.
                    # While a suggestions pass is still owed, the crawl must NOT skip
                    # suggestion blocks: the netego carousel IS the block we are waiting
                    # for, and `scroll_feed_to_next_post` is the advance to the next REAL
                    # post — it scrolled straight past the carousel, so the probe above
                    # never saw it and the pass never fired (QA 2026-07-27: the dump showed
                    # the carousel on screen while the run kept liking posts).
                    res = self._advance_to_next_post(
                        skip_ads, skip_suggested and suggestion_passes_left <= 0
                    )
                    stats['posts_skipped_ads'] += res.get('ads_skipped', 0)
                    stats['posts_skipped_suggested'] = (
                        stats.get('posts_skipped_suggested', 0) + res.get('suggested_skipped', 0)
                    )

                    if not res.get('on_feed', False):
                        self.logger.info("🏁 Left the feed (reel/profile) - stopping")
                        break

                    # Feed suivi épuisé : N gestes "filler" (que des pubs/suggestions) d'affilée.
                    if res.get('filler_run'):
                        filler_streak += 1
                        if filler_streak >= self._TAIL_FILLER_RUNS:
                            self.logger.info("🏁 Feed tail (only recommendations) - stopping")
                            break
                    else:
                        filler_streak = 0

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
