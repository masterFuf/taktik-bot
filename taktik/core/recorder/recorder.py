"""
Human Behavior Recorder for Instagram
======================================
Poll the device UI every `poll_interval` seconds using lightweight XPath checks.
Emit timestamped events whenever the visible state changes.
Write one JSON object per line (JSONL) to `output_path`.

Events emitted
--------------
session_start       – recording started
screen_enter        – navigated to a new screen
screen_exit         – left a screen (includes dwell_ms)
content_change      – scrolled to a different post/reel/story (author changed)
like                – like button flipped to "liked" state
unlike              – like button flipped back to "not liked"
comment_open        – comments panel appeared
profile_visit       – arrived on a profile page (author = username)
session_end         – Ctrl-C received (includes summary stats)
"""

import time
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from loguru import logger
import uiautomator2 as u2

from taktik.core.social_media.instagram.ui.selectors import (
    DETECTION_SELECTORS,
    FEED_SELECTORS,
    POST_SELECTORS,
    STORY_SELECTORS,
    DM_SELECTORS,
)
from taktik.core.clone import rid as _rid

# ---------------------------------------------------------------------------
# Screen constants
# ---------------------------------------------------------------------------
SCREEN_FEED = "feed"
SCREEN_REEL_VIEWER = "reel_viewer"
SCREEN_STORY_VIEWER = "story_viewer"
SCREEN_PROFILE = "profile"
SCREEN_SEARCH = "search"
SCREEN_DM = "dm"
SCREEN_COMMENTS = "comments"
SCREEN_NOTIFICATIONS = "notifications"
SCREEN_OTHER = "other"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class UISnapshot:
    """Minimal snapshot of what's currently visible — built from XPath checks only."""
    ts: float                             # monotonic time (for dwell computation)
    screen: str = SCREEN_OTHER
    content_type: str = "unknown"         # post | reel | story | unknown
    author: Optional[str] = None          # author of the current content
    is_liked: bool = False                # like button is in "liked/Unlike" state
    is_comments_open: bool = False
    profile_username: Optional[str] = None


