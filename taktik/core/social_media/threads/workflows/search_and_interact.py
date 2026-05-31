"""Threads Search & Interact — MVP workflow (mirrors Instagram hashtag pattern).

Scope:
    1. Launch Threads and wait for the main feed to be ready
    2. Tap the search tab and type the query
    3. Submit the query → wait for the SERP (Search Engine Result Page)
    4. Switch to the "Related profiles" tab
    5. Scroll through the profile list; for each profile:
         a. Open the profile screen
         b. Extract bio + follower count
         c. Apply the filter (min/max followers, bio keywords — optional)
         d. Dispatch actions using per-action probabilities:
              - Follow   (probability follow_percentage)
              - Like     (probability like_percentage on up to N recent posts)
              - Repost   (probability repost_percentage on 1 recent post)
              - Comment  (probability comment_percentage — DEFERRED to step D / taktik-agent)
         e. Back to SERP → next profile

Persistence (step C) and taktik-agent smart-comment (step D) are intentionally
left as TODO hooks in this module — only in-memory stats + IPC events flow for
now, which is enough for the Electron front to render live feedback.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from loguru import logger

from taktik.core.social_media.threads import ThreadsManager
from taktik.core.social_media.threads import ui as tui


# ──────────────────────────────────────────────────────────────────────────────
# Config + stats
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ActionProbabilities:
    """Per-action probability in the 0-100 range (0 = disabled, 100 = always)."""
    follow: int = 80
    like: int = 50
    repost: int = 0
    comment: int = 0  # step D — requires taktik-agent

    def normalised(self) -> "ActionProbabilities":
        clamp = lambda v: max(0, min(100, int(v)))
        return ActionProbabilities(
            follow=clamp(self.follow),
            like=clamp(self.like),
            repost=clamp(self.repost),
            comment=clamp(self.comment),
        )


@dataclass
class ProfileFilters:
    """Optional filters applied to each candidate profile before interaction."""
    min_followers: int = 0
    max_followers: int = 10_000_000
    bio_keywords_include: List[str] = field(default_factory=list)
    bio_keywords_exclude: List[str] = field(default_factory=list)


@dataclass
class SearchInteractConfig:
    device_id: str
    search_query: str
    max_profiles: int = 10
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 5.0
    max_likes_per_profile: int = 2
    actions: ActionProbabilities = field(default_factory=ActionProbabilities)
    filters: ProfileFilters = field(default_factory=ProfileFilters)


@dataclass
class InteractStats:
    profiles_visited: int = 0
    profiles_filtered: int = 0
    private_profiles: int = 0
    follows: int = 0
    likes: int = 0
    reposts: int = 0
    replies: int = 0  # smart comments (step D)
    errors: int = 0

    def as_dict(self) -> dict:
        return {
            "profiles_visited": self.profiles_visited,
            "profiles_interacted": self.follows + self.likes + self.reposts + self.replies,
            "profiles_filtered": self.profiles_filtered,
            "private_profiles": self.private_profiles,
            "likes": self.likes,
            "follows": self.follows,
            "reposts": self.reposts,
            "replies": self.replies,
            "errors": self.errors,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _sleep_jitter(cfg: SearchInteractConfig, scale: float = 1.0) -> None:
    time.sleep(random.uniform(cfg.min_delay_seconds, cfg.max_delay_seconds) * scale)


def _roll(probability: int) -> bool:
    """Uniform 0-100 roll. probability=0 → never, probability=100 → always."""
    if probability <= 0:
        return False
    if probability >= 100:
        return True
    return random.random() * 100 < probability


def _wait_resource(device, resource_id: str, timeout: float = 10.0):
    sel = device(resourceId=resource_id)
    return sel if sel.wait(timeout=timeout) else None


def _wait_any_resource(device, resource_ids, timeout: float = 15.0, poll: float = 0.5):
    """Return the first selector among `resource_ids` that appears before `timeout`.

    Useful because Threads may resume on different screens (main feed, search,
    profile, SERP) and each one exposes a different root resource-id.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for rid in resource_ids:
            sel = device(resourceId=rid)
            if sel.exists:
                return sel, rid
        time.sleep(poll)
    return None, None


