"""DM inbox reset/top-position helpers for the Instagram DM bridge."""

from __future__ import annotations

import random
import time

from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class DMInboxResetMixin:
    """Keep the DM inbox in a deterministic top/Primary state."""

    def _ensure_primary_tab(self):
        """Ensure we're on the Primary tab in DM inbox."""
        for text in DM_SELECTORS.primary_tab_text_contains:
            primary_tab = self.device(textContains=text)
            if primary_tab.exists:
                logger.info("Clicking Primary tab to ensure we're in the right section")
                primary_tab.click()
                time.sleep(1)
                return True

            primary_tab = self.device(descriptionContains=text)
            if primary_tab.exists:
                logger.info("Clicking Primary tab (via description)")
                primary_tab.click()
                time.sleep(1)
                return True

        logger.warning("Primary tab not found")
        return False

    def _is_dm_inbox_top_visible(self) -> bool:
        """Return True when the inbox header area is visible near the top."""
        header = self.device(
            resourceId=DM_SELECTORS.inbox_header_text_resource_id,
            text=DM_SELECTORS.inbox_header_messages_text,
        )
        requests = self.device(
            resourceId=DM_SELECTORS.inbox_header_action_button_resource_id,
            text=DM_SELECTORS.inbox_header_requests_text,
        )
        if header.exists or requests.exists:
            return True

        for text in DM_SELECTORS.inbox_top_visible_texts:
            elem = self.device(text=text)
            if elem.exists or self.device(textContains=text).exists:
                return True
        return False

    def _is_accounts_to_follow_visible(self) -> bool:
        """Detect the bottom recommendations block in the DM inbox."""
        for text in DM_SELECTORS.inbox_recommendation_texts:
            if self.device(text=text).exists or self.device(textContains=text).exists:
                return True
        return False

    def _scroll_to_top_of_inbox(self, max_swipes: int = 8):
        """Scroll to the top of the inbox list and ensure we're on Primary tab."""
        logger.info("Scrolling to top of inbox...")
        self._ensure_primary_tab()

        for attempt in range(max_swipes):
            if self._is_dm_inbox_top_visible():
                logger.info(f"DM inbox top visible after {attempt} swipe(s)")
                break
            self.device.swipe(
                self.screen_width // 2,
                int(self.screen_height * 0.55),
                self.screen_width // 2,
                int(self.screen_height * 0.85),
                duration=0.2,
            )
            time.sleep(0.3)

        time.sleep(0.5)

    def _reset_inbox_via_tab_roundtrip(self) -> bool:
        """Leave the DM inbox through a regular tab, then re-open DMs."""
        logger.info("Resetting DM inbox via tab roundtrip...")
        tab_ids = list(DM_SELECTORS.bottom_tab_resource_ids)
        random.shuffle(tab_ids)

        for resource_id in tab_ids:
            try:
                tab = self.device(resourceId=resource_id)
                if tab.exists(timeout=1):
                    tab.click()
                    time.sleep(random.uniform(0.8, 1.4))
                    if self.navigate_to_dm_inbox():
                        self._ensure_primary_tab()
                        if self._is_dm_inbox_top_visible():
                            logger.info(f"DM inbox reset via tab roundtrip ({resource_id})")
                            return True
                        self._scroll_to_top_of_inbox(max_swipes=4)
                        return self._is_dm_inbox_top_visible()
            except Exception as exc:
                logger.debug(f"Tab roundtrip failed for {resource_id}: {exc}")

        y = int(self.screen_height * 0.94)
        x_positions = [
            int(self.screen_width * 0.12),
            int(self.screen_width * 0.32),
            int(self.screen_width * 0.55),
            int(self.screen_width * 0.78),
        ]
        random.shuffle(x_positions)
        for x in x_positions:
            try:
                self.device.click(x, y)
                time.sleep(random.uniform(0.8, 1.4))
                if self.navigate_to_dm_inbox():
                    self._ensure_primary_tab()
                    if self._is_dm_inbox_top_visible():
                        logger.info(f"DM inbox reset via bottom bar coordinate ({x},{y})")
                        return True
                    self._scroll_to_top_of_inbox(max_swipes=4)
                    return self._is_dm_inbox_top_visible()
            except Exception as exc:
                logger.debug(f"Bottom bar coordinate roundtrip failed at x={x}: {exc}")

        return False

    def _reset_inbox_to_top(self, strategy: str = "auto"):
        """Reset inbox position using either scroll or tab roundtrip."""
        if self._is_dm_inbox_top_visible():
            logger.info("DM inbox already at top")
            return

        chosen = strategy
        if strategy == "auto":
            chosen = random.choice(["scroll", "tab_roundtrip"])

        if chosen == "tab_roundtrip" and self._reset_inbox_via_tab_roundtrip():
            return

        self._scroll_to_top_of_inbox(max_swipes=10)