@dataclass
class RecordedEvent:
    """One event that will be written as a JSONL line."""
    ts: str                               # ISO 8601 UTC
    event: str
    screen: Optional[str] = None
    content_type: Optional[str] = None
    author: Optional[str] = None
    dwell_ms: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_jsonl(self) -> str:
        d = {k: v for k, v in asdict(self).items() if v is not None and v != {}}
        return json.dumps(d, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _exists(device, selector: str) -> bool:
    try:
        return device.xpath(_rid(selector)).exists
    except Exception:
        return False


def _text(device, selector: str) -> Optional[str]:
    try:
        el = device.xpath(_rid(selector))
        if el.exists:
            return el.get_text() or None
    except Exception:
        pass
    return None


def _first_text(device, selectors: list) -> Optional[str]:
    for sel in selectors:
        val = _text(device, sel)
        if val:
            return val
    return None


# ---------------------------------------------------------------------------
# Screen detector
# ---------------------------------------------------------------------------
class ScreenDetector:
    """
    Determine current Instagram screen using a small number of fast XPath checks.
    Priority order matters: most distinctive screen first.

    Story vs Reel distinction
    -------------------------
    Stories always have a progress bar at the top (`reel_viewer_progress_bar`).
    Reels (fullscreen feed) always have audio mute/unmute controls.
    Both share `reel_viewer` as a resource-id prefix — so we check the
    distinguishing elements BEFORE falling back to the generic prefix.
    """

    # Stories: progress bar at the top — unique to story viewer, NOT in reels
    _STORY_PROGRESS = STORY_SELECTORS.story_progress_bar   # reel_viewer_progress_bar
    _STORY_HEADER   = STORY_SELECTORS.story_viewer_header   # reel_viewer_header

    # Reels: audio controls always visible in fullscreen reel player
    _REEL_PLAYER = (
        '//*[@content-desc="Couper le son"]',
        '//*[@content-desc="Activer le son"]',
        '//*[contains(@content-desc, "Turn sound off")]',
        '//*[contains(@content-desc, "Turn sound on")]',
        '//*[@content-desc="Audio"]',
    )

    # Feed: author name row — fast & reliable
    _FEED = '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]'

    # Comments sheet can overlay feed — check before feed
    _COMMENTS = (
        '//*[contains(@resource-id, "comments_header")]',
        '//*[contains(@resource-id, "layout_comment_thread")]',
    )

    # DM: use concrete selectors from DM_SELECTORS
    _DM = (
        DM_SELECTORS.inbox_thread_list,          # inbox list
        DM_SELECTORS.thread_container,           # single conversation row
        '//*[@resource-id="com.instagram.android:id/message_list"]',  # open thread
    )

    _PROFILE = (
        '//*[contains(@resource-id, "profile_header_full_name")]',
        '//*[contains(@resource-id, "profile_header")]',
    )
    _NOTIF = '//*[contains(@resource-id, "notification_inbox")]'
    _SEARCH = (
        '//*[contains(@content-desc, "Rechercher") and @selected="true"]',
        '//*[contains(@content-desc, "Search") and @selected="true"]',
    )

    def __init__(self, device):
        self._d = device

    def detect(self) -> str:
        d = self._d
        # 1. Story viewer — progress bar is story-unique
        if _exists(d, self._STORY_PROGRESS) or _exists(d, self._STORY_HEADER):
            return SCREEN_STORY_VIEWER
        # 2. Reel fullscreen player — audio controls
        for sel in self._REEL_PLAYER:
            if _exists(d, sel):
                return SCREEN_REEL_VIEWER
        # 3. Comments sheet (can overlay feed)
        for sel in self._COMMENTS:
            if _exists(d, sel):
                return SCREEN_COMMENTS
        # 4. Home feed
        if _exists(d, self._FEED):
            return SCREEN_FEED
        # 5. DM
        for sel in self._DM:
            if _exists(d, sel):
                return SCREEN_DM
        # 6. Profile
        for sel in self._PROFILE:
            if _exists(d, sel):
                return SCREEN_PROFILE
        # 7. Notifications
        if _exists(d, self._NOTIF):
            return SCREEN_NOTIFICATIONS
        # 8. Search/Explore
        for sel in self._SEARCH:
            if _exists(d, sel):
                return SCREEN_SEARCH
        return SCREEN_OTHER


# ---------------------------------------------------------------------------
# Content sampler
# ---------------------------------------------------------------------------
class ContentSampler:
    """
    Given the current screen, extract the relevant state (author, like status, etc.)
    using only XPath checks — no full UI dump.
    """

    _FEED_AUTHOR = [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_username"]',
    ]
    _REEL_AUTHOR = [
        '//*[@resource-id="com.instagram.android:id/clips_author_info"]//android.widget.TextView',
        '//*[@resource-id="com.instagram.android:id/clips_author_username"]',
        '//*[@resource-id="com.instagram.android:id/username"]',
        '//android.widget.TextView[starts-with(@text, "@")]',
        # row_feed selectors also appear when a reel is embedded in the feed
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
    ]
    # Story author: reel_viewer_title is the reliable resource-id (confirmed in STORY_SELECTORS)
    _STORY_AUTHOR = [
        STORY_SELECTORS.story_viewer_title,      # com.instagram.android:id/reel_viewer_title
        '//*[contains(@resource-id, "reel_viewer_title")]',
        '//*[contains(@resource-id, "story_username")]',
        '//*[contains(@resource-id, "reel_viewer_username")]',
        '//*[contains(@resource-id, "username")]',
    ]
    _PROFILE_USERNAME = [
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
        '//*[contains(@resource-id, "username")]',
    ]
    # "Already liked" = button shows "Unlike" / "Ne plus aimer"
    _LIKED = FEED_SELECTORS.already_liked_indicators[:3]

    def __init__(self, device):
        self._d = device

    def sample(self, screen: str) -> UISnapshot:
        snap = UISnapshot(ts=time.monotonic(), screen=screen)

        if screen == SCREEN_FEED:
            snap.content_type = "reel" if self._is_reel_in_feed() else "post"
            snap.author = _first_text(self._d, self._FEED_AUTHOR)
            snap.is_liked = self._is_liked()

        elif screen == SCREEN_REEL_VIEWER:
            snap.content_type = "reel"
            snap.author = _first_text(self._d, self._REEL_AUTHOR)

        elif screen == SCREEN_STORY_VIEWER:
            snap.content_type = "story"
            snap.author = _first_text(self._d, self._STORY_AUTHOR)

        elif screen == SCREEN_PROFILE:
            snap.profile_username = _first_text(self._d, self._PROFILE_USERNAME)

        elif screen == SCREEN_COMMENTS:
            # Comments sheet open over the feed — still capture the underlying post author
            snap.author = _first_text(self._d, self._FEED_AUTHOR)
            snap.is_comments_open = True

        return snap

    def _is_reel_in_feed(self) -> bool:
        for sel in FEED_SELECTORS.reel_indicators:
            if _exists(self._d, sel):
                return True
        return False

    def _is_liked(self) -> bool:
        for sel in self._LIKED:
            if _exists(self._d, sel):
                return True
        return False


# ---------------------------------------------------------------------------
# Detection probe — partial dump when selectors fail
# ---------------------------------------------------------------------------

class DetectionProbe:
    """
    Triggered when the recorder is "stuck" (SCREEN_OTHER or author=None for too long).
    Performs a single throttled `dump_hierarchy()` and extracts visible resource-ids
    and text values so the developer can add the missing selectors afterwards.

    The raw findings are written as a `detection_miss` event in the JSONL file.
    """

    _THROTTLE_S = 10.0   # minimum seconds between two probes

    def __init__(self, device):
        self._d = device
        self._last_probe_ts: float = 0.0

    def maybe_probe(self, screen: str, author: Optional[str], stuck_since: float) -> Optional[dict]:
        """
        Return a dict with findings if a probe fires, otherwise None.

        Fires when:
        - screen == SCREEN_OTHER  (unrecognised screen)
        - OR author is None on a content screen (feed / reel / story) for > 3s
        AND at least _THROTTLE_S seconds since the last probe.
        """
        now = time.monotonic()
        stuck_s = now - stuck_since

        should_probe = (
            screen == SCREEN_OTHER
            or (
                screen in (SCREEN_FEED, SCREEN_REEL_VIEWER, SCREEN_STORY_VIEWER)
                and author is None
                and stuck_s > 3.0
            )
        )
        if not should_probe:
            return None
        if now - self._last_probe_ts < self._THROTTLE_S:
            return None

        self._last_probe_ts = now
        return self._run_probe(screen)

    def _run_probe(self, screen: str) -> dict:
        findings: dict = {"screen_guess": screen, "resource_ids": [], "texts": []}
        try:
            import xml.etree.ElementTree as ET
            xml_str = self._d.dump_hierarchy(compressed=True)
            root = ET.fromstring(xml_str)
            rid_set: set = set()
            text_list: list = []
            for node in root.iter():
                rid = node.attrib.get("resource-id", "")
                if rid and "instagram" in rid:
                    # Keep only the local name (after ":id/")
                    short = rid.split(":id/")[-1] if ":id/" in rid else rid
                    rid_set.add(short)
                txt = node.attrib.get("text", "").strip()
                cd  = node.attrib.get("content-desc", "").strip()
                if txt and len(txt) < 60:
                    text_list.append(txt)
                elif cd and len(cd) < 60:
                    text_list.append(f"[desc]{cd}")
            findings["resource_ids"] = sorted(rid_set)[:40]  # cap to avoid huge events
            findings["texts"] = list(dict.fromkeys(text_list))[:30]
        except Exception as exc:
            findings["probe_error"] = str(exc)
        return findings


# ---------------------------------------------------------------------------
# Main recorder
# ---------------------------------------------------------------------------
class HumanBehaviorRecorder:
    """
    Poll the Instagram UI and emit JSONL events whenever state changes.

    Usage
    -----
    recorder = HumanBehaviorRecorder(device_id="R3CN50BXLPN", output_path="recordings/session.jsonl")
    recorder.connect()
    recorder.run()      # blocks until Ctrl-C
    """

    def __init__(self, device_id: str, output_path: str, poll_interval: float = 0.5):
        self._device_id = device_id
        self._output_path = Path(output_path)
        self._poll_interval = poll_interval

        self._d: Optional[u2.Device] = None
        self._detector: Optional[ScreenDetector] = None
        self._sampler: Optional[ContentSampler] = None
        self._probe: Optional[DetectionProbe] = None
        self._prev: Optional[UISnapshot] = None
        self._content_enter_ts: float = 0.0   # monotonic ts when current content was first seen
        self._author_seen_ts: float = 0.0     # last time author was non-None (for probe trigger)
        self._session_start_ts: float = 0.0

        self._stats: Dict[str, int] = {
            "content_changes": 0,   # scrolls / swipes to new content
            "likes": 0,
            "unlikes": 0,
            "comments_opened": 0,
            "screen_changes": 0,
            "profile_visits": 0,
            "poll_errors": 0,
            "detection_misses": 0,  # times probe fired (= missing selectors)
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self):
        logger.info(f"Connecting to {self._device_id} …")
        self._d = u2.connect(self._device_id)
        info = self._d.info
        logger.success(
            f"Connected: {info.get('productName', '?')}  "
            f"{info.get('displayWidth', '?')}×{info.get('displayHeight', '?')}"
        )
        self._detector = ScreenDetector(self._d)
        self._sampler = ContentSampler(self._d)
        self._probe = DetectionProbe(self._d)

    def run(self):
        """Main recording loop — blocks until Ctrl-C."""
        if self._d is None:
            raise RuntimeError("Call connect() before run()")

        self._session_start_ts = time.monotonic()
        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Recording → {self._output_path}")
        logger.info("Open Instagram and use it normally. Press Ctrl-C to stop.\n")

        with open(self._output_path, "a", encoding="utf-8") as fh:
            self._emit(fh, RecordedEvent(
                ts=_now_iso(),
                event="session_start",
                extra={
                    "device": self._device_id,
                    "poll_interval_ms": int(self._poll_interval * 1000),
                },
            ))
            try:
                while True:
                    self._tick(fh)
                    time.sleep(self._poll_interval)
            except KeyboardInterrupt:
                self._finalize(fh)

    # ------------------------------------------------------------------
    # Core polling tick
    # ------------------------------------------------------------------

    def _tick(self, fh):
        try:
            screen = self._detector.detect()
            snap = self._sampler.sample(screen)
        except Exception as exc:
            self._stats["poll_errors"] += 1
            logger.debug(f"Poll error: {exc}")
            return

        # Update "last time we had a valid author" timestamp
        if snap.author:
            self._author_seen_ts = snap.ts
        stuck_since = self._author_seen_ts or snap.ts

        # DetectionProbe: fire a partial dump when stuck, log findings as detection_miss
        probe_findings = self._probe.maybe_probe(screen, snap.author, stuck_since)
        if probe_findings:
            logger.warning(
                f"Detection miss on screen={screen!r} — triggering partial dump "
                f"(add missing selectors to fix)"
            )
            self._emit(fh, RecordedEvent(
                ts=_now_iso(),
                event="detection_miss",
                screen=screen,
                extra=probe_findings,
            ))
            self._stats["detection_misses"] += 1

        prev = self._prev

        # First tick — just record baseline
        if prev is None:
            self._prev = snap
            self._content_enter_ts = snap.ts
            self._emit(fh, RecordedEvent(
                ts=_now_iso(),
                event="screen_enter",
                screen=screen,
                content_type=snap.content_type,
                author=snap.author,
            ))
            return

        # ── Screen change ───────────────────────────────────────────────
        if snap.screen != prev.screen:
            dwell = int((snap.ts - self._content_enter_ts) * 1000)
            self._emit(fh, RecordedEvent(
                ts=_now_iso(), event="screen_exit",
                screen=prev.screen, dwell_ms=dwell,
            ))
            self._emit(fh, RecordedEvent(
                ts=_now_iso(), event="screen_enter",
                screen=snap.screen,
                content_type=snap.content_type,
                author=snap.author,
            ))
            self._stats["screen_changes"] += 1
            self._content_enter_ts = snap.ts

        # ── Content change (scroll / swipe) ─────────────────────────────
        elif (
            snap.author
            and prev.author
            and snap.author != prev.author
            and snap.screen in (SCREEN_FEED, SCREEN_REEL_VIEWER, SCREEN_STORY_VIEWER)
        ):
            dwell = int((snap.ts - self._content_enter_ts) * 1000)
            self._emit(fh, RecordedEvent(
                ts=_now_iso(), event="content_change",
                screen=snap.screen,
                content_type=snap.content_type,
                author=snap.author,
                dwell_ms=dwell,
                extra={"prev_author": prev.author},
            ))
            self._stats["content_changes"] += 1
            self._content_enter_ts = snap.ts

        # ── Like / unlike ────────────────────────────────────────────────
        if snap.is_liked and not prev.is_liked:
            self._emit(fh, RecordedEvent(
                ts=_now_iso(), event="like",
                screen=snap.screen,
                content_type=snap.content_type,
                author=snap.author,
            ))
            self._stats["likes"] += 1
        elif not snap.is_liked and prev.is_liked:
            self._emit(fh, RecordedEvent(
                ts=_now_iso(), event="unlike",
                screen=snap.screen,
                author=snap.author,
            ))
            self._stats["unlikes"] += 1

        # ── Comments opened ──────────────────────────────────────────────
        if snap.is_comments_open and not prev.is_comments_open:
            self._emit(fh, RecordedEvent(
                ts=_now_iso(), event="comment_open",
                screen=prev.screen,
                author=snap.author or prev.author,
            ))
            self._stats["comments_opened"] += 1

        # ── Profile visit ────────────────────────────────────────────────
        if (
            snap.screen == SCREEN_PROFILE
            and snap.profile_username
            and snap.profile_username != prev.profile_username
        ):
            self._emit(fh, RecordedEvent(
                ts=_now_iso(), event="profile_visit",
                author=snap.profile_username,
            ))
            self._stats["profile_visits"] += 1

        self._prev = snap

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def _finalize(self, fh):
        elapsed = time.monotonic() - self._session_start_ts
        self._emit(fh, RecordedEvent(
            ts=_now_iso(),
            event="session_end",
            extra={"duration_s": round(elapsed, 1), **self._stats},
        ))
        logger.info(f"\n{'─' * 52}")
        logger.info(f"Session ended after {elapsed:.0f}s")
        logger.info(f"  Content changes (scrolls) : {self._stats['content_changes']}")
        logger.info(f"  Likes                     : {self._stats['likes']}")
        logger.info(f"  Unlikes                   : {self._stats['unlikes']}")
        logger.info(f"  Comments opened           : {self._stats['comments_opened']}")
        logger.info(f"  Screen changes            : {self._stats['screen_changes']}")
        logger.info(f"  Profile visits            : {self._stats['profile_visits']}")
        logger.info(f"  Detection misses (add selectors) : {self._stats['detection_misses']}")
        logger.info(f"  Poll errors               : {self._stats['poll_errors']}")
        logger.info(f"  Saved → {self._output_path}")

    # ------------------------------------------------------------------
    # Emit helper
    # ------------------------------------------------------------------

    @staticmethod
    def _emit(fh, event: RecordedEvent):
        line = event.to_jsonl()
        fh.write(line + "\n")
        fh.flush()
        logger.debug(f"  [{event.event:<18}] {line[:120]}")
