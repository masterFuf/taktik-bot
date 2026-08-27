"""The ``welcome_dm`` verb of the notifications batch (welcome-dm-spec.md, lot 1).

Sending a welcome message to a brand-new follower is not a new workflow: it is the
canonical ``send_dm`` production path, triggered by a notification row. This module holds
the three things the batch needs that the tap-a-row verbs do not — the ordering rule, the
private-writing guards, and the pacing — so ``cmd_batch`` keeps reading as a dispatcher.

The message text itself is written upstream (the app generates it with the account's
persona); the bot receives it and types it. Nothing here composes a message: a canned
sentence living in the bot would be sent in the app's name without the app knowing.

SECURITY (AGENTS): never log a message body — usernames, lengths and counts only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from bridges.instagram.engagement.runtime.cold_dm.timing import wait_before_next_cold_dm
from bridges.instagram.engagement.runtime.notifications.follow_actor import FOLLOW_ACTOR_ACTION
from bridges.instagram.engagement.runtime.notifications.persistence import (
    dm_already_sent,
    dm_conversation_exists,
)
from bridges.instagram.runtime.ipc import logger

WELCOME_DM_ACTION = "welcome_dm"

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


def welcome_dm_skip_reason(account_id: Optional[int], recipient: str) -> Optional[str]:
    """Why this recipient must NOT be welcomed, or None to proceed.

    Ordered by cost: an unresolved account first (nothing could be recorded, so the same
    DM would be re-sent at every scan — the one case worth a hard refusal), then the two
    database reads.
    """
    if not account_id:
        return "no_account"
    if not (recipient or "").strip():
        return "no_recipient"
    if dm_already_sent(account_id, recipient):
        return "already_dmed"
    if dm_conversation_exists(account_id, recipient):
        return "conversation_exists"
    return None


def send_welcome_dm(device, recipient: str, message: str) -> Dict[str, Any]:
    """Send one welcome DM through the PRODUCTION path (``send_dm``), then come home.

    ``send_dm`` navigates to the profile, opens Message, types with the shared composer
    and presses send — the same function the Cold DM workflow and the Lab's
    ``dm.send_cold_dm`` use. Returning to home afterwards is not cosmetic: the next
    profile is reached through the search tab, which does not exist inside an open
    conversation.
    """
    text = (message or "").strip()
    if not text:
        return {"success": False, "error": "empty message"}

    from taktik.core.social_media.instagram.actions.business.workflows.messaging.workflow import (
        send_dm,
    )

    try:
        sent = bool(send_dm(device, recipient, text, navigate_to_profile=True))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[NOTIF] Welcome DM to @{recipient} raised: {exc}")
        sent = False
        result: Dict[str, Any] = {"success": False, "error": str(exc)}
    else:
        result = ({"success": True, "message": f"welcome DM sent to @{recipient}"} if sent
                  else {"success": False, "error": "Could not send the DM (private profile, "
                                                  "no Message button, or composer not found)"})
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
    "WELCOME_DM_ACTION",
    "order_batch_actions",
    "send_welcome_dm",
    "wait_before_next_off_screen_action",
    "welcome_dm_skip_reason",
]
