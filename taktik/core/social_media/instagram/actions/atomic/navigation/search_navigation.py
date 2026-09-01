"""Search-based navigation (profile search, hashtag navigation, content navigation)."""

import time
import random
from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS
from ....ui.selectors.surfaces.story_viewer import STORY_SELECTORS
from taktik.core.clone import get_active_package
from taktik.core.shared.behavior.gesture_primitives import human_hswipe_raw
from ..story_state import parse_story_position


_STORY_TRANSITION_POLL_DELAYS = (0.12, 0.18, 0.28, 0.40)


def _safe_story_advance_zone(screen_width: int, screen_height: int, sticker: Optional[dict]):
    """Return the (x0, y0, x1, y1) tap zone to ADVANCE a story, avoiding an interactive sticker.

    The advance tap lives on the right side, in the mid band (0.30–0.70 h) so it never hits the
    close button (top) or the reply/like toolbar (bottom). When an interactive sticker (countdown,
    poll…) overlaps that band, tapping it would open a blocking consumption sheet — so we pick the
    largest safe sub-band ABOVE or BELOW the sticker, else a sliver to its RIGHT, else a small
    upper-right corner. Pure geometry (no device I/O) so it is unit-tested. `sticker` is a bounds
    dict {left,top,right,bottom} or None."""
    zx0, zy0 = int(screen_width * 0.62), int(screen_height * 0.30)
    zx1, zy1 = int(screen_width * 0.88), int(screen_height * 0.70)
    if not sticker:
        return zx0, zy0, zx1, zy1

    margin = int(screen_height * 0.02)
    st_top = sticker.get("top", 0) - margin
    st_bottom = sticker.get("bottom", 0) + margin
    st_right = sticker.get("right", 0)

    # No vertical overlap with the band → the default zone is already clear.
    if st_bottom <= zy0 or st_top >= zy1:
        return zx0, zy0, zx1, zy1

    min_band = int(screen_height * 0.05)
    above_h = min(zy1, st_top) - zy0
    below_h = zy1 - max(zy0, st_bottom)
    if above_h >= below_h and above_h >= min_band:
        return zx0, zy0, zx1, min(zy1, st_top)
    if below_h >= min_band:
        return zx0, max(zy0, st_bottom), zx1, zy1

    # No safe band above/below → tap to the RIGHT of the sticker if there is room.
    right_x0 = min(st_right + int(screen_width * 0.01), screen_width - int(screen_width * 0.03))
    if screen_width - right_x0 >= int(screen_width * 0.04):
        return right_x0, zy0, int(screen_width * 0.97), zy1

    # Last resort: a small upper-right corner (below the close button, above most stickers).
    return int(screen_width * 0.80), int(screen_height * 0.22), int(screen_width * 0.90), int(screen_height * 0.27)