def _find_any_text(device, candidates):
    for text in candidates:
        sel = device(text=text)
        if sel.exists:
            return sel
    return None


# Content-description candidates for the search entry point across locales.
# In recent Threads builds the loupe has no content-desc, but older builds do.
_SEARCH_LOUPE_DESCRIPTIONS = (
    "Search", "Rechercher", "Recherche", "Buscar", "Cerca", "Suche", "Procurar",
)


def _open_search_screen(device, log_fn) -> bool:
    """Open the Search screen.

    Recent Threads builds (Barcelona, 2026-04+) do NOT have a Search tab in
    the bottom navigation bar. Search is accessed via a loupe icon at the
    TOP-RIGHT of `MainFeedScreen`'s header. The loupe is an `android.widget.Button`
    with no resource-id and no content-description, so we identify it
    positionally as "clickable Button in the top-right of the header row".
    """
    # Strategy 1: try the legacy bottom-bar search tab resource-id (old builds).
    sel = device(resourceId=tui.TAB_SEARCH)
    if sel.exists:
        sel.click()
        return True

    # Strategy 2: clickable View/Button in top-right header with a Search-ish desc.
    for desc in _SEARCH_LOUPE_DESCRIPTIONS:
        sel = device(description=desc, clickable=True)
        if sel.exists:
            sel.click()
            return True

    # Strategy 3: find the unique unnamed clickable Button on the same row as
    # `main_feed_menu_button` (the hamburger top-left), positioned to its right.
    try:
        hamburger = device(resourceId=tui.MAIN_FEED_MENU_BUTTON)
        if hamburger.exists:
            h = hamburger.info.get("bounds") or {}
            row_top, row_bottom = h.get("top", 0), h.get("bottom", 0)
            row_mid = (row_top + row_bottom) / 2 if row_bottom else 0

            screen = device.info
            screen_w = screen.get("displayWidth", 1080)

            for el in device.xpath("//android.widget.Button").all():
                try:
                    attrs = el.attrib
                    if attrs.get("clickable") != "true":
                        continue
                    if attrs.get("resource-id"):  # hamburger or other named button
                        continue
                    # Parse bounds "[l,t][r,b]"
                    import re
                    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", attrs.get("bounds", ""))
                    if not m:
                        continue
                    left, top, right, bottom = map(int, m.groups())
                    # Must be in the same horizontal row as the hamburger, on its right side.
                    if row_bottom and not (row_top - 20 <= top and bottom <= row_bottom + 20):
                        continue
                    if (left + right) / 2 <= screen_w * 0.5:
                        continue
                    # Tap centre of the detected loupe button.
                    cx = (left + right) // 2
                    cy = (top + bottom) // 2
                    log_fn("info", f"Tapping top-right search loupe at ({cx},{cy})")
                    device.click(cx, cy)
                    return True
                except Exception:  # noqa: BLE001
                    continue
    except Exception as exc:  # noqa: BLE001
        log_fn("warning", f"Loupe detection via hamburger row failed: {exc}")

    # Strategy 4: positional fallback based on the captured fraction.
    try:
        info = device.info
        w = info.get("displayWidth", 1080)
        h = info.get("displayHeight", 1920)
        fx, fy = tui.FEED_SEARCH_LOUPE_FRACTION
        cx, cy = int(w * fx), int(h * fy)
        log_fn("info", f"Falling back to positional loupe tap at ({cx},{cy})")
        device.click(cx, cy)
        return True
    except Exception as exc:  # noqa: BLE001
        log_fn("error", f"Positional loupe fallback failed: {exc}")

    # Diagnostic dump so the next capture tells us how to locate the loupe.
    try:
        visible = []
        for elem in device.xpath("//*[@resource-id]").all()[:40]:
            rid = elem.attrib.get("resource-id") or ""
            desc = elem.attrib.get("content-desc") or ""
            if rid or desc:
                visible.append(f"{rid}|{desc}")
        log_fn("error",
               "Search loupe not found. Visible rid|desc: " + ", ".join(visible[:20]))
    except Exception as exc:  # noqa: BLE001
        log_fn("error", f"Search loupe not found and diagnostic dump failed: {exc}")
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def run_search_and_interact(
    config: SearchInteractConfig,
    *,
    on_log: Optional[Callable[[str, str], None]] = None,
    on_stats: Optional[Callable[[InteractStats], None]] = None,
    on_profile_visit: Optional[Callable[[dict], None]] = None,
    on_action: Optional[Callable[[str, str, dict], None]] = None,
    startup=None,
) -> InteractStats:
    """Run the Threads search-and-interact workflow.

    Callbacks let the bridge forward IPC events without coupling this module to
    the transport layer.
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

    query = (config.search_query or "").strip()
    if not query:
        _log("error", "No search query provided")
        stats.errors += 1
        _push_stats()
        return stats

    # Connect + launch remains the default bridge path; Agent handlers can inject startup.
    if startup is None:
        from taktik.core.social_media.threads.workflows._common import threads_startup

        startup = threads_startup(
            config.device_id,
            log=_log,
            anchors=(
                tui.TABS_BOTTOM_BAR,
                tui.MAIN_FEED_SCREEN,
                tui.SEARCH_BAR,
                tui.PROFILE_SCREEN_ROOT,
                tui.SERP_MENU_BUTTON,
            ),
        )
    if startup is None:
        stats.errors += 1
        _push_stats()
        return stats
    manager, device, anchor_rid = startup

    # ── Search ────────────────────────────────────────────────────────────
    if not _open_search_and_submit(device, query, _log):
        stats.errors += 1
        _push_stats()
        return stats

    # ── Related profiles tab ──────────────────────────────────────────────
    serp_mode = _switch_to_related_profiles(device, _log)
    if not serp_mode:
        # Not fatal — some queries show profiles directly on Top posts tab.
        _log("warning", "Could not locate 'Related profiles' section — continuing on current SERP")
    elif serp_mode == "section":
        # Layout B: profiles are already visible in the carousel.
        # Give the page an extra moment to settle before collecting.
        time.sleep(0.8)

    _sleep_jitter(config, scale=0.3)

    # ── Iterate profile cells ──────────────────────────────────────────────
    processed = 0
    seen_usernames: set[str] = set()
    consecutive_empty_scrolls = 0

    while processed < config.max_profiles:
        usernames = _collect_visible_usernames(device)
        fresh = [u for u in usernames if u and u not in seen_usernames]

        if not fresh:
            consecutive_empty_scrolls += 1
            if consecutive_empty_scrolls >= 3:
                _log("info", "No more fresh profiles after 3 scrolls — stopping")
                break
            _scroll_serp(device)
            _sleep_jitter(config, scale=0.4)
            continue

        consecutive_empty_scrolls = 0
        for username in fresh:
            if processed >= config.max_profiles:
                break
            seen_usernames.add(username)

            try:
                outcome = _visit_and_act(
                    device, username,
                    cfg=config, actions=actions, stats=stats, log_fn=_log,
                    on_profile_visit=on_profile_visit,
                    on_action=on_action,
                )
                if outcome == "visited":
                    processed += 1
            except Exception as exc:  # noqa: BLE001 — per-profile guard
                stats.errors += 1
                _log("error", f"Error while processing @{username}: {exc}")
                # Try to recover by pressing back a couple of times.
                for _ in range(2):
                    device.press("back")
                    time.sleep(0.6)

            _push_stats()
            _sleep_jitter(config)

        # Need more? Scroll and continue.
        if processed < config.max_profiles:
            _scroll_serp(device)
            _sleep_jitter(config, scale=0.4)

    _log("info",
         f"Done — visited={stats.profiles_visited} follows={stats.follows} "
         f"likes={stats.likes} reposts={stats.reposts} errors={stats.errors}")
    _push_stats()
    return stats


# ──────────────────────────────────────────────────────────────────────────────
# Workflow steps
# ──────────────────────────────────────────────────────────────────────────────


def _wait_search_screen(device, timeout: float = 7.0) -> bool:
    """Return True when the search screen (BdsSearchBar or BasicTextField) is visible."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if device(resourceId=tui.SEARCH_BAR).exists:
            return True
        if device(resourceId=tui.SEARCH_TEXT_FIELD).exists:
            return True
        time.sleep(0.4)
    return False


