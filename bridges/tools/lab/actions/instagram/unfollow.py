"""Unfollow capabilities for the Cartography Lab, one production function each.

Each action calls exactly what the unfollow engine (`UnfollowBusiness`) runs in production, so
every step can be tested on its own: the syncs, the sort, the fans category, the rows the list
shows, the decision on data (no screen), and the block detector. The destructive ones (the whole
step, one account) live in `engagement.py`. Params `account` (the Lab binds the component to it),
and for the decision the same fields as the page.
"""

from datetime import datetime, timezone

from loguru import logger

from bridges.tools.lab.actions.instagram import action, detection_action
from bridges.tools.lab.action_test.not_applicable import not_applicable


def unfollow_config_from_params(p):
    """The engine's config from Lab params (same names as the engine; lists as comma text)."""
    cfg = {}
    if p.get("max_unfollows") not in (None, ""):
        cfg["max_unfollows"] = int(p["max_unfollows"])
    if p.get("unfollow_mode"):
        cfg["unfollow_mode"] = str(p["unfollow_mode"])
    for key in ("bot_follows_only", "skip_verified", "skip_business"):
        if p.get(key) not in (None, ""):
            cfg[key] = str(p[key]).strip().lower() in ("1", "true", "yes", "oui")
    if p.get("min_days_since_follow") not in (None, ""):
        cfg["min_days_since_follow"] = float(p["min_days_since_follow"])
    for key in ("whitelist", "blacklist"):
        value = p.get(key)
        if isinstance(value, str):
            value = [part.strip() for part in value.split(",")]
        if value:
            cfg[key] = [v for v in value if v]
    if p.get("min_delay") not in (None, "") or p.get("max_delay") not in (None, ""):
        cfg["unfollow_delay_range"] = (float(p.get("min_delay") or 2), float(p.get("max_delay") or 5))
    return cfg


def _sync_summary(stats):
    return {key: (sorted(value)[:50] if isinstance(value, (set, frozenset)) else value)
            for key, value in (stats or {}).items()}


@action("unfollow.sync_following")
def sync_following(a, p):
    """Sync our following list into the base (production `sync_following_list`): reads the
    list, writes the follow graph, marks the accounts unfollowed elsewhere after a complete read.
    Says what the read proves (`list_proof`); one that proves nothing fails. Reads only on screen."""
    stats = a.unfollow.sync_following_list({"mode": "fast"})
    return {"success": bool(stats.get("success")),
            "message": (f"{stats.get('total_seen', 0)} seen of {stats.get('expected')}"
                        f" (proof: {stats.get('proof') or 'none'})"),
            "details": _sync_summary(stats)}


@action("unfollow.sync_followers")
def sync_followers(a, p):
    """Sync of our followers list (production `sync_followers_list`): what the non-followers and
    mutual modes trust. Read from the top; stops at the followers the base knows when the base
    plus the new ones match the tab's count (proof `base_count`), else reads the whole list and
    marks the followers gone. Says the proof, the drags and the time. Reads only on screen."""
    stats = a.unfollow.sync_followers_list({"mode": "fast"})
    how = "stopped at the known followers" if stats.get("incremental") else "whole list"
    return {"success": bool(stats.get("success")),
            "message": (f"{stats.get('total_seen', 0)} read of {stats.get('expected')}, {how}"
                        f" (proof: {stats.get('proof') or 'none'}), {stats.get('scrolls', 0)} drags"
                        f" in {stats.get('read_seconds', 0)} s, {stats.get('departures', 0)} gone"),
            "details": _sync_summary(stats)}


@action("unfollow.sort_following_list")
def sort_following_list(a, p):
    """Sort the open following list (production `_set_following_list_sort`). Param order:
    latest (default) | earliest | default. False when the language has no known label for it."""
    order = (p.get("order") or "latest").strip()
    ok = a.unfollow._set_following_list_sort(order)
    return {"success": bool(ok), "message": f"sort {order}: {ok}"}


@action("unfollow.read_fans_category")
def read_fans_category(a, p):
    """Open the 'followers you don't follow back' category and record those FANS (production
    `scrape_non_followers_category`). Nothing is deduced for the accounts we follow. Not applicable
    only when production proved the category not served (the list opens on its accounts). A
    category not read has no count: the message says why, never « 0 fans »."""
    stats = a.unfollow.scrape_non_followers_category()
    if stats.get("category_not_served"):
        return not_applicable("unfollow.read_fans_category",
                              "our followers list opens on its accounts, Instagram serves it no category now",
                              **_sync_summary(stats))
    fans = stats.get("fans_count")
    if fans is not None:
        message = f"{fans} fans"
    elif stats.get("read_failed"):
        message = "fans not read: the open category could not be read"
    else:
        message = "fans not read"
    return {"success": bool(stats.get("success")), "message": message, "details": _sync_summary(stats)}


@action("unfollow.read_list_rows")
def read_list_rows(a, p):
    """Read the rows of the open follow list: username and button state, in any language
    (production `_visible_follow_rows`, the read the unfollow acts on)."""
    rows = a.unfollow._visible_follow_rows()
    listed = [{"username": row["username"], "state": row["state"]} for row in rows]
    return {"success": bool(listed), "message": f"{len(listed)} row(s)", "details": {"rows": listed}}


@action("unfollow.plan")
def plan(a, p):
    """The decision on data, without touching the screen: the candidates and the refusals per
    rule, from the base (production `select_candidates`). No followers sync is run here: the
    non-followers mode then refuses everyone (reciprocity unknown), as the engine would."""
    from taktik.core.database.instagram_follow_graph import InstagramFollowGraphService
    from taktik.core.social_media.instagram.actions.business.workflows.unfollow.candidates import (
        records_from_rows,
        select_candidates,
    )

    account_id = a.unfollow._get_account_id()
    if not account_id:
        return {"success": False, "message": "account param required (the base is read per account)"}
    cfg = {**a.unfollow.default_config, **unfollow_config_from_params(p)}
    selection = select_candidates(
        records_from_rows(InstagramFollowGraphService.list_active_followings(account_id)),
        cfg, None, datetime.now(timezone.utc).replace(tzinfo=None),
    )
    logger.info(f"unfollow.plan: {len(selection.candidates)} candidates, refused {selection.refusals}")
    return {"success": True, "message": f"{len(selection.candidates)} candidate(s)",
            "details": {"candidates": selection.candidates[:100], "refusals": selection.refusals}}


@detection_action("detection.is_action_blocked")
def is_action_blocked(a, p):
    """Is Instagram showing its "Try again later" dialog now? Reads only (production
    `is_action_blocked`, the check that stops the unfollow and the followers workflow). No
    detector on the navigation: no answer, never "not blocked"."""
    detector = getattr(a.unfollow.nav_actions, "problematic_page_detector", None)
    return detector.is_action_blocked() if detector else None
