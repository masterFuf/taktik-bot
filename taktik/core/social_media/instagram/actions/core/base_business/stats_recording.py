"""Stats recording — record actions to DB, update stats, validate resource limits."""

from typing import Optional, Dict, Any, List

from ..ipc import IPCEmitter
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService


class StatsRecordingMixin:
    """Mixin: enregistrement actions DB + mise à jour stats + validation limites."""

    def _action_timestamp(self) -> str:
        """UTC timestamp of NOW, to capture the real moment a gesture succeeds.

        Batched recorders (likes at end of profile, stories at viewer close) collect one
        of these per successful gesture and pass the list to _record_action — otherwise
        every row of the batch shares the same insert-time second and per-action timing
        stats are meaningless (observed: 2230/3022 prod interactions shared their second).
        """
        return InstagramWorkflowStateService.utc_timestamp()

    def _record_action(self, username: str, action_type: str, count: int = 1,
                       timestamps: Optional[List[str]] = None,
                       content: Optional[str] = None) -> bool:
        """
        Record an action in the database and emit IPC event for WorkflowAnalyzer.
        Centralized method to avoid code duplication across business actions.

        Args:
            username: Target username
            action_type: Type of action (LIKE, FOLLOW, UNFOLLOW, STORY_WATCH, STORY_LIKE, COMMENT, etc.)
            count: Number of actions to record
            timestamps: Real per-gesture times (from _action_timestamp) for batched calls;
                omit for count=1 calls made at the moment of the action
            content: The action's real payload when it has one — the posted comment text. Stored
                in interactions.content, which the desktop session drill-down displays; without
                it every row falls back to a generic "Action <TYPE> sur profil @x" label.

        Returns:
            True if recording succeeded, False otherwise
        """
        try:
            account_id = self._get_account_id()
            session_id = self._get_session_id()

            if not account_id:
                self.logger.warning(f"Cannot record {action_type} - no account_id")
                return False

            InstagramWorkflowStateService.record_individual_actions(
                username=username,
                action_type=action_type,
                count=count,
                account_id=account_id,
                session_id=session_id,
                timestamps=timestamps,
                content=content,
            )
            self.logger.debug(f"✅ {count} {action_type} action(s) recorded for @{username}")

            # Emit IPC event for WorkflowAnalyzer
            IPCEmitter.emit_action(action_type.lower(), username, {"count": count})

            return True

        except Exception as e:
            self.logger.error(f"Failed to record {action_type} for @{username}: {e}")
            return False

    def _update_stats_from_interaction_result(
        self,
        username: str,
        interaction_result: Dict[str, Any],
        account_id: int = None,
        session_id: int = None
    ) -> None:
        """
        Update stats_manager and record DB actions from a unified interaction result.
        Used by workflows that call _perform_interactions_on_profile (hashtag, post_url).
        
        Args:
            username: Target username
            interaction_result: Dict with keys: likes, follows, comments, stories, stories_liked, actually_interacted
            account_id: Account ID for DB recording
            session_id: Session ID for DB recording
        """
        # Only the per-profile counters are set here. The ACTION counters (likes, follows,
        # comments, stories, story likes) are moved by the interaction engine at the moment
        # of each gesture, so the desktop live panel ticks action by action instead of
        # jumping by the profile's total once it is done — re-adding the totals here would
        # double-count. Same reason the FOLLOW is not re-recorded in DB: _do_follow already
        # did it when the button was tapped.
        self.stats_manager.increment('profiles_visited')
        self.stats_manager.increment('profiles_interacted')

    def _validate_resource_limits(self, available: int, requested: int, resource_name: str = "resources") -> Dict[str, Any]:
        """
        Generic validation of interaction limits vs available resources.
        Replaces duplicated _validate_follower_limits, _validate_hashtag_limits,
        _validate_interaction_limits across workflows.
        
        Args:
            available: Number of available resources (followers, likes, etc.)
            requested: Number of requested interactions
            resource_name: Human-readable name for log messages (e.g. "followers", "likes")
            
        Returns:
            Dict with keys: valid, warning, suggestion, adjusted_max
        """
        result = {
            'valid': True,
            'warning': None,
            'suggestion': None,
            'adjusted_max': None
        }
        
        if available == 0:
            result['valid'] = False
            result['warning'] = f"No {resource_name} available, cannot proceed"
            result['suggestion'] = f"Choose a source with {resource_name}"
            return result
        
        if requested > available:
            result['valid'] = False
            result['warning'] = f"Requested {requested} interactions but only {available} {resource_name} available"
            result['suggestion'] = f"Automatically adjusting to maximum {available} interactions"
            result['adjusted_max'] = available
        
        return result

    def _get_account_id(self) -> Optional[int]:
        """Get the active account ID from automation or fallback to default."""
        if self.automation and hasattr(self.automation, 'active_account_id'):
            return self.automation.active_account_id
        return self.active_account_id
    
    def _get_session_id(self) -> Optional[int]:
        """Get the current session ID from automation or session_manager."""
        if self.automation and hasattr(self.automation, 'current_session_id'):
            return self.automation.current_session_id
        if self.session_manager and hasattr(self.session_manager, 'session_id'):
            return self.session_manager.session_id
        return None