def _open_search_and_submit(device, query: str, log_fn) -> bool:
    """Open search screen (top-right loupe), type the query, submit via IME action."""
    # If the search bar is already visible, skip the loupe click.
    if not device(resourceId=tui.SEARCH_BAR).exists:
        if not _open_search_screen(device, log_fn):
            return False
        time.sleep(0.8)
        # Wait for the search screen to appear; retry the tap once if needed.
        if not _wait_search_screen(device, timeout=7.0):
            log_fn("warning", "Search screen did not appear — retrying loupe tap")
            time.sleep(0.5)
            _open_search_screen(device, log_fn)
            time.sleep(0.8)
            if not _wait_search_screen(device, timeout=8.0):
                log_fn("error", "Search screen did not open after tapping the loupe (2 attempts)")
                return False

    # The text input is Jetpack-Compose based; resource-id is BasicTextField.
    # Tap the search bar once to focus it (some Threads builds require tapping
    # BdsSearchBar first, then the inner BasicTextField becomes editable).
    bar = device(resourceId=tui.SEARCH_BAR)
    if bar.exists:
        bar.click()
        time.sleep(0.5)

    text_field = device(resourceId=tui.SEARCH_TEXT_FIELD)
    if not text_field.wait(timeout=5.0):
        # Fallback: generic EditText
        text_field = device(className="android.widget.EditText")
        if not text_field.wait(timeout=4.0):
            log_fn("error", "Search input did not appear on the search screen")
            return False

    text_field.click()
    time.sleep(0.3)
    try:
        text_field.clear_text()
    except Exception:  # noqa: BLE001
        pass
    text_field.set_text(query)
    time.sleep(1.2)

    # Submit: press IME search action (Enter). uiautomator2 maps this to key 66.
    device.press("enter")
    log_fn("info", f"🔍 Searched: {query}")
    time.sleep(2.0)
    return True


