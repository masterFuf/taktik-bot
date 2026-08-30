"""Profile READ actions for TikTok compat diagnostics.

The Lab could drive TikTok but never read a profile with it, which is how a dead reader survived
three months behind green unit tests: nothing put a real screen in front of it. These call the
PRODUCTION extractor, so a green run here means production reads that screen — not that a Lab-only
path does.

`extract_profile_from_screen` is a module-level function taking a raw device, so none of this
needs the action bundle to grow.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action
from taktik.core.social_media.tiktok.actions.business.workflows._internal.profile_extractor import (
    extract_profile_from_screen,
)
from taktik.core.social_media.tiktok.actions.core.utils import first_matching, first_text
from taktik.core.social_media.tiktok.ui.labels import classify_profile_stat_label
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS


def _raw(a):
    """The bare uiautomator2 device behind the facade — what the extractor expects."""
    device = getattr(a, "device", None)
    return getattr(device, "_device", None) or device


@action("tt.profile.get_enriched")
def get_enriched(a, p):
    """Read the whole profile, exactly as scraping and the followers loop do."""
    data = extract_profile_from_screen(_raw(a), (p or {}).get("username", ""))
    if not data:
        logger.warning("tt.profile.get_enriched: nothing read")
        return {"success": False, "message": "profile unreadable"}

    read = [key for key in ("username", "display_name", "bio") if data.get(key)]
    counters = [k for k in ("followers_count", "following_count", "likes_count") if data.get(k)]
    # Reported by NAME, not just counted. `website`, `is_verified` and `is_private` were all
    # unreadable until 2026-08-30 — the first two were dropped on the way to the database and
    # the flags were read through two hardcoded English words — and a summary that only says
    # "3/3 text fields" is exactly what let that sit. A Lab line that names what came back empty
    # is what makes the next silent loss visible on the first run.
    flags = [k for k in ("website", "is_verified", "is_private") if data.get(k)]
    logger.info(
        f"tt.profile.get_enriched: @{data.get('username')} — "
        f"{len(read)}/3 text fields, {len(counters)}/3 counters, "
        f"flags: {', '.join(flags) if flags else 'none'}"
    )
    # A profile whose text fields are all empty is a failure even though nothing raised — that is
    # precisely the shape the dead reader had, and reporting it as success is what hid it.
    return {
        "success": bool(read),
        "message": (
            f"{len(read)}/3 text fields, {len(counters)}/3 counters, "
            f"flags: {', '.join(flags) if flags else 'none'}"
        ),
        "details": data,
    }


@action("tt.profile.get_username")
def get_username(a, p):
    value = first_text(_raw(a), PROFILE_SELECTORS.username).replace("@", "").strip()
    logger.info(f"tt.profile.get_username: {value!r}")
    return {"success": bool(value), "message": value, "details": {"username": value}}


@action("tt.profile.get_stats")
def get_stats(a, p):
    """The three counters AND the labels that decide which is which.

    The labels are reported deliberately: the row is paired by position, so a counter landing in
    the wrong field is a LABEL problem, and a run that only shows numbers cannot tell the two
    apart. A French phone once reported zero for all three because the labels were compared
    against English words.
    """
    device = _raw(a)
    values = first_matching(device, PROFILE_SELECTORS.stat_value)
    labels = first_matching(device, PROFILE_SELECTORS.stat_label)

    pairs = []
    for index in range(min(len(values), len(labels))):
        try:
            raw_value = values[index].text or ""
            raw_label = labels[index].text or ""
        except Exception:  # noqa: BLE001
            continue
        pairs.append({
            "value": raw_value,
            "label": raw_label,
            "classified": classify_profile_stat_label(raw_label),
        })

    unclassified = [pair["label"] for pair in pairs if not pair["classified"]]
    if unclassified:
        logger.warning(f"tt.profile.get_stats: labels not in the catalogue: {unclassified}")
    logger.info(f"tt.profile.get_stats: {pairs}")

    return {
        "success": bool(pairs) and not unclassified,
        "message": f"{len(pairs)} stat(s), {len(unclassified)} label(s) unclassified",
        "details": {"pairs": pairs, "unclassified": unclassified},
    }


@action("tt.profile.get_biography")
def get_biography(a, p):
    """The bio, and WHICH of the two paths found it.

    Production reads the catalogue anchor and, failing that, falls back to any button carrying a
    long text. Reporting only the final string would have hidden what the first run on a 43.1.4
    profile showed: the anchor resolves nothing and the fallback carries the whole feature. That
    is a dead selector wearing a working feature's clothes, and it is exactly what this family
    exists to surface.
    """
    device = _raw(a)
    by_anchor = first_text(device, PROFILE_SELECTORS.bio_text)

    by_fallback = ""
    if not by_anchor:
        try:
            buttons = device(**PROFILE_SELECTORS.bio_button_fallback_selector)
            for index in range(buttons.count):
                text = buttons[index].get_text() or ""
                if "\n" in text or len(text) > 50:
                    by_fallback = text
                    break
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"tt.profile.get_biography: fallback unavailable: {exc}")

    value = by_anchor or by_fallback
    path = "anchor" if by_anchor else ("fallback" if by_fallback else "none")
    if path == "fallback":
        logger.warning(
            "tt.profile.get_biography: the catalogue anchor found nothing; the bio comes from "
            "the long-button fallback. The anchor is dead on this version."
        )
    logger.info(f"tt.profile.get_biography: {len(value)} chars via {path}")

    return {
        "success": bool(value),
        "message": f"{len(value)} chars via {path}",
        "details": {"bio": value, "path": path, "anchorAlive": bool(by_anchor)},
    }


@action("tt.profile.open_own")
def open_own(a, p):
    """Go to OUR profile, and prove it is ours.

    Wired because the production check was wrong for an unknown time: it accepted "a username is
    visible", which is true on every profile in the app, so a tap landing on a stranger's page
    passed and their follower count was recorded as the bot's. The Lab now asks the same two
    questions production asks, on a real screen.
    """
    from taktik.core.social_media.tiktok.actions.business.actions.profile_actions import (
        ProfileActions,
    )

    ok = ProfileActions(a.device).navigate_to_own_profile()
    markers = {
        "edit_button": len(first_matching(_raw(a), PROFILE_SELECTORS.edit_profile_button)),
        "profile_menu": len(first_matching(_raw(a), PROFILE_SELECTORS.profile_menu_button)),
    }
    logger.info(f"tt.profile.open_own: {ok}, markers={markers}")
    return {
        "success": bool(ok),
        "message": "own profile" if ok else "not our profile (or not a profile)",
        "details": {"markers": markers},
    }


@action("tt.profile.count_posts")
def count_posts(a, p):
    """How many video thumbnails the profile grid exposes.

    This is the action whose absence let a whole version go unnoticed: `profile_post_item` was
    anchored on a 43.1.4 build id and read 0 on 46.6.3, so the followers workflow visited every
    profile, said "no posts" and interacted with nothing — reporting success. Nothing measured
    the grid, so nothing caught it. Now a version bump fails here instead of in production.
    """
    from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import (
        FOLLOWERS_SELECTORS,
    )

    device = _raw(a)
    per_anchor = {}
    for index, selector in enumerate(FOLLOWERS_SELECTORS.profile_post_item):
        try:
            per_anchor[f"#{index + 1}"] = len(device.xpath(selector).all())
        except Exception:  # noqa: BLE001
            per_anchor[f"#{index + 1}"] = 0

    total = max(per_anchor.values()) if per_anchor else 0
    dead = [name for name, count in per_anchor.items() if not count]
    logger.info(f"tt.profile.count_posts: {total} post(s), per anchor {per_anchor}")
    if total and dead:
        logger.warning(
            f"tt.profile.count_posts: {len(dead)} anchor(s) dead on this version — the grid is "
            f"carried by the others"
        )
    return {
        # A profile with a grid that reads zero is the failure this exists for. An account with
        # genuinely no video reads zero too, which is why the per-anchor split is reported: the
        # two look identical from the total alone.
        "success": total > 0,
        "message": f"{total} post(s)",
        "details": {"posts": total, "perAnchor": per_anchor, "deadAnchors": dead},
    }
