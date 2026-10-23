"""The Instagram cold DM workflow: the one engine of the desktop bridge, the CLI and the Lab.

It was the cold DM bridge's own class, built on the bridge's device base; the CLI had a second
engine with other reads and no record of what it sent. The host now hands the workflow what used
to come from the bridge base: the device (the bridges' clone-aware, facade-wrapped device), its
manager and the clean restart of Instagram, plus where the progress lines, the texts sent and the
AI spend go. The keyboard is not the host's to give: the send reads the one of the device itself.

A text written by an AI (the AI mode's, or a list `aiDmRules` says an AI wrote) goes through the one
rule of `taktik/core/ai/dm_rules.py`: a list is checked when the payload is read, a text the AI mode
writes here once written, before it is typed.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from loguru import logger

from taktik.core.ai.credential import AICredential
from taktik.core.ai.dm_rules import AiDmRules, check_ai_dm_text
from taktik.core.shared.diagnostics import run_halt
from taktik.core.shared.diagnostics.action_block import look_for_action_block
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.workflows.cold_dm.messages import choose_cold_dm_message
from taktik.core.social_media.instagram.workflows.cold_dm.navigation import (
    NOT_ON_PROFILE,
    ColdDMNavigationMixin,
)
from taktik.core.social_media.instagram.workflows.cold_dm.recipients import ColdDMRecipientMixin
from taktik.core.social_media.instagram.workflows.cold_dm.results import (
    apply_cold_dm_send_result,
    build_all_recipients_processed_result,
    build_cold_dm_summary,
    validate_cold_dm_inputs,
)
from taktik.core.social_media.instagram.workflows.cold_dm.sender import ColdDMSenderMixin
from taktik.core.social_media.instagram.workflows.cold_dm.timing import wait_before_next_cold_dm
from taktik.core.social_media.instagram.workflows.cold_dm.recipient_policy import (
    PRIVATE_SKIP_REASONS,
    SKIP_VERIFIED,
    ColdDmRecipientPolicy,
)


#: `reach_and_send` outcomes other than the recipient policy's skip reasons.
SENT = "sent"
#: The production profile search opened no profile of this handle: no row of it among the results,
#: the search not reached, or the profile opened another one.
NOT_FOUND = "not_found"
NO_CONVERSATION = "no_conversation"
NO_MESSAGE = "no_message"
#: The text the AI mode wrote breaks the rule of a DM written by an AI: nothing typed.
TEXT_REFUSED = "text_refused"
#: Instagram refused the send ("Try again later"): the run stops, the dialog stays on screen.
ACTION_BLOCKED = "action_blocked"


ProgressCallback = Callable[..., None]
#: `sent(current=, username=, message=, ai_written=)`: a text the conversation took.
SentCallback = Callable[..., None]


class ColdDMWorkflow(
    ColdDMRecipientMixin,
    ColdDMSenderMixin,
    ColdDMNavigationMixin,
):
    """Cold DM workflow - sends DMs to new users (cold outreach)."""

    def __init__(
        self,
        device,
        device_manager,
        *,
        restart: Optional[Callable[[], Any]] = None,
        progress: Optional[ProgressCallback] = None,
        sent: Optional[SentCallback] = None,
        ai_ipc=None,
    ):
        self.device = device
        self.device_manager = device_manager
        self._restart = restart
        self._progress = progress
        self._sent = sent
        self._ai_ipc = ai_ipc
        self.dms_sent = 0
        self.dms_success = 0
        self.dms_failed = 0
        self.private_profiles = 0
        self.verified_profiles = 0
        self.texts_refused = 0

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
        ai_credential: Optional[AICredential] = None,
        recipient_policy: ColdDmRecipientPolicy | None = None,
        ai_dm_rules: AiDmRules | None = None,
    ) -> dict:
        """Run the cold DM workflow.

        `ai_dm_rules` is the frame of texts written by an AI; None: the texts are the operator's.
        """
        recipient_policy = recipient_policy or ColdDmRecipientPolicy()
        use_ai = bool(ai_prompt and ai_credential is not None and ai_credential.usable)
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

        if self._restart is not None:
            self._restart()
        self._detect_app_language()

        for i, recipient in enumerate(filtered_recipients[:max_dms]):
            if run_halt.arret_demande():
                logger.warning(f"Run stop requested ({run_halt.arret_demande().get('code')}): no more DMs")
                break
            if self.dms_sent >= max_dms:
                logger.info(f"Reached max DMs limit: {max_dms}")
                break

            logger.info(f"[{i+1}/{min(len(filtered_recipients), max_dms)}] Sending DM to: {recipient}")

            if self._progress is not None:
                self._progress(
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
                        ai_credential=ai_credential,
                        ipc=self._ai_ipc,
                    ),
                    recipient_policy,
                    rules=ai_dm_rules if use_ai else None,
                )
                outcome = reached["outcome"]
                if outcome == TEXT_REFUSED:
                    self.texts_refused += 1
                    logger.warning(f"Text for {recipient} refused ({reached['refusal'].reason}): not sent")
                elif outcome in PRIVATE_SKIP_REASONS:
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
                    if reached["send_result"] is True and self._sent is not None:
                        self._sent(current=i + 1, username=recipient, message=reached["message"],
                                   ai_written=ai_dm_rules is not None)
                else:
                    self.dms_failed += 1
                if outcome == ACTION_BLOCKED:
                    # No way back home: its Back would close the dialog, which is acting again.
                    break
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

    def reach_and_send(self, recipient: str, compose, policy: ColdDmRecipientPolicy | None = None,
                       *, rules: AiDmRules | None = None) -> dict:
        """One recipient, the production steps: open the profile through the production profile
        search, decide, open the conversation, compose, send. Shared by `run` and the Lab
        (`dm.send_cold_dm`).

        `compose` is called only once the conversation is open (an AI message costs a call).
        `rules`: the composed text was written by an AI and is held to them before it is typed.
        Returns `outcome` (`SENT`, a `recipient_policy.SKIP_*` reason, or one of the
        `NOT_FOUND`, `NOT_ON_PROFILE`, `NO_CONVERSATION`, `NO_MESSAGE`
        failures, or `TEXT_REFUSED` with its `refusal`), with `message` and `send_result` once
        sent. Counting and recording are the caller's.
        """
        if not self.open_recipient_profile(recipient):
            logger.warning(f"The profile search opened no profile of {recipient}")
            return {"outcome": NOT_FOUND}
        open_result = self.open_dm_from_profile(policy)
        if open_result == NOT_ON_PROFILE:
            logger.warning(f"The search for {recipient} did not open a profile: nothing tapped")
            return {"outcome": NOT_ON_PROFILE}
        if open_result in PRIVATE_SKIP_REASONS or open_result == SKIP_VERIFIED:
            logger.warning(f"Skipping {recipient} - {open_result}")
            return {"outcome": open_result}
        if not open_result:
            logger.warning(f"Could not open DM for: {recipient}")
            return {"outcome": NO_CONVERSATION}
        message = compose()
        if not message:
            return {"outcome": NO_MESSAGE}
        if rules is not None:
            refusal = check_ai_dm_text(message, rules)
            if refusal is not None:
                return {"outcome": TEXT_REFUSED, "refusal": refusal}
        send_result = self.send_message(message)
        if look_for_action_block(ProblematicPageDetector(self.device), after='dm', target=recipient):
            return {"outcome": ACTION_BLOCKED, "message": message, "send_result": False}
        return {"outcome": SENT, "message": message, "send_result": send_result}

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
