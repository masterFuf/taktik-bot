"""Interact with a hand-picked LIST of profiles — with the profiles themselves.

Target Search lets the operator pick N profiles and send them to a workflow. Until now the
only destination was "interact with THEIR followers/following": the picked accounts were
sources, never targets. This workflow is the other reading of the same selection — go to each
picked profile and interact with that person directly.

The only thing that differs from the followers workflow is where the usernames come from: a
list the operator chose, not a list Instagram scrolled for us. So everything downstream is the
production path, unchanged — `_process_profile_on_screen` (extract → relationship → filters →
AI → interact → record), the same stats shape ('followers_direct', so the live panel, the
aliases and the session finalisation all keep working), the same revisit policy. No Lab-only
path, no second interaction engine.

Two things the followers loop does are deliberately absent here, because they answer questions
a chosen list does not ask: there is no scrolling (the list is finite and already known) and no
private-zone escape (a private profile in a hand-picked list is just a private profile — it is
not evidence that Instagram reordered a list it never served us).
"""

from typing import Any, Dict, List, Optional

from ....core.stats import create_workflow_stats, sync_aliases
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.shared.telemetry import emit_step
from ..common.interaction_config import build_interaction_config
from ..common.revisit_policy import RevisitPolicy


class ProfileListWorkflowMixin:
    """Mixin: interact_with_profile_list — interact with each profile of a chosen list."""

    def interact_with_profile_list(self, usernames: List[str],
                                   max_interactions: int = 30,
                                   config: Optional[Dict[str, Any]] = None,
                                   account_id: Optional[int] = None,
                                   finalize: bool = True) -> Dict[str, Any]:
        """
        Visit each username of `usernames` and interact with that profile.

        Args:
            usernames: the profiles to interact WITH (bare usernames, no leading @)
            max_interactions: budget — the run stops once that many profiles were interacted
                with, even if the list is longer
            config: the same workflow config the followers workflow receives
            account_id: DB id of the acting account
            finalize: False when a driver finalises the session itself
        """
        config = config or {}
        stats = create_workflow_stats('followers_direct')

        interaction_config = build_interaction_config(config)
        # Same owner of the "how long does an interaction keep a profile off-limits" semantic as
        # every other workflow. It matters MORE here: the operator hand-picked these profiles, so
        # re-running the same selection twice must not re-interact with everyone.
        revisit_policy = RevisitPolicy.from_filters(interaction_config['filter_criteria'])

        targets = []
        seen = set()
        for raw in usernames or []:
            username = str(raw or '').strip().lstrip('@')
            if username and username.lower() not in seen:
                seen.add(username.lower())
                targets.append(username)

        if not targets:
            self.logger.error("No profiles provided for the profile-list workflow")
            sync_aliases(stats, 'followers_direct')
            stats['stop_reason'] = 'no_targets'
            return stats

        session_stop_reason = None
        session_id = self._get_session_id()

        try:
            if self.session_manager:
                self.session_manager.start_interaction_phase()

            self.logger.info(
                f"🎯 Interacting with {len(targets)} hand-picked profiles (max: {max_interactions})"
            )

            for idx, username in enumerate(targets):
                if stats['interacted'] >= max_interactions:
                    self.logger.info(f"🏁 Interaction budget reached ({max_interactions})")
                    break

                if self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        session_stop_reason = stop_reason
                        break

                # Was this profile already handled recently BY THIS ACCOUNT? Same DB check and same
                # policy the followers loop applies before tapping a row — done here BEFORE any
                # navigation, so a skip costs neither a screen nor an AI call. "Already known" gets
                # its own buckets, never stats['skipped']: mixing "we already did this one" with
                # "we rejected this one" is what makes a run's reject stats unreadable.
                if account_id:
                    try:
                        should_skip, skip_reason = InstagramWorkflowStateService.is_profile_skippable(
                            username, account_id,
                            hours_limit=revisit_policy.reinteraction_hours,
                            filtered_max_age_days=revisit_policy.filtered_max_age_days,
                        )
                    except Exception as e:
                        self.logger.debug(f"Skip check failed for @{username}: {e}")
                        should_skip, skip_reason = False, None
                    if should_skip:
                        if skip_reason == "already_filtered":
                            stats['already_filtered'] += 1
                        else:
                            stats['already_processed'] += 1
                        self.logger.info(f"⏭️ @{username} skipped — {skip_reason or 'db_skip'}")
                        emit_step("profile_list_decision", action="already_known", target=username,
                                  reason=skip_reason or "db_skip", encounter_order=idx + 1,
                                  source_type="SELECTION")
                        continue

                self._maybe_take_break()

                self.logger.info(
                    f"[{stats['interacted']}/{max_interactions} interactions] "
                    f"👤 Profile {idx + 1}/{len(targets)}: @{username}"
                )

                # === UNIFIED PROFILE PROCESSING ===
                # navigate_if_needed=True: this is the ONE thing the followers loop does not need
                # (it taps a row). Navigation goes through the search bar like a person; the atomic
                # keeps its deep-link fallback.
                result = self._process_profile_on_screen(
                    username, interaction_config,
                    source_type='SELECTION', source_name='target_search',
                    account_id=account_id, session_id=session_id,
                    navigate_if_needed=True,
                )

                if result.was_error:
                    stats['errors'] += 1
                    emit_step("profile_list_decision", action="not_interacted", target=username,
                              reason="error", encounter_order=idx + 1, source_type="SELECTION")
                    continue

                if result.was_private or result.was_filtered:
                    stats['filtered' if result.was_filtered and not result.was_private else 'skipped'] += 1
                    emit_step("profile_list_decision", action="not_interacted", target=username,
                              reason="filtered_or_private", encounter_order=idx + 1,
                              source_type="SELECTION")
                    continue

                # Passed the filters — a visit in the persisted sense.
                stats['visited'] += 1
                self.stats_manager.increment('profiles_visited')

                if result.actually_interacted:
                    # Action counters are moved by the interaction engine as each gesture lands
                    # (that is what makes the live panel tick per gesture); only the local run
                    # tallies are accumulated here, exactly as the followers loop does.
                    if result.likes > 0:
                        stats['liked'] += result.likes
                    if result.follows > 0:
                        stats['followed'] += 1
                    if result.stories > 0:
                        stats['stories_viewed'] += result.stories
                    if result.stories_liked > 0:
                        stats['story_likes'] += result.stories_liked
                    if result.comments > 0:
                        stats['comments_made'] += result.comments

                    stats['interacted'] += 1
                    stats['processed'] += 1
                    self.stats_manager.increment('profiles_interacted')
                    self.human.record_interaction()

                    if self.session_manager:
                        self.session_manager.record_profile_processed()

                    emit_step("profile_list_decision", action="interacted", target=username,
                              encounter_order=idx + 1, source_type="SELECTION")
                else:
                    stats['skipped'] += 1
                    emit_step("profile_list_decision", action="not_interacted", target=username,
                              reason="skipped_probability", encounter_order=idx + 1,
                              source_type="SELECTION")

                self.stats_manager.display_stats(current_profile=username)

            sync_aliases(stats, 'followers_direct')
            stats['stop_reason'] = session_stop_reason or ''
            self.logger.info(f"✅ Profile-list interactions completed: {stats}")
            self.stats_manager.display_final_stats(workflow_name="PROFILE_LIST")

            if finalize and self.automation and hasattr(self.automation, 'helpers'):
                if session_stop_reason:
                    self.automation.helpers.finalize_session(
                        status='COMPLETED', reason=session_stop_reason)
                else:
                    self.automation.helpers.finalize_session(
                        status='COMPLETED',
                        reason=f"Workflow completed ({stats['interacted']} interactions)")

            return stats

        except Exception as e:
            self.logger.error(f"Error in profile-list workflow: {e}")
            sync_aliases(stats, 'followers_direct')
            stats.setdefault('stop_reason', '')
            return stats
