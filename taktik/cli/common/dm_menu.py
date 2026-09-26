"""The DM entries of the interactive Instagram menu, on the DM Responses page's two launchers.

The page reads the inbox (`instagram.engagement.dm_read`), then sends one reply per conversation
(`instagram.engagement.dm_send`), to the thread's inbox handle. The menu does the same with the
same payloads; the replies are typed at the terminal, since writing them with AI is the app's.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

DM_READ_WORKFLOW_ID = "instagram.engagement.dm_read"
DM_SEND_WORKFLOW_ID = "instagram.engagement.dm_send"

Runner = Callable[[Any, str, str, Mapping[str, Any]], dict]
Ask = Callable[[str], str]
Show = Callable[[str], None]


def _default_runner() -> Runner:
    from taktik.cli.common.instagram_host import run_instagram_dm_payload

    return run_instagram_dm_payload


def replyable(conversations: list[dict]) -> list[dict]:
    """The page's rule: the thread allows a reply and holds a message from the other side."""
    return [conv for conv in conversations
            if conv.get("can_reply") and any(not m.get("is_sent") for m in conv.get("messages") or [])]


def recipient_of(conversation: Mapping[str, Any]) -> str:
    """A thread is reached by its inbox handle; the display name is only a label."""
    return conversation.get("inbox_username") or conversation.get("username") or ""


def read_inbox(device_manager, device_id: str, limit: int, *, run: Optional[Runner] = None) -> dict:
    """One read, as the page asks for it."""
    run = run or _default_runner()
    return run(device_manager, device_id, DM_READ_WORKFLOW_ID,
               {"command": "read", "deviceId": device_id, "limit": limit})


def reply_to_inbox(device_manager, device_id: str, limit: int, *, ask: Ask, show: Show = print,
                   run: Optional[Runner] = None) -> dict:
    """Read the inbox, then send what the operator types for each conversation that awaits a
    reply (an empty answer skips it). Returns the read result and the outcome of each send."""
    run = run or _default_runner()
    result = read_inbox(device_manager, device_id, limit, run=run)
    sent: list[dict] = []
    if not result.get("success"):
        return {"read": result, "sent": sent}

    for conversation in replyable(result.get("conversations") or []):
        show(f"\n@{conversation.get('username')}")
        for message in (conversation.get("messages") or [])[-5:]:
            who = "me" if message.get("is_sent") else conversation.get("username")
            show(f"  {who}: {message.get('text') or ''}")
        text = (ask(f"Reply to @{conversation.get('username')} (empty: skip)") or "").strip()
        if not text:
            continue
        username = recipient_of(conversation)
        outcome = run(device_manager, device_id, DM_SEND_WORKFLOW_ID,
                      {"command": "send", "deviceId": device_id, "username": username, "message": text})
        sent.append({"username": username, "success": bool(outcome.get("success")),
                     "error": outcome.get("error")})
        # A refusal puts the account to rest, as the app's launch guard does after a block.
        if outcome.get("stop_reason") == "action_blocked":
            break
    return {"read": result, "sent": sent}


__all__ = [
    "DM_READ_WORKFLOW_ID",
    "DM_SEND_WORKFLOW_ID",
    "read_inbox",
    "recipient_of",
    "replyable",
    "reply_to_inbox",
]
