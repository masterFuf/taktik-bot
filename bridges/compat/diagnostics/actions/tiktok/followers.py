"""Follower-list READ actions for TikTok compat diagnostics.

Read-only on purpose: listing and scrolling are here, tapping a row into a profile is not. A Lab
action that opens someone's profile is a visit, and this family exists to measure whether the
catalogue can SEE the list — the question the scraping workflow got wrong for months while it
scrolled a list it could not read.

`find_follower_rows` is a module-level service function, so nothing here needs the bundle to grow.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action
from taktik.core.social_media.tiktok.actions.core.utils import first_matching
from taktik.core.social_media.tiktok.services.followers.listing import find_follower_rows
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS


def _raw(a):
    device = getattr(a, "device", None)
    return getattr(device, "_device", None) or device


@action("tt.followers.list_visible_rows")
def list_visible_rows(a, p):
    """The rows production would work on, with the username each one is paired to."""
    rows = find_follower_rows(_raw(a), logger=logger)
    named = [row for row in rows if row.get("username")]
    logger.info(f"tt.followers.list_visible_rows: {len(rows)} rows, {len(named)} with a username")
    return {
        # Rows without a username are the failure that matters: the buttons were found, the
        # names were not, so the list scrolls and nothing is ever scraped.
        "success": bool(named),
        "message": f"{len(rows)} row(s), {len(named)} named",
        "details": {
            "rows": len(rows),
            "named": len(named),
            "usernames": [row.get("username") for row in named][:20],
        },
    }


@action("tt.followers.count_anchors")
def count_anchors(a, p):
    """How many of the list's anchors resolve, one catalogue field at a time.

    Separates "the screen is not the list" from "the catalogue is dead on this version" — the two
    readings of an empty result, and the difference between a null probe and a finding.
    """
    device = _raw(a)
    counts = {}
    for field in ("follower_any_button", "follower_username", "follower_display_name"):
        selectors = getattr(FOLLOWERS_SELECTORS, field, None) or []
        counts[field] = len(first_matching(device, selectors))

    logger.info(f"tt.followers.count_anchors: {counts}")
    alive = [name for name, count in counts.items() if count]
    return {
        "success": bool(alive),
        "message": ", ".join(f"{name}={count}" for name, count in counts.items()),
        "details": counts,
    }
