"""Search actions for TikTok compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action


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
    """Tap the Message button on the open profile (1st step of cold DM; selector +
    privacy-blocked aware)."""
    ok = a.click.click_message_button()
    return {"success": bool(ok), "message": f"message button tapped={ok}"}

