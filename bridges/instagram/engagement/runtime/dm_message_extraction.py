"""DM message extraction helpers for the Instagram DM bridge."""

from __future__ import annotations

from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class DMMessageExtractionMixin:
    """Collect visible text and reel messages from an opened DM conversation."""

    def _collect_messages(self) -> list:
        """Collect messages from current conversation."""
        all_items = []
        all_items.extend(self._collect_text_messages())
        all_items.extend(self._collect_reel_messages())
        all_items.sort(key=lambda x: x["top"])

        return [
            {
                "type": msg["type"],
                "text": msg["text"],
                "is_sent": msg["is_sent"],
            }
            for msg in all_items
        ]

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
