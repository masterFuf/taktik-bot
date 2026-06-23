"""Scraping-flow actions for Instagram compat diagnostics (Cartography Lab).

The reads/navigations at the heart of every follower/following/post scrape, exposed so each
can be unit-tested in isolation (a selector drift here silently yields 0 profiles in prod):
- entry navigations (``a.nav``): open a hashtag / open a post by URL (deep-link).
- list reads/detections (``a.detection``): list the visible profiles, and the three stop
  signals (limited list, end reached, suggestions section).
- list pagination (``a.scroll``): scroll the followers list, click "load more".
- shared helpers: read a post's share URL, detect reel-vs-post.

All call the exact production methods on the warm Lab device. Only usernames/flags are
returned (never raw UI element objects).
"""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


# === Entry navigations =======================================================

@action("navigation.open_hashtag")
def open_hashtag(a, p):
    """Navigate to a hashtag page (search + open result) — the entry of a hashtag scrape.
    Param: hashtag (required, with or without #)."""
    hashtag = (p.get("hashtag") or "").strip().lstrip("#")
    if not hashtag:
        return {"success": False, "message": "hashtag param is required"}
    ok = a.nav.navigate_to_hashtag(hashtag)
    return {"success": bool(ok), "message": f"#{hashtag} open={ok}"}


@action("navigation.open_post_url")
def open_post_url(a, p):
    """Open a post by its URL via deep-link (fragile cross-device) — the entry of a
    post_url scrape. Param: post_url (required)."""
    post_url = (p.get("post_url") or "").strip()
    if not post_url:
        return {"success": False, "message": "post_url param is required"}
    ok = a.nav.navigate_to_post_url(post_url)
    return {"success": bool(ok), "message": f"post url open={ok}"}


# === List reads / stop signals ===============================================

@action("scraping.list_visible_profiles")
def list_visible_profiles(a, p):
    """Read the profiles currently visible in a followers/following list (the core scrape
    read — a selector drift yields 0 silently). Returns usernames + count (no raw elements).
    Be on a followers/following list."""
    rows = a.detection.get_visible_followers_with_elements() or []
    usernames = [r.get("username") for r in rows if isinstance(r, dict) and r.get("username")]
    logger.info(f"scraping.list_visible_profiles: {len(usernames)} visible profile(s)")
    return {"success": bool(usernames), "count": len(usernames),
            "usernames": usernames[:80], "message": f"{len(usernames)} visible profile(s)"}


@action("scraping.is_list_limited")
def is_list_limited(a, p):
    """Detection: is the followers list LIMITED (Meta Verified / Business cap)?"""
    v = a.detection.is_followers_list_limited()
    return {"success": True, "found": bool(v), "message": f"list_limited={bool(v)}"}


@action("scraping.is_list_end_reached")
def is_list_end_reached(a, p):
    """Detection: is the followers list END reached ('And X others' footer)? Scrape stop."""
    v = a.detection.is_followers_list_end_reached()
    return {"success": True, "found": bool(v), "message": f"list_end_reached={bool(v)}"}


@action("scraping.is_suggestions_section")
def is_suggestions_section(a, p):
    """Detection: are we in the 'Suggested for you' section (2nd scrape stop)?"""
    v = a.detection.is_in_suggestions_section()
    return {"success": True, "found": bool(v), "message": f"in_suggestions={bool(v)}"}


# === List pagination =========================================================

@action("scraping.scroll_list_down")
def scroll_list_down(a, p):
    """Scroll the followers/following list down one page (production geometry) — the
    pagination of every list scrape."""
    ok = a.scroll.scroll_followers_list_down()
    return {"success": bool(ok), "message": f"list scrolled={ok}"}


@action("scraping.click_load_more")
def click_load_more(a, p):
    """Recovery: detect + click a 'load more' affordance on a stuck list."""
    ok = a.scroll.check_and_click_load_more()
    return {"success": bool(ok), "message": f"load-more clicked={ok}"}


# === Shared post helpers =====================================================

@action("post.read_share_url")
def read_share_url(a, p):
    """Read the OPEN post's share URL (production get_post_url_from_share: open share sheet
    + copy link + read clipboard) — used to dedup posts. A post must be open."""
    from taktik.core.social_media.instagram.workflows.common.post_navigation import get_post_url_from_share
    url = get_post_url_from_share(a.device)
    return {"success": bool(url), "message": url or "no share URL read", "details": {"url": url}}


@action("detection.is_reel_post")
def is_reel_post(a, p):
    """Detection: is the OPEN post a REEL (vs a feed photo/carousel)? Drives the scrape
    branch. A post must be open."""
    from taktik.core.social_media.instagram.workflows.common.detection import is_reel_post as _is_reel
    v = _is_reel(a.device)
    return {"success": True, "found": bool(v), "message": f"is_reel={bool(v)}"}
