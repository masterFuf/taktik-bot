"""DM engagement actions for Instagram compat diagnostics (Cartography Lab).

Real production DM path, unit-testable step by step:
- ``DMAutoReplyWorkflow`` (DMNavigationMixin + DMReplyActionsMixin) built on the warm Lab
  device (device_manager=facade, nav=a.nav, detection=a.detection) — the exact methods the
  auto-reply workflow runs.
- the cold-DM ``send_dm`` entry point (profile -> Message -> type -> send).

Privacy: DM body content is NEVER passed through ``logger`` calls (only char counts /
usernames are logged). ``dm.read_last_incoming`` returns the read text in its result so the
tester can verify the read worked — same data path the DM reader/persistence already uses.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


def _dm_workflow(a):
    from taktik.core.social_media.instagram.workflows.management.dm.auto_reply_workflow import (
        DMAutoReplyWorkflow,
    )
    return DMAutoReplyWorkflow(a.device, a.nav, a.detection)


@action("dm.open_inbox")
def open_inbox(a, p):
    """Navigate to the Direct (DM) inbox via the production DM workflow (Direct tab +
    content-desc fallbacks). Entry point of every DM flow."""
    ok = _dm_workflow(a)._navigate_to_dm_inbox()
    return {"success": bool(ok), "message": "DM inbox open" if ok else "could not open DM inbox"}


@action("dm.list_unread")
def list_unread(a, p):
    """List the UNREAD conversations in the inbox (username + unread flag + message count).
    Message bodies are NOT returned/logged. Be on the DM inbox."""
    convs = _dm_workflow(a)._get_unread_conversations() or []
    items = [{"username": getattr(c, "username", None),
              "has_unread": getattr(c, "has_unread", None),
              "messages": len(getattr(c, "messages", []) or [])} for c in convs]
    logger.info(f"dm.list_unread: {len(items)} unread conversation(s)")
    return {"success": True, "count": len(items), "conversations": items,
            "message": f"{len(items)} unread conversation(s)"}


@action("dm.open_thread")
def open_thread(a, p):
    """Open the conversation thread of ``username`` (row-targeted). Param: username
    (required). Be on the DM inbox."""
    username = (p.get("username") or "").strip()
    if not username:
        return {"success": False, "message": "username param is required"}
    ok = _dm_workflow(a)._open_conversation(username)
    return {"success": bool(ok), "message": f"thread @{username} open={ok}"}


@action("dm.read_last_incoming")
def read_last_incoming(a, p):
    """Read the LAST incoming message of the OPEN thread (production heuristic: left/right
    bounds, skips our own replies). A thread must be open. Returns the text to the Lab UI;
    the content is not logged."""
    text = _dm_workflow(a)._get_last_incoming_message()
    logger.info(f"dm.read_last_incoming: {'message read' if text else 'none'} ({len(text or '')} chars)")
    return {"success": bool(text),
            "message": f"read {len(text or '')} chars" if text else "no incoming message",
            "details": {"text": text}}


@action("dm.send_reply")
def send_reply(a, p):
    """Type + send a reply in the OPEN thread (production _send_reply, Taktik keyboard).
    Param: text (required). A thread must be open."""
    text = (p.get("text") or "").strip()
    if not text:
        return {"success": False, "message": "text param is required"}
    ok = _dm_workflow(a)._send_reply(text)
    return {"success": bool(ok), "message": "reply sent" if ok else "reply failed"}


@action("dm.back_to_inbox")
def back_to_inbox(a, p):
    """Go back from an open thread to the inbox (production header back cascade)."""
    _dm_workflow(a)._go_back_to_inbox()
    return {"success": True, "message": "back to inbox"}


@action("dm.send_cold_dm")
def send_cold_dm(a, p):
    """Cold DM (canonical send_dm): navigate to ``username``'s profile, open Message, type +
    send ``text``. Params: username (required), text (required)."""
    username = (p.get("username") or "").strip()
    text = (p.get("text") or "").strip()
    if not username or not text:
        return {"success": False, "message": "username and text params are required"}
    from taktik.core.social_media.instagram.actions.business.workflows.messaging.workflow import send_dm
    ok = send_dm(a.device, username, text, navigate_to_profile=True)
    return {"success": bool(ok), "message": f"cold DM to @{username} sent={ok}"}
