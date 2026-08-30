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


@action("tt.activity.open")
def open_activity(a, p):
    """Open the Activity page from the inbox. READS ONLY.

    Separate from reading it so the two failures stay apart: "the page would not open" and "the
    page is empty" need opposite responses, and one action reporting both as zero hides that.
    """
    from taktik.core.social_media.tiktok.actions.atomic.activity_actions import ActivityActions

    opened = ActivityActions(a.device).open_activity()
    return {"success": opened, "message": "activity page open" if opened else "could not open it"}


@action("tt.activity.read")
def read_activity(a, p):
    """READS ONLY: the notifications on the open Activity page, parsed.

    Params: max (default 20). Reports the count of each KIND, and names any row it did not
    recognise -- TikTok adds notification types without warning, and a count that only mentions
    what it understood is how those go unnoticed for months.
    """
    import collections

    from taktik.core.social_media.tiktok.actions.atomic.activity_actions import ActivityActions

    limit = int((p or {}).get("max") or 20)
    rows = ActivityActions(a.device).read_activity(max_rows=limit)
    if not rows:
        return {"success": False, "message": "no rows (is the Activity page open?)"}

    kinds = collections.Counter(r.kind for r in rows)
    unknown = [r.raw[:80] for r in rows if r.kind == "unknown"]
    return {
        "success": True,
        "message": ", ".join(f"{k}={n}" for k, n in sorted(kinds.items())),
        "details": {
            "rows": [
                {
                    "kind": r.kind,
                    "usernames": r.usernames,
                    "others_count": r.others_count,
                    "age": r.age_label,
                    "post_count": r.post_count,
                    "comment": r.comment[:120],
                }
                for r in rows[:20]
            ],
            "unknown": unknown,
        },
    }


@action("tt.activity.suggested.read")
def read_suggested(a, p):
    """READS ONLY: the accounts TikTok suggests at the bottom of the Activity SUMMARY.

    Summary, not the expanded list -- the block does not exist behind "Tout voir", measured.
    """
    from taktik.core.social_media.tiktok.actions.atomic.activity_actions import ActivityActions

    rows = ActivityActions(a.device).read_suggested_accounts()
    return {
        "success": bool(rows),
        "message": ", ".join(r["name"] for r in rows[:6]) or "no suggestions on this screen",
        "details": {"accounts": rows},
    }


@action("tt.activity.suggested.follow")
def follow_suggested(a, p):
    """Follow one suggested account. ACTS: it follows.

    Params: name (required) -- the DISPLAY NAME as the row shows it. Judged by the button
    disappearing from that row, never by the tap.
    """
    from taktik.core.social_media.tiktok.actions.atomic.activity_actions import ActivityActions

    name = str((p or {}).get("name") or "").strip()
    if not name:
        return {"success": False, "message": "name is required"}

    done = ActivityActions(a.device).follow_suggested_account(name)
    logger.info(f"tt.activity.suggested.follow: {name!r} -> {done}")
    return {"success": done, "message": f"followed {name}" if done else f"{name} still offers Follow"}
