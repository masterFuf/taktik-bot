"""Unified profile processing — extract, filter, interact, record.

Eliminates the duplicated "extract → check private → filter → interact → record"
pipeline found in 5+ workflow files.

Each workflow handles navigation TO/FROM the profile itself.
This mixin only handles what happens WHILE on the profile screen.
"""

import time
from typing import Optional, Dict, Any
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.shared.telemetry.sink import emit_step
from ..ipc import IPCEmitter
from taktik.core.shared.config import resolve_filter_criteria


class ProfileProcessingResult:
    """Standardized result from profile processing."""
    __slots__ = (
        'status', 'username', 'profile_data', 'interaction_result',
        'filter_reasons', 'error_message'
    )
    
    # Status constants
    SUCCESS = 'interacted'
    SKIPPED_PROBABILITY = 'skipped_probability'
    FILTERED_PRIVATE = 'filtered_private'
    FILTERED_CRITERIA = 'filtered_criteria'
    # A RELATIONSHIP already existed. This status is distinct from a criteria
    # rejection: it is not a profile-criteria rejection, and confusing the two would
    # make the live panel and the session statistics unreadable.
    FILTERED_RELATIONSHIP = 'filtered_relationship'
    ERROR_NO_DATA = 'error_no_data'
    ERROR_INTERACTION = 'error_interaction'
    ERROR_EXCEPTION = 'error_exception'
    
    def __init__(self, status: str, username: str):
        self.status = status
        self.username = username
        self.profile_data = None
        self.interaction_result = None
        self.filter_reasons = []
        self.error_message = None
    
    @property
    def actually_interacted(self) -> bool:
        return self.status == self.SUCCESS
    
    @property
    def was_filtered(self) -> bool:
        return self.status in (
            self.FILTERED_PRIVATE, self.FILTERED_CRITERIA, self.FILTERED_RELATIONSHIP
        )

    @property
    def was_relationship_skip(self) -> bool:
        return self.status == self.FILTERED_RELATIONSHIP
    
    @property
    def was_private(self) -> bool:
        return self.status == self.FILTERED_PRIVATE
    
    @property
    def was_error(self) -> bool:
        return self.status in (
            self.ERROR_NO_DATA, self.ERROR_INTERACTION, self.ERROR_EXCEPTION
        )
    
    @property
    def likes(self) -> int:
        return (self.interaction_result or {}).get('likes', 0)
    
    @property
    def follows(self) -> int:
        return (self.interaction_result or {}).get('follows', 0)
    
    @property
    def comments(self) -> int:
        return (self.interaction_result or {}).get('comments', 0)
    
    @property
    def stories(self) -> int:
        return (self.interaction_result or {}).get('stories', 0)
    
    @property
    def stories_liked(self) -> int:
        return (self.interaction_result or {}).get('stories_liked', 0)


