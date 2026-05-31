"""DM inbox and conversation navigation for the Instagram DM bridge."""

from __future__ import annotations

import random
import time

from bridges.instagram.base import logger
from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS


class DMInboxNavigationMixin:
    """Navigation helpers shared by DM read/send commands."""

    def navigate_to_dm_inbox(self) -> bool:
        """Navigate to DM inbox using multiple methods."""
        logger.info("Navigating to DM inbox...")

        logger.info("Trying method 1: direct_tab resource-id (uiautomator2)...")
        dm_tab = self.device(resourceId="com.instagram.android:id/direct_tab")
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            logger.info("Navigated via direct_tab (uiautomator2)")
            return True

        logger.info("Trying method 2: content-desc 'Message'...")
        for desc in ["Message", "Messages", "Direct", "Messenger"]:
            btn = self.device(description=desc)
            if btn.exists:
                btn.click()
                time.sleep(2)
                logger.info(f"Navigated via content-desc: {desc}")
                return True

        logger.info("Trying method 3: direct_tab xpath...")
        dm_tab = self.device.xpath(DM_SELECTORS.direct_tab)
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            logger.info("Navigated via direct_tab xpath")
            return True

        logger.info("Trying method 4: DM_SELECTORS content-desc xpaths...")
        for selector in DM_SELECTORS.direct_tab_content_desc:
            dm_btn = self.device.xpath(selector)
            if dm_btn.exists:
                dm_btn.click()
                time.sleep(2)
                logger.info(f"Navigated via content-desc xpath: {selector}")
                return True

        logger.info("Trying method 5: action_bar_inbox_button...")
        messenger = self.device(resourceId="com.instagram.android:id/action_bar_inbox_button")
        if messenger.exists:
            messenger.click()
            time.sleep(2)
            logger.info("Navigated via messenger icon")
            return True

        logger.info("Trying method 6: descriptionContains variations...")
        for desc in ["Message", "Messenger", "Inbox", "Boîte de réception", "Envoyer un message"]:
            btn = self.device(descriptionContains=desc)
            if btn.exists:
                btn.click()
                time.sleep(2)
                inbox = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
                if inbox.exists:
                    logger.info(f"Navigated via descriptionContains: {desc}")
                    return True
                logger.warning(f"Clicked '{desc}' but did not reach DM inbox, pressing back")
                self.device.press("back")
                time.sleep(1)

        logger.info("Trying method 7: ImageView in action bar...")
        action_bar = self.device(resourceId="com.instagram.android:id/action_bar_container")
        if action_bar.exists:
            images = action_bar.child(className="android.widget.ImageView", clickable=True)
            if images.count > 0:
                images[images.count - 1].click()
                time.sleep(2)
                inbox = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
                if inbox.exists:
                    logger.info("Navigated via action bar ImageView")
                    return True
                logger.warning("Clicked action bar ImageView but did not reach DM inbox, pressing back")
                self.device.press("back")
                time.sleep(1)

        logger.error("Cannot find DM button - all methods failed")
        return False

    def _ensure_primary_tab(self):
        """Ensure we're on the Primary tab in DM inbox."""
        primary_tab = self.device(textContains="Primary")
        if primary_tab.exists:
            logger.info("Clicking Primary tab to ensure we're in the right section")
            primary_tab.click()
            time.sleep(1)
            return True

        primary_tab = self.device(descriptionContains="Primary")
        if primary_tab.exists:
            logger.info("Clicking Primary tab (via description)")
            primary_tab.click()
            time.sleep(1)
            return True

        logger.warning("Primary tab not found")
        return False

    def _is_dm_inbox_top_visible(self) -> bool:
        """Return True when the inbox header area is visible near the top."""
        header = self.device(resourceId="com.instagram.android:id/header_text", text="Messages")
        requests = self.device(resourceId="com.instagram.android:id/header_action_button", text="Requests")
        if header.exists or requests.exists:
            return True

        for text in (
            "Messages",
            "Requests",
            "Demandes",
            "Search or ask Meta AI",
            "Search",
            "Rechercher",
            "Your note",
            "Votre note",
            "Map",
            "Carte",
        ):
            elem = self.device(text=text)
            if elem.exists or self.device(textContains=text).exists:
                return True
        return False

    def _is_accounts_to_follow_visible(self) -> bool:
        """Detect the bottom recommendations block in the DM inbox."""
        for text in (
            "Accounts to follow",
            "Suggested for you",
            "See all",
            "Comptes à suivre",
            "Suggestions pour vous",
            "Voir tout",
        ):
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
                self.screen_width // 2, int(self.screen_height * 0.55),
                self.screen_width // 2, int(self.screen_height * 0.85),
                duration=0.2,
            )
            time.sleep(0.3)

        time.sleep(0.5)

    def _reset_inbox_via_tab_roundtrip(self) -> bool:
        """Leave the DM inbox through a regular tab, then re-open DMs."""
        logger.info("Resetting DM inbox via tab roundtrip...")
        tab_ids = [
            "com.instagram.android:id/feed_tab",
            "com.instagram.android:id/search_tab",
            "com.instagram.android:id/clips_tab",
            "com.instagram.android:id/profile_tab",
        ]
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

    def _search_conversation_in_visible_list(self, username_lower: str) -> bool:
        """Search for a conversation in the currently visible inbox list."""
        inbox_items = self.device(resourceId="com.instagram.android:id/row_inbox_container")

        for i in range(min(inbox_items.count, 20)):
            try:
                item = inbox_items[i]
                username_elem = item.child(resourceId="com.instagram.android:id/row_inbox_username")
                if username_elem.exists:
                    item_username = username_elem.get_text()
                    if item_username:
                        item_username_lower = item_username.lower().strip()
                        if (
                            item_username_lower == username_lower
                            or username_lower in item_username_lower
                            or item_username_lower in username_lower
                        ):
                            logger.info(f"Found conversation: {item_username}")
                            item.click()
                            time.sleep(2)
                            return True
            except Exception:
                continue
        return False

    def open_conversation(self, username: str) -> bool:
        """Open a specific conversation by username."""
        logger.info(f"Opening conversation with: {username}")
        username_lower = username.lower().strip()

        if self._search_conversation_in_visible_list(username_lower):
            return True

        logger.info("Trying direct search on all row_inbox_username elements...")
        username_elems = self.device(resourceId="com.instagram.android:id/row_inbox_username")
        for i in range(min(username_elems.count, 20)):
            try:
                elem = username_elems[i]
                item_username = elem.get_text()
                if item_username:
                    item_username_lower = item_username.lower().strip()
                    if (
                        item_username_lower == username_lower
                        or username_lower in item_username_lower
                        or item_username_lower in username_lower
                    ):
                        logger.info(f"Found via direct username element: {item_username}")
                        elem.click()
                        time.sleep(2)
                        return True
            except Exception:
                continue

        user_elem = self.device(textContains=username)
        if user_elem.exists:
            logger.info(f"Found via textContains: {username}")
            user_elem.click()
            time.sleep(2)
            return True

        for scroll_attempt in range(5):
            logger.info(f"Scrolling down to find conversation (attempt {scroll_attempt + 1}/5)...")
            self.device.swipe(
                self.screen_width // 2, int(self.screen_height * 0.7),
                self.screen_width // 2, int(self.screen_height * 0.3),
                duration=0.3,
            )
            time.sleep(1)

            if self._search_conversation_in_visible_list(username_lower):
                return True

        logger.error(f"Conversation with {username} not found after scrolling")
        return False
