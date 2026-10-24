"""The ``welcome_dm`` verb of the notifications batch (welcome-dm-spec.md, lot 1).

Sending a welcome message to a brand-new follower is not a new workflow: it is the
canonical ``send_dm`` production path, triggered by a notification row. This module holds
the three things the batch needs that the tap-a-row verbs do not — the ordering rule, the
private-writing guards, and the pacing — so the batch command keeps reading as a dispatcher.

The message text itself is written upstream (the app generates it with the account's
persona); the bot receives it and types it. Nothing here composes a message: a canned
sentence living in the bot would be sent in the app's name without the app knowing. Being
written by an AI, it goes through the one rule of `taktik/core/ai/dm_rules.py` before anything
moves on screen.

SECURITY (AGENTS): never log a message body — usernames, lengths and counts only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from taktik.core.ai.dm_rules import AiDmRules, check_ai_dm_text
from taktik.core.database.messaging import (
    NOBODY_HAS_WRITTEN,
    ONLY_THEY_HAVE_WRITTEN,
    WE_HAVE_WRITTEN,
)
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.workflows.cold_dm.timing import wait_before_next_cold_dm
from taktik.core.social_media.instagram.workflows.notifications.follow_actor import (
    FOLLOW_ACTOR_ACTION,
)
from taktik.core.social_media.instagram.workflows.notifications.persistence import (
    dm_already_sent,
    dm_thread_writer,
)

WELCOME_DM_ACTION = "welcome_dm"
#: A batch entry's `reason` when the welcome message breaks the rule of a DM written by an AI.
TEXT_REFUSED = "text_refused"

# Verbs that LEAVE the activity screen: they open a profile, and from there a conversation.
# Every other verb acts on the feed the scan left on screen. Ordered among themselves too —
# a follow is one tap on a page we are already on, a DM walks further.
OFF_SCREEN_ACTIONS = (FOLLOW_ACTOR_ACTION, WELCOME_DM_ACTION)

# Pause between two welcome DMs. Wider than the batch's other verbs on purpose: the tap
# verbs stay on one screen, a DM walks profile -> conversation -> home each time, and a
# burst of private messages is the fastest way to get an account reported.
WELCOME_DM_DELAY_MIN = 25
WELCOME_DM_DELAY_MAX = 70


def order_batch_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return ``actions`` with the screen-leaving verbs moved to the end, order preserved.

    The tap verbs act on the activity feed the scan left on screen; a follow opens a
    profile and a DM walks on to a conversation. Running those last means the cheap taps
    are all landed before anything navigates away — and a batch stopped mid-DM has already
    done the likes and the follow-backs. The bot imposes the order rather than trusting the
    caller to have sorted its list.
    """
    def rank(entry: Dict[str, Any]) -> int:
        action = (entry.get("action") or "").strip()
        return OFF_SCREEN_ACTIONS.index(action) + 1 if action in OFF_SCREEN_ACTIONS else 0

    # Stable: entries of equal rank keep the order the caller sent them in.
    return sorted(actions, key=rank)


#: What the thread's answer means for a welcome (`who_has_written`); None: the record could not
#: be read, and a lock that cannot read refuses.
_THREAD_SKIP = {
    NOBODY_HAS_WRITTEN: None,
    WE_HAVE_WRITTEN: "conversation_exists",
    ONLY_THEY_HAVE_WRITTEN: "wrote_to_us",
}


def welcome_dm_skip_reason(account_id: Optional[int], recipient: str) -> Optional[str]:
    """Why this recipient must NOT be welcomed, or None to proceed.

    Ordered by cost: an unresolved account first (nothing could be recorded, so the same
    DM would be re-sent at every scan — the one case worth a hard refusal), then the two
    database reads.

    Someone who wrote to us first is not welcomed (product decision): they are answered, never
    greeted. The answer is not written by this verb (see `welcome-dm-spec.md`), so today they
    are left out with their reason, `wrote_to_us`.
    """
    if not account_id:
        return "no_account"
    if not (recipient or "").strip():
        return "no_recipient"
    if dm_already_sent(account_id, recipient):
        return "already_dmed"
    written = dm_thread_writer(account_id, recipient)
    if written not in _THREAD_SKIP:
        return "guard_unavailable"
    return _THREAD_SKIP[written]


def send_welcome_dm(device, recipient: str, message: str, *, rules: AiDmRules = AiDmRules()) -> Dict[str, Any]:
    """Send one welcome DM through the PRODUCTION path (``send_dm``), then come home.

    The message, written by an AI, is first held to ``rules`` (the account's frame; by default
    the most prudent): a message the rule refuses is a skip (``text_refused``), nothing moves.

    ``send_dm`` navigates to the profile, opens Message, types with the shared composer,
    presses send and reads what the conversation shows — the same function the Cold DM workflow
    and the Lab's ``dm.send_cold_dm`` use. A message Instagram shows waiting to be sent (no
    network) is ``pending`` (``DM_SEND_PENDING``): not a success, and not a failure to try again,
    it leaves by itself. Returning to home afterwards is not cosmetic: the next profile is reached
    through the search tab, which does not exist inside an open conversation.
    """
    text = (message or "").strip()
    if not text:
        return {"success": False, "error": "empty message"}
    refusal = check_ai_dm_text(text, rules)
    if refusal is not None:
        logger.warning(f"[NOTIF] Welcome DM to @{recipient} refused ({refusal.reason}): not sent")
        return {"success": True, "skipped": True, "reason": TEXT_REFUSED,
                "message": f"text refused: {refusal.describe()}", "textRefusal": refusal.as_line()}

    from taktik.core.social_media.instagram.workflows.dm.messaging import send_dm
    from taktik.core.social_media.instagram.workflows.dm.reply_check import ReplyOutcome

    result: Dict[str, Any]
    try:
        outcome = send_dm(device, recipient, text, navigate_to_profile=True)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[NOTIF] Welcome DM to @{recipient} raised: {exc}")
        result = {"success": False, "error": str(exc)}
    else:
        if outcome is ReplyOutcome.SENT:
            result = {"success": True, "message": f"welcome DM sent to @{recipient}"}
        elif outcome is ReplyOutcome.PENDING:
            result = {"success": False, "pending": True, "error_code": "DM_SEND_PENDING",
                      "error": "The welcome DM waits to be sent: Instagram sends it when the "
                               "network is back"}
        else:
            result = {"success": False, "error": "Could not send the DM (private profile, "
                                                 "no Message button, or composer not found)"}
    # `send_dm` looks for the block after its send; the dialog then stays (Back would close it).
    if run_halt.arret_demande():
        return result
    _return_home(device)
    return result


def _return_home(device) -> None:
    """Best-effort walk back to the feed. A failed return must not fail the send."""
    try:
        from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions

        NavigationActions(device).navigate_to_home()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[NOTIF] Could not return home after a welcome DM: {exc}")


def wait_before_next_off_screen_action(*, is_last: bool) -> None:
    """Pace two consecutive screen-leaving actions — the Cold DM helper, same sampling.

    A follow costs less than a DM, but both mean walking to someone's profile: chaining
    them back to back is what makes a session look machine-driven.
    """
    if is_last:
        return
    wait_before_next_cold_dm(index=0, total=2,
                             delay_min=WELCOME_DM_DELAY_MIN, delay_max=WELCOME_DM_DELAY_MAX)


__all__ = [
    "OFF_SCREEN_ACTIONS",
    "TEXT_REFUSED",
    "WELCOME_DM_ACTION",
    "order_batch_actions",
    "send_welcome_dm",
    "wait_before_next_off_screen_action",
    "welcome_dm_skip_reason",
]
