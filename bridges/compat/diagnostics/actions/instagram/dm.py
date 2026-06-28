"""DM engagement actions for Instagram compat diagnostics (Cartography Lab).

These actions drive the **real production DM runtime** — the same reader / navigation / sender
mixins under ``bridges/instagram/engagement/runtime/dm/**`` that the desktop front pilots — bound
to the warm Lab device, so the Lab tests the EXACT prod code path step by step. (It previously
drove ``DMAutoReplyWorkflow``, which the front no longer uses and is dead outside the Lab — so the
Lab was validating non-prod code. Règle Cartography Lab : réutiliser la vraie fonction prod.)

Privacy: DM body content is NEVER passed through ``logger`` calls (only counts / usernames are
logged). ``dm.read_last_incoming`` returns the read text in its result so the tester can verify
the read worked — same data path the prod reader/persistence already use.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


def _dm_runtime(a):
    """Compose the production DM mixins (engagement/runtime/dm) onto the warm Lab device.

    The prod mixins operate on a raw uiautomator2 device and read only a small attribute surface
    (``device``, ``screen_width/height``, ``_keyboard``) — no other bridge coupling — so we bind
    the raw device under the Lab facade and supply those attributes. Every method then runs the
    exact prod code on the warm device (no second connection, no app restart)."""
    from bridges.instagram.engagement.runtime.dm.navigation import DMInboxNavigationMixin
    from bridges.instagram.engagement.runtime.dm.reader import DMConversationReaderMixin
    from bridges.instagram.engagement.runtime.dm.sender import DMSenderMixin
    from bridges.common.input.keyboard import KeyboardService

    class _LabDMRuntime(DMSenderMixin, DMConversationReaderMixin, DMInboxNavigationMixin):
        def __init__(self, facade):
            # The prod mixins expect a raw u2 device (self.device(...), .xpath, .long_click, .info);
            # the Lab facade exposes it as `.device`.
            self.device = getattr(facade, "device", facade)
            device_id = getattr(facade, "device_id", None) or "lab"
            try:
                info = self.device.info
                self.screen_width = int(info.get("displayWidth") or 1080)
                self.screen_height = int(info.get("displayHeight") or 1920)
            except Exception:
                self.screen_width, self.screen_height = 1080, 1920
            self._keyboard = KeyboardService(device_id)

    return _LabDMRuntime(a.device)


@action("dm.open_inbox")
def open_inbox(a, p):
    """Navigate to the Direct (DM) inbox via the PROD runtime (``navigate_to_dm_inbox``)."""
    ok = _dm_runtime(a).navigate_to_dm_inbox()
    return {"success": bool(ok), "message": "DM inbox open" if ok else "could not open DM inbox"}


@action("dm.list_unread")
def list_unread(a, p):
    """Run the PROD conversation reader (``read_conversations``) and list what it found (username +
    message count per conversation). Message bodies are NOT returned/logged here. Param: limit
    (optional, default 5; <= 0 = read all). Be on the DM inbox."""
    try:
        limit = int(p.get("limit", 5))
    except (TypeError, ValueError):
        limit = 5
    convs = _dm_runtime(a).read_conversations(limit) or []
    items = []
    for c in convs:
        get = c.get if isinstance(c, dict) else (lambda k, d=None: getattr(c, k, d))
        items.append({
            "username": get("username") or get("real_username"),
            "messages": len(get("messages", []) or []),
        })
    logger.info(f"dm.list_unread: prod reader returned {len(items)} conversation(s)")
    return {"success": True, "count": len(items), "conversations": items,
            "message": f"{len(items)} conversation(s) read"}


@action("dm.open_thread")
def open_thread(a, p):
    """Open the conversation thread of ``username`` via the PROD runtime (``open_conversation``).
    Param: username (required). Be on the DM inbox."""
    username = (p.get("username") or "").strip()
    if not username:
        return {"success": False, "message": "username param is required"}
    ok = _dm_runtime(a).open_conversation(username)
    return {"success": bool(ok), "message": f"thread @{username} open={ok}"}


@action("dm.read_last_incoming")
def read_last_incoming(a, p):
    """Read the LAST incoming message of the OPEN thread via the PROD message extractor
    (``_collect_text_messages``: left/right bounds heuristic, skips our own replies). A thread
    must be open. Returns the text to the Lab UI; the content is not logged."""
    msgs = _dm_runtime(a)._collect_text_messages() or []
    incoming = [m for m in msgs if not m.get("is_sent")]
    text = incoming[-1]["text"] if incoming else None
    logger.info(f"dm.read_last_incoming: {'message read' if text else 'none'} ({len(text or '')} chars)")
    return {"success": bool(text),
            "message": f"read {len(text or '')} chars" if text else "no incoming message",
            "details": {"text": text}}


@action("dm.send_reply")
def send_reply(a, p):
    """Type + send a reply in the OPEN thread via the PROD sender (``send_message``, Taktik
    keyboard). Param: text (required). A thread must be open."""
    text = (p.get("text") or "").strip()
    if not text:
        return {"success": False, "message": "text param is required"}
    ok = _dm_runtime(a).send_message(text)
    return {"success": bool(ok), "message": "reply sent" if ok else "reply failed"}


@action("dm.back_to_inbox")
def back_to_inbox(a, p):
    """Go back from an open thread to the inbox via the PROD runtime
    (``_go_back_from_conversation``)."""
    _dm_runtime(a)._go_back_from_conversation()
    return {"success": True, "message": "back to inbox"}


@action("dm.send_cold_dm")
def send_cold_dm(a, p):
    """Cold DM (canonical ``send_dm``): navigate to ``username``'s profile, open Message, type +
    send ``text``. Params: username (required), text (required). (Cold DM is a separate prod path
    from the inbox auto-reply runtime above.)"""
    username = (p.get("username") or "").strip()
    text = (p.get("text") or "").strip()
    if not username or not text:
        return {"success": False, "message": "username and text params are required"}
    from taktik.core.social_media.instagram.actions.business.workflows.messaging.workflow import send_dm
    ok = send_dm(a.device, username, text, navigate_to_profile=True)
    return {"success": bool(ok), "message": f"cold DM to @{username} sent={ok}"}
