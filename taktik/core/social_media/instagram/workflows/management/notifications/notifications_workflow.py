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
here (AGENTS invariant). Text classification is delegated to the pure
``classifier`` module; per-row control pairing to ``row_layout``.

Live step narration is emitted through an OPTIONAL injected ``notifier`` callback
(Dependency Inversion: this core workflow never imports the bridge layer); it is a
no-op when run standalone.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from lxml import etree

from ....ui.selectors.surfaces.notifications import NOTIFICATION_SELECTORS
from .classifier import classify_row, extract_time, row_has_action
from .row_layout import center, index_of_closest_row, parse_bounds, vertical_center

StepNotifier = Callable[..., None]


class NotificationsEngagementWorkflow:
    """Engagement workflow over the Instagram notifications/activity surface."""

    def __init__(self, device, device_id: str, notifier: Optional[StepNotifier] = None):
        self.device = device
        self.device_id = device_id
        self._notify_cb = notifier
        self.logger = logger.bind(module="instagram-notifications")
        self.selectors = NOTIFICATION_SELECTORS

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
    # Low-level UI helpers (mirror ChangeLanguageWorkflow)
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

    def _scroll_down(self, times: int = 1) -> None:
        try:
            width, height = self.device.window_size()
        except Exception:
            width, height = 720, 1280
        x = width // 2
        y_start = int(height * 0.75)
        y_end = int(height * 0.30)
        for _ in range(times):
            try:
                self.device.swipe(x, y_start, x, y_end, duration=0.4)
                time.sleep(0.7)
            except Exception as exc:
                self.logger.warning(f"Swipe failed: {exc}")
                break

    @staticmethod
    def _element_bounds(element) -> Optional[tuple]:
        """Best-effort bounds 4-tuple from a uiautomator2 XPath element."""
        try:
            bounds = element.bounds
        except Exception:
            bounds = None
        if bounds and len(tuple(bounds)) == 4:
            return tuple(bounds)
        try:
            return parse_bounds(element.attrib.get("bounds", ""))
        except Exception:
            return None

    @staticmethod
    def _element_text(element) -> str:
        for getter in ("text",):
            try:
                value = getattr(element, getter)
                if value:
                    return str(value).strip()
            except Exception:
                continue
        try:
            return (element.attrib.get("text") or "").strip()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _on_notifications_screen(self) -> bool:
        return self._element_exists(self.selectors.notifications_screen_indicators)

    def _on_follow_requests_screen(self) -> bool:
        return self._element_exists(self.selectors.follow_requests_screen_indicators)

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

    def ensure_follow_requests_screen(self) -> bool:
        """Open the follow-requests sub-screen from the notifications screen."""
        if self._on_follow_requests_screen():
            return True
        if not self.ensure_notifications_screen():
            return False
        self._notify("open_requests", "running", "Opening follow requests")
        if not self._click_first_match(self.selectors.follow_requests_header, "Follow requests header"):
            self._notify("open_requests", "failed", "Follow requests section not found")
            return False
        time.sleep(1.5)
        ok = self._on_follow_requests_screen()
        self._notify("open_requests", "done" if ok else "failed")
        return ok

    # ------------------------------------------------------------------
    # Read pass — classify the activity feed (all families)
    # ------------------------------------------------------------------
    def _rows_on_screen(self) -> List[Dict[str, Any]]:
        """Classify every story row currently rendered (one XML dump, no scroll)."""
        try:
            xml = self.device.dump_hierarchy()
        except Exception as exc:
            self.logger.error(f"dump_hierarchy failed: {exc}")
            return []
        if not xml:
            return []
        try:
            root = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
        except Exception as exc:
            self.logger.error(f"XML parse failed: {exc}")
            return []

        fragments = self.selectors.classifier_fragments
        row_rid = self.selectors.notification_row_resource_id
        rows: List[Dict[str, Any]] = []
        for node in root.iter("node"):
            if row_rid not in (node.get("resource-id") or ""):
                continue
            parts: List[str] = []
            for descendant in node.iter():
                for attr in ("text", "content-desc"):
                    val = descendant.get(attr)
                    if val and val.strip():
                        parts.append(val.strip())
            full = " ".join(dict.fromkeys(parts)).strip()
            if not full:
                continue
            ntype, username = classify_row(full, fragments)
            rows.append({
                "type": ntype,
                "username": username,
                "time": extract_time(full),
                "text": full[:200],
                "has_action": row_has_action(full),
            })
        return rows

    def scan(self, max_scrolls: int = 3) -> Dict[str, Any]:
        """Read + classify the activity feed across a few screens (all families).

        Returns ``{success, count, by_type, items, has_grouped_requests}``. Items
        are de-duplicated by text and kept in chronological (top-to-bottom) order.
        """
        if not self.ensure_notifications_screen():
            return {"success": False, "count": 0, "by_type": {}, "items": [],
                    "has_grouped_requests": False, "message": "Notifications screen not reachable"}

        self._notify("scan", "running", "Reading notifications")
        has_grouped = self._element_exists(self.selectors.follow_requests_header)

        items: List[Dict[str, Any]] = []
        seen: set = set()
        for attempt in range(max_scrolls + 1):
            new_count = 0
            for row in self._rows_on_screen():
                key = row["text"].lower()
                if key in seen:
                    continue
                seen.add(key)
                items.append(row)
                new_count += 1
            if attempt < max_scrolls and new_count:
                self._scroll_down(1)
            elif attempt < max_scrolls and not new_count:
                break  # nothing new revealed -> reached the bottom

        by_type: Dict[str, int] = {}
        for item in items:
            by_type[item["type"]] = by_type.get(item["type"], 0) + 1
        summary = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())) or "none"
        msg = f"{len(items)} notifications [{summary}]"
        self.logger.info(f"scan: {msg}")
        self._notify("scan", "done", msg)
        return {"success": True, "count": len(items), "by_type": by_type,
                "items": items, "has_grouped_requests": has_grouped, "message": msg}

    # ------------------------------------------------------------------
    # Follow requests — sub-screen, row-scoped
    # ------------------------------------------------------------------
    def _request_rows(self) -> List[Dict[str, Any]]:
        """Pending requests on the sub-screen: ``[{username, y, accept?, ignore?}]``.

        Each entry pairs a username with the Confirm/Delete button on its row by
        vertical-center proximity (the controls live on the same horizontal band).
        ``accept``/``ignore`` are tap points ``(x, y)`` when resolvable.
        """
        usernames = self._all_matches(self.selectors.request_username)
        accepts = self._all_matches(self.selectors.request_accept_button)
        ignores = self._all_matches(self.selectors.request_ignore_button)

        accept_boxes = [self._element_bounds(e) for e in accepts]
        ignore_boxes = [self._element_bounds(e) for e in ignores]
        accept_ys = [vertical_center(b) for b in accept_boxes if b]
        ignore_ys = [vertical_center(b) for b in ignore_boxes if b]
        accept_valid = [b for b in accept_boxes if b]
        ignore_valid = [b for b in ignore_boxes if b]

        rows: List[Dict[str, Any]] = []
        for element in usernames:
            name = self._element_text(element)
            box = self._element_bounds(element)
            if not name or not box:
                continue
            y = vertical_center(box)
            entry: Dict[str, Any] = {"username": name, "y": y, "accept": None, "ignore": None}
            ai = index_of_closest_row(y, accept_ys)
            if ai is not None:
                entry["accept"] = center(accept_valid[ai])
            ii = index_of_closest_row(y, ignore_ys)
            if ii is not None:
                entry["ignore"] = center(ignore_valid[ii])
            rows.append(entry)
        return rows

    def list_requests(self, max_requests: int = 50) -> Dict[str, Any]:
        """Enumerate pending follow requests (usernames) on the sub-screen."""
        if not self.ensure_follow_requests_screen():
            return {"success": False, "count": 0, "requests": [],
                    "message": "Follow requests screen not reachable"}

        seen: set = set()
        requests: List[Dict[str, str]] = []
        for _ in range(8):  # bounded scroll
            for row in self._request_rows():
                name = row["username"]
                if name in seen:
                    continue
                seen.add(name)
                requests.append({"username": name})
                if len(requests) >= max_requests:
                    break
            if len(requests) >= max_requests:
                break
            before = len(seen)
            self._scroll_down(1)
            # If a scroll revealed nothing new, we have reached the bottom.
            if len(set(r["username"] for r in self._request_rows()) - seen) == 0 and len(seen) == before:
                break

        msg = f"{len(requests)} pending follow request(s)"
        self.logger.info(f"list_requests: {msg}")
        return {"success": True, "count": len(requests), "requests": requests, "message": msg}

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

    def _act_on_request(self, username: str, action: str) -> Dict[str, Any]:
        """Confirm or delete the follow request of ``username`` (sub-screen)."""
        result = {"success": False, "username": username, "action": action, "message": ""}
        if not self.ensure_follow_requests_screen():
            result["message"] = "Follow requests screen not reachable"
            return result

        # The row may be off-screen; scroll until the username is visible.
        target = None
        for _ in range(8):
            rows = self._request_rows()
            target = next((r for r in rows if r["username"] == username), None)
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
        import random

        if not self.ensure_follow_requests_screen():
            return {"success": False, "count": 0, "accepted": [],
                    "message": "Follow requests screen not reachable"}

        accepted: List[str] = []
        self._notify("accept_all", "running", "Confirming follow requests")
        for _ in range(max_requests):
            rows = self._request_rows()
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
    # Comment mentions — open the reply UI (best-effort; typed reply staged)
    # ------------------------------------------------------------------
    def open_mention(self, username: str = "") -> Dict[str, Any]:
        """Tap the Reply affordance on a comment-mention row to open its thread.

        v1 opens the reply UI on the device (the first mention row, or the one
        whose text contains ``username``). Typing the reply text is staged for a
        later increment (needs a reply-content source: templates or AI).
        """
        result = {"success": False, "username": username, "message": ""}
        if not self.ensure_notifications_screen():
            result["message"] = "Notifications screen not reachable"
            return result

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
