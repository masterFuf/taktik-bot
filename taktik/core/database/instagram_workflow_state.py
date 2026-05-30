"""Database-owned Instagram workflow bookkeeping helpers.

This module owns small persistence decisions that were historically called from
`social_media/instagram/.../database_helpers.py`:

- record repeated interaction rows
- check whether a profile was already processed or filtered
- mark a profile as processed
- combine those checks into a skip decision

It intentionally uses the public database client returned by
`taktik.core.database.get_db_service()` so legacy workflows keep their existing
runtime contract while the ownership moves into the database layer.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

log = logger.bind(module="database-instagram-workflow-state")


class InstagramWorkflowStateService:
    """Database facade for Instagram workflow state decisions."""

    @staticmethod
    def _db():
        from taktik.core.database import get_db_service

        return get_db_service()

    @staticmethod
    def record_individual_actions(
        username: str,
        action_type: str,
        count: int,
        account_id: Optional[int] = None,
        session_id: Optional[int] = None,
    ) -> bool:
        if not account_id:
            log.warning(
                "account_id missing - cannot record {} for @{}",
                action_type,
                username,
            )
            return False

        success_count = 0

        try:
            db = InstagramWorkflowStateService._db()
            for _ in range(count):
                content = f"Action {action_type} sur profil @{username}"
                success = db.record_interaction(
                    account_id=account_id,
                    username=username,
                    interaction_type=action_type,
                    success=True,
                    content=content,
                    session_id=session_id,
                )
                if success:
                    success_count += 1

            if success_count:
                log.debug(
                    "{}/{} action(s) {} recorded for @{}",
                    success_count,
                    count,
                    action_type,
                    username,
                )
            else:
                log.warning(
                    "No {} action could be recorded for @{}",
                    action_type,
                    username,
                )

            return success_count > 0
        except Exception as exc:
            log.error(
                "Error recording {} action(s) for @{}: {}",
                action_type,
                username,
                exc,
            )
            return False

    @staticmethod
    def is_profile_already_processed(
        username: str,
        account_id: Optional[int] = None,
        hours_limit: int = 1440,
    ) -> bool:
        if not account_id:
            return False

        try:
            is_processed = InstagramWorkflowStateService._db().is_profile_processed(
                account_id=account_id,
                username=username,
                hours_limit=hours_limit,
            )

            if is_processed:
                log.debug(
                    "Profile @{} already processed in the last {} hour(s)",
                    username,
                    hours_limit,
                )

            return is_processed
        except Exception as exc:
            log.error("Error checking processed profile @{}: {}", username, exc)
            return False

    @staticmethod
    def mark_profile_as_processed(
        username: str,
        source: str,
        account_id: Optional[int] = None,
        session_id: Optional[int] = None,
    ) -> bool:
        if not account_id:
            log.warning("account_id missing - cannot mark @{} as processed", username)
            return False

        try:
            InstagramWorkflowStateService._db().mark_profile_as_processed(
                account_id=account_id,
                username=username,
                notes=source,
                session_id=session_id,
            )
            log.debug("@{} marked as processed (source: {})", username, source)
            return True
        except Exception as exc:
            log.error("Error marking @{} as processed: {}", username, exc)
            return False

    @staticmethod
    def record_filtered_profile(
        username: str,
        reason: str,
        source_type: str,
        source_name: str,
        account_id: Optional[int] = None,
        session_id: Optional[int] = None,
    ) -> bool:
        if not account_id:
            log.warning(
                "account_id missing - cannot record filtered profile @{}",
                username,
            )
            return False

        try:
            success = InstagramWorkflowStateService._db().record_filtered_profile(
                account_id=account_id,
                username=username,
                reason=reason,
                source_type=source_type,
                source_name=source_name,
                session_id=session_id,
            )

            if success:
                log.debug("Filtered profile @{} recorded: {}", username, reason)
            else:
                log.warning("Filtered profile @{} could not be recorded", username)

            return success
        except Exception as exc:
            log.error("Error recording filtered profile @{}: {}", username, exc)
            return False

    @staticmethod
    def is_profile_filtered(
        username: str,
        account_id: Optional[int] = None,
    ) -> bool:
        if not account_id:
            return False

        try:
            is_filtered = InstagramWorkflowStateService._db().is_profile_filtered(
                username,
                account_id,
            )
            if is_filtered:
                log.debug("Profile @{} already filtered", username)
            return is_filtered
        except Exception as exc:
            log.debug("Error checking filtered profile @{}: {}", username, exc)
            return False

    @staticmethod
    def is_profile_skippable(
        username: str,
        account_id: Optional[int] = None,
        hours_limit: int = 1440,
    ) -> tuple[bool, str]:
        if not account_id:
            return False, ""

        if InstagramWorkflowStateService.is_profile_already_processed(
            username,
            account_id,
            hours_limit,
        ):
            return True, "already_processed"

        if InstagramWorkflowStateService.is_profile_filtered(username, account_id):
            return True, "already_filtered"

        return False, ""


__all__ = ["InstagramWorkflowStateService"]