class SearchNavigationMixin(BaseAction):
    """Mixin: navigate via search (profiles, hashtags) and content navigation (posts, stories, lists)."""

    def navigate_to_profile(self, username: str, deep_link_usage_percentage: int = 0, force_search: bool = False) -> bool:
        """
        Navigate to a user's profile.

        Search FIRST, deep link only as a fallback. A deep link is not an app gesture: it is
        an external ADB intent (`am start -a android.intent.action.VIEW -d
        "https://www.instagram.com/<user>/"`), visible as such to the system and to the app —
        no human has ever opened a profile that way. It used to be the default NINE times out
        of ten, on every profile entry of every workflow. The search path is the one a person
        takes and the one we already use for hashtags: search tab, search bar, typed query,
        tap the result.

        The fallback below is unchanged, so a search that fails still lands via deep link:
        this inverts the preference, it does not remove a capability. Cost: a search costs
        roughly 5-8s against ~2s, paid once per profile entry.

        Args:
            username: The username to navigate to
            deep_link_usage_percentage: Percentage chance to try the deep link FIRST (0-100).
                                        0 (default) = always start with search.
            force_search: If True, never use the deep link at all — not even as a fallback.

        Returns:
            True if navigation successful, False otherwise
        """
        self.logger.info(f"🎯 Navigating to profile @{username}")
        
        # Determine navigation method
        active_pkg = get_active_package()
        is_clone = active_pkg != "com.instagram.android"
        
        if force_search or is_clone:
            use_deep_link = False
            if is_clone:
                self.logger.debug(f"Clone detected ({active_pkg}), forcing search navigation (deep links unsupported)")
            else:
                self.logger.debug("Forced to use search navigation")
        else:
            use_deep_link = random.randint(1, 100) <= deep_link_usage_percentage
        
        if use_deep_link:
            self.logger.debug("Using deep link")
            success = self._navigate_via_deep_link(username)
        else:
            self.logger.debug("Using search")
            success = self._navigate_via_search(username)
        
        if success:
            # Vérifier et fermer les popups problématiques (no extra sleep — deep_link/search already have delays)
            self._check_and_close_problematic_pages()
            return True
        
        # Fallback: try the other method
        if not use_deep_link and not force_search and not is_clone:
            self.logger.debug("Fallback attempt with deep link")
            success = self._navigate_via_deep_link(username)
            if success:
                self._check_and_close_problematic_pages()
                return True
        elif use_deep_link:
            self.logger.debug("Fallback attempt with search")
            success = self._navigate_via_search(username)
            if success:
                self._check_and_close_problematic_pages()
                return True
        
        self.logger.warning(f"Navigation failed to @{username}, but continuing")
        return False

    def _navigate_via_search(self, username: str) -> bool:
        """
        Navigate to a profile using the search feature with human-like typing.
        
        Flow:
        1. Click on search tab (bottom bar)
        2. Click on search bar to activate it
        3. Type username with human-like delays
        4. Wait for results and click on the matching profile
        """
        self.logger.info(f"🔍 Navigating to @{username} via search")
        
        # Step 1: Navigate to search tab
        if not self.navigate_to_search():
            self.logger.error("Cannot access search screen")
            return False
        
        self._human_like_delay('navigation')
        
        # Step 2: Click on search bar to activate it
        # On the explore page, we need to click on the search bar at the top
        search_bar_selectors = NAVIGATION_SELECTORS.explore_search_bar
        
        if not self._find_and_click(search_bar_selectors, timeout=5):
            self.logger.error("Cannot find/click search bar")
            return False
        
        self._human_like_delay('click')
        
        # Wait for keyboard to appear and search field to be active
        time.sleep(0.5)

        # Step 2b: EMPTY the field before typing into it.
        #
        # The keyboard broadcast APPENDS — it types characters, it does not replace a value. When a
        # search finds nothing (a profile that was deleted, banned or renamed), this function
        # returns False and leaves the query sitting in the box. The next profile then typed itself
        # onto the end of the last one — 'deletedusernextuser' — which matches nobody either, so
        # every profile after the first missing one failed in turn. Measured: a qualification run
        # of 50 profiles stopped producing after 7.
        #
        # Cheap and unconditional: clearing an already-empty field costs one broadcast, and makes
        # the search independent of whatever the previous one left behind.
        self._clear_text_with_taktik_keyboard()
        
        # Step 3: Type username using Taktik Keyboard (reliable ADB broadcast)
        if not self._type_with_taktik_keyboard(username):
            self.logger.warning("Taktik Keyboard failed for username, falling back to send_keys")
            self.device.send_keys(username)
        
        # Wait for search results to load
        self._human_like_delay('typing')
        time.sleep(1.5)  # Extra time for Instagram to fetch results
        
        search_result_selectors = NAVIGATION_SELECTORS.search_result_selectors_for_username(username)
        
        # Wait for results to appear
        if self._wait_for_element(search_result_selectors, timeout=5):
            self.logger.debug(f"🔍 Found search result for @{username}, clicking...")
            if self._find_and_click(search_result_selectors, timeout=3):
                self.logger.debug(f"✅ Clicked on search result for @{username}")
                self._human_like_delay('navigation')
                time.sleep(2.0)  # Extra wait for profile screen to fully load
                return self._verify_profile_navigation(username)
            else:
                self.logger.warning(f"Found but could not click on @{username}")
        
        self.logger.warning(f"Could not find @{username} in search results")
        return False

    def navigate_to_hashtag(self, hashtag: str) -> bool:
        try:
            self.logger.debug(f"🏷️ Navigating to hashtag #{hashtag}")
            
            if not self.navigate_to_search():
                self.logger.error("Cannot navigate to search screen")
                return False
            
            search_bar_clicked = self._find_and_click(
                self.detection_selectors.hashtag_search_bar_selectors, timeout=2
            )

            if not search_bar_clicked:
                self.logger.error("Cannot click on search bar")
                return False
            
            self._human_like_delay('input')
            
            hashtag_query = f"#{hashtag}"
            # Use Taktik Keyboard for more reliable typing (especially for # character)
            if not self._type_with_taktik_keyboard(hashtag_query):
                self.logger.warning("Taktik Keyboard failed, falling back to send_keys")
                self.device.send_keys(hashtag_query)
            self._human_like_delay('typing')
            time.sleep(2)
            hashtag_result_selectors = NAVIGATION_SELECTORS.hashtag_result_selectors(hashtag)
            
            hashtag_clicked = self._find_and_click(hashtag_result_selectors, timeout=3)

            if not hashtag_clicked:
                self.logger.error(f"Cannot click on hashtag #{hashtag}")
                return False
            
            self._human_like_delay('navigation')
            time.sleep(2)
            
            hashtag_specific = NAVIGATION_SELECTORS.hashtag_text_contains(hashtag)
            if self.device.xpath(hashtag_specific).exists:
                self.logger.debug(f"✅ Hashtag page #{hashtag} loaded successfully")
                return True
            
            for indicator in self.detection_selectors.hashtag_page_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"✅ Hashtag page #{hashtag} loaded successfully")
                    return True
            
            self.logger.warning(f"Hashtag page #{hashtag} might be loaded but no confirmation")
            return True
            
        except Exception as e:
            self.logger.error(f"Error navigating to hashtag #{hashtag}: {e}")
            return False

    # === Profile verification ===

    def _verify_profile_navigation(self, expected_username: str) -> bool:
        # NOTE: _check_and_close_problematic_pages() removed here - already called by navigate_to_profile()
        
        # === FAST PATH: try the top username selectors directly (up to 3 attempts) ===
        # If one exists, we're on a profile screen AND we have the username (2-3 calls max instead of 18)
        _fast_selectors = PROFILE_SELECTORS.username[:3]
        for _attempt in range(3):
            for selector in _fast_selectors:
                try:
                    el = self.device.xpath(selector)
                    if el.exists:
                        current_username = (el.get_text() or '').strip().replace('@', '')
                        if current_username:
                            expected_clean = self._clean_username(expected_username)
                            current_clean = self._clean_username(current_username)
                            self.logger.debug(f"✅ On profile screen, username: '{current_clean}' vs '{expected_clean}'")
                            return current_clean == expected_clean
                except Exception:
                    continue
            if _attempt < 2:
                self.logger.debug(f"Profile not yet loaded (attempt {_attempt + 1}/3), waiting...")
                time.sleep(1.5)
        
        # === FALLBACK: full check (slower but covers edge cases) ===
        if not self._is_profile_screen():
            self.logger.debug(f"❌ Not on profile screen")
            return False
        
        self.logger.debug(f"✅ On profile screen, verifying username...")
        
        from ..detection import DetectionActions
        detection = DetectionActions(self.device)
        current_username = detection.get_username_from_profile()
        
        if current_username:
            current_username = self._clean_username(current_username)
            expected_clean = self._clean_username(expected_username)
            self.logger.debug(f"Username comparison: '{current_username}' vs '{expected_clean}'")
            return current_username == expected_clean
        
        self.logger.warning(f"⚠️ Could not extract username from profile")
        return True
    
    def is_on_profile(self, username: str) -> bool:
        return self._verify_profile_navigation(username)
    
    def get_current_username(self) -> Optional[str]:
        if not self._is_profile_screen():
            return None
        
        username = self._get_text_from_element(PROFILE_SELECTORS.username)
        return self._clean_username(username) if username else None

    # === Content navigation (lists, posts, stories) ===

    def open_followers_list(self) -> bool:
        self.logger.debug("👥 Opening followers list")
        
        if self._find_and_click(self.profile_selectors.followers_link, timeout=5):
            self._human_like_delay('navigation')
            
            # Wait for the list to load, which can be slow
            time.sleep(2)
            
            # Is the list open?
            is_open = self._is_followers_list_open()
            if is_open:
                self.logger.debug("✅ Followers list opened successfully")
            else:
                self.logger.warning("⚠️ Followers list may not be fully loaded, but continuing...")
                # Carry on even when the detection fails: the list may be open with different différents)
                return True
            
            return is_open
        
        return False
    
    def open_following_list(self) -> bool:
        self.logger.debug("👥 Opening following list")
        
        if self._find_and_click(self.profile_selectors.following_link, timeout=5):
            self._human_like_delay('navigation')
            
            # Wait for the list to load (Instagram can be slow)
            time.sleep(2)
            
            is_open = self._is_following_list_open()
            if is_open:
                self.logger.debug("✅ Following list opened successfully")
            else:
                self.logger.warning("⚠️ Following list may not be fully loaded, but continuing...")
                # Even if detection fails, the list was clicked — proceed
                return True
            
            return is_open
        
        return False

    def navigate_to_next_post(self) -> bool:
        try:
            self.logger.debug("➡️ Navigating to next post")

            # Humanized horizontal swipe to the next post (was a fixed normalized-coord swipe).
            decision = self._plan_behavior_gesture("generic_post_pager", "hswipe")
            ok = human_hswipe_raw(
                self.device, "left", distance_ratio=0.6,
                distance_scale=decision["distance_scale"],
                velocity_scale=decision["velocity_scale"],
            )
            if ok:
                self._human_like_delay('navigation', scale=decision["settle_scale"])
            return bool(ok)
            
        except Exception as e:
            self.logger.error(f"Error navigating to next post: {e}")
            return False

    def _first_interactive_sticker_bounds(self) -> Optional[dict]:
        """Bounds of the first interactive story sticker (countdown, poll…) on screen, else None.

        These stickers open a blocking consumption sheet when tapped, so the advance tap must avoid
        them. Never raises."""
        try:
            for selector in STORY_SELECTORS.interactive_sticker_selectors:
                el = self.device.xpath(selector)
                if el.exists:
                    bounds = el.info.get('bounds', {}) if hasattr(el, 'info') else {}
                    if bounds and bounds.get('right', 0) > bounds.get('left', 0):
                        return bounds
        except Exception:
            pass
        return None

    def _story_transition_signature(self) -> Optional[tuple[bool, tuple]]:
        """Read a lightweight story identity without requesting an explicit hierarchy dump.

        The first item says whether the signature contains a reliable position marker. Weak
        signatures are still useful to prove a change, but never to reject a gesture: two slides
        from the same author can legitimately expose the same rounded timestamp.
        """
        selectors = (
            STORY_SELECTORS.story_viewer_text_container,
            STORY_SELECTORS.story_viewer_title,
            STORY_SELECTORS.story_viewer_timestamp,
            STORY_SELECTORS.story_progress_bar,
            STORY_SELECTORS.story_image,
            STORY_SELECTORS.story_video,
        )
        try:
            elements = self.device.xpath(" | ".join(selectors)).all() or []
        except Exception:
            return None

        identities = []
        positions = set()
        progress_states = []

        for element in elements:
            attributes = getattr(element, "attrib", None) or {}
            resource_id = str(attributes.get("resource-id") or "").casefold()
            text = " ".join(str(attributes.get("text") or "").split()).casefold()
            content_desc = " ".join(
                str(attributes.get("content-desc") or "").split()
            ).casefold()

            if "reel_viewer_text_container" in resource_id or "progress_bar" in resource_id:
                position = parse_story_position(f"{content_desc} {text}")
                if position:
                    positions.add(position)

            if any(token in resource_id for token in (
                "reel_viewer_text_container",
                "reel_viewer_title",
                "reel_viewer_timestamp",
                "reel_media_image",
                "reel_media_video",
            )) and (content_desc or text):
                identities.append((resource_id.rsplit("/", 1)[-1], content_desc, text))

            if "progress_bar" in resource_id:
                selected = str(attributes.get("selected") or "").casefold()
                checked = str(attributes.get("checked") or "").casefold()
                progress_states.append((selected, checked))

        active_progress = any(
            value in {"1", "true"}
            for state in progress_states
            for value in state
        )
        value = (
            tuple(sorted(positions)),
            tuple(sorted(set(identities))),
            tuple(progress_states),
        )
        return bool(positions or active_progress), value

    def _wait_for_story_transition(
        self,
        before: Optional[tuple[bool, tuple]],
    ) -> Optional[bool]:
        """Return True/False when observable, or None to preserve the legacy fallback."""
        if not before or not before[0]:
            return None

        latest = None
        for delay in _STORY_TRANSITION_POLL_DELAYS:
            time.sleep(delay)
            latest = self._story_transition_signature()
            if latest and latest[1] != before[1]:
                return True

        if latest and latest[0] and latest[1] == before[1]:
            return False
        return None

    def navigate_to_next_story(self, *, settle: bool = True) -> bool:
        try:
            decision = self._plan_behavior_gesture("story_advance", "tap")
            screen_width = self.device.info.get('displayWidth', 1080)
            screen_height = self.device.info.get('displayHeight', 1920)

            # Advance zone (right side, mid band) — computed to AVOID any interactive sticker
            # (countdown, poll…) so a mis-tap never opens its blocking consumption sheet.
            sticker = self._first_interactive_sticker_bounds()
            if sticker:
                self.logger.debug(f"🎯 Interactive story sticker detected {sticker} — steering advance tap around it")
            zx0, zy0, zx1, zy1 = _safe_story_advance_zone(screen_width, screen_height, sticker)
            right_zone = (zx0, zy0, zx1, zy1)

            tap_x = (zx0 + zx1) // 2
            tap_y = (zy0 + zy1) // 2
            before_signature = self._story_transition_signature()

            # Human-tap a varied point in the (sticker-safe) right-side advance zone; quick tap so a
            # held press never pauses the story. Fall back to the zone centre if sampling fails.
            if not self.device.human_tap(right_zone, quick=True):
                self.logger.debug(f"👆 Tap for next story: ({tap_x}, {tap_y})")
                self.device.click(tap_x, tap_y)

            transition = self._wait_for_story_transition(before_signature)
            if transition is False:
                self.logger.debug("Story advance gesture was injected but the slide did not change")
                return False
            if transition is True:
                if settle:
                    self._human_like_delay(
                        "story_transition", scale=decision["settle_scale"]
                    )
                self.logger.debug("✅ Story transition confirmed")
                return True

            # The viewer check below is the functional transition wait. By default the atomic action
            # owns one human beat; StoryBusiness passes settle=False and applies its configured range.
            # It is retained for viewers that expose no reliable position marker.
            for indicator in self.detection_selectors.story_viewer_indicators:
                if self._wait_for_element(indicator, timeout=2):
                    if settle:
                        self._human_like_delay(
                            "story_transition", scale=decision["settle_scale"]
                        )
                    self.logger.debug("✅ Still in stories")
                    return True
            
            self.logger.debug("ℹ️ No more stories or end of stories")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to next story: {e}")
            return False

    def navigate_to_previous_story(self) -> bool:
        """Return to the previous story with the shared horizontal production gesture."""
        try:
            decision = self._plan_behavior_gesture("story_previous", "hswipe")
            before_signature = self._story_transition_signature()
            ok = self.device.human_hswipe(
                "right",
                distance_scale=decision["distance_scale"],
                velocity_scale=decision["velocity_scale"],
            )
            if not ok:
                return False

            transition = self._wait_for_story_transition(before_signature)
            if transition is False:
                self.logger.debug("Previous-story gesture was injected but the slide did not change")
                return False

            self._human_like_delay(
                "story_transition", scale=decision["settle_scale"]
            )
            return True
        except Exception as e:
            self.logger.error(f"Error navigating to previous story: {e}")
            return False
