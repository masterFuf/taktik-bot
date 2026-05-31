"""
Instagram human behavior recorder.

This runtime tool polls the visible Instagram UI with lightweight XPath checks
and writes behavioral events as JSONL for later analysis.
"""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import uiautomator2 as u2
from loguru import logger

from taktik.core.clone import rid as _rid
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.story_viewer import STORY_SELECTORS

SCREEN_FEED = "feed"
SCREEN_REEL_VIEWER = "reel_viewer"
SCREEN_STORY_VIEWER = "story_viewer"
SCREEN_PROFILE = "profile"
SCREEN_SEARCH = "search"
SCREEN_DM = "dm"
SCREEN_COMMENTS = "comments"
SCREEN_NOTIFICATIONS = "notifications"
SCREEN_OTHER = "other"


@dataclass
class UISnapshot:
    """Minimal snapshot built from fast XPath checks only."""

    ts: float
    screen: str = SCREEN_OTHER
    content_type: str = "unknown"
    author: Optional[str] = None
    is_liked: bool = False
    is_comments_open: bool = False
    profile_username: Optional[str] = None


@dataclass
class RecordedEvent:
    """One JSONL event written by the recorder."""

    ts: str
    event: str
    screen: Optional[str] = None
    content_type: Optional[str] = None
    author: Optional[str] = None
    dwell_ms: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_jsonl(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if v is not None and v != {}}
        return json.dumps(payload, ensure_ascii=False)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _exists(device, selector: str) -> bool:
    try:
        return device.xpath(_rid(selector)).exists
    except Exception:
        return False


def _text(device, selector: str) -> Optional[str]:
    try:
        element = device.xpath(_rid(selector))
        if element.exists:
            return element.get_text() or None
    except Exception:
        pass
    return None


def _first_text(device, selectors: list) -> Optional[str]:
    for selector in selectors:
        value = _text(device, selector)
        if value:
            return value
    return None