class ProfileProcessingMixin:
    """Mixin: unified profile processing while on a profile screen.
    
    Handles: extract info → check private → apply filters → interact → record.
    Does NOT handle navigation to/from the profile — that's the caller's job.
    """

    def _process_profile_on_screen(
        self,
        username: str,
        config: Dict[str, Any],
        source_type: str = 'UNKNOWN',
        source_name: str = '',
        account_id: int = None,
        session_id: int = None,
        navigate_if_needed: bool = False,
    ) -> ProfileProcessingResult:
        """
        Process a profile we are currently viewing (or can navigate to).
        
        This is the SINGLE implementation of the extract→filter→interact pipeline.
        
        Args:
            username: Target username
            config: Workflow config with filter_criteria, like_percentage, etc.
            source_type: 'HASHTAG', 'POST_URL', 'FOLLOWER', 'FEED', 'NOTIFICATIONS'
            source_name: e.g. '#travel', 'https://...', '@target_user', 'feed'
            account_id: For DB recording
            session_id: For DB recording
            navigate_if_needed: If True, navigate to profile first
            
        Returns:
            ProfileProcessingResult with status, profile_data, interaction_result
        """
        result = ProfileProcessingResult('pending', username)
        # Cadence heartbeat: a profile's extract->filter->(AI)->interact phase is the
        # main source of long silent gaps (tens of seconds with no tap/scroll). We
        # stamp a start/done step_metric around it so the run log + cadence can
        # attribute that time (and its outcome) instead of showing a mystery gap.
        analysis_t0 = 0.0
        analysis_started = False

        try:
            # === 1. Navigate if needed ===
            if navigate_if_needed:
                if not self.nav_actions.navigate_to_profile(username):
                    result.status = ProfileProcessingResult.ERROR_NO_DATA
                    result.error_message = 'Navigation failed'
                    self.logger.warning(f"Cannot navigate to @{username}")
                    return result

            # We are on the profile now — open/refresh its live card in the Taktik
            # Agent copilot. Centralized here (the single extract->filter->interact
            # pipeline) so EVERY profile workflow opens a card — Target, Hashtag,
            # Post Likers, post_url — not only Target. The Target-specific callers
            # used to emit this themselves; those duplicates have been removed.
            IPCEmitter.emit_profile_visit(username)

            analysis_t0 = time.time()
            analysis_started = True
            emit_step("analysis", action="start", target=username, source_type=source_type)

            # === 2. Extract profile info ===
            # The FULL bio (auto-expanded if truncated) + website + business category now come
            # from the STANDARD extraction (enrich gates only the heavier About-account
            # navigation, which this path does not need). They feed bio keyword filtering and
            # AI qualification — a truncated bio would silently degrade both.
            profile_data = self.profile_business.get_complete_profile_info(
                username=username, navigate_if_needed=False
            )
            
            if not profile_data:
                result.status = ProfileProcessingResult.ERROR_NO_DATA
                result.error_message = 'Profile data extraction failed'
                self.logger.warning(f"Could not get profile data for @{username}")
                return result
            
            result.profile_data = profile_data
            
            # === 3. Check private ===
            if profile_data.get('is_private', False):
                result.status = ProfileProcessingResult.FILTERED_PRIVATE
                result.filter_reasons = ['Private profile']
                self.logger.info(f"🔒 Private profile @{username} - skipped")
                self.stats_manager.increment('private_profiles')
                self._record_filtered_in_db(
                    username, 'Private profile', source_type, source_name,
                    account_id, session_id
                )
                IPCEmitter.emit_action('private', username, {
                    'followers_count': profile_data.get('followers_count', 0),
                })
                return result
            
            # === Existing relationship ===
            # Placed AFTER the extraction, since the header button is already read, and BEFORE
            # the filters and the qualification: a profile skipped here costs neither action
            # budget nor a qualification call. Without this guard, an existing follower was
            # re-targeted as a fresh one, the follow-back button coming back as followable.
            filter_criteria = resolve_filter_criteria(config)
            relationship_reason = self._relationship_skip_reason(username, profile_data, filter_criteria)
            if relationship_reason:
                result.status = ProfileProcessingResult.FILTERED_RELATIONSHIP
                result.filter_reasons = [relationship_reason]
                self.logger.info(f"🤝 @{username} ignore — {relationship_reason}")
                self.stats_manager.increment('relationship_skipped')
                # The record is MANDATORY: without it the already-handled check would never see
                # this profile and the bot would come back to it on every pass, indefinitely.
                self._record_filtered_in_db(
                    username, relationship_reason, source_type, source_name,
                    account_id, session_id
                )
                IPCEmitter.emit_action('filter', username, {
                    'reasons': [relationship_reason],
                    'followers_count': profile_data.get('followers_count', 0),
                })
                return result

            # === 4. Apply filters ===
            filter_result = self.filtering_business.apply_comprehensive_filter(
                profile_data, filter_criteria
            )
            
            if not filter_result.get('suitable', False):
                reasons = filter_result.get('reasons', [])
                result.status = ProfileProcessingResult.FILTERED_CRITERIA
                result.filter_reasons = reasons
                self.logger.info(f"🚫 @{username} filtered: {', '.join(reasons)}")
                self.stats_manager.increment('profiles_filtered')
                self._record_filtered_in_db(
                    username, ', '.join(reasons), source_type, source_name,
                    account_id, session_id
                )
                IPCEmitter.emit_action('filter', username, {
                    'reasons': reasons,
                    'followers_count': profile_data.get('followers_count', 0),
                })
                return result
            
            # === 5. Perform interactions ===
            interaction = self._perform_interactions_on_profile(
                username, config, profile_data=profile_data
            )
            result.interaction_result = interaction
            
            if interaction and interaction.get('actually_interacted', False):
                result.status = ProfileProcessingResult.SUCCESS
                self.logger.success(f"✅ Successful interaction with @{username}")
            elif interaction and interaction.get('technical_failure'):
                result.status = ProfileProcessingResult.ERROR_INTERACTION
                result.error_message = (
                    f"Interaction failed at {interaction.get('failure_stage') or 'unknown stage'}"
                )
                self.logger.warning(
                    f"@{username} not marked processed: {result.error_message}"
                )
                return result
            else:
                result.status = ProfileProcessingResult.SKIPPED_PROBABILITY
                self.logger.debug(f"@{username} visited but no interaction (probability)")

            # Mark as processed in DB on EVERY successful visit — interacted OR
            # skipped-by-probability. A visited-but-not-interacted profile used to
            # leave no `interactions` row, so the `already_processed` check missed it
            # and a later pass / followers-list re-scroll re-visited and re-qualified
            # the same profile (confirmed on the live DB: @sample_profile was
            # visited once with no row, then fully re-processed ~5 min later).
            InstagramWorkflowStateService.mark_profile_as_processed(
                username, source_name, account_id, session_id
            )

            return result
            
        except Exception as e:
            result.status = ProfileProcessingResult.ERROR_EXCEPTION
            result.error_message = str(e)
            self.logger.error(f"Error processing @{username}: {e}")
            return result
        finally:
            # One done-heartbeat per profile, carrying the elapsed time + the outcome
            # (interacted / filtered_private / filtered_criteria / skipped / error), so
            # the silent per-profile time is attributed in the cadence and run log.
            if analysis_started:
                emit_step(
                    "analysis", action="done", target=username,
                    duration_ms=int((time.time() - analysis_t0) * 1000),
                    outcome=result.status,
                )

    def _relationship_skip_reason(
        self, username: str, profile_data: Dict[str, Any], filter_criteria: Dict[str, Any]
    ) -> Optional[str]:
        """Should this profile be skipped because a relationship already exists?

        Two INDEPENDENT axes, both off by default, so the behaviour is unchanged without
        any setting:
          - skip_follows_us:        the button offers to follow back, so THEY follow us.
          - skip_already_following: the button says following, so WE follow them.

        An unreadable state is RE-READ once, since the header may not be populated yet, and
        then let through when it stays unreadable. The guard is a targeting optimisation and
        must never lose valid targets on an unstable read. The case is logged, so its real
        frequency can be measured.
        """
        skip_follows_us = bool(filter_criteria.get('skip_follows_us', False))
        skip_already_following = bool(filter_criteria.get('skip_already_following', False))
        if not skip_follows_us and not skip_already_following:
            return None

        state = (profile_data or {}).get('follow_button_state', 'unknown')
        if state == 'unknown':
            try:
                state = self.click_actions.get_follow_button_state()
                # Re-reading it is pointless unless it is remembered for the rest of the handling.
                if isinstance(profile_data, dict):
                    profile_data['follow_button_state'] = state
            except Exception as exc:  # noqa: BLE001 — never fatal
                self.logger.debug(f"Relation @{username} : relecture impossible ({exc})")
                state = 'unknown'
            if state == 'unknown':
                self.logger.debug(f"Relation @{username} : etat illisible -> on interagit")
                return None

        if skip_follows_us and state == 'follow_back':
            return 'Already follows us'
        if skip_already_following and state in ('following', 'requested'):
            return 'Already followed by us'
        return None

    def _record_filtered_in_db(
        self, username: str, reason: str, source_type: str,
        source_name: str, account_id: int, session_id: int
    ) -> None:
        """Record a filtered profile in the database. Silent on failure."""
        try:
            InstagramWorkflowStateService.record_filtered_profile(
                username=username,
                reason=reason,
                source_type=source_type,
                source_name=source_name,
                account_id=account_id,
                session_id=session_id
            )
        except Exception as e:
            self.logger.debug(f"Error recording filtered profile @{username}: {e}")