def _switch_to_related_profiles(device, log_fn):
    """Detect 'Related profiles' on the SERP and handle both layouts.

    Threads shows two different SERP layouts depending on the query:

    Layout A (tab switcher): 'Related profiles' is a **clickable** compact tab
        at the top of the page alongside 'Top posts'. Tapping it switches the
        view to a dedicated profiles list with BdsPeopleCell rows.

    Layout B (inline section): 'Related profiles' is a **non-clickable**
        full-width section header followed by a horizontal IgLazyRow carousel
        of profile cards. Profiles are already visible — nothing to click.

    Returns:
        "tab"     — Layout A clicked successfully; now on profiles list view.
        "section" — Layout B detected; profiles already in IgLazyRow carousel.
        False     — Not found at all.
    """
    for text in tui.RELATED_PROFILES_TAB_TEXTS:
        # Try exact match first, then textContains (some builds append an emoji).
        sel = device(text=text)
        if not sel.exists:
            sel = device(textContains=text)
        if not sel.exists:
            continue
        try:
            info = sel.info
        except Exception:  # noqa: BLE001
            continue
        if info.get("clickable"):
            # Layout A: it's an actual tab button.
            sel.click()
            time.sleep(1.5)
            log_fn("info", f"Switched to SERP profiles tab: {text!r}")
            return "tab"
        else:
            # Layout B: section header — profiles are already in the carousel.
            log_fn("info", "Related profiles visible as inline section (Layout B)")
            return "section"
    return False


