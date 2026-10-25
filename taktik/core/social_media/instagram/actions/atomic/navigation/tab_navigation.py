"""Tab-based UI navigation (home, search, profile tab)."""

import time
from loguru import logger

from taktik.core.shared.device.snapshot import SnapshotUnavailable
from taktik.core.social_media.instagram.actions.base.base_action import BaseAction
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import (
    NAVIGATION_SELECTORS,
    NavigationSelectors,
)


class TabNavigationMixin(BaseAction):
    """Mixin: navigate between Instagram tabs via bottom bar clicks."""

    # Set by `NavigationActions.__init__`, the class that composes this mixin.
    selectors: NavigationSelectors

    def _navigate_to_tab(self, tab_selectors, tab_name: str, emoji: str, verify_func,
                         probe: bool = False) -> bool:
        """
        Generic method to navigate to a tab.
        
        Args:
            tab_selectors: Selectors for the tab
            tab_name: Name for logging
            emoji: Emoji for logging
            verify_func: Function to verify navigation success
            probe: the screen may well not show the tab bar (a conversation, a profile opened
                from a search): its absence is no warning and keeps no screen; the caller
                reports it once if its way ends without the tab (`_report_selector_miss`)
            
        Returns:
            True if navigation successful, False otherwise
        """
        self.logger.debug(f"{emoji} Navigating to {tab_name}")
        
        if self._find_and_click(tab_selectors, timeout=3, report_miss=not probe):
            self._human_like_delay('navigation')
            return verify_func()
        
        return False
    
    def navigate_to_home(self) -> bool:
        """The home feed, by its tab, or Back after Back until the tab shows (`_back_out_until`).

        Every look for the tab on the way is a probe: a screen without the tab bar is the normal
        start (a conversation, a profile opened from a search) and each screen a Back leaves may
        hide it too. Only the way that ends without home says so, once, with its screen kept
        (2026-10-25, Pixel 6a: a warning and a capture at each of the four Backs of every DM)."""
        started = time.time()
        if self._navigate_to_tab(self.selectors.home_tab, "home screen", "🏠", self._is_home_screen,
                                 probe=True):
            return True

        # Back never leaves the Android launcher or another app: bring Instagram back first.
        if not self._is_instagram_open():
            self.logger.warning("🏠 Instagram is not in the foreground — opening it before going home")
            self._open_instagram()
            if self._is_home_screen():
                return True
            if self._navigate_to_tab(self.selectors.home_tab, "home screen", "🏠", self._is_home_screen,
                                     probe=True):
                return True

        # Incremental fallback: press Back ONE at a time and stop the instant we reach the
        # feed. A blind 3× back can close a story → land on the feed → exit the feed → leave
        # Instagram entirely (ending on the Android launcher), from which the home tab is gone.
        # Early-return as soon as we're home avoids backing out of the app.
        self.logger.debug("Fallback: using back button (incremental, stop at home)")
        # A Back that brings the tab bar back (a search, a profile) leaves home one tap away.
        if self._back_out_until(lambda: self._is_home_screen() or self._navigate_to_tab(
                self.selectors.home_tab, "home screen", "🏠", self._is_home_screen, probe=True)):
            return True
        if self._is_home_screen():
            return True
        self._report_selector_miss(self.selectors.home_tab, timeout=3,
                                   elapsed_ms=round((time.time() - started) * 1000))
        return False

    def navigate_to_search(self) -> bool:
        # The search screen may already be up: the results of an earlier search, which Instagram
        # 447 shows without the tab bar. Its own bar says so; the search types into it as it is.
        if self._is_search_bar_shown():
            self.logger.debug("🔍 Already on the search screen")
            return True
        if self._navigate_to_tab(self.selectors.search_tab, "search screen", "🔍", self._is_search_screen):
            return True

        # The search tab lives in the BOTTOM NAV BAR. If we're parked on a fullscreen surface that
        # hides it — a reel/clips viewer, an open post, a likers sheet, the keyboard — the tap finds
        # nothing and EVERY hashtag iteration looped forever on "Cannot navigate to search screen".
        # Back out one screen at a time, as navigate_to_home does, and stop on the first screen that
        # is the search screen or shows the tab bar. Going home first was not enough: on Instagram
        # 447 a likers sheet, its post, the profile and the search results that opened them hide the
        # tab bar all four, and the three Backs of the way home ended on those results, which nothing
        # then recognised (cold DM from a likers run, 2026-10-24). If a stray back dropped us to the
        # launcher, bring Instagram back to the foreground first.
        self.logger.warning("🔍 Search tab not found — backing out to the search screen or the tab bar")
        if not self._is_instagram_open():
            self._open_instagram()
            if self._is_search_bar_shown() or self._navigate_to_tab(
                    self.selectors.search_tab, "search screen", "🔍", self._is_search_screen):
                return True
        return self._back_out_until(lambda: self._is_search_bar_shown() or self._navigate_to_tab(
            self.selectors.search_tab, "search screen", "🔍", self._is_search_screen))

    def _back_out_until(self, arrived, max_backs: int = 3) -> bool:
        """One real Back at a time, at most `max_backs` screens left, until `arrived()` answers True
        after one.

        A keyboard on screen takes the first Back for itself and leaves no screen: that Back is not
        one of the `max_backs`. After a DM, the keyboard is still up over the conversation; it took
        the first of the three Backs of the way home, which then ended on the results of the search
        that opened the profile (cold DM, 447, Pixel 6a, 2026-10-25).

        Never out of Instagram: the facade refuses a Back on a root screen (home feed, a main tab),
        where it would leave the app or switch tab. Never on Instagram's account check either: no
        Back takes the run past it, and the run stops there."""
        if self._gesture_ruled_out():
            return False
        if self._is_element_present(NAVIGATION_SELECTORS.keyboard_window):
            self._back_one_screen()
            if arrived():
                return True
        for _ in range(max_backs):
            self._back_one_screen()
            if arrived():
                return True
        return False

    def _gesture_ruled_out(self) -> bool:
        """Must no gesture be made on this screen? Yes when the tab bar is gone because Instagram
        is checking the account (the run stops: the detector sets its latch), and yes on a screen
        that could not be read, which may be that check: no Back is pressed blindly."""
        detector = getattr(self, 'problematic_page_detector', None)
        if detector is None:
            return False
        try:
            return bool(detector.is_account_challenged())
        except SnapshotUnavailable as exc:
            self.logger.warning(f"Screen unreadable ({exc}): Instagram's account check cannot be "
                                "ruled out, no Back pressed on it")
            return True

    def _is_search_bar_shown(self) -> bool:
        """The search screen's own bar is on screen (Explore, or the results of a query)."""
        return self._is_element_present(NAVIGATION_SELECTORS.search_screen_bar)
    
    def navigate_to_profile_tab(self) -> bool:
        self.logger.debug("👤 Navigating to profile tab")
        
        max_attempts = 3
        
        for attempt in range(max_attempts):
            from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
            detection = DetectionActions(self.device)
            
            if detection.is_on_own_profile():
                self.logger.debug("✅ Already on own profile")
                return True
            
            # If on someone else's profile, press back to pop navigation stack
            # (Instagram restores nav state after restart, clicking profile_tab
            # when already on the profile tab doesn't navigate back)
            if detection.is_on_profile_screen():
                self.logger.debug(f"📱 On another user's profile, pressing back (attempt {attempt + 1})")
                self._back_one_screen()
                if detection.is_on_own_profile():
                    self.logger.debug(f"✅ Back to own profile via back button (attempt {attempt + 1})")
                    return True

            # A follow list covers the whole screen, bottom bar included: Back returns to the
            # profile it was opened from, without searching 15 s for a tab that is not there.
            if detection.is_followers_list_open() and self._is_instagram_open():
                self.logger.debug(f"📋 On a follow list, pressing back (attempt {attempt + 1})")
                self._back_one_screen()
                if detection.is_on_own_profile():
                    self.logger.debug(f"✅ Back to own profile from the follow list (attempt {attempt + 1})")
                    return True
                continue

            def own_profile_loaded() -> bool:
                # The tab switches at once, the profile header loads seconds later.
                detection.wait_for_profile_screen()
                return detection.is_on_own_profile()

            if self._navigate_to_tab(self.selectors.profile_tab, "profile tab", "👤", own_profile_loaded):
                self.logger.debug(f"✅ Successfully navigated to own profile (attempt {attempt + 1})")
                return True

            self.logger.debug(f"❌ Profile tab not reached (attempt {attempt + 1})")
            if self._gesture_ruled_out():
                return False
            # A full-screen surface hides the bottom bar: the followers / following lists since
            # Instagram 410 (Pixel 3, 2026-09-24), a DM conversation and its keyboard (Pixel 6 Pro,
            # 2026-10-24: two searches of 15 s, one per Back). Back out as the search tab does,
            # one Back at a time until the tab bar shows, never out of Instagram.
            if self._is_instagram_open():
                self._back_out_until(lambda: self._is_element_present(self.selectors.profile_tab))

        self.logger.error("❌ Failed to navigate to own profile after 3 attempts")
        # Debug: dump UI hierarchy to understand what's on screen
        try:
            xml = self.device.dump_hierarchy()
            if xml:
                # Extract text/content-desc attributes for a readable snapshot
                import re
                texts = re.findall(r'text="([^"]+)"', xml)
                descs = re.findall(r'content-desc="([^"]+)"', xml)
                visible_texts = [t for t in texts if t.strip()][:20]
                visible_descs = [d for d in descs if d.strip()][:10]
                self.logger.warning(f"UI texts on screen: {visible_texts}")
                self.logger.warning(f"UI content-descs: {visible_descs}")
        except Exception as e:
            self.logger.debug(f"UI dump failed: {e}")
        return False

    def _back_one_screen(self) -> None:
        """One real Back, through the shared facade's `press_back()`."""
        self.device.press_back()
        self._human_like_delay('navigation')

    # === Screen detection helpers ===

    def _is_screen(self, indicators, screen_name: str = None) -> bool:
        """Generic method to check if on a specific screen."""
        return self._is_element_present(indicators)
    
    def _is_home_screen(self) -> bool:
        return self._is_screen(self.detection_selectors.home_screen_indicators)
    
    def _is_search_screen(self) -> bool:
        return self._is_screen(self.detection_selectors.search_screen_indicators)
    
    def _is_profile_screen(self) -> bool:
        return self._is_screen(self.detection_selectors.profile_screen_indicators)
    
    def _is_followers_list_open(self) -> bool:
        return self._is_screen(self.detection_selectors.followers_list_indicators)
    
    def _is_following_list_open(self) -> bool:
        return self._is_followers_list_open()

    # === Popup/modal handling ===

    def close_modal_or_popup(self) -> bool:
        self.logger.debug("❌ Closing popup/modal")
        
        if self._find_and_click(self.selectors.close_button, timeout=2):
            self._human_like_delay('click')
            return True
        
        if self._find_and_click(self.selectors.back_button, timeout=2):
            self._human_like_delay('click')
            return True
        
        self._press_back(1)
        return True

    def _check_and_close_problematic_pages(self) -> None:
        """Check for and close the problematic pages after a navigation."""
        try:
            result = self.problematic_page_detector.detect_and_handle_problematic_pages()
            if result.get('detected'):
                if result.get('closed'):
                    self.logger.info(f"✅ Popup {result.get('page_type')} fermée automatiquement")
                else:
                    self.logger.warning(f"⚠️ Popup {result.get('page_type')} détectée mais non fermée")
        except SnapshotUnavailable as exc:
            self.logger.warning(f"Popups not checked after the navigation: screen unreadable ({exc})")
        except Exception as e:
            self.logger.debug(f"Erreur lors de la vérification des popups: {e}")
