"""Navigation actions for TikTok compat diagnostics."""

from bridges.tools.lab.actions.tiktok import action
from taktik.core.social_media.tiktok.services.navigation.deeplink import open_post_by_url


@action("tt.navigation.go_home")
def go_home(a, p):
    return a.nav.navigate_to_home()


@action("tt.navigation.go_inbox")
def go_inbox(a, p):
    return a.nav.navigate_to_inbox()


@action("tt.navigation.go_profile")
def go_profile(a, p):
    return a.nav.navigate_to_profile()


@action("tt.navigation.go_back")
def go_back(a, p):
    return a.nav.go_back()



@action("tt.navigation.open_post_url")
def open_post_url(a, p):
    """Open a video by its link, as the post URL workflow does (`open_post_by_url`): TikTok
    force-stopped, the link sent as an Android intent, success only once a video screen is up.
    Param: post_url (required)."""
    url = (p.get("post_url") or "").strip()
    if not url:
        return {"success": False, "message": "post_url param is required"}
    opened = open_post_by_url(a.device, url)
    return {"success": bool(opened), "message": f"video open={bool(opened)}", "details": {"post_url": url}}
