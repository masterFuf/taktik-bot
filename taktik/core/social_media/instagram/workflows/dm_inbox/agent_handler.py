"""The one launcher of the Instagram DM inbox, and its Agent handlers.

`run_instagram_dm` reads the inbox, reads the requests folder, or replies in a conversation. The
desktop bridge (`dm_bridge <config.json>`) calls it, and so do the handlers registered as
`instagram.engagement.dm_read` and `instagram.engagement.dm_send` (the CLI). What differs between
the hosts is injected:
- `runtime`: a `DMRuntime` already bound to a connected device, with `restart_instagram()` and
  `device_manager` (the bridges' `DMBridge`: clone-aware, facade-wrapped device, Taktik Keyboard,
  clean restart through `AppService`); its `dm_events` receives the conversation events of a read.
- `emit(payload)`: where the account read from the inbox header is announced (the bridge's stdout).
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.shared.diagnostics.action_block import look_for_action_block
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.dm_inbox.persistence import (
    account_id_for_send,
    account_id_from_inbox_header,
    record_conversations,
    record_reply,
    resolve_account_id,
)
from taktik.core.social_media.instagram.workflows.dm_inbox.session import ensure_dm_inbox, return_to_inbox


INSTAGRAM_DM_READ_WORKFLOW_ID = "instagram.engagement.dm_read"
INSTAGRAM_DM_SEND_WORKFLOW_ID = "instagram.engagement.dm_send"
DM_COMMANDS = ("read", "read_requests", "send")

RuntimeProvider = Callable[[Optional[str]], Any]
Emit = Callable[[dict], None]


def _failure(error: str) -> dict[str, Any]:
    return {"success": False, "error": error}


def run_instagram_dm(config: Mapping[str, Any], *, runtime, emit: Optional[Emit] = None) -> dict[str, Any]:
    """Run the DM command a payload describes: `read`, `read_requests` (`limit`, <= 0 for all) or
    `send` (`username`, `message`). Returns the result the desktop reads, or
    `{"success": False, "error": ...}`."""
    command = config.get("command")
    if command == "read":
        return _read(runtime, int(config.get("limit", 10)), emit)
    if command == "read_requests":
        return _read_requests(runtime, int(config.get("limit", 10)))
    if command == "send":
        username = config.get("username")
        message = config.get("message")
        if not username or not message:
            return _failure("send needs a username and a message")
        return _send(runtime, username, message)
    return _failure(f"Unknown command: {command}")


def _detect_app_language(runtime) -> None:
    """The app language, on the feed a clean restart opens, before the inbox's localized selectors:
    the setup every Instagram launcher shares. A reply has no restart, so it keeps what it finds."""
    from taktik.core.social_media.instagram.workflows.core import runtime_setup
    from taktik.core.social_media.instagram.workflows.core.agent_handler import _log_to_logger

    runtime_setup.prepare_instagram_selectors(device=getattr(runtime, "device", None), log=_log_to_logger)


def _read(runtime, limit: int, emit: Optional[Emit]) -> dict[str, Any]:
    runtime.restart_instagram()
    _detect_app_language(runtime)

    if not runtime.navigate_to_dm_inbox():
        return _failure("Cannot navigate to DM inbox")

    # Identify which of our accounts owns this inbox so the persisted threads link to the
    # right account. Read it from the inbox header (no navigation); fall back to a profile
    # visit only if the header is unreadable. Best-effort: None -> persistence skipped.
    account_id = account_id_from_inbox_header(runtime)

    # Announce the connected account as soon as the inbox opens, BEFORE reading the threads:
    # the front uses it to load THIS account's history (and only this one — the page stays
    # empty until the actually-connected account is known).
    detected_account = getattr(runtime, "_dm_account_username", None)
    if detected_account and emit is not None:
        emit({"type": "account_detected", "account_username": detected_account})

    time.sleep(2)
    conversations = runtime.read_conversations(limit)

    # Leave the inbox in a deterministic state for the next command. Without
    # this, the following send process can start from the bottom of a long DM
    # list and fail to find conversations that were read near the top.
    try:
        runtime._reset_inbox_to_top(strategy="auto")
    except Exception as exc:
        logger.warning(f"Could not reset DM inbox to top after read: {exc}")

    # Fallback: if the inbox header was unreadable, resolve our identity via a profile visit
    # (navigates away, but reading is done). Cheap path is the header read above.
    if account_id is None:
        account_id = resolve_account_id(runtime)

    # Persist the conversations (threads + messages). Best-effort, never blocks the result.
    record_conversations(account_id, conversations)

    return {
        "type": "result",
        "success": True,
        "conversations": conversations,
        "total": len(conversations),
        # Which of our accounts owns this inbox (read from the inbox header). Lets the
        # front load that account's AI persona for reply generation.
        "account_username": getattr(runtime, "_dm_account_username", None),
    }


def _read_requests(runtime, limit: int) -> dict[str, Any]:
    runtime.restart_instagram()
    _detect_app_language(runtime)

    if not runtime.navigate_to_dm_inbox():
        return _failure("Cannot navigate to DM inbox")

    # Resolve the owning account from the inbox header while we are still on the inbox (parity
    # with a read): lets the front load this account's persona even for a requests read.
    account_id_from_inbox_header(runtime)
    account_username = getattr(runtime, "_dm_account_username", None)

    if not runtime.open_requests_folder():
        # No pending requests (or the folder could not be opened): return an empty result.
        return {
            "type": "result", "success": True, "conversations": [], "total": 0,
            "is_requests": True, "account_username": account_username,
        }

    time.sleep(2)
    # Request rows reuse the inbox row structure, so the standard reader handles them.
    conversations = runtime.read_conversations(limit)

    return {
        "type": "result",
        "success": True,
        "conversations": conversations,
        "total": len(conversations),
        "is_requests": True,
        "account_username": account_username,
    }


def _send(runtime, username: str, message: str) -> dict[str, Any]:
    if not ensure_dm_inbox(runtime):
        return _failure("Cannot navigate to DM inbox")

    if not runtime.open_conversation(username):
        logger.info(f"Utilisateur {username} non visible, scroll en haut et reessai...")
        runtime._ensure_primary_tab()
        runtime._reset_inbox_to_top(strategy="scroll")

        if not runtime.open_conversation(username):
            return _failure(f"Cannot find conversation with {username}")

    sent = runtime.send_message(message)
    # The one look after a write. Refused, nothing is recorded and the dialog stays on screen
    # (the way back to the inbox would close it, which is acting again).
    device = getattr(runtime, "device", None)
    if device is not None and look_for_action_block(ProblematicPageDetector(device), after="dm",
                                                    target=username):
        return {**_failure("Instagram refuses the message (Try again later)"),
                "stop_reason": "action_blocked"}
    if not sent:
        return _failure("Failed to send message")

    return_to_inbox(runtime)
    # Persist the reply (best-effort). Reuses the account of the thread read earlier;
    # only resolves identity (profile visit) if this conversation was never read.
    record_reply(account_id_for_send(runtime, username), username, message)
    return {"success": True, "username": username, "message": message}


def build_instagram_dm_handler(
    *,
    instagram_dm_runtime: Optional[RuntimeProvider] = None,
    instagram_dm_emit: Optional[Emit] = None,
) -> WorkflowHandler:
    """Build an injectable DM handler: the launcher, on the runtime the host prepares."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        if instagram_dm_runtime is None:
            raise RuntimeError("Instagram DM needs a connected device")
        config = dict(payload)
        config.update(invocation.params)
        if invocation.workflow_id == INSTAGRAM_DM_SEND_WORKFLOW_ID:
            config["command"] = "send"
        elif config.get("command") != "read_requests":
            config["command"] = "read"
        return run_instagram_dm(config, runtime=instagram_dm_runtime(config.get("packageName")),
                                emit=instagram_dm_emit)

    return handler


def register_instagram_dm_handlers(
    registry: WorkflowRegistry,
    *,
    instagram_dm_runtime: Optional[RuntimeProvider] = None,
    instagram_dm_emit: Optional[Emit] = None,
) -> WorkflowRegistry:
    """Register the Instagram DM inbox handlers into an injected Agent registry."""
    handler = build_instagram_dm_handler(instagram_dm_runtime=instagram_dm_runtime,
                                         instagram_dm_emit=instagram_dm_emit)
    registry.register(INSTAGRAM_DM_READ_WORKFLOW_ID, handler)
    registry.register(INSTAGRAM_DM_SEND_WORKFLOW_ID, handler)
    return registry


__all__ = [
    "DM_COMMANDS",
    "INSTAGRAM_DM_READ_WORKFLOW_ID",
    "INSTAGRAM_DM_SEND_WORKFLOW_ID",
    "build_instagram_dm_handler",
    "register_instagram_dm_handlers",
    "run_instagram_dm",
]
