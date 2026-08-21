"""Inbox / nouveaux followers actions for TikTok compat diagnostics (inbox v2).

Exposes the atomic actions of the new-followers page to the diagnostics probes,
and therefore to the scenarios. Built on the DM actions.
"""

from bridges.compat.diagnostics.actions.tiktok import action


@action("tt.inbox.open_new_followers")
def open_new_followers(a, p):
    """Open the "new followers" page of the TikTok inbox."""
    return a.dm.open_new_followers_page()


@action("tt.inbox.get_new_followers")
def get_new_followers(a, p):
    """List the accounts on the new-followers page, read-only. Param: max_items."""
    return a.dm.get_new_followers(int(p.get("max_items", 50)))


@action("tt.inbox.follow_back")
def follow_back(a, p):
    """Follow back one account of the new-followers page. Param: username."""
    return a.dm.follow_back(p.get("username", ""))


@action("tt.inbox.get_unreplied")
def get_unreplied(a, p):
    """List the conversations, with the unanswered flag."""
    return a.dm.get_inbox_conversations(int(p.get("max_items", 30)))


@action("tt.inbox.open_message_requests")
def open_message_requests(a, p):
    """Open the message-requests page."""
    return a.dm.open_message_requests_page()


@action("tt.inbox.get_requests")
def get_requests(a, p):
    """List the message requests."""
    return a.dm.get_message_requests(int(p.get("max_items", 30)))


@action("tt.inbox.open_request")
def open_request(a, p):
    """Open the request of the given username."""
    return a.dm.open_request(p.get("username", ""))


@action("tt.inbox.accept_request")
def accept_request(a, p):
    """Accept the open request."""
    return a.dm.accept_request()


@action("tt.inbox.decline_request")
def decline_request(a, p):
    """Decline and delete the open request."""
    return a.dm.decline_request()


@action("tt.inbox.get_notifications")
def get_notifications(a, p):
    """Read the activity and system-notification sections, read-only."""
    return a.dm.get_inbox_notifications(int(p.get("max_items", 20)))


@action("tt.inbox.open_conversation")
def open_conversation(a, p):
    """Open the conversation of ``name``. Param: name (required)."""
    name = (p.get("name") or p.get("username") or "").strip()
    if not name:
        return {"success": False, "message": "name param is required"}
    ok = a.dm.click_conversation(name)
    return {"success": bool(ok), "message": f"conversation '{name}' open={ok}"}


@action("tt.inbox.get_messages")
def get_messages(a, p):
    """Read the messages of the open thread. Param: limit
    (20 by default). Message bodies are NOT logged."""
    msgs = a.dm.get_messages(int(p.get("limit") or 20)) or []
    return {"success": bool(msgs), "count": len(msgs), "messages": msgs,
            "message": f"{len(msgs)} message(s)"}


@action("tt.inbox.send_message")
def send_message(a, p):
    """Send a text message in the open thread (an engagement write: type, then send
    fallback). Param: text (requis)."""
    text = (p.get("text") or "").strip()
    if not text:
        return {"success": False, "message": "text param is required"}
    ok = a.dm.send_text_message(text)
    return {"success": bool(ok), "message": f"message sent={ok}"}