class ScreenDetector:
    """Detect the current Instagram screen from a minimal set of selectors."""

    _STORY_PROGRESS = STORY_SELECTORS.story_progress_bar
    _STORY_HEADER = STORY_SELECTORS.story_viewer_header
    _REEL_PLAYER = (
        '//*[@content-desc="Couper le son"]',
        '//*[@content-desc="Activer le son"]',
        '//*[contains(@content-desc, "Turn sound off")]',
        '//*[contains(@content-desc, "Turn sound on")]',
        '//*[@content-desc="Audio"]',
    )
    _FEED = '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]'
    _COMMENTS = (
        '//*[contains(@resource-id, "comments_header")]',
        '//*[contains(@resource-id, "layout_comment_thread")]',
    )
    _DM = (
        DM_SELECTORS.inbox_thread_list,
        DM_SELECTORS.thread_container,
        '//*[@resource-id="com.instagram.android:id/message_list"]',
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
        self._device = device

    def detect(self) -> str:
        if _exists(self._device, self._STORY_PROGRESS) or _exists(self._device, self._STORY_HEADER):
            return SCREEN_STORY_VIEWER
        for selector in self._REEL_PLAYER:
            if _exists(self._device, selector):
                return SCREEN_REEL_VIEWER
        for selector in self._COMMENTS:
            if _exists(self._device, selector):
                return SCREEN_COMMENTS
        if _exists(self._device, self._FEED):
            return SCREEN_FEED
        for selector in self._DM:
            if _exists(self._device, selector):
                return SCREEN_DM
        for selector in self._PROFILE:
            if _exists(self._device, selector):
                return SCREEN_PROFILE
        if _exists(self._device, self._NOTIF):
            return SCREEN_NOTIFICATIONS
        for selector in self._SEARCH:
            if _exists(self._device, selector):
                return SCREEN_SEARCH
        return SCREEN_OTHER


class ContentSampler:
    """Extract author and lightweight state for the current Instagram surface."""

    _FEED_AUTHOR = [
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_username"]',
    ]
    _REEL_AUTHOR = [
        '//*[@resource-id="com.instagram.android:id/clips_author_info"]//android.widget.TextView',
        '//*[@resource-id="com.instagram.android:id/clips_author_username"]',
        '//*[@resource-id="com.instagram.android:id/username"]',
        '//android.widget.TextView[starts-with(@text, "@")]',
        '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
    ]
    _STORY_AUTHOR = [
        STORY_SELECTORS.story_viewer_title,
        '//*[contains(@resource-id, "reel_viewer_title")]',
        '//*[contains(@resource-id, "story_username")]',
        '//*[contains(@resource-id, "reel_viewer_username")]',
        '//*[contains(@resource-id, "username")]',
    ]
    _PROFILE_USERNAME = [
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
        '//*[contains(@resource-id, "username")]',
    ]
    _LIKED = FEED_SELECTORS.already_liked_indicators[:3]

    def __init__(self, device):
        self._device = device

    def sample(self, screen: str) -> UISnapshot:
        snapshot = UISnapshot(ts=time.monotonic(), screen=screen)

        if screen == SCREEN_FEED:
            snapshot.content_type = "reel" if self._is_reel_in_feed() else "post"
            snapshot.author = _first_text(self._device, self._FEED_AUTHOR)
            snapshot.is_liked = self._is_liked()
        elif screen == SCREEN_REEL_VIEWER:
            snapshot.content_type = "reel"
            snapshot.author = _first_text(self._device, self._REEL_AUTHOR)
        elif screen == SCREEN_STORY_VIEWER:
            snapshot.content_type = "story"
            snapshot.author = _first_text(self._device, self._STORY_AUTHOR)
        elif screen == SCREEN_PROFILE:
            snapshot.profile_username = _first_text(self._device, self._PROFILE_USERNAME)
        elif screen == SCREEN_COMMENTS:
            snapshot.author = _first_text(self._device, self._FEED_AUTHOR)
            snapshot.is_comments_open = True

        return snapshot

    def _is_reel_in_feed(self) -> bool:
        for selector in FEED_SELECTORS.reel_indicators:
            if _exists(self._device, selector):
                return True
        return False

    def _is_liked(self) -> bool:
        for selector in self._LIKED:
            if _exists(self._device, selector):
                return True
        return False


class DetectionProbe:
    """Capture a partial hierarchy dump when selectors cannot classify the UI."""

    _THROTTLE_S = 10.0

    def __init__(self, device):
        self._device = device
        self._last_probe_ts = 0.0

    def maybe_probe(self, screen: str, author: Optional[str], stuck_since: float) -> Optional[dict]:
        now = time.monotonic()
        stuck_s = now - stuck_since
        should_probe = screen == SCREEN_OTHER or (
            screen in (SCREEN_FEED, SCREEN_REEL_VIEWER, SCREEN_STORY_VIEWER)
            and author is None
            and stuck_s > 3.0
        )
        if not should_probe or now - self._last_probe_ts < self._THROTTLE_S:
            return None

        self._last_probe_ts = now
        return self._run_probe(screen)

    def _run_probe(self, screen: str) -> dict:
        findings = {"screen_guess": screen, "resource_ids": [], "texts": []}
        try:
            import xml.etree.ElementTree as ET

            xml_str = self._device.dump_hierarchy(compressed=True)
            root = ET.fromstring(xml_str)
            resource_ids = set()
            texts = []
            for node in root.iter():
                resource_id = node.attrib.get("resource-id", "")
                if resource_id and "instagram" in resource_id:
                    short = resource_id.split(":id/")[-1] if ":id/" in resource_id else resource_id
                    resource_ids.add(short)
                text = node.attrib.get("text", "").strip()
                content_desc = node.attrib.get("content-desc", "").strip()
                if text and len(text) < 60:
                    texts.append(text)
                elif content_desc and len(content_desc) < 60:
                    texts.append(f"[desc]{content_desc}")
            findings["resource_ids"] = sorted(resource_ids)[:40]
            findings["texts"] = list(dict.fromkeys(texts))[:30]
        except Exception as exc:
            findings["probe_error"] = str(exc)
        return findings


class HumanBehaviorRecorder:
    """Poll the Instagram UI and write JSONL events whenever state changes."""

    def __init__(self, device_id: str, output_path: str, poll_interval: float = 0.5):
        self._device_id = device_id
        self._output_path = Path(output_path)
        self._poll_interval = poll_interval

        self._device: Optional[u2.Device] = None
        self._detector: Optional[ScreenDetector] = None
        self._sampler: Optional[ContentSampler] = None
        self._probe: Optional[DetectionProbe] = None
        self._prev: Optional[UISnapshot] = None
        self._content_enter_ts = 0.0
        self._author_seen_ts = 0.0
        self._session_start_ts = 0.0

        self._stats: Dict[str, int] = {
            "content_changes": 0,
            "likes": 0,
            "unlikes": 0,
            "comments_opened": 0,
            "screen_changes": 0,
            "profile_visits": 0,
            "poll_errors": 0,
            "detection_misses": 0,
        }

    def connect(self):
        logger.info(f"Connecting to {self._device_id}...")
        self._device = u2.connect(self._device_id)
        info = self._device.info
        logger.success(
            f"Connected: {info.get('productName', '?')} "
            f"{info.get('displayWidth', '?')}x{info.get('displayHeight', '?')}"
        )
        self._detector = ScreenDetector(self._device)
        self._sampler = ContentSampler(self._device)
        self._probe = DetectionProbe(self._device)

    def run(self):
        if self._device is None:
            raise RuntimeError("Call connect() before run()")

        self._session_start_ts = time.monotonic()
        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Recording -> {self._output_path}")
        logger.info("Open Instagram and use it normally. Press Ctrl-C to stop.\n")

        with open(self._output_path, "a", encoding="utf-8") as handle:
            self._emit(
                handle,
                RecordedEvent(
                    ts=_now_iso(),
                    event="session_start",
                    extra={"device": self._device_id, "poll_interval_ms": int(self._poll_interval * 1000)},
                ),
            )
            try:
                while True:
                    self._tick(handle)
                    time.sleep(self._poll_interval)
            except KeyboardInterrupt:
                self._finalize(handle)

    def _tick(self, handle):
        try:
            screen = self._detector.detect()
            snapshot = self._sampler.sample(screen)
        except Exception as exc:
            self._stats["poll_errors"] += 1
            logger.debug(f"Poll error: {exc}")
            return

        if snapshot.author:
            self._author_seen_ts = snapshot.ts
        stuck_since = self._author_seen_ts or snapshot.ts

        probe_findings = self._probe.maybe_probe(screen, snapshot.author, stuck_since)
        if probe_findings:
            logger.warning(
                f"Detection miss on screen={screen!r} - triggering partial dump (add missing selectors to fix)"
            )
            self._emit(
                handle,
                RecordedEvent(ts=_now_iso(), event="detection_miss", screen=screen, extra=probe_findings),
            )
            self._stats["detection_misses"] += 1

        previous = self._prev
        if previous is None:
            self._prev = snapshot
            self._content_enter_ts = snapshot.ts
            self._emit(
                handle,
                RecordedEvent(
                    ts=_now_iso(),
                    event="screen_enter",
                    screen=screen,
                    content_type=snapshot.content_type,
                    author=snapshot.author,
                ),
            )
            return

        if snapshot.screen != previous.screen:
            dwell = int((snapshot.ts - self._content_enter_ts) * 1000)
            self._emit(handle, RecordedEvent(ts=_now_iso(), event="screen_exit", screen=previous.screen, dwell_ms=dwell))
            self._emit(
                handle,
                RecordedEvent(
                    ts=_now_iso(),
                    event="screen_enter",
                    screen=snapshot.screen,
                    content_type=snapshot.content_type,
                    author=snapshot.author,
                ),
            )
            self._stats["screen_changes"] += 1
            self._content_enter_ts = snapshot.ts
        elif (
            snapshot.author
            and previous.author
            and snapshot.author != previous.author
            and snapshot.screen in (SCREEN_FEED, SCREEN_REEL_VIEWER, SCREEN_STORY_VIEWER)
        ):
            dwell = int((snapshot.ts - self._content_enter_ts) * 1000)
            self._emit(
                handle,
                RecordedEvent(
                    ts=_now_iso(),
                    event="content_change",
                    screen=snapshot.screen,
                    content_type=snapshot.content_type,
                    author=snapshot.author,
                    dwell_ms=dwell,
                    extra={"prev_author": previous.author},
                ),
            )
            self._stats["content_changes"] += 1
            self._content_enter_ts = snapshot.ts

        if snapshot.is_liked and not previous.is_liked:
            self._emit(
                handle,
                RecordedEvent(
                    ts=_now_iso(),
                    event="like",
                    screen=snapshot.screen,
                    content_type=snapshot.content_type,
                    author=snapshot.author,
                ),
            )
            self._stats["likes"] += 1
        elif not snapshot.is_liked and previous.is_liked:
            self._emit(handle, RecordedEvent(ts=_now_iso(), event="unlike", screen=snapshot.screen, author=snapshot.author))
            self._stats["unlikes"] += 1

        if snapshot.is_comments_open and not previous.is_comments_open:
            self._emit(
                handle,
                RecordedEvent(ts=_now_iso(), event="comment_open", screen=previous.screen, author=snapshot.author or previous.author),
            )
            self._stats["comments_opened"] += 1

        if snapshot.screen == SCREEN_PROFILE and snapshot.profile_username and snapshot.profile_username != previous.profile_username:
            self._emit(handle, RecordedEvent(ts=_now_iso(), event="profile_visit", author=snapshot.profile_username))
            self._stats["profile_visits"] += 1

        self._prev = snapshot

    def _finalize(self, handle):
        elapsed = time.monotonic() - self._session_start_ts
        self._emit(
            handle,
            RecordedEvent(
                ts=_now_iso(),
                event="session_end",
                extra={"duration_s": round(elapsed, 1), **self._stats},
            ),
        )
        logger.info(f"\n{'-' * 52}")
        logger.info(f"Session ended after {elapsed:.0f}s")
        logger.info(f"  Content changes (scrolls) : {self._stats['content_changes']}")
        logger.info(f"  Likes                     : {self._stats['likes']}")
        logger.info(f"  Unlikes                   : {self._stats['unlikes']}")
        logger.info(f"  Comments opened           : {self._stats['comments_opened']}")
        logger.info(f"  Screen changes            : {self._stats['screen_changes']}")
        logger.info(f"  Profile visits            : {self._stats['profile_visits']}")
        logger.info(f"  Detection misses          : {self._stats['detection_misses']}")
        logger.info(f"  Poll errors               : {self._stats['poll_errors']}")
        logger.info(f"  Saved -> {self._output_path}")

    @staticmethod
    def _emit(handle, event: RecordedEvent):
        line = event.to_jsonl()
        handle.write(line + "\n")
        handle.flush()
        logger.debug(f"  [{event.event:<18}] {line[:120]}")
