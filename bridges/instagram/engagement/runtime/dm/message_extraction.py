"""DM message extraction helpers for the Instagram DM bridge."""

from __future__ import annotations

import time

from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS

# How much conversation history to capture for context. Bounded so we stay fast and never
# loop forever on very long threads (Kevin: ~20 recent messages is enough to understand
# the conversation). A short conversation triggers at most one extra (no-op) scroll.
_MAX_HISTORY_MESSAGES = 20
_MAX_HISTORY_SCROLLS = 4


class DMMessageExtractionMixin:
    """Collect visible text and reel messages from an opened DM conversation."""

    def _collect_messages(
        self,
        max_messages: int = _MAX_HISTORY_MESSAGES,
        max_scrolls: int = _MAX_HISTORY_SCROLLS,
    ) -> list:
        """Collect the recent messages of the open conversation, chronological order.

        A conversation opens scrolled to the bottom (newest message). We capture the
        visible screen, then scroll UP a few times to load older messages for context,
        accumulating de-duplicated messages until we have ``max_messages`` recent ones
        or reach the top. Order stays oldest-first so the last item remains the newest
        (``last_message_is_ours`` and the reply context rely on this).
        """
        collected = self._collect_current_screen()
        seen = {self._message_key(message) for message in collected}

        for _ in range(max_scrolls):
            if len(collected) >= max_messages:
                break
            self._scroll_to_older_messages()
            screen = self._collect_current_screen()
            fresh = [m for m in screen if self._message_key(m) not in seen]
            if not fresh:
                break  # no new messages above -> reached the top of the thread
            seen.update(self._message_key(m) for m in fresh)
            # Older messages sit above the overlap -> prepend them, preserving order.
            collected = fresh + collected

        if len(collected) > max_messages:
            collected = collected[-max_messages:]  # keep the most recent context

        return [
            {
                "type": message["type"],
                "text": message["text"],
                "is_sent": message["is_sent"],
            }
            for message in collected
        ]

    @staticmethod
    def _message_key(message: dict) -> tuple:
        """Dedup key across scroll steps (a re-read of the same screen overlaps)."""
        return (message["is_sent"], message["text"])

    def _collect_current_screen(self) -> list[dict]:
        """All text + reel messages currently on screen, sorted top -> bottom."""
        all_items = []
        all_items.extend(self._collect_text_messages())
        all_items.extend(self._collect_reel_messages())
        all_items.sort(key=lambda x: x["top"])
        return all_items

    def _scroll_to_older_messages(self) -> None:
        """Swipe down so the conversation reveals older messages above the viewport."""
        try:
            x = self.screen_width // 2
            self.device.swipe(
                x, int(self.screen_height * 0.35),
                x, int(self.screen_height * 0.78),
                duration=0.3,
            )
            time.sleep(1.0)
        except Exception:
            # Best-effort: a failed scroll just means we keep the messages we already have.
            pass

    def _collect_text_messages(self) -> list[dict]:
        items = []
        msg_elements = self.device(resourceId=DM_SELECTORS.message_item_resource_id)
        for j in range(msg_elements.count):
            try:
                msg_elem = msg_elements[j]
                msg_bounds = msg_elem.info.get("bounds", {})
                text = msg_elem.get_text()
                if not text:
                    continue
                msg_left = msg_bounds.get("left", 0)
                msg_top = msg_bounds.get("top", 0)
                is_received = msg_left < self.screen_width * 0.25
                items.append({
                    "type": "text",
                    "text": text,
                    "is_sent": not is_received,
                    "top": msg_top,
                })
            except Exception:
                continue
        return items

    def _collect_reel_messages(self) -> list[dict]:
        items = []
        reel_shares = self.device(resourceId=DM_SELECTORS.reel_share_item_resource_id)
        for j in range(reel_shares.count):
            try:
                reel = reel_shares[j]
                reel_bounds = reel.info.get("bounds", {})
                reel_left = reel_bounds.get("left", 0)
                reel_top = reel_bounds.get("top", 0)
                is_received = reel_left < self.screen_width * 0.25

                reel_author = self._extract_reel_author(reel_bounds)
                items.append({
                    "type": "reel",
                    "text": f"[Reel de @{reel_author}]" if reel_author else "[Reel partagé]",
                    "is_sent": not is_received,
                    "top": reel_top,
                })
            except Exception:
                continue
        return items

    def _extract_reel_author(self, reel_bounds: dict) -> str:
        title_elem = self.device(resourceId=DM_SELECTORS.reel_author_title_resource_id)
        for k in range(title_elem.count):
            try:
                title = title_elem[k]
                title_bounds = title.info.get("bounds", {})
                if (
                    title_bounds.get("top", 0) >= reel_bounds.get("top", 0)
                    and title_bounds.get("bottom", 0) <= reel_bounds.get("bottom", 0)
                ):
                    return title.get_text() or ""
            except Exception:
                continue
        return ""
