"""Instagram notifications engagement workflow.

Drives the modern "Notifications" surface as an ENGAGEMENT flow (replacing the
legacy NotificationsBusiness "treat-notifications-as-a-profile-source" automation):

    scan()              read + classify the activity feed (all families)
    list_requests()     enumerate pending follow requests (sub-screen)
    accept_request()    confirm one follow request by username
    ignore_request()    delete one follow request by username
    accept_all_requests()  confirm pending requests in batch
    open_mention()      open the reply UI on a comment-mention row

Every UI signature comes from the centralized ``NOTIFICATION_SELECTORS`` catalog
(language-neutral resource-ids + FR/EN locale overlay); no selector literal lives
here (AGENTS invariant). Rows are matched in a raw XML dump by SUBSTRING of the
bare resource-id (IG renders feed rows bare, follow-requests qualified — a bare
substring matches both). Text classification is delegated to ``classifier``; XML
extraction to ``dump_parsing``; per-row geometry to ``row_layout``.

Live step narration is emitted through an OPTIONAL injected ``notifier`` callback
(Dependency Inversion: this core workflow never imports the bridge layer); it is a
no-op when run standalone.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from lxml import etree

from taktik.core.shared.behavior.gesture import sample_swipe
from taktik.core.shared.input.taktik_keyboard import type_text_human
from taktik.core.shared.vision import locate_text_on_screen

from ....ui.language import detect_and_optimize
from ....ui.selectors.surfaces.notifications import NOTIFICATION_SELECTORS
from ....ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS
from .classifier import clean_label, longest_clean_run
from .dump_parsing import (
    concat_text,
    find_inline_like_target,
    find_row_reply_target,
    find_truncated_targets,
    node_bounds_deep,
    node_text_deep,
    parse_feed_rows,
    parse_request_rows,
    parse_section_headers,
)

# Families whose row text carries USER-written content that may contain emojis the XML
# dump corrupts (so we re-read them via the element API to recover the real text).
_EMOJI_TEXT_TYPES = {"comment_mention", "post_comment", "comment_reply", "comment_like"}
from .row_layout import parse_bounds
from taktik.core.shared.behavior.tap import (
    tap_element_human,
    sample_tap_point,
    sample_tap_down_ms,
)

StepNotifier = Callable[..., None]


class NotificationsEngagementWorkflow:
    """Engagement workflow over the Instagram notifications/activity surface."""

    def __init__(self, device, device_id: str, notifier: Optional[StepNotifier] = None,
                 relauncher: Optional[Callable[[], None]] = None):
        self.device = device
        self.device_id = device_id
        self._notify_cb = notifier
        # Optional callback that restarts Instagram to a clean home state. Injected
        # by the bridge so a per-row action can SELF-HEAL when Instagram has drifted
        # to another screen (or was closed) since the scan — the action re-navigates
        # from scratch instead of being "lost". DIP: the core never imports the bridge.
        self._relauncher = relauncher
        self.logger = logger.bind(module="instagram-notifications")
        self.selectors = NOTIFICATION_SELECTORS
        # Comment-thread surface (click-in lands on the standard comments composer):
        # reused as-is so the notifications reply carries zero hardcoded selector.
        self.comment_selectors = POST_COMMENTS_SELECTORS
        self._locale_ready = False

    # ------------------------------------------------------------------
    # Language detection (same service as the other workflows)
    # ------------------------------------------------------------------
    def _optimize_locale(self) -> None:
        """Detect the app language and filter selectors to it (once per run).

        Mirrors every other Instagram workflow (runtime_setup / change_language):
        the notifications/activity surface mixes language-neutral resource-ids with
        a few TEXT-only signatures (e.g. the grouped follow-requests digest, which
        has no resource-id). Aligning the active locale to the device makes those
        text selectors resolve in the right language. Best-effort / non-fatal.
        """
        if self._locale_ready:
            return
        self._locale_ready = True
        try:
            lang = detect_and_optimize(self.device)
            self.logger.info(f"App language detected: {lang}")
        except Exception as exc:  # never block the flow on detection
            self.logger.warning(f"Language detection failed (non-fatal): {exc}")

    # ------------------------------------------------------------------
    # Step narration (no-op when no notifier is injected)
    # ------------------------------------------------------------------
    def _notify(self, step: str, status: str, message: str = "", **extra: Any) -> None:
        if self._notify_cb is None:
            return
        try:
            self._notify_cb(step=step, status=status, message=message, **extra)
        except Exception as exc:  # narration must never break the flow
            self.logger.debug(f"step notifier failed: {exc}")

    # ------------------------------------------------------------------
    # Low-level UI helpers
    # ------------------------------------------------------------------
    def _find_element(self, selectors: List[str]):
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element
            except Exception:
                continue
        return None

    def _element_exists(self, selectors: List[str]) -> bool:
        return self._find_element(selectors) is not None

    def _click_first_match(self, selectors: List[str], name: str) -> bool:
        element = self._find_element(selectors)
        if element is None:
            return False
        try:
            if not tap_element_human(self.device, element):
                element.click()
            self.logger.success(f"Clicked '{name}'")
            return True
        except Exception as exc:
            self.logger.error(f"Click on '{name}' failed: {exc}")
            return False

    def _all_matches(self, selectors: List[str]) -> list:
        """uiautomator2 elements for the FIRST selector that yields any match."""
        for selector in selectors:
            try:
                matches = self.device.xpath(selector).all()
            except Exception:
                continue
            if matches:
                return matches
        return []

    def _human_scroll(self, direction: str = "up") -> bool:
        """One humanized scroll using the shared calibration engine (real swipe
        trajectories via ``sample_swipe`` + ``swipe_points``), not a fixed straight
        swipe. Falls back to a plain swipe along the sampled endpoints, then to a
        centred straight swipe."""
        try:
            width, height = self.device.window_size()
        except Exception:
            width, height = 1080, 2220
        try:
            path, duration = sample_swipe(int(width), int(height), direction=direction)
        except Exception as exc:
            self.logger.debug(f"sample_swipe failed: {exc}")
            path, duration = None, 0.4
        if path:
            raw = getattr(self.device, "_device", None) or self.device
            try:
                if hasattr(raw, "swipe_points"):
                    raw.swipe_points(path, duration / max(1, len(path) - 1))
                    return True
                self.device.swipe(path[0][0], path[0][1], path[-1][0], path[-1][1], duration=duration)
                return True
            except Exception as exc:
                self.logger.debug(f"human swipe exec failed: {exc}")
        try:
            x = int(width) // 2
            self.device.swipe(x, int(height * 0.72), x, int(height * 0.32), duration=0.4)
            return True
        except Exception as exc:
            self.logger.warning(f"Swipe failed: {exc}")
            return False

    def _scroll_down(self, times: int = 1) -> None:
        for _ in range(times):
            if not self._human_scroll("up"):
                break
            time.sleep(0.7)

    def _tap_show_more(self) -> bool:
        """Tap the 'Show more' / 'Voir plus' button to load older notifications.

        The button's text node is not clickable itself, but tapping its bounds
        center lands on the clickable parent. Returns False when absent.
        """
        element = self._find_element(self.selectors.show_more_button)
        if element is None:
            return False
        try:
            if not tap_element_human(self.device, element):
                element.click()
            self.logger.info("Tapped 'Show more'")
            self._notify("show_more", "running", "Loading older notifications")
            return True
        except Exception as exc:
            self.logger.debug(f"Show more tap failed: {exc}")
            return False

    def _dump_root(self):
        """Full (uncompressed) hierarchy dump parsed to an lxml root, or None."""
        xml = None
        try:
            xml = self.device.dump_hierarchy(compressed=False)
        except TypeError:
            try:
                xml = self.device.dump_hierarchy()
            except Exception as exc:
                self.logger.error(f"dump_hierarchy failed: {exc}")
        except Exception as exc:
            self.logger.error(f"dump_hierarchy failed: {exc}")
        if not xml:
            return None
        try:
            return etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
        except Exception as exc:
            self.logger.error(f"XML parse failed: {exc}")
            return None

    def _tap_point(self, point: Optional[tuple], name: str) -> bool:
        if not point:
            self.logger.warning(f"{name}: no tap point")
            return False
        try:
            # The parser keeps only the affordance CENTRE (center(box)), not the box, so sample a
            # human point within a small box AROUND the centre + a varied finger-down time —
            # removes the "exact same pixel + instant click" fingerprint without needing the bounds.
            x0, y0 = int(point[0]), int(point[1])
            r = 18
            x, y = sample_tap_point((x0 - r, y0 - r, x0 + r, y0 + r))
            try:
                self.device.long_click(x, y, sample_tap_down_ms() / 1000.0)
            except Exception:
                self.device.click(x, y)
            self.logger.success(f"{name}: tapped @ ({x}, {y})")
            return True
        except Exception as exc:
            self.logger.error(f"{name}: tap failed: {exc}")
            return False

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _on_notifications_screen(self) -> bool:
        return self._element_exists(self.selectors.notifications_screen_indicators)

    def _on_follow_requests_screen(self) -> bool:
        if self._element_exists(self.selectors.follow_requests_screen_indicators):
            return True
        root = self._dump_root()
        return root is not None and len(self._parse_requests(root)) > 0

    def _tap_activity_and_check(self) -> bool:
        if not self._click_first_match(self.selectors.activity_entry, "Activity entry"):
            return False
        time.sleep(1.5)
        return self._on_notifications_screen()

    def ensure_notifications_screen(self) -> bool:
        """Open the notifications screen (tap the activity/heart entry) if needed.

        Self-healing: if the activity entry is not reachable from the current screen
        (Instagram drifted elsewhere or was closed since the scan), restart Instagram
        to a clean home state via the injected relauncher and retry — so a per-row
        action triggered later still works without being "lost"."""
        if self._on_notifications_screen():
            return True
        self._notify("open_notifications", "running", "Opening notifications")
        if self._tap_activity_and_check():
            self._notify("open_notifications", "done")
            return True
        if self._relauncher is not None:
            self.logger.info("Activity entry unreachable — relaunching Instagram to recover")
            try:
                self._relauncher()
            except Exception as exc:
                self.logger.warning(f"relauncher failed: {exc}")
            time.sleep(2.0)
            self._locale_ready = False  # re-detect language on the fresh home screen
            self._optimize_locale()
            if self._tap_activity_and_check():
                self._notify("open_notifications", "done")
                return True
        self._notify("open_notifications", "failed", "Activity entry not found")
        return False

    def _open_grouped_requests(self) -> bool:
        """Open the follow-requests sub-screen by tapping the grouped digest row.

        Tapping the row CENTER lands on the text and often does not trigger
        navigation (confirmed flaky even by hand); the profile-picture cluster on
        the LEFT is the reliable hit target. We locate the digest story row in the
        dump (text matches the localized header) and tap its left avatar zone.
        Falls back to the plain element click if the row bounds are unavailable.
        """
        root = self._dump_root()
        if root is not None:
            frags = [f.lower() for f in self.selectors.follow_requests_header_text]
            row_id = self.selectors.notification_row_resource_id
            for node in root.iter("node"):
                if row_id not in (node.get("resource-id") or ""):
                    continue
                if not any(f in concat_text(node).lower() for f in frags):
                    continue
                box = parse_bounds(node.get("bounds", ""))
                if box:
                    x1, y1, x2, y2 = box
                    x = x1 + max(70, int((x2 - x1) * 0.08))  # left avatar cluster
                    y = (y1 + y2) // 2
                    return self._tap_point((x, y), "Follow requests (avatars)")
        # Fallback: whole-row element click.
        return self._click_first_match(self.selectors.follow_requests_header, "Follow requests header")

    def _return_to_notifications(self, attempts: int = 3) -> bool:
        """Back out of the follow-requests sub-screen to the notifications feed."""
        for _ in range(attempts):
            if self._on_notifications_screen():
                return True
            try:
                self.device.press("back")
            except Exception:
                pass
            time.sleep(1.0)
        return self._on_notifications_screen()

    def ensure_follow_requests_screen(self, load_timeout_s: float = 10.0) -> bool:
        """Open the follow-requests sub-screen from the notifications screen.

        The sub-screen loads its rows over the network, so after tapping the
        grouped header we POLL until the request rows actually appear (up to
        ``load_timeout_s``) instead of giving up after a fixed sleep — a 1.5s wait
        landed on the empty transition screen and reported "no pending request".
        """
        if self._on_follow_requests_screen():
            return True
        if not self.ensure_notifications_screen():
            return False
        self._optimize_locale()  # the grouped header is text-only -> needs the right locale
        self._notify("open_requests", "running", "Opening follow requests")
        if not self._open_grouped_requests():
            self._notify("open_requests", "failed", "Follow requests section not found")
            return False
        deadline = load_timeout_s
        waited = 0.0
        while waited < deadline:
            time.sleep(1.0)
            waited += 1.0
            if self._on_follow_requests_screen():
                self._notify("open_requests", "done", "Follow requests opened")
                return True
        self._notify("open_requests", "failed", "Follow requests screen did not load")
        return False

    # ------------------------------------------------------------------
    # Read pass — classify the activity feed (all families)
    # ------------------------------------------------------------------
    def _rows_on_screen(self) -> List[Dict[str, Any]]:
        rows, _ = self._dump_screen()
        return rows

    def _dump_screen(self) -> tuple:
        """One dump -> (classified feed rows, visible time-section header texts)."""
        root = self._dump_root()
        if root is None:
            return [], []
        rows = parse_feed_rows(root, self.selectors.notification_row_resource_id,
                               self.selectors.classifier_fragments)
        headers = parse_section_headers(root, self.selectors.notification_section_header_resource_id)
        return rows, headers

    def _resolve_emoji_text(self, parsed_text: str) -> Optional[str]:
        """Re-read a comment row's REAL text via uiautomator2's element API to recover
        emojis the XML dump corrupted into "."/"…" placeholders.

        The XML hierarchy dump mangles supplementary-plane emojis; ``UiObject.get_text()``
        (JSON-RPC) does not. We anchor on the longest clean run of the parsed text
        (``textContains``) to find the on-screen node, then return its real text. Returns
        None (caller keeps the dump text) if there's no usable anchor, the node isn't
        found, or the re-read doesn't actually contain the anchor (wrong node guard).
        """
        anchor = longest_clean_run(parsed_text)
        if not anchor:
            return None
        raw = getattr(self.device, "_device", None) or self.device
        try:
            element = raw(textContains=anchor)
            if not element.exists(timeout=0.4):
                return None
            real = (element.get_text() or "").strip()
        except Exception as exc:
            self.logger.debug(f"emoji re-read failed: {exc}")
            return None
        # Guard against a wrong-node match; only use a re-read that is actually richer.
        if real and anchor in real and real != parsed_text:
            return real
        return None

    def _expand_one_more(self) -> bool:
        """Expand ONE not-yet-tried truncated row (reveal its full comment/mention text).

        The "… more" / "… suite" expander is a ClickableSpan with NO accessibility node,
        so its position cannot come from the dump. We take the row's REAL text-node bounds
        (from the dump) as an OCR region and let OCR find the word's true on-screen
        position, then tap it. Returns True if a row was tried (caller re-reads). Each row
        is tried once (tracked by its truncated text) so a miss never loops; if the tap
        misses and opens the post, we recover (back to the feed). No-op (returns False)
        when OCR is unavailable — the scan keeps the truncated text.
        """
        root = self._dump_root()
        if root is None:
            return False
        for target in find_truncated_targets(root, self.selectors.notification_row_resource_id):
            if target["key"] in self._expanded_keys:
                continue
            self._expanded_keys.add(target["key"])
            matches = locate_text_on_screen(
                self.device, self.selectors.expander_words, region=target["region"],
            )
            if not matches:
                return True  # tried this row (no OCR hit / OCR unavailable); move on
            self._notify("expand", "running", "Expanding a comment")
            # Lowest match = the expander sits on the last line of the truncated text.
            point = max(matches, key=lambda m: m.top).center
            self._tap_point(point, "expand more (ocr)")
            time.sleep(0.7)
            if not self._on_notifications_screen():
                self.logger.info("expand more: tap opened the post, recovering")
                self._return_to_notifications()
            return True
        return False

    def _parse_requests(self, root) -> List[Dict[str, Any]]:
        return parse_request_rows(
            root,
            self.selectors.follow_request_username_resource_id,
            self.selectors.follow_request_accept_resource_id,
            self.selectors.follow_request_ignore_resource_id,
        )

    def _request_rows(self) -> List[Dict[str, Any]]:
        root = self._dump_root()
        if root is None:
            return []
        return self._parse_requests(root)

    def scan(self, max_scrolls: int = 3) -> Dict[str, Any]:
        """Read + classify the activity feed across a few screens (all families),
        AND navigate into the follow-requests sub-screen to enumerate the pending
        requests in the same pass (so the page gets the actionable list directly).

        Returns ``{success, count, by_type, items, requests, has_grouped_requests}``.
        Items are de-duplicated by text, top-to-bottom; the grouped "follow requests"
        digest row is dropped from ``items`` since it is surfaced via ``requests``.
        """
        # Detect the app language on the HOME feed FIRST (Instagram just launched):
        # the bottom nav carries strong EN/FR content-desc signal there (Home/Profile/
        # Search vs Accueil/Profil/Rechercher), whereas the notifications screen has
        # almost none and ties FR=EN -> 'unknown'. Detecting before navigating gives a
        # confident locale (L() then resolves the right language for the text-only
        # follow-requests header).
        time.sleep(1.5)  # let the home feed render before detection
        self._optimize_locale()

        if not self.ensure_notifications_screen():
            return {"success": False, "count": 0, "by_type": {}, "items": [], "requests": [],
                    "has_grouped_requests": False, "message": "Notifications screen not reachable"}

        self._notify("scan", "running", "Reading notifications")
        time.sleep(1.0)  # let the feed settle before the first dump
        has_grouped = self._element_exists(self.selectors.follow_requests_header)

        # Collect follow requests FIRST, while the grouped header is still at the TOP
        # of the feed. Scrolling the feed for activity (below) would push the header
        # off-screen and the tap into the sub-screen would miss it.
        requests: List[Dict[str, str]] = []
        if has_grouped:
            requests = self._collect_requests(max_requests=50)
            self._return_to_notifications()

        # Scroll the activity feed and classify it. When a screen reveals nothing new,
        # tap "Show more" to load older notifications THEN scroll to reveal them; stop
        # after two consecutive empty rounds (reached the bottom).
        items: List[Dict[str, Any]] = []
        seen: set = set()
        seen_sections: set = set()
        self._expanded_keys: set = set()
        stale = 0
        iteration_cap = max(max_scrolls + 1, 12)
        for index in range(iteration_cap):
            rows, headers = self._dump_screen()
            if not rows and not items and index == 0:
                time.sleep(1.2)  # feed may still be rendering
                rows, headers = self._dump_screen()
            # Reveal truncated comment/mention text in view ("… more" / "… suite") via OCR,
            # then re-read so the FULL text is captured. Bounded + best-effort.
            expanded_any = False
            for _ in range(4):
                if not self._expand_one_more():
                    break
                expanded_any = True
                time.sleep(0.4)
            if expanded_any:
                rows, headers = self._dump_screen()
            # Narrate each newly-revealed time bucket ("Today", "Yesterday", "Last 7
            # days"…) as the scroll uncovers it (Taktik Agent live card).
            for header in headers:
                if header not in seen_sections:
                    seen_sections.add(header)
                    self._notify("section", "running", header, section=header)
            new_count = 0
            for row in rows:
                key = row["text"].lower()
                if key in seen:
                    continue
                seen.add(key)
                # Recover emojis the XML dump corrupted: re-read comment rows via the
                # element API (preserves emojis) while the row is still on screen.
                if row["type"] in _EMOJI_TEXT_TYPES:
                    real = self._resolve_emoji_text(row["text"])
                    if real:
                        row["text"] = real[:200]
                        row["label"] = clean_label(real)
                items.append(row)
                new_count += 1
            if new_count:
                stale = 0
                self._scroll_down(1)
            elif self._tap_show_more():
                time.sleep(1.5)       # let older notifications load
                self._scroll_down(1)  # reveal the freshly-loaded rows
                stale = 0
            else:
                stale += 1
                if stale >= 2:
                    break  # nothing new + no "Show more" twice -> reached the bottom
                self._scroll_down(1)

        # Drop the grouped "follow requests" digest row from the feed: it is not a
        # real activity item, it is the entry to the requests sub-screen (surfaced
        # via `requests`). Heuristic, locale-aware (matches the header fragments).
        header_frags = [f.lower() for f in self.selectors.follow_requests_header_text]
        items = [it for it in items
                 if not (it["type"] in ("follow_request", "other")
                         and any(f in it["text"].lower() for f in header_frags))]

        by_type: Dict[str, int] = {}
        for item in items:
            by_type[item["type"]] = by_type.get(item["type"], 0) + 1
        summary = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())) or "none"
        msg = f"{len(items)} notifications [{summary}], {len(requests)} request(s)"
        self.logger.info(f"scan: {msg}")
        self._notify("scan", "done", msg)
        return {"success": True, "count": len(items), "by_type": by_type, "items": items,
                "requests": requests, "has_grouped_requests": has_grouped, "message": msg}

    # ------------------------------------------------------------------
    # Follow requests — sub-screen, row-scoped
    # ------------------------------------------------------------------
    def _collect_requests(self, max_requests: int = 50) -> List[Dict[str, str]]:
        """Open the follow-requests sub-screen and enumerate pending usernames.

        Returns ``[]`` if the sub-screen is unreachable. Scrolls (bounded) to gather
        requests beyond the first screen.
        """
        if not self.ensure_follow_requests_screen():
            return []
        # The request rows render progressively over the network and usually all fit
        # on one screen ABOVE the "Suggested for you" header. So we RE-PARSE with a
        # short settle between rounds to catch late-rendering rows, scroll only while
        # the bottom marker is not yet visible, and stop once it is (everything below
        # is recommendations, not requests).
        seen: set = set()
        requests: List[Dict[str, str]] = []
        stale = 0
        for _ in range(20):
            added = False
            for row in self._request_rows():
                name = row["username"]
                if name in seen:
                    continue
                seen.add(name)
                requests.append({"username": name})
                added = True
                if len(requests) >= max_requests:
                    break
            if len(requests) >= max_requests:
                break
            stale = 0 if added else stale + 1
            at_bottom = self._element_exists(self.selectors.suggested_for_you)
            # Done once we HAVE requests, the bottom marker is visible, and TWO
            # consecutive re-parses added nothing. We require two (not one) empty rounds
            # because rows render progressively and a slow one (e.g. a verified account
            # whose badge loads late) can be absent on a single re-parse — breaking on
            # the first empty round dropped the top request. We never break on at_bottom
            # while requests is still empty (the "Suggested for you" header is on screen
            # from the start, all requests fitting above it).
            if at_bottom and requests and stale >= 2:
                break
            if not requests and stale >= 6:
                break  # nothing ever rendered after patient retries -> give up
            if not at_bottom:
                self._scroll_down(1)  # reveal more requests (never past the bottom marker)
            time.sleep(0.9)  # let progressively-loading rows render

        # Always log the parse breakdown: lets us see, from a normal run's logs,
        # whether a missing request is a render-timing issue or the username node
        # lacking self/descendant text or bounds (no extra device dump needed).
        root = self._dump_root()
        if root is not None:
            uid = self.selectors.follow_request_username_resource_id
            unodes = [n for n in root.iter("node") if uid in (n.get("resource-id") or "")]
            self_text = sum(1 for n in unodes if (n.get("text") or "").strip())
            deep_text = sum(1 for n in unodes if node_text_deep(n))
            deep_bounds = sum(1 for n in unodes if node_bounds_deep(n))
            acc = sum(1 for n in root.iter("node")
                      if self.selectors.follow_request_accept_resource_id in (n.get("resource-id") or ""))
            self.logger.info(
                f"requests parse: {len(requests)} collected | dump now: {len(unodes)} username "
                f"[{self_text} self-text, {deep_text} deep-text, {deep_bounds} bounds], {acc} accept")
        return requests

    def list_requests(self, max_requests: int = 50) -> Dict[str, Any]:
        """Enumerate pending follow requests (usernames) on the sub-screen."""
        requests = self._collect_requests(max_requests)
        msg = f"{len(requests)} pending follow request(s)"
        self.logger.info(f"list_requests: {msg}")
        return {"success": True, "count": len(requests), "requests": requests, "message": msg}

    def _wait_for_request_rows(self, timeout_s: float = 6.0) -> List[Dict[str, Any]]:
        """Poll the sub-screen until the request rows have rendered (or timeout).

        The rows load progressively after navigating in, so an action that parses
        once immediately finds nothing — every action (accept/ignore/accept_all)
        must wait for them, exactly like the scan's collect loop does."""
        rows = self._request_rows()
        waited = 0.0
        while not rows and waited < timeout_s:
            time.sleep(0.9)
            waited += 0.9
            rows = self._request_rows()
        return rows

    def _act_on_request(self, username: str, action: str) -> Dict[str, Any]:
        """Confirm or delete the follow request of ``username`` (sub-screen)."""
        result = {"success": False, "username": username, "action": action, "message": ""}
        if not self.ensure_follow_requests_screen():
            result["message"] = "Follow requests screen not reachable"
            return result

        # Wait for rows to render, then scroll if the username is off-screen.
        target = None
        for _ in range(8):
            rows = self._wait_for_request_rows()
            target = next((r for r in rows if r["username"] == username), None)
            if target or not rows:
                break
            self._scroll_down(1)
        if not target:
            result["message"] = f"Request not found: {username}"
            self._notify(action, "failed", result["message"], username=username)
            return result

        point = target["accept"] if action == "accept" else target["ignore"]
        self._notify(action, "running", username, username=username)
        if not self._tap_point(point, f"{action} {username}"):
            result["message"] = f"Could not tap {action} for {username}"
            self._notify(action, "failed", result["message"], username=username)
            return result
        time.sleep(1.0)
        result["success"] = True
        result["message"] = f"{action} {username}"
        self._notify(action, "done", result["message"], username=username)
        return result

    def accept_request(self, username: str) -> Dict[str, Any]:
        return self._act_on_request(username, "accept")

    def ignore_request(self, username: str) -> Dict[str, Any]:
        return self._act_on_request(username, "ignore")

    def accept_all_requests(self, max_requests: int = 50,
                            delay_range: tuple = (1.0, 2.0)) -> Dict[str, Any]:
        """Confirm pending follow requests in batch (top of the list each time).

        Accepting a request removes its row, so we always act on the FIRST
        remaining request and re-read between taps. Stops at ``max_requests`` or
        when no request remains.
        """
        if not self.ensure_follow_requests_screen():
            return {"success": False, "count": 0, "accepted": [],
                    "message": "Follow requests screen not reachable"}

        accepted: List[str] = []
        self._notify("accept_all", "running", "Confirming follow requests")
        for _ in range(max_requests):
            rows = self._wait_for_request_rows()  # rows render progressively after each accept
            row = next((r for r in rows if r.get("accept")), None)
            if not row:
                break
            username = row["username"]
            if not self._tap_point(row["accept"], f"accept {username}"):
                break
            accepted.append(username)
            self._notify("accept_all", "running", username, username=username,
                         accepted_count=len(accepted))
            time.sleep(random.uniform(*delay_range))

        msg = f"Confirmed {len(accepted)} follow request(s)"
        self.logger.success(f"accept_all_requests: {msg}")
        self._notify("accept_all", "done", msg, accepted_count=len(accepted))
        return {"success": True, "count": len(accepted), "accepted": accepted, "message": msg}

    # ------------------------------------------------------------------
    # Inline like — like a comment / mention directly from the feed
    # ------------------------------------------------------------------
    def _find_inline_like(self, username: str) -> Optional[tuple]:
        root = self._dump_root()
        if root is None:
            return None
        return find_inline_like_target(
            root,
            self.selectors.notification_row_resource_id,
            self.selectors.inline_like_button,
            username,
        )

    def like_comment(self, username: str = "") -> Dict[str, Any]:
        """Like the comment / mention of ``username`` inline, from the feed.

        Comment and mention rows carry a clickable inline "Like button" (content-desc),
        so we tap it directly — no click-in. Navigation self-heals like the other
        per-row actions (re-open notifications, relaunch IG if it drifted). The target
        row may be below the fold, so we scroll a few times to reveal it.
        """
        result = {"success": False, "username": username, "message": ""}
        if not self.ensure_notifications_screen():
            result["message"] = "Notifications screen not reachable"
            self._notify("like", "failed", result["message"], username=username)
            return result
        self._optimize_locale()  # the "Like button" content-desc is localized
        self._notify("like", "running", username or "comment", username=username)

        point = self._find_inline_like(username)
        for _ in range(4):
            if point:
                break
            if not self._human_scroll("up"):
                break
            time.sleep(0.7)
            point = self._find_inline_like(username)
        if not point:
            result["message"] = (f"No inline like for: {username}" if username
                                 else "No likeable row on screen")
            self._notify("like", "failed", result["message"], username=username)
            return result

        if not self._tap_point(point, f"like {username}".strip()):
            result["message"] = f"Could not tap like for {username}"
            self._notify("like", "failed", result["message"], username=username)
            return result
        time.sleep(0.8)
        result["success"] = True
        result["message"] = (f"Liked {username}" if username else "Liked comment")
        self._notify("like", "done", result["message"], username=username)
        return result

    # ------------------------------------------------------------------
    # Comment / mention reply — click-in + type + send (manual or AI text)
    # ------------------------------------------------------------------
    def _find_reply_in_row(self, username: str) -> Optional[tuple]:
        root = self._dump_root()
        if root is None:
            return None
        return find_row_reply_target(
            root, self.selectors.notification_row_resource_id,
            self.selectors.reply_label, username,
        )

    def _open_reply_thread(self, username: str) -> bool:
        """Open the comment thread for ``username``'s row (row-scoped).

        Taps the Reply affordance INSIDE that row (paired by bounds), scrolling to
        reveal it if below the fold. With a username we NEVER fall back to a
        different row (that would reply to the wrong comment); with no username we
        tap the first reply affordance on screen (open-only convenience).
        """
        if username:
            point = self._find_reply_in_row(username)
            for _ in range(4):
                if point:
                    break
                if not self._human_scroll("up"):
                    break
                time.sleep(0.7)
                point = self._find_reply_in_row(username)
            if not point:
                return False
            return self._tap_point(point, f"reply {username}")
        replies = self._all_matches(self.selectors.reply_button)
        if not replies:
            return False
        try:
            if not tap_element_human(self.device, replies[0]):
                replies[0].click()
            return True
        except Exception as exc:
            self.logger.error(f"reply open (fallback) failed: {exc}")
            return False

    def _on_comment_thread(self) -> bool:
        """True once the standard comment-thread composer is on screen."""
        return self._element_exists(self.comment_selectors.comment_composer_indicators)

    def _type_into(self, field, text: str) -> bool:
        """Type ``text`` into the open composer ``field``, mirroring the proven
        Taktik-Keyboard -> set_text fallback, each verified by the field's text
        growing. Uses the shared CORE keyboard (humanized cadence) so the workflow
        never imports the bridge layer (DIP)."""
        try:
            before = field.get_text() or ""
        except Exception:
            before = ""
        try:
            if not tap_element_human(self.device, field):
                field.click()  # focus the composer before the IME broadcast
            time.sleep(0.3)
        except Exception:
            pass
        # 1) Taktik Keyboard (humanized typing) into the focused composer.
        try:
            if type_text_human(self.device_id, text):
                time.sleep(0.5)
                after = field.get_text() or ""
                if len(after) > len(before):
                    return True
                self.logger.warning("Taktik Keyboard ack OK but composer text not inserted")
        except Exception as exc:
            self.logger.warning(f"Taktik Keyboard typing failed: {exc}")
        # 2) set_text rescue (reliable when the IME broadcast acks but text is absent).
        try:
            field.set_text(before + text)
            time.sleep(0.5)
            after = field.get_text() or ""
            if len(after) > len(before):
                return True
        except Exception as exc:
            self.logger.warning(f"set_text fallback failed: {exc}")
        return False

    def open_mention(self, username: str = "") -> Dict[str, Any]:
        """Open the comment thread of a mention / comment row WITHOUT typing.

        Row-scoped by ``username`` (falls back to the first reply affordance only
        when no username is given). Used when the operator writes the reply by hand
        on the device, or as the first half of ``reply_to_comment``.
        """
        result = {"success": False, "username": username, "message": ""}
        if not self.ensure_notifications_screen():
            result["message"] = "Notifications screen not reachable"
            self._notify("reply", "failed", result["message"], username=username)
            return result
        self._optimize_locale()  # the Reply affordance is text-only -> needs the right locale

        self._notify("reply", "running", username or "mention", username=username)
        if not self._open_reply_thread(username):
            result["message"] = (f"No reply affordance for: {username}" if username
                                 else "No reply affordance on screen")
            self._notify("reply", "failed", result["message"], username=username)
            return result
        time.sleep(1.0)
        result["success"] = True
        result["message"] = "Reply UI opened"
        self._notify("reply", "done", result["message"], username=username)
        return result

    def reply_to_comment(self, username: str = "", text: str = "") -> Dict[str, Any]:
        """Reply to ``username``'s comment / mention with ``text`` (click-in + type + send).

        Opens the SPECIFIC row's comment thread, types the reply into the standard
        comment composer (``POST_COMMENTS_SELECTORS``), taps send, then backs out to
        the feed. ``text`` is composed by the front (manual or AI); the bot is a dumb
        type+send executor — no AI here. Empty ``text`` just opens the reply UI.
        """
        text = (text or "").strip()
        if not text:
            return self.open_mention(username)

        result = {"success": False, "username": username, "action": "reply", "message": ""}
        if not self.ensure_notifications_screen():
            result["message"] = "Notifications screen not reachable"
            self._notify("reply", "failed", result["message"], username=username)
            return result
        self._optimize_locale()  # composer / send labels are locale-dependent

        self._notify("reply", "running", username or "comment", username=username)
        if not self._open_reply_thread(username):
            result["message"] = (f"No reply affordance for: {username}" if username
                                 else "No reply affordance on screen")
            self._notify("reply", "failed", result["message"], username=username)
            return result

        # The comment thread loads after the tap; poll for its composer.
        field = None
        for _ in range(6):
            time.sleep(0.6)
            if self._on_comment_thread():
                field = self._find_element(self.comment_selectors.comment_composer_indicators)
                if field is not None:
                    break
        if field is None:
            result["message"] = "Comment composer did not open"
            self._notify("reply", "failed", result["message"], username=username)
            self._return_to_notifications()
            return result

        if not self._type_into(field, text):
            result["message"] = "Could not type the reply"
            self._notify("reply", "failed", result["message"], username=username)
            self._return_to_notifications()
            return result

        send = self._find_element(self.comment_selectors.post_comment_button_xpaths)
        if send is None:
            result["message"] = "Send button not found"
            self._notify("reply", "failed", result["message"], username=username)
            self._return_to_notifications()
            return result
        try:
            if not tap_element_human(self.device, send):
                send.click()
        except Exception as exc:
            result["message"] = f"Send tap failed: {exc}"
            self._notify("reply", "failed", result["message"], username=username)
            self._return_to_notifications()
            return result
        time.sleep(1.2)

        # Best-effort verification: the composer cleared (our text is no longer in it).
        sent = True
        try:
            f2 = self._find_element(self.comment_selectors.comment_composer_indicators)
            remaining = (f2.get_text() or "") if f2 is not None else ""
            if text and text in remaining:
                sent = False
        except Exception:
            pass

        self._return_to_notifications()
        result["success"] = sent
        result["message"] = (f"Replied to {username}" if sent else "Reply may not have been sent")
        self._notify("reply", "done" if sent else "failed", result["message"], username=username)
        return result


__all__ = ["NotificationsEngagementWorkflow"]
