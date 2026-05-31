"""Threads Feed & Interact — workflow that iterates the home feed.

Scope:
    1. Launch Threads and wait for the main feed to be ready
    2. Ensure we are on the Home feed tab (tap barcelona_tab_main_feed if needed)
    3. Scroll through the home feed; for each post author encountered:
         a. Open the author's profile screen
         b. Extract bio + follower count
         c. Apply the filter (min/max followers, bio keywords — optional)
         d. Dispatch actions using per-action probabilities:
              - Follow   (probability follow_percentage)
              - Like     (probability like_percentage on up to N recent posts)
              - Repost   (probability repost_percentage on 1 recent post)
              - Comment  (probability comment_percentage — DEFERRED, taktik-agent)
         e. Back to feed → next post

The profile interaction pipeline is shared with search_and_interact via
direct import of the private helpers (duck typing, no ABC required).
"""

from __future__ import annotations

import re
import random
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from loguru import logger

from taktik.core.social_media.threads import ThreadsManager
from taktik.core.social_media.threads import ui as tui

# Reuse shared helpers from the search workflow (duck typing; FeedInteractConfig
# exposes the same attributes _visit_and_act and _sleep_jitter consume).
from taktik.core.social_media.threads.workflows.search_and_interact import (
    ActionProbabilities,  # re-exported below
    InteractStats,        # re-exported below
    ProfileFilters,       # re-exported below
    _leave_profile,
    _open_search_screen,
    _roll,
    _sleep_jitter,
    _visit_and_act,
    _wait_any_resource,
    _wait_resource,
)


# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class FeedInteractConfig:
    """Configuration for the Feed & Interact workflow."""
    device_id: str
    max_profiles: int = 10
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 5.0
    max_likes_per_profile: int = 2
    actions: ActionProbabilities = field(default_factory=ActionProbabilities)
    filters: ProfileFilters = field(default_factory=ProfileFilters)


# ──────────────────────────────────────────────────────────────────────────────
# Handle-pattern helpers
# ──────────────────────────────────────────────────────────────────────────────

# Typical Threads/Instagram handle: 3-30 chars, only [a-z0-9._], no leading dot.
_HANDLE_RE = re.compile(r'^[a-z0-9][a-z0-9._]{2,29}$', re.IGNORECASE)

# Content-desc values that look like handles but are UI labels — skip them.
_EXCLUDED_DESCS = frozenset({
    "follow", "unfollow", "following", "follow back",
    "like", "unlike", "reply", "repost", "share",
    "more options", "dismiss action to hide user.",
    "profile photo",  # partial — checked with 'endswith' below
})


def _looks_like_handle(text: str) -> bool:
    """Return True if *text* looks like a Threads/Instagram handle."""
    t = text.strip().rstrip(".").lower()
    if not t or " " in t:
        return False
    if t in _EXCLUDED_DESCS:
        return False
    if t.endswith("profile photo"):
        return False
    return bool(_HANDLE_RE.match(t))


# ──────────────────────────────────────────────────────────────────────────────
# Feed-specific helpers
# ──────────────────────────────────────────────────────────────────────────────


def _navigate_to_home_feed(device, log_fn) -> bool:
    """Ensure the Home feed tab is active and the feed is visible."""
    tab = device(resourceId=tui.TAB_MAIN_FEED)
    if tab.exists:
        tab.click()
        time.sleep(1.2)
    # Confirm feed is visible.
    if device(resourceId=tui.MAIN_FEED_SCREEN).wait(timeout=8.0):
        return True
    if device(resourceId=tui.FEED_POST_LIKE).wait(timeout=5.0):
        return True
    log_fn("warning", "Home feed not confirmed after tab click")
    return False


def _collect_feed_usernames(device) -> List[str]:
    """Extract post-author handles from the currently visible feed.

    Two strategies:
    1. ig_text resources whose text looks like a handle — these sit in the
       post-header row at the top of each FeedPostRow.
    2. Unnamed clickable elements whose content-desc looks like a handle
       (fallback for builds where ig_text has no resourceId match).

    Duplicates are removed; ordering follows visual top-to-bottom.
    """
    usernames: List[str] = []

    # Strategy 1: ig_text with handle-like text.
    try:
        for el in device(resourceId=tui.IG_TEXT):
            try:
                txt = (el.info.get("text") or "").strip().lstrip("@")
                if txt and _looks_like_handle(txt) and txt not in usernames:
                    usernames.append(txt)
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass

    # Strategy 2: clickable elements with handle-like content-desc.
    if not usernames:
        try:
            for el in device(clickable=True):
                try:
                    desc = (el.info.get("contentDescription") or "").strip().rstrip()
                    if desc and _looks_like_handle(desc) and desc not in usernames:
                        usernames.append(desc)
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            pass

    return usernames


