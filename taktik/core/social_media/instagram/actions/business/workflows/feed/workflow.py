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

from ..common.likers_base import LikersWorkflowBase
from ....core.stats import create_workflow_stats
from ....core.ipc import IPCEmitter
from .post_actions import FeedPostActionsMixin
from .suggestions import FeedSuggestionsMixin
from .suggestions_visit import DiscoverSuggestionsVisitMixin


class FeedBusiness(FeedPostActionsMixin, DiscoverSuggestionsVisitMixin,
                   FeedSuggestionsMixin, LikersWorkflowBase):
    """Business logic for interacting with users from the home feed.

    Base swapped from `BaseBusinessAction` to `LikersWorkflowBase`, which only ADDS the
    likers-walking loop to the same class (checked: no method of it collides with the feed
    mixins). That loop is what `interact_with_post_likers` needs, and re-implementing a
    second one here is exactly the duplication this project keeps paying for.
    """

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
    
    def _advance_to_next_post(self, skip_ads: bool, skip_suggested: bool,
                              on_ad=None) -> Dict[str, Any]:
        """One human advance to the next real post via the shared crawl.

        Replaces the old fixed ~50% swipe (`_scroll_to_next_post`): a decisive flick/drag
        that coasts, skips ads/suggestions, stops once the engagement bar is in view and
        frames the post at the top. Returns the scroll result dict (`on_feed`, `filler_run`,
        `ads_skipped`, `suggested_skipped`, ...); on error a safe off-feed result so the
        caller stops cleanly.

        `on_ad` (opt-in) is handed straight to the crawl, which calls it while a sponsored
        post is still on screen — see `ad_capture`.
        """
        try:
            return self.scroll_actions.scroll_feed_to_next_post(
                skip_ads=skip_ads, skip_suggested=skip_suggested, on_ad=on_ad
            )
        except Exception as e:
            self.logger.debug(f"Feed advance error: {e}")
            return {'on_feed': False}

    def _engage_post_author(self, username: str, config: Dict[str, Any],
                            stats: Dict[str, Any]) -> bool:
        """Visit the author of the post we just engaged, interact, come back to the feed.

        This is where `follow_percentage` and `story_watch_percentage` finally mean
        something: both were in the catalogue and read by nobody, because the feed workflow
        never left the feed. A feed post carries no Follow button and no story ring — the
        author's PROFILE does, so reaching them requires the visit.

        Delegates to `_perform_interactions_on_profile`, the same engine target, hashtag and
        post_url use: probabilities, caps, telemetry and the AI hooks are shared rather than
        re-implemented for the feed. Returns True when something was actually done.
        """
        try:
            self.logger.info(f"👤 Visiting the post author @{username}")
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.debug(f"Could not reach @{username}")
                return False

            profile_data = self.profile_business.get_complete_profile_info(
                username, navigate_if_needed=False,
            )
            result = self._perform_interactions_on_profile(username, config, profile_data=profile_data)

            stats['likes_made'] += result.get('likes', 0)
            stats['follows_made'] = stats.get('follows_made', 0) + result.get('follows', 0)
            stats['comments_made'] += result.get('comments', 0)
            stats['stories_watched'] = stats.get('stories_watched', 0) + result.get('stories', 0)
            stats['stories_liked'] = stats.get('stories_liked', 0) + result.get('stories_liked', 0)
            return bool(result.get('actually_interacted'))
        except Exception as exc:
            self.logger.debug(f"Author engagement failed: {exc}")
            return False
        finally:
            # Always hand the feed back: the loop's next advance assumes we are on it, and a
            # crawl that starts from a profile page walks somebody else's posts.
            try:
                self.nav_actions.navigate_to_home()
            except Exception as exc:
                self.logger.debug(f"Could not return to the feed: {exc}")

    def _engage_post_likers(self, config: Dict[str, Any], stats: Dict[str, Any]) -> None:
        """Open the likers of the post on screen and walk them, then come back to the feed.

        Same loop as the hashtag and post_url workflows (`_interact_with_likers_list`), which
        is why this class now extends `LikersWorkflowBase`: the feed had no way to reach it,
        and a second implementation of "walk a likers sheet" is exactly the duplication this
        project keeps paying for.
        """
        try:
            if not self._open_likers_popup(is_reel=self._is_reel_post()):
                self.logger.debug("No likers sheet on this post")
                return

            budget = int(config.get('max_likers_per_post', 5) or 5)
            self.logger.info(f"👥 Walking the post likers (up to {budget})")
            self._interact_with_likers_list(
                stats=stats,
                effective_config={**config, 'source': 'feed'},
                max_interactions=budget,
                source_type='FEED',
                source_name='feed',
            )
        except Exception as exc:
            self.logger.debug(f"Likers engagement failed: {exc}")
        finally:
            try:
                self.nav_actions.navigate_to_home()
            except Exception as exc:
                self.logger.debug(f"Could not return to the feed: {exc}")

    def interact_with_feed(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Interact with users from the feed.
        
        Args:
            config: workflow configuration
            
        Returns:
            Dict of statistics
        """
        effective_config = {**self.default_config, **(config or {})}
        
        stats = create_workflow_stats('feed')
        
        try:
            self.logger.info("📱 Starting feed workflow")
            self.logger.info(f"Max interactions: {effective_config['max_interactions']}")
            self.logger.info(f"Max posts to check: {effective_config['max_posts_to_check']}")
            
            # Navigate to the feed
            if not self.nav_actions.navigate_to_home():
                self.logger.error("Failed to navigate to home feed")
                stats['errors'] += 1
                return stats
            
            time.sleep(2)

            # Suggestions-only run: this is NOT about engaging our own feed, it is
            # about finding the suggestions carousel. No like, no comment,
            # no story: scroll until the carousel is found, follow, and stop.
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
            
            # Simplified mode: like the posts directly in the feed
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
                # These three settings existed in the catalog without ANY code reading
                # them: the front could send them and nothing happened. They act
                # now, and keep their historical values by default.
                skip_reels = effective_config.get('skip_reels', False)
                visit_author = effective_config.get('interact_with_post_author', False)
                visit_likers = effective_config.get('interact_with_post_likers', False)
                filler_streak = 0

                # Ad harvesting (opt-in). The crawl already recognises sponsored posts to
                # skip them; this keeps what it recognised instead of throwing it away.
                # Built once per run, and only when asked — the callback stays None
                # otherwise, so the crawl behaves exactly as before.
                on_ad = None
                if effective_config.get('capture_ads', False):
                    from .ad_capture import make_ad_capturer
                    on_ad = make_ad_capturer(
                        self.device,
                        account_id=getattr(self.automation, 'active_account_id', None)
                        if self.automation else None,
                    )
                    self.logger.info("Ad capture: ON (sponsored posts met will be recorded)")

                # Suggestions-follow mode: the carousel is watched for during the scroll
                # so the run can leave for the discovery screen, follow in bulk,
                # then come back to the feed.
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

                    # A reel is watched, not browsed: an operator who ticks this wants to
                    # engage posts, not be captured by the viewer.
                    if process_post and skip_reels and self._is_reel_post():
                        self.logger.debug("⏭️ Skipping reel")
                        stats['posts_skipped_reels'] = stats.get('posts_skipped_reels', 0) + 1
                        process_post = False

                    # Taktik Agent copilot: one feed card per real (non-ad) post.
                    # The branches below set `feed_action` ('like'/'like_comment'/'skip')
                    # and `feed_reason`; the author is best-effort (None if not found).
                    post_author = self._get_current_post_author() if process_post else None
                    feed_action = None
                    feed_reason = None

                    # Filter by like count when configured
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
                        # RELATIONSHIP filters are NOT applicable here, by design. This workflow
                        # engages OUR OWN feed — posts and story tray — which is our already
                        # subscribed audience. It visits no profile, reads no action button and
                        # follows nobody, so there is no
                        # de decision d'ACQUISITION a gater (contrairement a target/hashtag/likers).
                        # Like the post directly in the feed
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

                        # Comment the post when configured
                        commented = False
                        if liked and random.randint(1, 100) <= effective_config.get('comment_percentage', 0):
                            if self._comment_current_post(effective_config):
                                stats['comments_made'] += 1
                                self.stats_manager.increment('comments')
                                self.logger.info(f"💬 Comment posted")
                                commented = True

                        if liked or commented:
                            # An engaged feed post IS the output of this workflow: it visits no
                            # profile, so nothing else counts it.
                            stats['posts_engaged'] = stats.get('posts_engaged', 0) + 1
                            self.stats_manager.increment('posts_engaged')

                        if liked:
                            feed_action = 'like_comment' if commented else 'like'
                            feed_reason = 'Commenté' if commented else 'Liké'
                        else:
                            feed_action, feed_reason = 'skip', 'Non liké (probabilité)'

                        # Human reading of the post (carousel, caption, content-aware dwell)
                        # replaces the fixed sleep: time is actually spent in front of the post.
                        self.scroll_actions.human_reading_pause(
                            read_captions=read_captions, browse_carousels=browse_carousels
                        )

                        # ACQUISITION from the feed (opt-in). This workflow long engaged only
                        # its own posts; these two modes take it out of the feed to go and
                        # find profiles. They are therefore off by default, and the RELATIONSHIP
                        # filters become relevant again as soon as they are active — unlike the
                        # feed-liking mode, there is a
                        # vraie decision d'acquisition a gater.
                        if visit_author and post_author:
                            stats['users_interacted'] = stats.get('users_interacted', 0) + (
                                1 if self._engage_post_author(post_author, effective_config, stats) else 0
                            )

                        if visit_likers:
                            self._engage_post_likers(effective_config, stats)

                    # Copilot feed card (skip pure ad-skips, which leave feed_action None).
                    if feed_action is not None:
                        IPCEmitter.emit_feed_decision(post_author, feed_action, reason=feed_reason)

                    # The suggestions carousel reached the screen: leave to follow
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

                    # Human advance to the next REAL post (skips ads and suggestions,
                    # stops on metadata, reframes). One single advance point for the loop.
                    # While a suggestions pass is still owed, the crawl must NOT skip
                    # suggestion blocks: the netego carousel IS the block we are waiting
                    # for, and `scroll_feed_to_next_post` is the advance to the next REAL
                    # post — it scrolled straight past the carousel, so the probe above
                    # never saw it and the pass never fired (QA 2026-07-27: the dump showed
                    # the carousel on screen while the run kept liking posts).
                    res = self._advance_to_next_post(
                        skip_ads, skip_suggested and suggestion_passes_left <= 0,
                        on_ad=on_ad,
                    )
                    stats['posts_skipped_ads'] += res.get('ads_skipped', 0)
                    stats['posts_skipped_suggested'] = (
                        stats.get('posts_skipped_suggested', 0) + res.get('suggested_skipped', 0)
                    )

                    if not res.get('on_feed', False):
                        self.logger.info("🏁 Left the feed (reel/profile) - stopping")
                        break

                    # Followed feed exhausted: N filler gestures in a row, ads and suggestions only.
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
