"""Unified interaction engine — perform interactions on profile, view stories, IPC events."""

import time
import random
from typing import Optional, Dict, Any, List

from ..ipc import IPCEmitter
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.shared.behavior.interaction_plan import (
    apply_relevance_gating,
    build_interaction_plan,
    empty_interaction_plan,
    interaction_plan_from_payload,
    mask_exhausted_intents,
    sample_story_like_count,
    sample_story_like_slots,
)
from taktik.core.shared.telemetry import emit_step
from taktik.core.shared.behavior.dwell import story_dwell


class InteractionEngineMixin:
    """Mixin: moteur d'interaction unifié (perform_interactions, stories, IPC events)."""

    _VISIBLE_PROFILE_RELATION_STATES = {
        'follow', 'follow_back', 'following', 'requested', 'message',
    }

    def _count_live(self, stat_name: str, value: int = 1) -> None:
        """Move a live counter THE INSTANT the gesture lands.

        `BaseStatsManager.increment` publishes a stats snapshot on every call, so counting
        here — inside the engine, right after the tap — is what makes the desktop live panel
        tick action by action. The callers used to add the profile's totals afterwards
        (`increment('likes', 3)`), which meant the panel sat still for the whole profile and
        then jumped by 3; that aggregation has been removed from them, so counting here is
        the single source and cannot double-count.
        """
        manager = getattr(self, 'stats_manager', None)
        if manager is None:
            return
        try:
            manager.increment(stat_name, value)
        except Exception as e:
            self.logger.debug(f"Live counter {stat_name} failed: {e}")

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
            injected_decision = (profile_data or {}).get('ai_agent_decision')
            configured_decision_mode = config.get('ai_decision_mode') == 'decide'
            uses_injected_decision = configured_decision_mode or (
                isinstance(injected_decision, dict)
                and injected_decision.get('mode') == 'decide'
            )
            if uses_injected_decision and not isinstance(injected_decision, dict):
                injected_decision = {
                    'mode': 'decide',
                    'ok': False,
                    'error': 'No profile decision was provided',
                    'decision': {
                        'dryRun': bool(config.get('ai_decision_dry_run', True)),
                        'score': None,
                        'reason': 'Aucune décision reçue : aucune action exécutée.',
                        'notes': [],
                    },
                }
            decision_details = (
                injected_decision.get('decision')
                if uses_injected_decision and isinstance(injected_decision.get('decision'), dict)
                else {}
            )
            decision_dry_run = (
                bool(decision_details.get(
                    'dryRun', config.get('ai_decision_dry_run', True)
                )) if uses_injected_decision else False
            )
            interactions_to_do = (
                [] if uses_injected_decision else self._determine_interactions_from_config(config)
            )
            # Resolve the per-profile plan: turns the rolled intents into concrete
            # quantities — a likes target sampled PROPORTIONALLY to the profile's post count
            # (a 10-post account gets few likes, a 500-post one can take more) and the single
            # story slide to like (a human likes one slide, not all).
            posts_count = (profile_data or {}).get('posts_count')
            if uses_injected_decision:
                # Electron already selected actions and quantities. The public Bot validates hard
                # execution bounds only; a failed/missing response becomes an empty plan.
                plan = interaction_plan_from_payload(
                    injected_decision.get('plan') if injected_decision.get('ok') else None,
                    config,
                )
            else:
                # Strictly compatible off/enrich path: probabilities still own selection.
                plan = build_interaction_plan(config, interactions_to_do, posts_count=posts_count)
            # === DAILY SUB-QUOTAS ===
            # A spent follow/comment quota removes ITS OWN intent for the rest of the day instead
            # of ending the session: the run keeps liking and watching stories on the action
            # budget it still has. No-op in standalone (no caps injected).
            session = getattr(self, 'session_manager', None)
            if session is not None and hasattr(session, 'exhausted_daily_quotas'):
                try:
                    spent = session.exhausted_daily_quotas()
                except Exception as e:
                    self.logger.debug(f"Daily quota read failed (no masking): {e}")
                    spent = None
                plan, quota_masked = mask_exhausted_intents(plan, spent)
                if quota_masked:
                    self.logger.info(
                        f"📵 @{username}: {', '.join(quota_masked)} désactivé(s) — quota du jour atteint"
                    )
                    emit_step("daily_quota", action="mask", target=username, masked=quota_masked)

            # === RELEVANCE GATING (opt-in) ===
            # The AI engagement verdict + gating settings ride on profile_data (set by the
            # profile-analysis hook). apply_relevance_gating decides whether to skip this
            # profile entirely and/or mask planned intents the verdict advises against.
            # Fail-open: no verdict/disabled → passthrough (today's behaviour). In dry-run it
            # only REPORTS what it would do, so the operator can vet verdict quality first.
            gate = None if uses_injected_decision else apply_relevance_gating(
                plan,
                (profile_data or {}).get('ai_engagement'),
                (profile_data or {}).get('ai_relevance_gating'),
            )
            if gate is not None and gate.active:
                score_str = f"{gate.score:.2f}" if isinstance(gate.score, (int, float)) else "?"
                if gate.would_skip:
                    prefix = "[dry-run] " if gate.dry_run else ""
                    self.logger.info(
                        f"🛑 {prefix}Relevance gate @{username}: not worth engaging "
                        f"(score {score_str}){' · ' + gate.reason if gate.reason else ''}"
                    )
                    emit_step("relevance_gate", action="skip", target=username,
                              score=gate.score, dry_run=gate.dry_run, reason=gate.reason)
                    IPCEmitter.emit_action('relevance_skip', username, {
                        'score': gate.score, 'reason': gate.reason, 'dry_run': gate.dry_run,
                    })
                    if gate.skip:
                        return result  # not relevant → skip the whole interaction phase
                elif gate.masked:
                    prefix = "[dry-run] " if gate.dry_run else ""
                    self.logger.info(
                        f"✂️ {prefix}Relevance gate @{username}: masking {', '.join(gate.masked)} "
                        f"(score {score_str})"
                    )
                    emit_step("relevance_gate", action="mask", target=username,
                              masked=list(gate.masked), dry_run=gate.dry_run)
                plan = gate.plan  # enforced plan (unchanged in dry-run)

            # Detect the story ONCE on arrival, BEFORE announcing the plan: the profile header is
            # visible and its avatar content-desc carries the reliable "unseen story" / "non vue"
            # marker (the post-header avatar does NOT). A short settle retry rides out the ring
            # animation (it spins on open, so an immediate check can miss a real story). We only
            # schedule a story phase when a story actually exists, and remember it (`story_available`)
            # so a later phase can open it from the post header too, without re-detecting.
            story_available = bool(plan.do_watch_story) and self.detection_actions.has_unseen_profile_story(
                settle_attempts=3, settle_delay=0.35
            )

            plan_label = "Plan simulé" if decision_dry_run else "Plan final"
            self.logger.info(
                f"{plan_label} @{username}: likes={plan.like_target}, "
                f"follow={'oui' if plan.do_follow else 'non'}, "
                f"commentaires={plan.max_comments if plan.do_comment else 0}, "
                f"story={'oui' if story_available else 'non'}, "
                f"like_story={'oui' if story_available and plan.do_story_like else 'non'}"
            )

            if uses_injected_decision:
                IPCEmitter.emit_action('decision', username, {
                    'likes': plan.like_target,
                    'story': story_available,
                    'story_like': story_available and plan.do_story_like,
                    'follow': plan.do_follow,
                    'comment': plan.max_comments if plan.do_comment else 0,
                    'score': decision_details.get('score'),
                    'reason': decision_details.get('reason') or injected_decision.get('error'),
                    'notes': decision_details.get('notes') or [],
                    'dry_run': decision_dry_run,
                    'ok': bool(injected_decision.get('ok')),
                })

            # Pre-announce the plan to the live copilot (Taktik Agent) BEFORE acting. The story /
            # story-like intentions reflect a story that ACTUALLY exists on the profile (detected
            # just above), NOT merely the rolled probability — so the panel never shows "story +
            # like" on a profile that has no unseen story. Reuses the instagram_action channel
            # (action='plan'); no-op in standalone (no bridge adapter).
            IPCEmitter.emit_action('plan', username, {
                'likes': plan.like_target,
                'posts_count': posts_count or 0,
                'story': story_available,
                'story_like': story_available and plan.do_story_like,
                'follow': plan.do_follow,
                'comment': plan.max_comments if plan.do_comment else 0,
                'dry_run': decision_dry_run,
                'decision_mode': uses_injected_decision,
            })

            # Announcement-only mode is permanent: narrate the exact plan above, then replace it
            # by an empty execution plan. No tap, story open, follow or comment can follow.
            if decision_dry_run:
                plan = empty_interaction_plan()
                story_available = False

            # Human ordering of the header-dependent actions. The story sits right at the top on
            # arrival, so watch it FIRST most of the time; the follow is mixed early/late (a human
            # often follows AFTER browsing the posts). Whatever is deferred to 'end' runs after a
            # humanized scroll back to the top (see PHASE END below).
            story_phase = ('start' if random.random() < 0.75 else 'end') if story_available else None
            follow_phase = ('start' if random.random() < 0.35 else 'end') if plan.do_follow else None

            # === PHASE START — the profile header is visible on arrival ===
            if story_phase == 'start':
                self._do_watch_story(username, plan, profile_data, result)
            if follow_phase == 'start':
                self._do_follow(username, plan, profile_data, result)

            # === LIKE / COMMENT ===
            should_like = plan.like_target > 0
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
                    should_like=should_like,
                    # Live counters tick per gesture: the like loop lives inside
                    # LikeOrchestration, which owns a DIFFERENT stats manager, so it reports
                    # each landed like/comment back through these callbacks instead.
                    on_like=lambda: self._count_live('likes'),
                    on_comment=lambda: self._count_live('comments'),
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

            # The like/comment phase taps the post action bar, where the SHARE button sits next to
            # comment — a mis-tap there opens the Direct share sheet, which would block the
            # follow/story phase that follows. Clear any such stray modal before continuing so the
            # rest of the profile still runs (proactive counterpart to the time-based watchdog).
            self._recover_from_blocking_modal(username, context="after like/comment")

            # === PHASE END — header-dependent actions, after a state-aware return to the top ===
            # Back-navigation often restores a usable header/action-bar immediately. Only gesture
            # when the exact deferred affordance is still absent, and stop as soon as it appears.
            if story_phase == 'end' or follow_phase == 'end':
                if should_like or should_comment:
                    self._ensure_profile_header_actions_visible(
                        needs_story=story_phase == 'end',
                        needs_follow=follow_phase == 'end',
                    )
                if story_phase == 'end':
                    self._do_watch_story(username, plan, profile_data, result)
                if follow_phase == 'end':
                    self._do_follow(username, plan, profile_data, result)

            # Final sweep before leaving: never hand the next profile a screen with a blocking modal
            # still open (a stray share sheet here would poison the next profile's navigation).
            self._recover_from_blocking_modal(username, context="leaving profile")

            return result

        except Exception as e:
            self.logger.error(f"Error performing interactions on @{username}: {e}")
            return result

    def _profile_header_actions_visible(
        self,
        *,
        needs_story: bool = False,
        needs_follow: bool = False,
    ) -> bool:
        """Prove that every deferred profile-header action is currently usable."""
        checks = []

        if needs_story:
            try:
                checks.append(bool(self.detection_actions.has_unseen_profile_story(
                    settle_attempts=1,
                    settle_delay=0.0,
                )))
            except Exception as exc:
                self.logger.debug(f"Deferred story visibility check failed: {exc}")
                checks.append(False)

        if needs_follow:
            try:
                state = self.click_actions.get_follow_button_state()
                checks.append(state in self._VISIBLE_PROFILE_RELATION_STATES)
            except Exception as exc:
                self.logger.debug(f"Deferred follow visibility check failed: {exc}")
                checks.append(False)

        return all(checks) if checks else True

    def _ensure_profile_header_actions_visible(
        self,
        *,
        needs_story: bool = False,
        needs_follow: bool = False,
        max_attempts: int = 3,
    ) -> bool:
        """Return toward the profile header only until the deferred actions are visible."""
        reached = self.scroll_actions.scroll_to_top(
            max_attempts=max_attempts,
            stop_condition=lambda: self._profile_header_actions_visible(
                needs_story=needs_story,
                needs_follow=needs_follow,
            ),
        )
        if not reached:
            self.logger.warning(
                "Profile header actions still unavailable after bounded recovery "
                f"(story={needs_story}, follow={needs_follow})"
            )
        return reached

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
            self._count_live('follows')
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
            # One generic progress container is ambiguous: it often represents the
            # whole segmented bar, not one slide. Treat only multiple metadata nodes as
            # a count; an explicit parsed "1 of 1" above remains authoritative.
            if total and total > 1:
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
                    # Story-like is enabled here (do_story_like) -> like AT LEAST one watched slide
                    # (toggling "Like a story" ON means we like at least one of the story we watch),
                    # and proportionally MORE on longer stories. The proportional sampler alone can
                    # return 0 on a short story, which read as "watched but never liked".
                    count = max(1, sample_story_like_count(watchable, max_story_likes))
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
            # Real time of each watched/liked slide — the DB write is batched after the
            # viewer closes, so without these all rows share one insert-time second.
            watch_times = []
            story_like_times = []

            for idx in range(max_stories):
                if not self.detection_actions.is_story_viewer_open():
                    break

                scale_provider = getattr(self, "_behavior_reading_scale", None)
                dwell_scale = (float(scale_provider("story_view"))
                               if callable(scale_provider) else 1.0)
                view_duration = story_dwell(random.uniform(2, 5) * dwell_scale)
                time.sleep(view_duration)
                stories_viewed += 1
                watch_times.append(self._action_timestamp())
                self._count_live('stories_watched')

                # Like this slide if it's one of the planned (varied) slots.
                if want_like and idx in like_slots:
                    try:
                        if self.click_actions.like_story():
                            stories_liked += 1
                            story_like_times.append(self._action_timestamp())
                            self._count_live('story_likes')
                            self.logger.debug(f"Story slide #{idx + 1} liked")
                    except Exception:
                        pass

                has_next = self.nav_actions.navigate_to_next_story()
                # Safety net: should an advance tap still land on an interactive sticker (countdown,
                # poll…), it opens a consumption sheet OVER the story — back out of it so the story
                # flow isn't blocked (the advance itself already steers around such stickers).
                self._recover_from_blocking_modal(username, context="story")
                if not has_next:
                    # Last slide: if likes were planned but none landed yet (story shorter
                    # than the sampled slots), leave a single like here so a planned
                    # story-like still happens.
                    if want_like and stories_liked == 0:
                        try:
                            if self.click_actions.like_story():
                                stories_liked += 1
                                story_like_times.append(self._action_timestamp())
                                self._count_live('story_likes')
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
                self._record_action(username, 'STORY_WATCH', stories_viewed, timestamps=watch_times)
                if stories_liked > 0:
                    self._record_action(username, 'STORY_LIKE', stories_liked, timestamps=story_like_times)
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

    # NOTE : l'ancien `_interact_with_user` (duplicata complet nav -> extract -> private -> filter
    # -> interact) a ete SUPPRIME (2026-07-18). C'etait un chemin mort : le seul appelant
    # (`notifications/workflow.py`) resout, par MRO, vers l'override
    # `NotificationInteractionsMixin._interact_with_user`, qui passe par `_process_profile_on_screen`.
    # Le duplicata court-circuitait ce pipeline partage — donc aussi le garde-fou de RELATION (skip
    # des profils qui nous suivent / qu'on suit deja). Tout traitement de profil doit passer par
    # `_process_profile_on_screen` (ProfileProcessingMixin), source unique de la decision de skip.