def _collect_visible_usernames(device) -> List[str]:
    """Extract usernames from the currently visible SERP rows.

    Handles three layouts:
    1. Tab view (Layout A after clicking Related profiles tab):
       Elements with resource-id=Username or BdsPeopleCell ig_text children.
    2. Inline section carousel (Layout B):
       ig_text children inside the IgLazyRow horizontal carousel.
       Usernames are identified as handle-like strings (no spaces, no @).
    """
    usernames: List[str] = []

    # Strategy 1: Profile rows with resource-id=Username (tab/list view).
    for el in device(resourceId=tui.PROFILE_USERNAME_TEXT):
        try:
            txt = (el.info.get("text") or "").strip().lstrip("@")
            if txt and " " not in txt and txt not in usernames:
                usernames.append(txt)
        except Exception:  # noqa: BLE001
            continue

    # Strategy 2: BdsPeopleCell ig_text children (tab/list view, legacy layout).
    if not usernames:
        for el in device(resourceId=tui.PEOPLE_CELL):
            try:
                for child in el.child(resourceId=tui.IG_TEXT):
                    txt = (child.info.get("text") or "").strip().lstrip("@")
                    if txt and " " not in txt and txt not in usernames:
                        usernames.append(txt)
                        break
            except Exception:  # noqa: BLE001
                continue

    # Strategy 3: IgLazyRow carousel (Layout B inline section view).
    # Each card has ig_text children; usernames are the no-space handle strings.
    if not usernames:
        row = device(resourceId=tui.SERP_LAZY_ROW)
        if row.exists:
            try:
                for child in row.child(resourceId=tui.IG_TEXT):
                    txt = (child.info.get("text") or "").strip().lstrip("@")
                    if txt and " " not in txt and txt not in usernames:
                        usernames.append(txt)
            except Exception:  # noqa: BLE001
                pass

    return usernames


