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
from taktik.core.social_media.tiktok.services.navigation.reset import return_to_tiktok_shell
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


@action("tt.followers.open_own_following")
def open_own_following(a, p):
    """From our profile, open OUR following list.

    Wired because the French entry for this opener was EMPTY, so only the English anchor applied
    and the list was not openable at all on a French phone — the unfollow workflow died at its
    step 2 and the follow-graph sync could not start. An empty locale entry is not neutral, and
    nothing measured this one.
    """
    return _open_own_list(a, "following")


@action("tt.followers.open_own_followers")
def open_own_followers(a, p):
    """From our profile, open OUR followers list."""
    return _open_own_list(a, "followers")


def _open_own_list(a, list_type: str):
    from taktik.core.social_media.tiktok.actions.business.actions.profile_actions import (
        ProfileActions,
    )

    # Same shared reset the sync workflow calls: a follow list has no bottom bar, so asking for
    # a tab from inside one taps nothing. Reading that as "the tab is gone" is what made this
    # action fail right after successfully reading the other list.
    return_to_tiktok_shell(_raw(a), logger=logger)
    if not ProfileActions(a.device).navigate_to_own_profile():
        logger.warning(f"tt.followers.open_own_{list_type}: never reached our own profile")
        return {"success": False, "message": "own profile unreachable"}

    openers = (FOLLOWERS_SELECTORS.following_list_opener if list_type == "following"
               else FOLLOWERS_SELECTORS.followers_counter)
    if not a.click._find_and_click(openers, timeout=5):
        logger.info(f"tt.followers.open_own_{list_type}: opener found nothing")
        return {
            "success": False,
            "message": f"{list_type} opener found nothing",
            "details": {"anchors": len(openers)},
        }

    # Wait for ROWS, not for a duration. Returning as soon as the tap lands reports a screen
    # that is still drawing: the first run of this action read seven handles and zero display
    # names off a half-rendered list, then measured nine of each a minute later.
    opened = _wait_for_rows(_raw(a))
    logger.info(f"tt.followers.open_own_{list_type}: rows visible = {opened}")
    return {
        "success": opened,
        "message": f"{list_type} list opened" if opened else f"{list_type} list never drew a row",
        "details": {"anchors": len(openers)},
    }


def _wait_for_rows(device, timeout: float = 8.0) -> bool:
    """True once the list has drawn at least one named row."""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        if first_matching(device, FOLLOWERS_SELECTORS.follower_display_name):
            time.sleep(0.6)
            return True
        time.sleep(0.5)
    return False


@action("tt.followers.read_own_list")
def read_own_list(a, p):
    """Read the rows of a follow list: display name, handle when shown, relationship.

    Reports the NAMED / UNNAMED split on purpose. Measured on the operated account, TikTok
    renders the handle on only about half the rows of the FOLLOWING list (39 names, 19 handles)
    while naming every row of the FOLLOWERS list. A display name is not an identity, so a run
    that only counted rows would look complete while half of them could not be recorded.
    """
    from taktik.core.social_media.tiktok.ui.labels import is_following_button, is_friends_button

    device = _raw(a)
    _wait_for_rows(device)

    def _texts(selectors):
        found = []
        for element in first_matching(device, selectors):
            text = (getattr(element, "text", "") or "").strip()
            if text:
                found.append(text)
        return found

    names = _texts(FOLLOWERS_SELECTORS.follower_display_name)
    handles = _texts(FOLLOWERS_SELECTORS.follower_username)
    states = _texts(FOLLOWERS_SELECTORS.follower_any_button)

    # The classification, not a pass/fail: "Suivre" and "Suivre en retour" are legitimate states
    # meaning we do NOT follow that person, so calling them unclassified would raise a false
    # alarm on every followers list. What is worth seeing is the mapping itself, because it is
    # the relationship the sync writes.
    classified = []
    for state in dict.fromkeys(states):
        classified.append({
            "label": state,
            "meaning": ("mutual" if is_friends_button(state)
                        else "we_follow" if is_following_button(state)
                        else "we_do_not_follow"),
        })

    logger.info(
        f"tt.followers.read_own_list: {len(names)} name(s), {len(handles)} handle(s), "
        f"states={[c['label'] for c in classified]}"
    )
    return {
        # The screen has to be a list at all; a zero here is "we are not on the list", which is
        # a different failure from "the list does not name its rows".
        "success": bool(names),
        "message": f"{len(names)} row(s), {len(handles)} named",
        "details": {
            "names": names[:20],
            "handles": handles[:20],
            "states": classified,
            "unnamedRows": max(0, len(names) - len(handles)),
        },
    }
