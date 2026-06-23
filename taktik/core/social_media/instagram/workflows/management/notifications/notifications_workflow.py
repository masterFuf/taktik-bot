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

from ....ui.language import detect_and_optimize
from ....ui.selectors.surfaces.notifications import NOTIFICATION_SELECTORS
from .dump_parsing import concat_text, parse_feed_rows, parse_request_rows
from .row_layout import parse_bounds

StepNotifier = Callable[..., None]


class NotificationsEngagementWorkflow:
    """Engagement workflow over the Instagram notifications/activity surface."""

    def __init__(self, device, device_id: str, notifier: Optional[StepNotifier] = None):
        self.device = device
        self.device_id = device_id
        self._notify_cb = notifier
        self.logger = logger.bind(module="instagram-notifications")
        self.selectors = NOTIFICATION_SELECTORS
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
            element.click()
            self.logger.info("Tapped 'Show more'")
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
            self.device.click(point[0], point[1])
            self.logger.success(f"{name}: tapped @ {point}")
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

    def ensure_notifications_screen(self) -> bool:
        """Open the notifications screen (tap the activity/heart entry) if needed."""
        if self._on_notifications_screen():
            return True
        self._notify("open_notifications", "running", "Opening notifications")
        if not self._click_first_match(self.selectors.activity_entry, "Activity entry"):
            self._notify("open_notifications", "failed", "Activity entry not found")
            return False
        time.sleep(1.5)
        ok = self._on_notifications_screen()
        self._notify("open_notifications", "done" if ok else "failed")
        return ok

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
                self._notify("open_requests", "done")
                return True
        self._notify("open_requests", "failed", "Follow requests screen did not load")
        return False

    # ------------------------------------------------------------------
    # Read pass — classify the activity feed (all families)
    # ------------------------------------------------------------------
    def _rows_on_screen(self) -> List[Dict[str, Any]]:
        root = self._dump_root()
        if root is None:
            return []
        return parse_feed_rows(root, self.selectors.notification_row_resource_id,
                               self.selectors.classifier_fragments)

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
        stale = 0
        iteration_cap = max(max_scrolls + 1, 12)
        for index in range(iteration_cap):
            rows = self._rows_on_screen()
            if not rows and not items and index == 0:
                time.sleep(1.2)  # feed may still be rendering
                rows = self._rows_on_screen()
            new_count = 0
            for row in rows:
                key = row["text"].lower()
                if key in seen:
                    continue
                seen.add(key)
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
        for _ in range(12):
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
            at_bottom = self._element_exists(self.selectors.suggested_for_you)
            if not added:
                stale += 1
                if at_bottom or stale >= 3:
                    break  # fully rendered (bottom reached) or nothing new 3x
                self._scroll_down(1)
            else:
                stale = 0
                if not at_bottom:
                    self._scroll_down(1)  # more requests below the fold
            time.sleep(0.8)  # let progressively-loading rows render

        if not requests:
            # Diagnostic: we reached the sub-screen but parsed nothing. Log the raw
            # node counts so a 'sparse dump / wrong id' case is distinguishable from
            # a pairing bug without needing another device dump.
            root = self._dump_root()
            if root is not None:
                u = sum(1 for n in root.iter("node")
                        if self.selectors.follow_request_username_resource_id in (n.get("resource-id") or ""))
                a = sum(1 for n in root.iter("node")
                        if self.selectors.follow_request_accept_resource_id in (n.get("resource-id") or ""))
                self.logger.warning(f"collect_requests: 0 parsed (dump has {u} username, {a} accept nodes)")
        return requests

    def list_requests(self, max_requests: int = 50) -> Dict[str, Any]:
        """Enumerate pending follow requests (usernames) on the sub-screen."""
        requests = self._collect_requests(max_requests)
        msg = f"{len(requests)} pending follow request(s)"
        self.logger.info(f"list_requests: {msg}")
        return {"success": True, "count": len(requests), "requests": requests, "message": msg}

    def _act_on_request(self, username: str, action: str) -> Dict[str, Any]:
        """Confirm or delete the follow request of ``username`` (sub-screen)."""
        result = {"success": False, "username": username, "action": action, "message": ""}
        if not self.ensure_follow_requests_screen():
            result["message"] = "Follow requests screen not reachable"
            return result

        # The row may be off-screen; scroll until the username is visible.
        target = None
        for _ in range(8):
            target = next((r for r in self._request_rows() if r["username"] == username), None)
            if target:
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
            row = next((r for r in self._request_rows() if r.get("accept")), None)
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
    # Comment mentions — open the reply UI (best-effort; typed reply staged)
    # ------------------------------------------------------------------
    def open_mention(self, username: str = "") -> Dict[str, Any]:
        """Tap the Reply affordance on a comment-mention row to open its thread.

        v1 opens the reply UI on the device (the first reply affordance found).
        Typing the reply text is staged for a later increment (needs a
        reply-content source: templates or AI).
        """
        result = {"success": False, "username": username, "message": ""}
        if not self.ensure_notifications_screen():
            result["message"] = "Notifications screen not reachable"
            return result
        self._optimize_locale()  # the Reply affordance is text-only -> needs the right locale

        replies = self._all_matches(self.selectors.reply_button)
        if not replies:
            result["message"] = "No reply affordance on screen"
            self._notify("reply", "failed", result["message"], username=username)
            return result

        self._notify("reply", "running", username or "mention", username=username)
        try:
            replies[0].click()
        except Exception as exc:
            result["message"] = f"Could not open reply: {exc}"
            self._notify("reply", "failed", result["message"], username=username)
            return result
        time.sleep(1.0)
        result["success"] = True
        result["message"] = "Reply UI opened"
        self._notify("reply", "done", result["message"], username=username)
        return result


__all__ = ["NotificationsEngagementWorkflow"]
