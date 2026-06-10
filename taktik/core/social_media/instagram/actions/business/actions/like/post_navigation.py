"""Post navigation helpers for the like workflow (open, next, return)."""

import time
import random
import re
from loguru import logger

from taktik.core.shared.behavior.grid_entry import plan_prescroll, sample_entry_index, GRID_COLUMNS
from taktik.core.shared.behavior.dwell import content_dwell
from taktik.core.shared.telemetry import emit_step
from ....core.ipc.emitter import IPCEmitter

# Advance gesture mix when browsing a profile's posts — same humanised profile as the
# feed (a decisive flick most of the time, an occasional slow drag), instead of the
# old single fixed swipe that read as a robotic, identical scroll every post.
_ADVANCE_MODE_WEIGHTS = (("flick", 0.85), ("drag", 0.15))

# Grid cells expose their position in content-desc ("... à la ligne R, colonne C" /
# "row R, column C"). Lets us narrate the real post position to the copilot.
_GRID_POS_RE = re.compile(r'(?:ligne|row)\D*(\d+)\D+(?:colonne|column)\D*(\d+)', re.IGNORECASE)


class PostNavigationMixin:
    """Mixin providing post navigation methods.

    Must be used with a class that inherits from BaseBusinessAction
    (provides self.device, self.logger, self.post_selectors, self.detection_selectors,
    self.scroll_actions, etc.)
    """

    def _open_entry_post_of_profile(self, posts_count: int = 0, username: str = None) -> bool:
        """Open a post to start engaging — but NOT always the top-left (newest) one.

        Humanised entry (see ``shared/behavior/grid_entry``): on a profile large
        enough, optionally scroll the grid down a little first, then open a
        thumbnail chosen with a top-weighted-but-spread distribution and a human
        tap on its real bounds. Always falls back to the legacy "open first post"
        on any problem, so this is a zero-regression replacement of the constant
        entry point.

        ``posts_count`` is the profile's publication count (already read upstream);
        it drives whether pre-scrolling the grid looks natural at all.
        """
        try:
            thumb_selector = self.detection_selectors.post_thumbnail_selectors[0]

            posts = self._visible_grid_thumbnails(thumb_selector)
            if not posts:
                self.logger.debug("Grid not visible — using legacy first-post open")
                return self._open_first_post_of_profile()

            # 1. Adaptive grid pre-scroll (only on big-enough profiles; human flick).
            prescroll = plan_prescroll(int(posts_count or 0))
            for _ in range(prescroll):
                scrolled = False
                try:
                    scrolled = self.scroll_actions._strong_flick("up")
                except Exception as e:
                    self.logger.debug(f"Grid flick failed: {e}")
                if not scrolled:
                    break
                time.sleep(random.uniform(0.5, 0.8))
            if prescroll:
                posts = self._visible_grid_thumbnails(thumb_selector)
                if not posts:
                    return self._open_first_post_of_profile()

            # 2. Open a varied visible thumbnail (top-weighted, spread).
            index = sample_entry_index(len(posts))
            target = posts[index]
            self.logger.info(
                f"Opening entry post: thumbnail #{index + 1}/{len(posts)} "
                f"(prescroll={prescroll}, profile posts={posts_count})"
            )

            # Narrate the entry decision to the live copilot (Taktik Agent):
            # "profile has N posts → opening post #X". Reuses the instagram_action
            # channel; no-op in standalone / Lab (guarded on username).
            if username:
                self._emit_entry_decision(username, posts_count, prescroll, target, index)

            if not self._human_tap_grid_thumbnail(target):
                target.click()  # centre-click fallback if bounds unreadable

            time.sleep(3)
            if self._is_in_post_view():
                self.logger.success("Entry post opened successfully")
                return True

            self.logger.warning("Entry post did not open — falling back to first post")
            return self._open_first_post_of_profile()

        except Exception as e:
            self.logger.error(f"Error opening entry post: {e} — falling back to first post")
            try:
                return self._open_first_post_of_profile()
            except Exception:
                return False

    def _open_post_at_position(self, index: int) -> bool:
        """Open a SPECIFIC grid post by absolute position (1-based), scrolling the
        grid (human flick) to reveal it if needed. Returns True if the post viewer
        opened. Deterministic — used by the Lab to test post targeting; prod entry
        stays humanised via `_open_entry_post_of_profile`.
        """
        if index < 1:
            index = 1
        row = (index - 1) // 3 + 1
        col = (index - 1) % 3 + 1
        selector = self.detection_selectors.post_grid_cell_by_position(row, col)
        try:
            if not self._visible_grid_thumbnails(self.detection_selectors.post_thumbnail_selectors[0]):
                self.logger.warning("Grid not visible — cannot open post by position")
                return False

            target = None
            for _ in range(6):
                el = self.device.xpath(selector)
                if el.exists:
                    target = el
                    break
                if not self.scroll_actions._strong_flick("up"):
                    break
                time.sleep(random.uniform(0.5, 0.8))

            if target is None:
                self.logger.warning(
                    f"Post #{index} (ligne {row}, colonne {col}) introuvable après scroll"
                )
                return False

            self.logger.info(f"Opening post #{index} (ligne {row}, colonne {col})")
            tapped = False
            try:
                el = target.get(timeout=1.0)
                bounds = tuple(el.bounds)
                if bounds and len(bounds) == 4 and bounds[2] > bounds[0] and bounds[3] > bounds[1]:
                    tapped = bool(self.device.human_tap(bounds))
            except Exception as e:
                self.logger.debug(f"position tap bounds unreadable ({e}); click fallback")
            if not tapped:
                target.click()

            time.sleep(3)
            if self._is_in_post_view():
                self.logger.success(f"Post #{index} opened successfully")
                return True
            self.logger.warning(f"Post #{index} did not open")
            return False

        except Exception as e:
            self.logger.error(f"Error opening post #{index}: {e}")
            return False

    def _emit_entry_decision(self, username, posts_count, prescroll, target, index):
        """Tell the copilot which post we're opening and why (the humanised entry
        decision). Best-effort: reads the chosen thumbnail's grid position from its
        content-desc so the narration says the real post number."""
        try:
            row = col = position = None
            try:
                cd = (target.attrib.get('content-desc') if hasattr(target, 'attrib') else None) or ''
                m = _GRID_POS_RE.search(cd)
                if m:
                    row, col = int(m.group(1)), int(m.group(2))
                    position = (row - 1) * GRID_COLUMNS + col
            except Exception:
                pass
            IPCEmitter.emit_action('entry', username, {
                'posts_count': int(posts_count or 0),
                'prescroll': int(prescroll or 0),
                'visible_index': int(index) + 1,
                'row': row,
                'col': col,
                'position': position,
            })
            # Also on the step_metric channel: the IPC action feeds the copilot
            # narration, but the metrics cards (Choix du post) read step_metric.
            emit_step(
                "post_entry", target=username,
                posts_count=int(posts_count or 0), prescroll=int(prescroll or 0),
                visible_index=int(index) + 1, position=position,
            )
        except Exception as e:
            self.logger.debug(f"entry decision narration failed: {e}")

    def _visible_grid_thumbnails(self, thumb_selector: str):
        """Return the currently rendered grid thumbnails, revealing the grid with a
        small scroll if none are on screen yet (mirrors the legacy reveal logic)."""
        posts = self.device.xpath(thumb_selector).all()
        if posts:
            return posts
        from ....core.device.facade import Direction
        self.device.swipe(Direction.UP, scale=0.3)
        time.sleep(0.5)
        posts = self.device.xpath(thumb_selector).all()
        if posts:
            return posts
        self.device.swipe(Direction.UP, scale=0.5)
        time.sleep(0.5)
        return self.device.xpath(thumb_selector).all()

    def _human_tap_grid_thumbnail(self, element) -> bool:
        """Human-tap a grid thumbnail at a sampled point within its bounds (never the
        exact centre). Returns False if bounds are unreadable so the caller can
        fall back to a plain ``element.click()``."""
        try:
            bounds = getattr(element, "bounds", None)
            if bounds and len(bounds) == 4 and bounds[2] > bounds[0] and bounds[3] > bounds[1]:
                return bool(self.device.human_tap(tuple(bounds)))
        except Exception as e:
            self.logger.debug(f"thumbnail human-tap bounds unreadable ({e}); centre-click fallback")
        return False

    def _open_first_post_of_profile(self) -> bool:
        try:
            self.logger.info("Opening first post of profile...")
            
            posts = self.device.xpath(self.detection_selectors.post_thumbnail_selectors[0]).all()
            
            # If no posts visible, try scrolling down slightly to reveal the grid
            # This can happen after follow when suggestions popup was hidden by scrolling up
            if not posts:
                self.logger.debug("No posts visible, scrolling down to reveal grid...")
                from ....core.device.facade import Direction
                self.device.swipe(Direction.UP, scale=0.3)  # UP = finger moves up = content goes DOWN
                time.sleep(0.5)
                posts = self.device.xpath(self.detection_selectors.post_thumbnail_selectors[0]).all()
            
            if not posts:
                # Try one more time with a bigger scroll
                self.logger.debug("Still no posts, trying bigger scroll...")
                from ....core.device.facade import Direction
                self.device.swipe(Direction.UP, scale=0.5)
                time.sleep(0.5)
                posts = self.device.xpath(self.detection_selectors.post_thumbnail_selectors[0]).all()
            
            if not posts:
                self.logger.error("No posts found in grid after scrolling")
                return False
            
            first_post = posts[0]
            first_post.click()
            self.logger.debug("Clicking on first post...")
            
            time.sleep(3)  # Increased from 2s to 3s for slower devices
            
            if self._is_in_post_view():
                self.logger.success("First post opened successfully")
                return True
            else:
                self.logger.error("Failed to open first post")
                return False
                
        except Exception as e:
            self.logger.error(f"Error opening first post: {e}")
            return False
    
    def _is_in_post_view(self) -> bool:
        try:
            # Use both post_view_indicators and post_detail_indicators for better detection
            post_indicators = self.post_selectors.post_view_indicators + self.post_selectors.post_detail_indicators
            
            for indicator in post_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Post view detected via: {indicator[:50]}...")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking post view: {e}")
            return False
    
    def _navigate_to_next_post_in_sequence(self) -> bool:
        try:
            self.logger.debug("Navigating to next post...")
            
            # Get screen dimensions for adaptive swipe coordinates
            width, height = self.device.get_screen_size()

            try:
                # Vertical advance to the next post — humanised like the FEED browse:
                # alternate a decisive flick (most of the time) with an occasional slow
                # drag, instead of the single fixed swipe that read as a robotic identical
                # scroll every post. Then a content-aware reading dwell (varied glance +
                # occasional linger) replaces the flat 2s pause.
                modes, weights = zip(*_ADVANCE_MODE_WEIGHTS)
                mode = random.choices(modes, weights=weights)[0]
                if mode == "drag":
                    advanced = self.scroll_actions._long_drag(
                        direction="up", distance_px=random.uniform(0.80, 0.90) * height
                    )
                else:
                    advanced = self.scroll_actions._strong_flick(
                        direction="up", distance_px=random.uniform(0.55, 0.72) * height
                    )
                # Land cleanly on the next post — exactly like the FEED does: a variable flick
                # can stop "half-and-half" (end of the post above + start of the one below), so
                # if the incoming post header isn't framed at the top, ONE precise 1:1 lift drag
                # brings it up (moves less than one post pitch → frames the topmost post, never
                # skips). No-op if no header is detected, so it can't regress navigation. A human
                # advances to SEE the next post in full, not stop mid-way.
                try:
                    self.scroll_actions.land_on_post_header()
                except Exception as land_exc:
                    self.logger.debug(f"land_on_post_header skipped: {land_exc}")

                # A human GLANCES at each post while scrolling — a short, varied dwell.
                # The deliberate "open + read the full description" is no longer done on
                # every advance: it's now an engagement step (see engagement_sequence), so
                # posts we act on get the full read+reframe and the rest get a glance.
                time.sleep(content_dwell(0))

                if advanced and self._is_in_post_view():
                    self.logger.debug(f"Navigation successful via human {mode}")
                    return True
            except Exception as e:
                self.logger.debug(f"Vertical advance failed: {e}")
            
            try:
                # Horizontal swipe: from 74% to 19% of width, center Y
                start_x = int(width * 0.74)
                end_x = int(width * 0.19)
                center_y = height // 2
                
                self.device.swipe_coordinates(start_x, center_y, end_x, center_y, duration=0.3)
                time.sleep(1)
                
                if self._is_in_post_view():
                    self.logger.debug("Navigation successful via horizontal swipe")
                    return True
            except Exception as e:
                self.logger.debug(f"Horizontal swipe failed: {e}")
            
            try:
                next_button_selectors = self.post_selectors.next_post_button_selectors
                
                for selector in next_button_selectors:
                    if self.device.xpath(selector).exists():
                        self.device.xpath(selector).click()
                        time.sleep(1)
                        
                        if self._is_in_post_view():
                            self.logger.debug("Navigation successful via Next button")
                            return True
            except Exception as e:
                self.logger.debug(f"Next button failed: {e}")
            
            self.logger.warning("All navigation methods failed")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to next post: {e}")
            return False
    
    def _return_to_profile_from_post(self):
        try:
            self.logger.info("Returning to profile from post...")
            
            back_selectors = self.post_selectors.back_button_selectors
            
            for selector in back_selectors:
                if self.device.xpath(selector).exists:
                    self.device.xpath(selector).click()
                    time.sleep(1.5)
                    self.logger.debug("Returned via back button")
                    return
            
            # Humanised downward swipe fallback (sampled geometry, not fixed coords).
            width, height = self.device.get_screen_size()
            dist = height * random.uniform(0.40, 0.55)
            if not self.scroll_actions._human_swipe(direction="down", distance_px=dist, controlled=True):
                center_x = width // 2
                self.device.swipe_coordinates(center_x, int(height * 0.625), center_x, int(height * 0.21), duration=0.5)
            time.sleep(1.5)
            self.logger.debug("Returned via downward swipe")
            
        except Exception as e:
            self.logger.error(f"Error returning to profile: {e}")
