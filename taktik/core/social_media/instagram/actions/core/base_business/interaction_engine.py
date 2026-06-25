"""Unified interaction engine — perform interactions on profile, view stories, IPC events."""

import time
import random
from typing import Optional, Dict, Any, List

from ..ipc import IPCEmitter
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.shared.behavior.interaction_plan import (
    build_interaction_plan,
    sample_story_like_count,
    sample_story_like_slots,
)
from taktik.core.shared.telemetry import emit_step


class InteractionEngineMixin:
    """Mixin: moteur d'interaction unifié (perform_interactions, stories, IPC events)."""

    def _perform_interactions_on_profile(
        self,
        username: str,
        config: Dict[str, Any],
        profile_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Perform interactions (like, follow, comment, story) on a profile
        we are ALREADY viewing. Does NOT navigate or filter.
        
        All workflows delegate here so interaction logic is in one place.
        
        Args:
            username: Target username
            config: Workflow config (supports both percentage and probability keys)
            profile_data: Already-extracted profile data (for follow_button_state check, IPC events)
            
        Returns:
            Dict with keys: likes, follows, comments, stories, stories_liked, actually_interacted
        """
        result = {
            'likes': 0, 'follows': 0, 'comments': 0,
            'stories': 0, 'stories_liked': 0,
            'actually_interacted': False
        }

        try:
            interactions_to_do = self._determine_interactions_from_config(config)
            # Resolve the per-profile plan: turns the rolled intents into concrete
            # quantities — a likes target sampled PROPORTIONALLY to the profile's post count
            # (a 10-post account gets few likes, a 500-post one can take more) and the single
            # story slide to like (a human likes one slide, not all).
            posts_count = (profile_data or {}).get('posts_count')
            plan = build_interaction_plan(config, interactions_to_do, posts_count=posts_count)
            self.logger.debug(f"🎯 Plan for @{username}: {interactions_to_do} → "
                              f"likes={plan.like_target}, story_slot={plan.story_like_slot}")

            # Pre-announce the plan to the live copilot (Taktik Agent) BEFORE acting:
            # "on va faire N likes, une story dispo…". Reuses the instagram_action
            # channel (action='plan'); no-op in standalone (no bridge adapter).
            IPCEmitter.emit_action('plan', username, {
                'likes': plan.like_target,
                'posts_count': posts_count or 0,
                'story': plan.do_watch_story,
                'story_like': plan.story_like_slot >= 0,
                'follow': plan.do_follow,
                'comment': plan.max_comments if plan.do_comment else 0,
            })

            # Human ordering of the header-dependent actions. The story sits right at the top on
            # arrival, so watch it FIRST most of the time; the follow is mixed early/late (a human
            # often follows AFTER browsing the posts). Whatever is deferred to 'end' runs after a
            # humanized scroll back to the top (see PHASE END below).
            story_phase = ('start' if random.random() < 0.75 else 'end') if plan.do_watch_story else None
            follow_phase = ('start' if random.random() < 0.35 else 'end') if plan.do_follow else None

            # === PHASE START — the profile header is visible on arrival ===
            if story_phase == 'start':
                self._do_watch_story(username, plan, profile_data, result)
            if follow_phase == 'start':
                self._do_follow(username, plan, profile_data, result)

            # === LIKE / COMMENT ===
            should_like = 'like' in interactions_to_do
            should_comment = plan.do_comment
            min_likes = config.get('min_likes_per_profile', 1)

            if should_like or should_comment:
                likes_result = self.like_business.like_profile_posts(
                    username,
                    max_likes=plan.like_target if should_like else 0,
                    config={'randomize_order': True},
                    should_comment=should_comment,
                    custom_comments=config.get('custom_comments', []),
                    comment_template_category=config.get('comment_template_category', 'generic'),
                    max_comments=plan.max_comments,
                    navigate_to_profile=False,
                    profile_data=profile_data,
                    should_like=should_like
                )
                if likes_result:
                    result['likes'] = likes_result.get('posts_liked', 0)
                    result['comments'] = likes_result.get('posts_commented', 0)

                    # The min-likes threshold ONLY gates whether the like counts as an
                    # interaction (e.g. a profile with too few posts in a like workflow).
                    # It must NEVER short-circuit the follow/story blocks below — those
                    # are independent interactions. Previously an early `return` here meant
                    # that whenever a like yielded 0 (no posts / broken selector), the bot
                    # also skipped follow AND story watching on EVERY workflow using this
                    # engine (target, hashtag, post_url, feed, notifications).
                    like_meets_threshold = (not should_like) or result['likes'] >= min_likes
                    if should_like and not like_meets_threshold:
                        self.logger.info(
                            f"⏭️ @{username}: only {result['likes']}/{min_likes} min likes possible "
                            f"(not enough posts) — like won't count, still evaluating follow/story"
                        )

                    if (like_meets_threshold and result['likes'] > 0) or result['comments'] > 0:
                        result['actually_interacted'] = True

                    # IPC event for likes (so frontend WorkflowAnalyzer can track)
                    if like_meets_threshold and result['likes'] > 0:
                        self._emit_like_event(username, result['likes'], profile_data)

                    # Telemetry: a comment was actually posted on this profile (so the Lab
                    # metrics show comments, not just keystrokes).
                    if result.get('comments', 0) > 0:
                        emit_step("comment", action="posted", target=username, count=result['comments'])

            # === PHASE END — header-dependent actions, after a humanized return to the top ===
            # The like flow above scrolls the post grid down, leaving the profile HEADER (the avatar
            # story ring + the follow button) off-screen — which silently made BOTH follow and story
            # fail. So anything deferred to the end first scrolls back to the top (humanized).
            if story_phase == 'end' or follow_phase == 'end':
                if should_like or should_comment:
                    self.scroll_actions.scroll_to_top()
                if story_phase == 'end':
                    self._do_watch_story(username, plan, profile_data, result)
                if follow_phase == 'end':
                    self._do_follow(username, plan, profile_data, result)

            return result

        except Exception as e:
            self.logger.error(f"Error performing interactions on @{username}: {e}")
            return result

    def _do_follow(self, username, plan, profile_data, result) -> None:
        """Follow the user if planned and not already following/requested. Needs the profile HEADER
        visible (call only from a phase where the header is on screen). Idempotent within a profile
        via the result['follows'] guard."""
        if not plan.do_follow or result.get('follows'):
            return
        follow_state = (profile_data or {}).get('follow_button_state', 'unknown')
        if follow_state in ('following', 'requested'):
            self.logger.info(f"⏭️ Already following @{username} (button: {follow_state}) - skipping follow")
            return
        if self.click_actions.follow_user(username):
            result['follows'] = 1
            result['actually_interacted'] = True
            self.logger.info(f"✅ Followed @{username}")
            # NOTE: stats_manager.increment('follows') is NOT called here (callers track stats to
            # avoid double-counting).
            self._record_action(username, 'FOLLOW', 1)
            self._emit_follow_event(username, profile_data)
            emit_step("follow", action="button", target=username)
            self._handle_follow_suggestions_popup()

    def _do_watch_story(self, username, plan, profile_data, result) -> None:
        """Watch the profile's unseen story if planned and not already watched this profile. Needs
        the profile HEADER (avatar story ring) visible."""
        if not plan.do_watch_story or result.get('stories'):
            return
        story_result = self._view_stories_on_current_profile(
            username,
            do_story_like=plan.do_story_like,        # like count resolved at open (∝ slides)
            max_story_likes=plan.max_story_likes,    # hard ceiling on the proportional count
            fallback_like_slot=plan.story_like_slot, # used only if the slide count is unreadable
            max_stories=plan.max_story_slides,
        )
        if story_result:
            result['stories'] = story_result.get('stories_viewed', 0)
            result['stories_liked'] = story_result.get('stories_liked', 0)
            if result['stories'] > 0:
                result['actually_interacted'] = True
                # IPC event for stories (live panel + WorkflowAnalyzer), mirroring like/follow.
                self._emit_story_event(username, result['stories'], result['stories_liked'], profile_data)
                emit_step("story", action="watch", target=username,
                          watched=result['stories'], liked=result['stories_liked'])

    def _read_story_slide_total(self) -> int:
        """Best-effort number of slides in the just-opened story (0 = unknown).

        Tries the viewer's 'story X of Y' content-desc (get_story_count_from_viewer); if that
        doesn't parse (FR content-desc, clone APK), falls back to the segment-bar count in the
        viewer metadata. Returns 0 when neither is available — the caller then keeps the safe
        ≤1 like fallback. Never raises."""
        try:
            _, total = self.detection_actions.get_story_count_from_viewer()
            if total and total > 0:
                return int(total)
        except Exception:
            pass
        try:
            meta = self.detection_actions.get_story_viewer_metadata()
            total = (meta or {}).get('total_stories', 0)
            if total and total > 0:
                return int(total)
        except Exception:
            pass
        return 0

    def _view_stories_on_current_profile(
        self, username: str, do_story_like: bool = False, max_story_likes: int = 3,
        fallback_like_slot: int = -1, max_stories: int = 3
    ) -> Optional[Dict[str, int]]:
        """View stories when already on a profile page. No navigation.

        Story-likes are PROPORTIONAL to the number of slides the story has (read at open):
        a human leaves a couple of likes on a long story, none/one on a short one — never
        all of them. The like count + the (varied, distinct) slots to like are resolved once
        the slide total is known. If the slide count can't be read (older/clone APK, FR
        content-desc), we fall back to AT MOST ONE like at `fallback_like_slot` — the prior
        safe behaviour, so there's no regression."""
        try:
            if not self.detection_actions.has_stories():
                return None

            if not self.click_actions.click_story_ring():
                return None

            self._human_like_delay('story_load')

            # Resolve how many slides to like from the real slide total (known at open).
            like_slots = set()
            want_like = False
            if do_story_like:
                slides_total = self._read_story_slide_total()
                if slides_total > 0:
                    # We can only like slides we actually watch: bound the proportional count
                    # and the sampled slots to the watch budget (max_stories).
                    watchable = min(slides_total, max_stories)
                    count = sample_story_like_count(watchable, max_story_likes)
                    like_slots = set(sample_story_like_slots(watchable, count))
                    want_like = bool(like_slots)
                    self.logger.debug(
                        f"Story @{username}: {slides_total} slides (watch {watchable}) → "
                        f"like {len(like_slots)} at slots {sorted(like_slots)}"
                    )
                else:
                    # Unknown slide count → safe legacy fallback: at most one like.
                    if fallback_like_slot >= 0:
                        like_slots = {fallback_like_slot}
                        want_like = True

            stories_viewed = 0
            stories_liked = 0

            for idx in range(max_stories):
                if not self.detection_actions.is_story_viewer_open():
                    break

                view_duration = random.uniform(2, 5)
                time.sleep(view_duration)
                stories_viewed += 1

                # Like this slide if it's one of the planned (varied) slots.
                if want_like and idx in like_slots:
                    try:
                        if self.click_actions.like_story():
                            stories_liked += 1
                            self.logger.debug(f"Story slide #{idx + 1} liked")
                    except Exception:
                        pass

                has_next = self.nav_actions.navigate_to_next_story()
                if not has_next:
                    # Last slide: if likes were planned but none landed yet (story shorter
                    # than the sampled slots), leave a single like here so a planned
                    # story-like still happens.
                    if want_like and stories_liked == 0:
                        try:
                            if self.click_actions.like_story():
                                stories_liked += 1
                                self.logger.debug(f"Story last slide (#{idx + 1}) liked (fallback)")
                        except Exception:
                            pass
                    break

            # Back to profile — robust close: swipe-down (a back press is unreliable
            # and can leave the viewer open, which then makes the followers-list
            # recovery overshoot to the target profile and re-scroll from the top).
            # Fall back to back only if the viewer is still open. Mirrors StoryBusiness.
            self.click_actions.close_story()
            if self.detection_actions.is_story_viewer_open():
                self.device.press('back')
            self._human_like_delay('navigation')

            if stories_viewed > 0:
                self._record_action(username, 'STORY_WATCH', stories_viewed)
                if stories_liked > 0:
                    self._record_action(username, 'STORY_LIKE', stories_liked)
                self.logger.debug(f"{stories_viewed} stories viewed, {stories_liked} liked")
                return {'stories_viewed': stories_viewed, 'stories_liked': stories_liked}

            return None

        except Exception as e:
            self.logger.error(f"Error viewing stories @{username}: {e}")
            return None

    def _emit_follow_event(self, username: str, profile_data: Dict[str, Any] = None):
        """Send IPC follow event to frontend for WorkflowAnalyzer."""
        pd = profile_data or {}
        IPCEmitter.emit_follow(username, success=True, profile_data={
            "followers_count": pd.get('followers_count', 0),
            "following_count": pd.get('following_count', 0),
            "posts_count": pd.get('posts_count', 0)
        } if profile_data else None)

    def _emit_like_event(self, username: str, likes_count: int, profile_data: Dict[str, Any] = None):
        """Send IPC like event to frontend for WorkflowAnalyzer."""
        pd = profile_data or {}
        IPCEmitter.emit_like(username, likes_count=likes_count, profile_data={
            "followers_count": pd.get('followers_count', 0),
            "following_count": pd.get('following_count', 0),
            "posts_count": pd.get('posts_count', 0)
        } if profile_data else None)

    def _emit_story_event(self, username: str, stories_watched: int, stories_liked: int,
                          profile_data: Dict[str, Any] = None):
        """Send IPC story event to frontend for the live panel & WorkflowAnalyzer."""
        pd = profile_data or {}
        IPCEmitter.emit_story(username, stories_watched=stories_watched, stories_liked=stories_liked, profile_data={
            "followers_count": pd.get('followers_count', 0),
            "following_count": pd.get('following_count', 0),
            "posts_count": pd.get('posts_count', 0)
        } if profile_data else None)

    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.error(f"❌ Cannot navigate to @{username}")
                return None
            
            profile_info = self.profile_business.get_complete_profile_info(username, navigate_if_needed=False)
            if not profile_info:
                self.logger.error(f"❌ Cannot get profile info for @{username}")
                return None
            
            if profile_info.get('is_private', False):
                self.logger.info(f"⏭️ Private profile @{username} - SKIP immediately")
                
                if hasattr(self, 'stats_manager'):
                    self.stats_manager.increment('private_profiles')
                
                return None
            
            filter_result = self.filtering_business.apply_comprehensive_filter(
                profile_info, 
                self._get_filter_criteria_from_config(config)
            )
            
            if not filter_result['suitable']:
                reason = filter_result.get('reason', 'Criteria not met')
                reasons = filter_result.get('reasons', [reason])
                self.logger.info(f"🚫 @{username} filtered: {reason}")
                
                if hasattr(self, 'stats_manager'):
                    if 'privé' in reason.lower() or 'private' in reason.lower():
                        self.stats_manager.increment('private_profiles')
                    else:
                        self.stats_manager.increment('profiles_filtered')
                
                try:
                    reasons_text = ', '.join(reasons) if reasons else reason
                    
                    source_type = 'HASHTAG' if 'hashtag' in self.logger._context.get('module', '') else 'POST_URL'
                    source_name = config.get('source', 'unknown')
                    
                    InstagramWorkflowStateService.record_filtered_profile(
                        username=username,
                        reason=reasons_text,
                        source_type=source_type,
                        source_name=source_name,
                        account_id=self._get_account_id(),
                        session_id=self._get_session_id()
                    )
                    self.logger.debug(f"✅ Filtered profile @{username} recorded in API")
                except Exception as e:
                    self.logger.error(f"❌ Error recording filtered profile @{username}: {e}")
                
                return None
            
            # === INTERACTIONS (delegated to unified method) ===
            result = self._perform_interactions_on_profile(username, config, profile_data=profile_info)
            
            return result if result.get('actually_interacted', False) else None
            
        except Exception as e:
            self.logger.error(f"❌ Error interacting with @{username}: {e}")
            return None
