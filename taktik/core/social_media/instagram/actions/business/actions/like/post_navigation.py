"""Post navigation helpers for the like workflow (open, next, return)."""

import time
import random
import re
from typing import Optional
from loguru import logger

from taktik.core.shared.behavior.grid_entry import plan_prescroll, sample_entry_index, GRID_COLUMNS
from taktik.core.shared.behavior.dwell import content_dwell
from taktik.core.shared.telemetry import emit_step
from ....core.ipc.emitter import IPCEmitter

# Long-run advance mix when browsing a profile's posts. Session memory turns this baseline into
# short brisk/steady/deliberate bursts instead of an independent 85/15 draw on every post.
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

    def _open_entry_post_of_profile(
        self,
        posts_count: int = 0,
        username: str = None,
        *,
        reopening: bool = False,
        posts_to_inspect: int = 0,
    ) -> bool:
        """Open a post to start engaging — but NOT always the top-left (newest) one.

        Humanised entry (see ``shared/behavior/grid_entry``): on a profile large
        enough, optionally scroll the grid down a little first, then open a
        thumbnail chosen with a top-weighted-but-spread distribution and a human
        tap on its real bounds. Always falls back to the legacy "open first post"
        on any problem, so this is a zero-regression replacement of the constant
        entry point.

        ``posts_count`` is the profile's publication count (already read upstream);
        it drives whether pre-scrolling the grid looks natural at all. A reopen after leaving a
        Reel is stricter: it never reuses a cell already opened during this profile visit and seeks
        a new grid row when all currently visible cells have been consumed.
        """
        try:
            thumb_selector = self.detection_selectors.post_thumbnail_selectors[0]

            posts = self._visible_grid_thumbnails(thumb_selector)
            if not posts:
                if reopening:
                    self.logger.info("Profile grid unavailable during Reel exit; stopping safely")
                    return False
                self.logger.debug("Grid not visible — using legacy first-post open")
                return self._open_first_post_of_profile(username=username)

            # 1. Adaptive grid pre-scroll (only on big-enough profiles; human flick).
            prescroll = 0 if reopening else plan_prescroll(int(posts_count or 0))
            for _ in range(prescroll):
                scrolled = self._session_grid_scroll(
                    "profile_grid_prescroll", distance_ratio=0.40, coast=True
                )
                if not scrolled:
                    break
            if prescroll:
                posts = self._visible_grid_thumbnails(thumb_selector)
                if not posts:
                    return self._open_first_post_of_profile(username=username)

            # 2. Open a varied visible thumbnail (top-weighted, spread). Re-entry from a Reel
            # must never pick a cell already visited during this profile pass. If this viewport is
            # exhausted but the profile has more posts, move the grid and retry with absolute cell
            # keys from the live content-desc.
            candidate_posts = posts
            candidate_indexes = list(range(len(posts)))
            if not reopening and int(posts_count or 0) > 0 and int(posts_to_inspect or 0) > 0:
                latest_start = max(
                    1,
                    int(posts_count) - min(int(posts_count), int(posts_to_inspect)) + 1,
                )
                eligible = [
                    (visible_index, post)
                    for visible_index, post in enumerate(posts)
                    if self._grid_entry_position(post, visible_index) <= latest_start
                ]
                if eligible:
                    candidate_indexes = [visible_index for visible_index, _post in eligible]
                    candidate_posts = [post for _visible_index, post in eligible]

            candidate_index = self._choose_session_grid_entry(
                candidate_posts, username=username, require_unseen=reopening
            )
            index = (
                candidate_indexes[candidate_index]
                if candidate_index is not None
                else None
            )
            if index is None and reopening and int(posts_count or 0) > len(posts):
                for _ in range(2):
                    if not self._session_grid_scroll(
                        "profile_grid_reopen_seek", distance_ratio=0.40, coast=False
                    ):
                        break
                    posts = self._visible_grid_thumbnails(thumb_selector)
                    index = self._choose_session_grid_entry(
                        posts, username=username, require_unseen=True
                    )
                    if index is not None:
                        break
            if index is None:
                self.logger.info(
                    "No unseen profile-grid thumbnail remains; stopping instead of reopening "
                    "a post already visited"
                )
                return False
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

            self.scroll_actions._plan_behavior_gesture("profile_grid_open", "tap")
            if not self._human_tap_grid_thumbnail(target):
                target.click()  # centre-click fallback if bounds unreadable

            time.sleep(3)
            if self._is_in_post_view():
                self._remember_session_grid_entry(target, index, username=username)
                self.logger.success("Entry post opened successfully")
                return True

            if reopening:
                self.logger.warning("Unseen grid entry did not open; refusing a repeated fallback")
                return False
            self.logger.warning("Entry post did not open — falling back to first post")
            return self._open_first_post_of_profile(username=username)

        except Exception as e:
            if reopening:
                self.logger.error(f"Error reopening unseen grid post: {e}")
                return False
            self.logger.error(f"Error opening entry post: {e} — falling back to first post")
            try:
                return self._open_first_post_of_profile(username=username)
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
                if not self._session_grid_scroll(
                    "profile_grid_target_seek", distance_ratio=0.40, coast=True
                ):
                    break

            if target is None:
                self.logger.warning(
                    f"Post #{index} (ligne {row}, colonne {col}) introuvable après scroll"
                )
                return False

            self.logger.info(f"Opening post #{index} (ligne {row}, colonne {col})")
            self.scroll_actions._plan_behavior_gesture("profile_grid_open", "tap")
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
                self._remember_session_grid_entry(target, index - 1, username=None)
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
        # Humanized controlled scroll to reveal the grid (was facade swipe_ext / Direction.UP).
        self._session_grid_scroll("profile_grid_reveal", distance_ratio=0.30)
        posts = self.device.xpath(thumb_selector).all()
        if posts:
            return posts
        self._session_grid_scroll("profile_grid_reveal", distance_ratio=0.50)
        return self.device.xpath(thumb_selector).all()

    def _session_grid_scroll(
        self, context: str, distance_ratio: float, coast: bool = False
    ) -> bool:
        """Route profile-grid motion through the same per-session gesture timeline."""
        try:
            _, height = self.device.get_screen_size()
            decision = self.scroll_actions._plan_behavior_gesture(
                context, "flick" if coast else "controlled_swipe"
            )
            distance_px = height * float(distance_ratio) * decision["distance_scale"]
            if coast:
                ok = self.scroll_actions._strong_flick(
                    "up", distance_px=distance_px,
                    velocity_scale=decision["velocity_scale"],
                )
                base_settle = (0.45, 0.75)
            else:
                ok = self.scroll_actions._human_swipe(
                    "up", distance_px=distance_px, controlled=True,
                    velocity_scale=decision["velocity_scale"],
                )
                base_settle = (0.30, 0.55)
            if ok:
                time.sleep(random.uniform(*base_settle) * decision["settle_scale"])
            return bool(ok)
        except Exception as exc:
            self.logger.debug(f"Grid session scroll failed: {exc}")
            return False

    @staticmethod
    def _grid_entry_position(element, index: int) -> int:
        """Return the one-based absolute grid position exposed by Instagram."""
        desc = ""
        try:
            desc = (element.attrib.get("content-desc") or "") if hasattr(element, "attrib") else ""
        except Exception:
            desc = ""
        if not desc:
            try:
                info = getattr(element, "info", {}) or {}
                desc = info.get("contentDescription") or info.get("content-desc") or ""
            except Exception:
                desc = ""
        match = _GRID_POS_RE.search(desc)
        if match:
            return ((int(match.group(1)) - 1) * GRID_COLUMNS + int(match.group(2)))
        return int(index) + 1

    @staticmethod
    def _grid_entry_key(element, index: int, username: str = None) -> str:
        """Stable per-profile cell key from live grid metadata, with an index fallback."""
        position = PostNavigationMixin._grid_entry_position(element, index)
        cell = f"position:{position}"
        return f"{username or 'current-profile'}:{cell}"

    def _choose_session_grid_entry(
        self, posts, username: str = None, *, require_unseen: bool = False
    ) -> Optional[int]:
        keys = [self._grid_entry_key(post, index, username) for index, post in enumerate(posts)]
        chooser = getattr(getattr(self, "behavior_state", None), "choose_grid_entry_index", None)
        if callable(chooser):
            choice = chooser(
                context=username or "current-profile",
                candidate_keys=keys,
                avoid_recent=None,
                require_unseen=require_unseen,
            )
            return int(choice) if choice is not None else None
        return sample_entry_index(len(posts))

    def _remember_session_grid_entry(self, target, index: int, username: str = None) -> None:
        context = username or "current-profile"
        key = self._grid_entry_key(target, index, username)
        position_match = re.search(r":position:(\d+)$", key)
        self._profile_post_cursor = {
            "context": context,
            "position": int(position_match.group(1)) if position_match else None,
        }
        remember = getattr(getattr(self, "behavior_state", None), "remember_grid_entry", None)
        if callable(remember):
            remember(
                context=context,
                key=key,
                index=index,
            )

    def _remember_sequential_profile_post(self) -> None:
        """Mark the next absolute profile position reached through the vertical viewer.

        Grid-only memory is incomplete: after opening position 3 and scrolling to position 4,
        returning from a Reel must not consider position 4 unseen merely because it was reached in
        the viewer. The cursor is reset from every real grid entry and advances only after a
        verified vertical navigation.
        """
        cursor = getattr(self, "_profile_post_cursor", None) or {}
        context = cursor.get("context")
        position = cursor.get("position")
        if not context or position is None:
            return
        next_position = int(position) + 1
        self._profile_post_cursor = {"context": context, "position": next_position}
        remember = getattr(getattr(self, "behavior_state", None), "remember_grid_entry", None)
        if callable(remember):
            remember(
                context=context,
                key=f"{context}:position:{next_position}",
                index=next_position - 1,
            )

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

    def _open_first_post_of_profile(self, username: str = None) -> bool:
        try:
            self.logger.info("Opening first post of profile...")
            
            posts = self.device.xpath(self.detection_selectors.post_thumbnail_selectors[0]).all()
            
            # If no posts visible, try scrolling down slightly to reveal the grid
            # This can happen after follow when suggestions popup was hidden by scrolling up
            if not posts:
                self.logger.debug("No posts visible, scrolling down to reveal grid...")
                self._session_grid_scroll("profile_grid_reveal", distance_ratio=0.30)
                posts = self.device.xpath(self.detection_selectors.post_thumbnail_selectors[0]).all()

            if not posts:
                # Try one more time with a bigger scroll
                self.logger.debug("Still no posts, trying bigger scroll...")
                self._session_grid_scroll("profile_grid_reveal", distance_ratio=0.50)
                posts = self.device.xpath(self.detection_selectors.post_thumbnail_selectors[0]).all()
            
            if not posts:
                self.logger.error("No posts found in grid after scrolling")
                return False
            
            first_post = posts[0]
            self.scroll_actions._plan_behavior_gesture("profile_grid_open", "tap")
            if not self._human_tap_grid_thumbnail(first_post):
                first_post.click()
            self.logger.debug("Clicking on first post...")
            
            time.sleep(3)  # Increased from 2s to 3s for slower devices
            
            if self._is_in_post_view():
                self._remember_session_grid_entry(first_post, 0, username=username)
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
            _, height = self.device.get_screen_size()

            try:
                # Vertical advance to the next post — humanised like the FEED browse:
                # alternate a decisive flick (most of the time) with an occasional slow
                # drag, instead of the single fixed swipe that read as a robotic identical
                # scroll every post. Then a content-aware reading dwell (varied glance +
                # occasional linger) replaces the flat 2s pause.
                mode_decision = self.scroll_actions._choose_advance_mode(
                    "profile_posts",
                    base_drag_probability=dict(_ADVANCE_MODE_WEIGHTS)["drag"],
                )
                mode = mode_decision["mode"]
                distance_scale = float(mode_decision.get("distance_scale", 1.0))
                velocity_scale = float(mode_decision.get("velocity_scale", 1.0))
                dwell_scale = float(mode_decision.get("dwell_scale", 1.0))
                if mode == "drag":
                    advanced = self.scroll_actions._long_drag(
                        direction="up",
                        distance_px=(random.uniform(0.80, 0.90) * height
                                     * distance_scale),
                        guard_start=True,
                        velocity_scale=velocity_scale,
                    )
                else:
                    advanced = self.scroll_actions._strong_flick(
                        direction="up",
                        # Stay below the primitive's safe 0.45h fling cap in most cases so the
                        # session reach multiplier changes real travel instead of being clipped.
                        distance_px=(random.uniform(0.34, 0.41) * height
                                     * distance_scale),
                        guard_start=True,
                        velocity_scale=velocity_scale,
                    )
                # Evaluate the landing exactly like the feed: severity, dump confidence, current
                # session style, and recent corrections decide whether a precise 1:1 lift is useful.
                # A moderate imperfection may remain; a severe half-shown post is always repaired.
                if advanced:
                    try:
                        self.scroll_actions.land_on_post_header()
                    except Exception as land_exc:
                        self.logger.debug(f"land_on_post_header skipped: {land_exc}")

                    # A human GLANCES at each post while scrolling — a short, varied dwell.
                    # The deliberate "open + read the full description" is no longer done on
                    # every advance: it's now an engagement step (see engagement_sequence), so
                    # posts we act on get the full read+reframe and the rest get a glance.
                    time.sleep(content_dwell(0) * dwell_scale)

                if advanced and self._is_in_post_view():
                    self._remember_sequential_profile_post()
                    self.logger.debug(
                        f"Navigation successful via human {mode} "
                        f"(style={mode_decision.get('style')}, "
                        f"burst_left={mode_decision.get('burst_remaining')})"
                    )
                    return True
            except Exception as e:
                self.logger.debug(f"Vertical advance failed: {e}")
            
            try:
                # A horizontal fallback is unsafe here: on a carousel it only changes SLIDE while
                # `_is_in_post_view()` stays true, falsely reporting a new post. Retry vertically
                # with a controlled production gesture instead.
                retry = self.scroll_actions._plan_behavior_gesture(
                    "profile_posts_retry", "controlled_swipe"
                )
                advanced = self.scroll_actions._human_swipe(
                    direction="up",
                    distance_px=0.68 * height * retry["distance_scale"],
                    start_band=(0.78 * height, 0.86 * height),
                    controlled=True,
                    guard_start=True,
                    velocity_scale=retry["velocity_scale"],
                )
                time.sleep(random.uniform(0.25, 0.50) * retry["settle_scale"])
                if advanced:
                    try:
                        self.scroll_actions.land_on_post_header()
                    except Exception as land_exc:
                        self.logger.debug(f"retry land_on_post_header skipped: {land_exc}")
                if advanced and self._is_in_post_view():
                    self._remember_sequential_profile_post()
                    time.sleep(content_dwell(0) * retry["dwell_scale"])
                    self.logger.debug("Navigation successful via controlled vertical retry")
                    return True
            except Exception as e:
                self.logger.debug(f"Controlled vertical retry failed: {e}")
            
            try:
                next_button_selectors = self.post_selectors.next_post_button_selectors
                
                for selector in next_button_selectors:
                    if self.device.xpath(selector).exists:
                        self.device.xpath(selector).click()
                        time.sleep(1)
                        
                        if self._is_in_post_view():
                            self._remember_sequential_profile_post()
                            self.logger.debug("Navigation successful via Next button")
                            return True
            except Exception as e:
                self.logger.debug(f"Next button failed: {e}")
            
            self.logger.warning("All navigation methods failed")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to next post: {e}")
            return False

    def _advance_or_exit_reel(self, is_reel: bool, total_posts_on_profile: int = 0, username: str = None) -> bool:
        """Advance to the next post — but a REEL must be handled specially.

        A reel opened from the grid drops us in the full-screen clips viewer, where the vertical
        advance (_navigate_to_next_post_in_sequence) scrolls the REELS FEED instead of the profile's
        posts, and after the first reel the top-left Back button disappears, trapping the run with no
        way out (device bug). So for a reel we EXIT to the grid (Back still present on this first
        reel) and open another post; for a normal post we advance in-viewer as before. Returns False
        when we couldn't advance (the caller should stop the scroll)."""
        if is_reel:
            return self._return_to_grid_and_open_another_post(total_posts_on_profile, username=username)
        cursor = getattr(self, "_profile_post_cursor", None) or {}
        if (
            int(total_posts_on_profile or 0) > 0
            and cursor.get("position") is not None
            and int(cursor["position"]) >= int(total_posts_on_profile)
        ):
            self.logger.info("Last profile post reached; no vertical advance attempted")
            return False
        return self._navigate_to_next_post_in_sequence()

    def _return_to_grid_and_open_another_post(self, posts_count: int = 0, username: str = None) -> bool:
        """Leave a Reel safely, return to the profile grid, and open an unseen post.

        Swiping vertically from a freshly opened Reel enters Instagram's global Reels feed and
        loses the profile-scoped Back control. Normal posts therefore remain in sequential viewer
        navigation, while this path is reserved for Reel escape (and its Cartography probe).

        Reuses the humanised entry path while requiring a cell not already opened during this
        profile visit. If the viewport is exhausted, that path scrolls the grid to seek a new
        absolute position; it stops instead of looping over an old post. Returns True only if we
        ended up back in a post view."""
        try:
            self.logger.debug("Navigating via grid: back to profile → reopen another post")
            if not self._return_to_profile_from_post():
                # Back didn't land on the grid (still in a post) → let the caller scroll instead.
                self.logger.debug("Grid-return: still in post view after back, aborting")
                return False
            opened = self._open_entry_post_of_profile(
                posts_count, username=username, reopening=True
            )
            if opened:
                self.logger.info("Navigated via grid (back → reopened another post)")
            return bool(opened)
        except Exception as e:
            self.logger.debug(f"Grid-return navigation failed: {e}")
            return False

    def _return_to_profile_from_post(self) -> bool:
        try:
            self.logger.info("Returning to profile from post...")
            
            back_selectors = self.post_selectors.back_button_selectors
            
            for selector in back_selectors:
                if self.device.xpath(selector).exists:
                    decision = self.scroll_actions._plan_behavior_gesture(
                        "profile_viewer_back", "tap"
                    )
                    self.device.xpath(selector).click()
                    time.sleep(random.uniform(0.60, 1.10) * decision["settle_scale"])
                    returned = self._wait_for_post_view_exit()
                    self.logger.debug(f"Returned via back button: {returned}")
                    if returned:
                        return True
                    # The selector was real but the tap was swallowed; continue into the gesture
                    # fallback instead of reporting failure immediately.
                    break
            
            # Humanised downward swipe fallback (sampled geometry, not fixed coords).
            _, height = self.device.get_screen_size()
            dist = height * random.uniform(0.40, 0.55)
            decision = self.scroll_actions._plan_behavior_gesture(
                "profile_viewer_dismiss", "controlled_swipe"
            )
            injected = self.scroll_actions._human_swipe(
                direction="down", distance_px=dist * decision["distance_scale"],
                controlled=True, guard_start=True,
                velocity_scale=decision["velocity_scale"],
            )
            if not injected:
                # The old coordinate fallback moved UP, the opposite of the intended dismiss.
                # Back is directionally correct and does not reintroduce hard-coded coordinates.
                self.device.press("back")
            time.sleep(random.uniform(0.60, 1.10) * decision["settle_scale"])
            returned = self._wait_for_post_view_exit()
            if injected and not returned:
                # A technically injected dismiss can still be ignored by the viewer. Fall back on
                # observed UI state, not only on the primitive's transport-level boolean.
                self.device.press("back")
                returned = self._wait_for_post_view_exit()
            self.logger.debug(f"Returned via downward swipe: {returned}")
            return returned
            
        except Exception as e:
            self.logger.error(f"Error returning to profile: {e}")
            return False

    def _wait_for_post_view_exit(self, attempts: int = 8, interval_s: float = 0.25) -> bool:
        """Wait briefly for a viewer transition instead of sampling the UI at one fixed instant."""
        for attempt in range(max(1, int(attempts))):
            if not self._is_in_post_view():
                return True
            if attempt + 1 < attempts:
                time.sleep(max(0.0, float(interval_s)))
        return False
