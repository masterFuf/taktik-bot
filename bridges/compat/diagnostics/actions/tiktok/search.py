"""Search actions for TikTok compat diagnostics."""

from types import SimpleNamespace

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action
from bridges.compat.diagnostics.runtime.action_test.action_bundle import bundle_device_id


@action("tt.search.open")
def open_search(a, p):
    return a.search.open_search()


@action("tt.search.submit")
def search_submit(a, p):
    query = p.get("query", "")
    if not query:
        logger.error("Missing 'query' param")
        return False
    return a.search.search_and_submit(query)


@action("tt.search.click_first")
def search_click_first(a, p):
    return a.search.click_first_video_result()


@action("tt.search.open_videos")
def open_videos(a, p):
    """Search a query AND open its videos feed (production search_and_open_videos) — the real
    entry of a Target/hashtag video scrape. Param: query (required)."""
    query = (p.get("query") or "").strip()
    if not query:
        return {"success": False, "message": "query param is required"}
    ok = a.search.search_and_open_videos(query)
    return {"success": bool(ok), "message": f"videos feed for '{query}' open={ok}"}


@action("tt.search.open_user_profile")
def open_user_profile(a, p):
    """Search + open a user's profile (production navigate_to_user_profile) — the entry of
    cold-DM/follow by username. Param: username (required)."""
    username = (p.get("username") or "").strip()
    if not username:
        return {"success": False, "message": "username param is required"}
    ok = a.search.navigate_to_user_profile(username)
    return {"success": bool(ok), "message": f"@{username} profile open={ok}"}


@action("tt.profile.click_message")
def click_message(a, p):
    """Open the conversation from the open profile: the cold DM's own step
    (`open_conversation_from_profile`). A recognised profile without any message entry answers
    `no_message_entry`, the recipient a run skips; `unexpected_screen` is a failure."""
    from taktik.core.social_media.tiktok.actions.business.workflows.dm import outreach

    # The session's device, not a second connection.
    session = SimpleNamespace(device_manager=SimpleNamespace(connect=lambda: True, device=a.device))
    workflow = outreach.TikTokDMOutreachWorkflow(
        bundle_device_id(a) or "", manager_factory=lambda device_id=None: session
    )
    workflow.connect()
    outcome = workflow.open_conversation_from_profile()
    return {
        "success": outcome == outreach.CONVERSATION_OPENED,
        "message": f"message entry: {outcome}",
        "details": {"outcome": outcome},
    }