def _scroll_feed(device) -> None:
    """Scroll the home feed one page down."""
    try:
        info = device.info
        w, h = info["displayWidth"], info["displayHeight"]
        device.swipe(w // 2, int(h * 0.70), w // 2, int(h * 0.30), duration=0.4)
    except Exception:  # noqa: BLE001
        device.swipe(288, 900, 288, 350, duration=0.4)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def run_feed_and_interact(
    config: FeedInteractConfig,
    *,
    on_log: Optional[Callable[[str, str], None]] = None,
    on_stats: Optional[Callable[[InteractStats], None]] = None,
    on_profile_visit: Optional[Callable[[dict], None]] = None,
    on_action: Optional[Callable[[str, str, dict], None]] = None,
    startup=None,
) -> InteractStats:
    """Run the Threads feed-and-interact workflow.

    Iterates visible home-feed posts, visits each author's profile and
    applies the configured action probabilities (follow / like / repost).
    """
    stats = InteractStats()
    actions = config.actions.normalised()

    def _log(level: str, message: str) -> None:
        getattr(logger, level, logger.info)(message)
        if on_log:
            try:
                on_log(level, message)
            except Exception:  # noqa: BLE001
                pass

    def _push_stats() -> None:
        if on_stats:
            try:
                on_stats(stats)
            except Exception:  # noqa: BLE001
                pass

    # Connect + launch remains the default bridge path; Agent handlers can inject startup.
    if startup is None:
        from taktik.core.social_media.threads.workflows._common import threads_startup

        startup = threads_startup(
            config.device_id,
            log=_log,
            anchors=(
                tui.TABS_BOTTOM_BAR,
                tui.MAIN_FEED_SCREEN,
                tui.PROFILE_SCREEN_ROOT,
            ),
        )
    if startup is None:
        stats.errors += 1
        _push_stats()
        return stats
    manager, device, anchor_rid = startup

    # ── Navigate to Home feed tab ──────────────────────────────────────────
    if not _navigate_to_home_feed(device, _log):
        _log("warning", "Home feed confirmation failed — continuing anyway")

    _log("info", "Starting feed iteration…")

    # ── Iterate feed posts ─────────────────────────────────────────────────
    processed = 0
    seen_usernames: set[str] = set()
    consecutive_empty_scrolls = 0

    while processed < config.max_profiles:
        usernames = _collect_feed_usernames(device)
        fresh = [u for u in usernames if u and u not in seen_usernames]

        if not fresh:
            consecutive_empty_scrolls += 1
            if consecutive_empty_scrolls >= 4:
                _log("info", "No more fresh profiles after 4 scrolls — stopping")
                break
            _scroll_feed(device)
            time.sleep(random.uniform(config.min_delay_seconds, config.max_delay_seconds) * 0.4)
            continue

        consecutive_empty_scrolls = 0
        for username in fresh:
            if processed >= config.max_profiles:
                break
            seen_usernames.add(username)

            try:
                outcome = _visit_and_act(
                    device, username,
                    cfg=config,
                    actions=actions,
                    stats=stats,
                    log_fn=_log,
                    on_profile_visit=on_profile_visit,
                    on_action=on_action,
                )
                if outcome == "visited":
                    processed += 1
            except Exception as exc:  # noqa: BLE001 — per-profile guard
                stats.errors += 1
                _log("error", f"Error while processing @{username}: {exc}")
                for _ in range(2):
                    device.press("back")
                    time.sleep(0.6)

            _push_stats()
            _sleep_jitter(config)

        # Need more? Scroll and continue.
        if processed < config.max_profiles:
            _scroll_feed(device)
            time.sleep(random.uniform(config.min_delay_seconds, config.max_delay_seconds) * 0.4)

    _log("info",
         f"Done — visited={stats.profiles_visited} follows={stats.follows} "
         f"likes={stats.likes} reposts={stats.reposts} errors={stats.errors}")
    _push_stats()
    return stats