def _scroll_serp(device) -> None:
    """Scroll the main results list one page down."""
    try:
        info = device.info
        w, h = info["displayWidth"], info["displayHeight"]
        device.swipe(w // 2, int(h * 0.75), w // 2, int(h * 0.35), duration=0.3)
    except Exception:  # noqa: BLE001
        device.swipe(500, 1500, 500, 600, duration=0.3)


# ──────────────────────────────────────────────────────────────────────────────
# Per-profile interaction
# ──────────────────────────────────────────────────────────────────────────────


def _visit_and_act(
    device,
    username: str,
    *,
    cfg: SearchInteractConfig,
    actions: ActionProbabilities,
    stats: InteractStats,
    log_fn,
    on_profile_visit,
    on_action,
) -> str:
    """Open a profile and run the probabilistic action pipeline.

    Returns:
        "visited"  — profile opened and stats.profiles_visited incremented
        "filtered" — profile was filtered out
        "skipped"  — could not open the profile
    """
    log_fn("info", f"▶ Visiting @{username}")
    # Tap the profile cell by username text.
    # In the SERP the text is bare (e.g. "username"); in the home feed it is
    # prefixed with "@" (e.g. "@username"), so we try both variants.
    cell = device(text=username)
    if not cell.exists:
        cell = device(text=f"@{username}")
    if not cell.exists:
        log_fn("warning", f"Profile row not tappable for @{username}")
        return "skipped"
    cell.click()
    time.sleep(2.0)

    if not _wait_resource(device, tui.PROFILE_SCREEN_ROOT, timeout=8.0):
        log_fn("warning", f"Profile screen did not open for @{username}")
        # Try to recover
        device.press("back")
        time.sleep(0.8)
        return "skipped"

    profile_info = _extract_profile_info(device)
    profile_info["username"] = username
    stats.profiles_visited += 1

    if on_profile_visit:
        try:
            on_profile_visit(profile_info)
        except Exception:  # noqa: BLE001
            pass

    # Filter
    if not _passes_filters(profile_info, cfg.filters, log_fn):
        stats.profiles_filtered += 1
        _leave_profile(device)
        return "filtered"

    # Action dispatch — order matters: follow first (cheapest), then likes, then repost
    if _roll(actions.follow):
        if _do_follow(device, log_fn):
            stats.follows += 1
            if on_action:
                try:
                    on_action("follow", username, profile_info)
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(random.uniform(1.0, 2.0))

    likes_done = 0
    if actions.like > 0 and cfg.max_likes_per_profile > 0:
        likes_done = _do_likes_on_posts(
            device, username,
            probability=actions.like,
            max_likes=cfg.max_likes_per_profile,
            stats=stats,
            log_fn=log_fn,
            on_action=on_action,
            profile_info=profile_info,
        )

    if actions.repost > 0 and _roll(actions.repost):
        if _do_repost_first_post(device, log_fn):
            stats.reposts += 1
            if on_action:
                try:
                    on_action("repost", username, profile_info)
                except Exception:  # noqa: BLE001
                    pass

    # Comment / smart-comment is step D — placeholder hook
    if actions.comment > 0 and _roll(actions.comment):
        log_fn("debug", "Smart comment requested but taktik-agent integration is not wired yet (step D)")

    _leave_profile(device)

    _ = likes_done  # (silence unused)
    return "visited"


def _extract_profile_info(device) -> dict:
    info: dict = {
        "full_name": None,
        "bio": None,
        "followers": None,
        "is_private": False,
        "already_following": False,
    }
    try:
        full_name_el = device(resourceId=tui.PROFILE_FULL_NAME)
        if full_name_el.exists:
            info["full_name"] = (full_name_el.info.get("text") or "").strip() or None
    except Exception:  # noqa: BLE001
        pass
    try:
        bio_el = device(resourceId=tui.PROFILE_BIO_TEXT)
        if bio_el.exists:
            info["bio"] = (bio_el.info.get("text") or "").strip() or None
    except Exception:  # noqa: BLE001
        pass
    try:
        followers_el = device(resourceId=tui.PROFILE_BIO_FOLLOWER_COUNT)
        if followers_el.exists:
            info["followers"] = _parse_followers((followers_el.info.get("text") or "").strip())
    except Exception:  # noqa: BLE001
        pass
    # Detect already following by button text
    follow_btn = device(resourceId=tui.PROFILE_FOLLOW_BUTTON)
    if follow_btn.exists:
        btn_text = (follow_btn.info.get("text") or "").strip()
        if btn_text in tui.FOLLOWING_BUTTON_TEXTS:
            info["already_following"] = True
    return info


def _parse_followers(text: str) -> Optional[int]:
    """Parse '266 followers' / '1,2K followers' / '12.3M followers' → int."""
    if not text:
        return None
    # Keep only digits, commas, dots and suffix letters
    raw = text.split()[0].replace(",", ".").lower()
    multiplier = 1
    if raw.endswith("k"):
        multiplier = 1_000
        raw = raw[:-1]
    elif raw.endswith("m"):
        multiplier = 1_000_000
        raw = raw[:-1]
    try:
        return int(float(raw) * multiplier)
    except ValueError:
        return None


def _passes_filters(info: dict, filters: ProfileFilters, log_fn) -> bool:
    followers = info.get("followers")
    if followers is not None:
        if followers < filters.min_followers or followers > filters.max_followers:
            log_fn("info", f"⏭️ Filtered @{info['username']} — {followers} followers outside [{filters.min_followers}, {filters.max_followers}]")
            return False

    bio = (info.get("bio") or "").lower()
    if filters.bio_keywords_include:
        if not any(kw.lower() in bio for kw in filters.bio_keywords_include):
            log_fn("info", f"⏭️ Filtered @{info['username']} — bio does not include required keyword")
            return False
    if filters.bio_keywords_exclude:
        if any(kw.lower() in bio for kw in filters.bio_keywords_exclude):
            log_fn("info", f"⏭️ Filtered @{info['username']} — bio matches excluded keyword")
            return False

    if info.get("already_following"):
        log_fn("info", f"⏭️ Skipped @{info['username']} — already following")
        return False

    return True


def _do_follow(device, log_fn) -> bool:
    follow_btn = device(resourceId=tui.PROFILE_FOLLOW_BUTTON)
    if not follow_btn.exists:
        log_fn("warning", "Follow button not present on profile")
        return False
    txt = (follow_btn.info.get("text") or "").strip()
    if txt in tui.FOLLOWING_BUTTON_TEXTS:
        log_fn("info", "Already following — skipping tap")
        return False
    follow_btn.click()
    log_fn("success", "👥 Followed")
    return True


def _do_likes_on_posts(device, username, *, probability: int, max_likes: int,
                       stats: InteractStats, log_fn, on_action, profile_info: dict) -> int:
    """Scroll profile feed, like up to `max_likes` recent posts with `probability`."""
    # Make sure we are on the Threads tab of the profile (default after open).
    liked = 0
    scrolls = 0
    max_scrolls = 4
    while liked < max_likes and scrolls <= max_scrolls:
        like_buttons = device(resourceId=tui.FEED_POST_LIKE)
        count = like_buttons.count if hasattr(like_buttons, "count") else 0
        for idx in range(count):
            if liked >= max_likes:
                break
            if not _roll(probability):
                continue
            try:
                btn = like_buttons[idx]
                # Skip already-liked (content-desc often contains "Unlike" / "Ne plus aimer")
                desc = (btn.info.get("contentDescription") or "").lower()
                if "unlike" in desc or "ne plus aimer" in desc:
                    continue
                btn.click()
                liked += 1
                stats.likes += 1
                log_fn("success", f"❤️ Liked post #{idx + 1} on @{username}")
                if on_action:
                    try:
                        on_action("like", username, {**profile_info, "post_index": idx})
                    except Exception:  # noqa: BLE001
                        pass
                time.sleep(random.uniform(0.8, 1.8))
            except Exception as exc:  # noqa: BLE001
                log_fn("warning", f"Like failed on post #{idx}: {exc}")
        if liked >= max_likes:
            break
        # Scroll profile feed
        try:
            info = device.info
            w, h = info["displayWidth"], info["displayHeight"]
            device.swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.3), duration=0.3)
        except Exception:  # noqa: BLE001
            device.swipe(500, 1400, 500, 600, duration=0.3)
        scrolls += 1
        time.sleep(1.2)
    return liked


