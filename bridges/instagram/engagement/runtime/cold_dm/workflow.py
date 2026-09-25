"""Instagram Cold DM bridge workflow runtime class."""

from __future__ import annotations

from bridges.instagram.engagement.runtime.cold_dm.messages import choose_cold_dm_message
from bridges.instagram.engagement.runtime.cold_dm.navigation import ColdDMNavigationMixin
from bridges.instagram.engagement.runtime.cold_dm.progress import emit_cold_dm_progress
from bridges.instagram.engagement.runtime.cold_dm.recipients import ColdDMRecipientMixin
from bridges.instagram.engagement.runtime.cold_dm.results import (
    apply_cold_dm_send_result,
    build_all_recipients_processed_result,
    build_cold_dm_summary,
    validate_cold_dm_inputs,
)
from bridges.instagram.engagement.runtime.cold_dm.search import ColdDMSearchMixin
from bridges.instagram.engagement.runtime.cold_dm.sender import ColdDMSenderMixin
from bridges.instagram.engagement.runtime.cold_dm.timing import wait_before_next_cold_dm
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.workflows.cold_dm.recipient_policy import (
    PRIVATE_SKIP_REASONS,
    SKIP_VERIFIED,
    ColdDmRecipientPolicy,
)


#: `reach_and_send` outcomes other than the recipient policy's skip reasons.
SENT = "sent"
NO_SEARCH = "no_search"
NOT_FOUND = "not_found"
NO_CONVERSATION = "no_conversation"
NO_MESSAGE = "no_message"


class ColdDMWorkflow(
    ColdDMRecipientMixin,
    ColdDMSearchMixin,
    ColdDMSenderMixin,
    ColdDMNavigationMixin,
    InstagramBridgeBase,
):
    """Cold DM workflow - sends DMs to new users (cold outreach)."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self._init_cold_dm_sender(device_id)
        self.dms_sent = 0
        self.dms_success = 0
        self.dms_failed = 0
        self.private_profiles = 0
        self.verified_profiles = 0

    def run(
        self,
        recipients: list,
        messages: list,
        delay_min: int = 30,
        delay_max: int = 60,
        max_dms: int = 50,
        account_id: int = 1,
        session_id: str = None,
        ai_prompt: str = "",
        openrouter_api_key: str = "",
        recipient_policy: ColdDmRecipientPolicy | None = None,
    ) -> dict:
        """Run the cold DM workflow."""
        recipient_policy = recipient_policy or ColdDmRecipientPolicy()
        use_ai = bool(ai_prompt and openrouter_api_key)
        logger.info(
            f"Starting Cold DM workflow: {len(recipients)} recipients, "
            f"{len(messages)} messages, AI mode: {use_ai}"
        )

        validation_error = validate_cold_dm_inputs(recipients=recipients, messages=messages, use_ai=use_ai)
        if validation_error:
            return validation_error

        filtered_recipients = self.filter_pending_recipients(recipients, account_id)

        if not filtered_recipients:
            return build_all_recipients_processed_result()

        self.restart_instagram()
        self._detect_app_language()

        for i, recipient in enumerate(filtered_recipients[:max_dms]):
            if self.dms_sent >= max_dms:
                logger.info(f"Reached max DMs limit: {max_dms}")
                break

            logger.info(f"[{i+1}/{min(len(filtered_recipients), max_dms)}] Sending DM to: {recipient}")

            emit_cold_dm_progress(
                current=i + 1,
                total=min(len(filtered_recipients), max_dms),
                username=recipient,
            )

            try:
                reached = self.reach_and_send(
                    recipient,
                    lambda: choose_cold_dm_message(
                        recipient=recipient,
                        messages=messages,
                        use_ai=use_ai,
                        ai_prompt=ai_prompt,
                        openrouter_api_key=openrouter_api_key,
                    ),
                    recipient_policy,
                )
                outcome = reached["outcome"]
                if outcome in PRIVATE_SKIP_REASONS:
                    self.private_profiles += 1
                elif outcome == SKIP_VERIFIED:
                    self.verified_profiles += 1
                elif outcome == SENT:
                    apply_cold_dm_send_result(
                        workflow=self,
                        recipient=recipient,
                        message=reached["message"],
                        send_result=reached["send_result"],
                        account_id=account_id,
                        session_id=session_id,
                    )
                else:
                    self.dms_failed += 1
                if outcome != SENT:
                    self.go_home()
                    continue

                self.go_home()

                wait_before_next_cold_dm(
                    index=i,
                    total=len(filtered_recipients),
                    delay_min=delay_min,
                    delay_max=delay_max,
                )

            except Exception as e:
                logger.error(f"Error sending DM to {recipient}: {e}")
                self.dms_failed += 1
                self.go_home()

        return build_cold_dm_summary(self)

    def reach_and_send(self, recipient: str, compose, policy: ColdDmRecipientPolicy | None = None) -> dict:
        """One recipient, the production steps: search, open the profile, decide, open the
        conversation, compose, send. Shared by `run` and the Lab (`dm.send_cold_dm`).

        `compose` is called only once the conversation is open (an AI message costs a call).
        Returns `outcome` (`SENT`, a `recipient_policy.SKIP_*` reason, or one of the
        `NO_SEARCH`, `NOT_FOUND`, `NO_CONVERSATION`, `NO_MESSAGE` failures), with `message`
        and `send_result` once sent. Counting and recording are the caller's.
        """
        if not self.navigate_to_search():
            logger.warning(f"Could not navigate to search for {recipient}")
            return {"outcome": NO_SEARCH}
        if not self.search_user(recipient):
            logger.warning(f"Could not find user: {recipient}")
            return {"outcome": NOT_FOUND}
        open_result = self.open_dm_from_profile(policy)
        if open_result in PRIVATE_SKIP_REASONS or open_result == SKIP_VERIFIED:
            logger.warning(f"Skipping {recipient} - {open_result}")
            return {"outcome": open_result}
        if not open_result:
            logger.warning(f"Could not open DM for: {recipient}")
            return {"outcome": NO_CONVERSATION}
        message = compose()
        if not message:
            return {"outcome": NO_MESSAGE}
        return {"outcome": SENT, "message": message, "send_result": self.send_message(message)}

    def _detect_app_language(self) -> None:
        """Pick the selector language once, on the app's first screen (best effort).

        The profile reads of this flow are localized (private notice, Message label, certified
        badge); without a detected language every locale is tried at once.
        """
        try:
            from taktik.core.social_media.instagram.ui.language import detect_and_optimize

            lang = detect_and_optimize(self.device)
            logger.info(f"App language detected: {lang}")
        except Exception as exc:
            logger.warning(f"Language detection failed (non-fatal): {exc}")


__all__ = ["ColdDMWorkflow"]
