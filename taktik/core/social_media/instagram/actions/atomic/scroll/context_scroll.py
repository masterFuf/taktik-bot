"""Context-specific scroll actions (followers list, comments, post grid, feed-down) + load more
and smart scroll.

The INTELLIGENT feed scroll (advance-to-next-post, framing, stop-on-metadata, reading, ad/suggested
skip, browse session) lives in `feed_scroll.py`; the humanized gesture/dwell primitives live in
`taktik.core.shared.behavior`. This module keeps only the simple, surface-specific scrolls used by
the followers / comments / grid flows.
"""

from ...core.base_action import BaseAction
from ....ui.selectors.surfaces.post.comments import POST_COMMENTS_SELECTORS


def comments_scroll_path(device, screen_width: int, screen_height: int, logger=None):
    """Return `((start_x, start_y), (end_x, end_y))` for a scroll CONTAINED in the comments list.

    Scoped to the list's own bounds on purpose: the comments sheet floats over the post, so a
    full-screen gesture starts on the post or the navigation bar behind it. When the list exposes
    no readable bounds it falls back to a fraction of the screen — never to a pixel constant, which
    would describe one device and misfire on every other.

    Module-level and bounds-only (it computes, it does not swipe) so every caller shares the one
    geometry: the IG action below, and the persona-analysis bridge, which held a duplicate written
    in raw pixels.
    """
    try:
        comments_list = device.xpath(POST_COMMENTS_SELECTORS.comments_list_selector())
        if comments_list.exists:
            bounds = (comments_list.info or {}).get("bounds") or {}
            if bounds:
                left = bounds.get("left", 0)
                top = bounds.get("top", int(screen_height * 0.07))
                right = bounds.get("right", screen_width)
                bottom = bounds.get("bottom", int(screen_height * 0.83))
                center_x = (left + right) // 2
                return ((center_x, top + int((bottom - top) * 0.75)),
                        (center_x, top + int((bottom - top) * 0.25)))
    except Exception as exc:
        if logger is not None:
            logger.debug(f"Could not read comments list bounds: {exc}")
    return ((screen_width // 2, int(screen_height * 0.75)),
            (screen_width // 2, int(screen_height * 0.30)))


class ContextScrollMixin(BaseAction):
    """Mixin: context-specific scrolls (followers, comments, feed, grid) + load more + smart scroll."""

    def scroll_followers_list_down(self, duration: float = 0.8, distance_ratio: float = 0.30) -> bool:
        self.logger.debug("👥 Scrolling followers list down")

        try:
            # Humanized controlled scroll (varied start point / sampled curve) instead of a
            # fixed-centre swipe — coast=False keeps the travel precise so we don't skip rows.
            self.device.human_scroll("down", distance_ratio=distance_ratio)
            self._human_like_delay('scroll')
            return True

        except Exception as e:
            self.logger.error(f"Error scrolling followers list: {e}")
            return False

    def scroll_comments_down(self) -> bool:
        """Scroll down in the comments bottom sheet view.

        NOTE: kept on the bounds-scoped raw swipe (not device.human_scroll) on purpose — the
        humanized sampler uses full-screen geometry and would start the gesture OUTSIDE the
        comments sheet (on the post/nav behind it). Humanizing this needs a bounds-aware variant
        (a start_band derived from the sheet bounds) — tracked as a deferred follow-up.
        """
        self.logger.debug("💬 Scrolling comments list down")

        try:
            (start_x, start_y), (end_x, end_y) = comments_scroll_path(
                self.device, int(self.screen_width), int(self.screen_height), self.logger
            )
            self.logger.debug(f"💬 Scrolling in comments: ({start_x}, {start_y}) → ({end_x}, {end_y})")
            self.device.swipe_coordinates(start_x, start_y, end_x, end_y, 0.6)
            self._human_like_delay('scroll')
            return True

        except Exception as e:
            self.logger.error(f"Error scrolling comments list: {e}")
            return False

    def scroll_post_grid_down(self) -> bool:
        self.logger.debug("📸 Scrolling post grid down")

        try:
            decision = self._plan_behavior_gesture("profile_grid_scroll", "controlled_swipe")
            ok = self._human_swipe(
                "up",
                distance_px=0.5 * self.screen_height * decision["distance_scale"],
                controlled=True,
                velocity_scale=decision["velocity_scale"],
            )
            if ok:
                self._human_like_delay('scroll', scale=decision["settle_scale"])
            return bool(ok)

        except Exception as e:
            self.logger.error(f"Error scrolling post grid: {e}")
            return False

    def scroll_feed_down(self) -> bool:
        self.logger.debug("📱 Scrolling feed down")

        try:
            decision = self._plan_behavior_gesture("generic_feed_scroll", "controlled_swipe")
            ok = self._human_swipe(
                "up",
                distance_px=0.4 * self.screen_height * decision["distance_scale"],
                controlled=True,
                velocity_scale=decision["velocity_scale"],
            )
            if ok:
                self._human_like_delay('scroll', scale=decision["settle_scale"])
            return bool(ok)

        except Exception as e:
            self.logger.error(f"Error scrolling feed: {e}")
            return False

    def check_and_click_load_more(self) -> bool:
        try:
            for selector in self.detection_selectors.load_more_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        self.logger.info(f"🔍 'Load more' button found with: {selector}")
                        element.click()
                        self.logger.success("✅ 'Load more' button clicked - loading 25 new followers")

                        self._human_like_delay('load_more')
                        return True

                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {e}")
                    continue

            for selector in self.detection_selectors.end_of_list_indicators:
                try:
                    if self.device.xpath(selector).exists:
                        self.logger.info(f"🏁 End of list detected with: {selector}")
                        return False
                except Exception:
                    continue

            self.logger.debug("🔍 No 'Voir plus' button found on screen")
            return None

        except Exception as e:
            self.logger.error(f"Error checking 'Load more' button: {e}")
            return False

    def smart_scroll_to_load_content(self, content_type: str = "posts", max_scrolls: int = 5) -> int:
        self.logger.debug(f"🧠 Smart scrolling to load {content_type}")

        scroll_count = 0

        for i in range(max_scrolls):
            if content_type == "posts":
                success = self.scroll_post_grid_down()
            elif content_type == "followers":
                success = self.scroll_followers_list_down()
            elif content_type == "feed":
                success = self.scroll_feed_down()
            else:
                success = self.scroll_down()

            if success:
                scroll_count += 1
                self._random_sleep(2.0, 3.0)
            else:
                break

        self.logger.debug(f"✅ {scroll_count} scrolls performed for {content_type}")
        return scroll_count