def _do_repost_first_post(device, log_fn) -> bool:
    """Tap the repost button of the first visible post of the profile.

    Threads repost opens a modal; for MVP we just dismiss it unless a clear
    confirm button appears. This is a best-effort implementation and should be
    refined with a dedicated UI dump of the repost modal.
    """
    repost_btn = device(resourceId=tui.FEED_POST_REPOST)
    if not repost_btn.exists:
        log_fn("debug", "No repost button visible")
        return False
    try:
        repost_btn.click()
    except Exception as exc:  # noqa: BLE001
        log_fn("warning", f"Repost click failed: {exc}")
        return False
    time.sleep(1.2)
    # Try to find a "Repost" confirm text on the modal; if not, press back.
    confirm = _find_any_text(device, tui.REPOST_CONFIRM_TEXTS)
    if confirm is not None:
        try:
            confirm.click()
        except Exception:  # noqa: BLE001
            pass
        log_fn("success", "🔁 Reposted")
        time.sleep(0.8)
        return True
    # No confirm modal — fall back to closing and treating as skipped
    device.press("back")
    log_fn("debug", "Repost modal not found — skipped")
    return False


def _leave_profile(device) -> None:
    """Press back from the profile screen to return to the SERP."""
    back_btn = device(resourceId=tui.NAV_BAR_BACK_BUTTON)
    if back_btn.exists:
        back_btn.click()
    else:
        device.press("back")
    time.sleep(1.0)
