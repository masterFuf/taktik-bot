"""How a human READS the post currently on screen — caption, carousel, content-aware dwell.

`PostReadingMixin` is the reading half of the intelligent feed scroll, extracted so it can be
reused on every surface that shows a post as a feed-style row — the home FEED and the PROFILE
POST VIEWER (browsing a user's posts in the like workflow) render the same components
(`IgTextLayoutView` caption + '… plus'/'… more' expander, carousel viewpager with its 'N/M'
index), so reading behaves identically on both.

Behaviours: expand & read a truncated caption (tap the expander, gently scroll the revealed
text into view), browse 1-2 carousel slides, and `human_reading_pause` — the one-call reading
beat whose TOTAL time matches the CONTENT (image glance vs prose-proportional reading, from
`taktik.core.shared.behavior.dwell`).

Pure mixin — host must expose `self.device` (facade with `snapshot()` and
`click_coordinates`), `self.screen_height`, `self.logger`, and the `_long_drag` gesture
primitive (shared `GestureMixin`). `FeedScrollMixin` inherits this; the like workflow reaches
it through its composed `scroll_actions`.
"""

import re
import time
import random
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, cast

from taktik.core.social_media.instagram.ui.caption_hygiene import clean_post_caption
from taktik.core.social_media.instagram.ui.extractors import count_from_counter_label, username_from_author_header
from taktik.core.social_media.instagram.ui.labels import is_liked_heart
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS
from taktik.core.shared.behavior.dwell import content_dwell, caption_prose_chars, MIN_DWELL_S
from taktik.core.shared.behavior.gesture import SWIPE_FLOOR_H
from taktik.core.shared.text import text_lost_emoji

if TYPE_CHECKING:
    from loguru import Logger

    from taktik.core.shared.device.facade import BaseDeviceFacade

# uiautomator bounds string: "[left,top][right,bottom]" — shared with the feed engine.
_BOUNDS_RE = re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')

# Carousel index "N/M" (pattern from the centralized feed-scroll selectors).
_CAROUSEL_INDEX_RE = re.compile(FS.carousel_index_pattern)

# Reading scrolls are slow 1:1 drags (no coast) — same velocity band as the feed's drag profile.
_READ_DRAG_VEL_PXS = (1500.0, 2200.0)

# Share of reading pauses that expand a truncated caption (a human doesn't always tap
# 'more'). Lowered from 0.85 after a real run showed nearly every description being
# opened — too eager to read as human. Tunable; will move to the behaviour profile.
_EXPAND_CAPTION_PROB = 0.45

# Below this cumulated reveal-scroll distance the post is still framed (image + button
# row on screen) → no reframe needed after reading.
_REFRAME_MIN_PX = 120

# The way back after reading is measured on the screen: the read post's caption (else its header)
# says how far it is from where it sat, and each gesture closes that gap, the first one a little
# short so the post comes back into view without being passed.
_REFRAME_FIRST_MOVE = (0.85, 0.95)       # share of the measured gap asked by the first gesture
_REFRAME_TOLERANCE_H = 0.03              # the caption is "back" within this share of the screen
_REFRAME_CHECKS = 3                      # gestures at most, each followed by a screen check
# Characters of the truncated caption kept to recognise it once expanded.
_CAPTION_ANCHOR_CHARS = 60

# Showing the framed post's button row when it runs under the bottom of the list (the like needs
# its heart): one 1:1 drag lifts the post until its header sits this share of the screen under the
# top of the list, so the row shows and the header, the post's identity, stays on screen. A drag
# never travels less than the swipe floor (`SWIPE_FLOOR_H`): it may carry up to this share of the
# header under the top, where its description is still read; when even the floor would carry more,
# the header is at the top already (the post is taller than the list) and nothing is dragged. A
# header in the lower half of the list belongs to a post mostly under the screen, which a like
# must not bring up.
_SHOW_BUTTONS_HEADER_MARGIN_H = (0.005, 0.02)
_SHOW_BUTTONS_HEADER_HIDDEN_MAX = 0.5
_SHOW_BUTTONS_MAX_HEADER_SHARE = 0.5

# Reading a caption that sits under the bottom of the screen (a tall video, a small phone): the post
# is lifted by reading drags until its caption, or its end, shows. A post whose header sits in the
# lower half of the list is mostly under the screen and is not lifted (the same bound as the like's).
# Once lifted, the post's own header is recognised where the drags carried it, within this share of
# the screen plus this share of the distance dragged: the next post may carry the same description.
_CAPTION_LIFTS = 2
_LIFTED_HEADER_TOLERANCE_H = 0.10
_LIFTED_HEADER_TOLERANCE_SHARE = 0.25


class PostReadingMixin:
    """Mixin: human reading of the on-screen post (caption expand/read, carousel browse,
    content-aware dwell). Host must expose `self.device`, `self.screen_height`, `self.logger`
    and `_long_drag`."""

    # What the host provides, declared as an interface would be (no value: nothing is shadowed).
    device: "BaseDeviceFacade"
    logger: "Logger"
    screen_height: int
    _long_drag: Callable[..., bool]
    _human_swipe: Callable[..., bool]
    _human_horizontal_swipe: Callable[..., bool]

    def _dump_root(self):
        """The tree of one screen photo (one dump; the tree `d.xpath()` sees), or None. Used by
        the reading actions; called during a multi-second reading pause, so its freeze overlaps
        the dwell (invisible)."""
        try:
            root = self.device.snapshot().root
            remember_geometry = getattr(self, "_remember_post_action_geometry", None)
            if callable(remember_geometry):
                remember_geometry(root)
            return root
        except Exception as e:
            self.logger.debug(f"dump_root failed: {e}")
            return None

    def expand_caption_if_truncated(self, zone: Optional[tuple] = None) -> bool:
        """If the dominant on-screen post has a truncated caption, tap its '… plus'/'… more'
        expander to read the full text — like a human pausing on a post. On v410 the caption
        is an empty-resource-id `IgTextLayoutView` whose dedicated expander is a child Button with
        content-desc EXACTLY 'plus' (FR) / 'more' (EN). We click that exact button (a random point
        in its bounds, humanised) — never `contains('plus')`, so the Sponsored 'En savoir plus' /
        'Learn more' ad CTA (a link) is excluded. Returns True if a caption was expanded.

        When a post is framed, only a caption inside its window is read: the one above belongs to
        the previous post, whose tail may still show at the top. `zone` (top, bottom) replaces that
        window when the post being read was lifted and its header left the screen
        (`_lifted_post_zone`)."""
        root = self._dump_root()
        if root is None:
            return False
        window = self._framed_window(root) if zone is None else None
        if zone is not None:
            span = zone
        elif window is not None:
            span = (window["header_bounds"][1], window["window_bottom"])
        else:
            span = None
        best = None  # (visible_height, (l, t, r, b), caption text, caption top)
        for node in root.iter():
            if node.tag != FS.caption_layout_class:
                continue
            layout = self._node_bounds(node)
            if span is not None and layout is not None and not (
                span[0] <= layout[1] and layout[3] <= span[1]
            ):
                continue
            target = None
            for child in node.iter():
                if child is node:
                    continue
                if (child.tag == FS.caption_expand_class
                        and child.get("clickable") == "true"
                        and (child.get("content-desc") or "").strip() in FS.caption_expand_descs):
                    target = child
                    break
            if target is None:   # fallback: a truncated layout whose text ends with the label
                txt = (node.get("text") or "").rstrip()
                if not txt.endswith(FS.caption_expand_suffixes):
                    continue
                target = node
            mc = _BOUNDS_RE.search(target.get("bounds", ""))      # where to click (the expander)
            ml = _BOUNDS_RE.search(node.get("bounds", ""))        # the caption layout (for ranking)
            if not mc or not ml:
                continue
            l, t, r, b = (int(mc.group(i)) for i in range(1, 5))
            if t < 0 or b > 0.93 * self.screen_height:   # must be fully on screen, off the tab bar
                continue
            if span is not None and b > span[1]:
                continue   # the expander runs under the bottom bar (or the next post)
            # rank by the caption layout's visible height → the dominant, fully-shown post's caption
            vis_h = int(ml.group(4)) - int(ml.group(2))
            if best is None or vis_h > best[0]:
                best = (vis_h, (l, t, r, b), node.get("text") or "", int(ml.group(2)))
        if best is None:
            return False
        l, t, r, b = best[1]
        # What the way back checks against: the caption, recognised by its text, and where it sat;
        # the post's header too, for when the caption is off screen.
        prefix = self._caption_anchor_text(best[2])
        self._reading_anchor = {
            "caption": prefix,
            "top": best[3],
            "header": window["header_desc"] if window is not None else "",
            "header_top": window["header_bounds"][1] if window is not None else None,
        } if prefix else None
        x = random.randint(min(l + 1, r), max(l + 1, r - 1))
        y = random.randint(min(t + 1, b), max(t + 1, b - 1))
        self.device.click_coordinates(x, y)
        self.logger.debug(f"📖 expanded truncated caption at ({x},{y})")
        # The expanded text usually runs below the fold (the expander sat low). Scroll a little to
        # read it, like a human reading on (gentle, smooth), instead of "opening" a caption nobody
        # can see. No-op if the whole caption already fits. The scrolled distance is remembered so
        # the reading pause can REFRAME the post afterwards (scroll back up to image + buttons).
        time.sleep(random.uniform(0.4, 0.8))   # let it expand + a beat before reading
        self._last_reveal_scroll_px = self._reveal_expanded_caption()
        return True

    def _reading_drag_up(self) -> int:
        """One reading drag: the content lifted by 20 to 30 % of the screen, slowly (1:1, no coast),
        then a reading beat. Returns the distance asked (px)."""
        motor_provider = getattr(self, "_motor_modulation", None)
        motor = (motor_provider("caption_read") if callable(motor_provider) else {
            "distance_scale": 1.0,
            "velocity_scale": 1.0,
            "settle_scale": 1.0,
            "dwell_scale": 1.0,
        })
        dist = (random.uniform(0.20, 0.30) * self.screen_height
                * motor["distance_scale"])
        self._long_drag(
            "up", distance_px=dist, vel_range=_READ_DRAG_VEL_PXS, guard_start=True,
            velocity_scale=motor["velocity_scale"],
        )
        time.sleep(random.uniform(0.7, 1.4) * motor["dwell_scale"])
        return int(dist)

    def _reveal_expanded_caption(self, max_scrolls: int = 2) -> int:
        """After expanding a caption, gently scroll so its now-visible text comes INTO view — a
        human reads it, they don't open a caption that stays below the fold. Each scroll is a slow
        drag (smooth) with a reading beat; stops once no caption extends below the fold. Returns
        the TOTAL distance scrolled in px (0 if none) so the caller can reframe the post after."""
        fold = int(0.86 * self.screen_height)
        scrolled_px = 0
        for _ in range(max_scrolls):
            root = self._dump_root()
            if root is None:
                break
            below = None    # tallest caption whose bottom runs past the fold
            for node in root.iter():
                if node.tag != FS.caption_layout_class:
                    continue
                m = _BOUNDS_RE.search(node.get("bounds", ""))
                if not m:
                    continue
                t, b = int(m.group(2)), int(m.group(4))
                if b > fold and (below is None or (b - t) > below):
                    below = b - t
            if below is None:
                break
            scrolled_px += self._reading_drag_up()
        if scrolled_px:
            self.logger.debug(f"📖 scrolled {scrolled_px}px to read the expanded caption")
        return scrolled_px

    @staticmethod
    def _caption_anchor_text(text: str) -> str:
        """The start of a truncated caption, as it will still start once expanded: the expander
        label and the ellipsis removed, cut to `_CAPTION_ANCHOR_CHARS`."""
        body = (text or "").rstrip()
        for suffix in FS.caption_expand_suffixes:
            if body.endswith(suffix):
                body = body[: -len(suffix)]
                break
        return body.rstrip("… .")[:_CAPTION_ANCHOR_CHARS]

    def _read_post_offset(self, anchor: dict) -> Optional[int]:
        """How far the read post is from where it sat (px, positive = lower), from one fresh dump:
        by its caption, found by its text, else by its header, found by its description. None
        when neither is on screen. A node cut by the top of the list reports its visible top."""
        root = self._dump_root()
        if root is None:
            return None
        header_top = None
        for node in root.iter():
            short = node.get("resource-id", "").rsplit("/", 1)[-1]
            if node.tag == FS.caption_layout_class:
                if anchor["caption"] and (node.get("text") or "").startswith(anchor["caption"]):
                    bounds = self._node_bounds(node)
                    if bounds:
                        return bounds[1] - anchor["top"]
            elif (short == FS.profile_header_id and anchor.get("header")
                  and (node.get("content-desc") or "").strip() == anchor["header"]):
                bounds = self._node_bounds(node)
                if bounds and header_top is None:
                    header_top = bounds[1]
        if header_top is not None and anchor.get("header_top") is not None:
            return header_top - anchor["header_top"]
        return None

    def _swipe_content_down(self, distance_px: float) -> None:
        """Bring the content DOWN by about `distance_px`: 1-2 controlled gestures (1:1 track, no
        fling) starting HIGH so the finger has room to travel down."""
        h = int(self.screen_height)
        gestures = 1 if distance_px <= 0.45 * h else 2
        per = distance_px / gestures
        for _ in range(gestures):
            self._human_swipe(direction="down", distance_px=per,
                              start_band=(0.18 * h, 0.32 * h), controlled=True,
                              guard_start=True)
            time.sleep(random.uniform(0.25, 0.55))

    def _reframe_post_after_reading(self, scrolled_px: int) -> bool:
        """Scroll BACK UP after reading a caption so the post is framed again (image +
        like/comment button row on screen) — what a human does before acting on the post.
        Without this, everything after the reading acts on a mis-framed screen: the
        double-tap band can hit the caption or the NEXT post's image, the generic
        like/comment button selectors can match the next post's row, and the AI
        smart-comment screenshot captures the caption zone instead of the image.

        The way back is measured on the screen, never computed: a drag loses its touch slop, a
        sampled path can be clamped, and a list may coast after a swipe, so neither the distance
        the reveal ASKED for nor the one the way back asks for is the distance the content
        travels. The read post's caption (found by its text), else its header (found by its
        description), says how far the post is from where it sat. Each gesture then closes that
        gap, the first one a little short of it so the post is not passed. Returns True once the
        post is back where it was, False when the screen never showed it back: nothing should
        then act on this screen.
        """
        if scrolled_px <= 0:
            return True
        h = int(self.screen_height)
        anchor = getattr(self, "_reading_anchor", None)
        try:
            if not anchor:
                self._swipe_content_down(scrolled_px * random.uniform(*_REFRAME_FIRST_MOVE))
                self.logger.warning("Post brought back after reading, unchecked: no caption to check")
                return False
            offset = None
            for attempt in range(_REFRAME_CHECKS + 1):
                offset = self._read_post_offset(anchor)
                if attempt == 0 and offset is not None and offset > _REFRAME_TOLERANCE_H * h:
                    # Reading only lifts a post: seen lower than it sat before any way back, this
                    # is another post with the same description (the next one, same author and day).
                    offset = None
                if offset is not None and abs(offset) <= _REFRAME_TOLERANCE_H * h:
                    self.logger.debug(f"📐 reframed post after reading ({offset:+d}px)")
                    return True
                if attempt >= _REFRAME_CHECKS:
                    break
                if offset is None:
                    if attempt:
                        break   # lost from sight after a gesture: no guess about where it went
                    # The whole post scrolled away while reading: back by what the reveal asked.
                    self._swipe_content_down(scrolled_px * random.uniform(*_REFRAME_FIRST_MOVE))
                elif offset > 0:
                    self._long_drag("up", distance_px=offset, vel_range=_READ_DRAG_VEL_PXS,
                                    guard_start=True)
                    time.sleep(random.uniform(0.25, 0.55))
                else:
                    share = random.uniform(*_REFRAME_FIRST_MOVE) if attempt == 0 else 1.0
                    self._swipe_content_down(-offset * share)
            where = "not on screen" if offset is None else f"{offset:+d}px from where it was"
            self.logger.warning(f"Post not brought back after reading: {where}")
            return False
        except Exception as e:
            self.logger.warning(f"Post reframe after reading failed: {e}")
            return False

    def browse_carousel_slides(self) -> int:
        """If the dominant on-screen post is a multi-slide carousel, swipe through 1-2 slides like
        a human. Detect via `carousel_viewpager`/`carousel_media_group` + the authoritative 'N/M'
        index text (`carousel_index_indicator_text_view`); swipe horizontally INSIDE the media band
        (vertical centre, |dy|≈0, travel ~60% width → pages the slide, never opens the post, never
        reads as a story-swipe), stop at the last slide. Returns the number of slides advanced."""
        swiped = 0
        for _ in range(2):   # at most 2 slides
            root = self._dump_root()
            if root is None:
                self._last_carousel_skip_reason = "hierarchy_unavailable"
                break
            candidate = self._current_framed_carousel(root)
            if candidate is None:
                break
            (l, t, r, b), cur, total = candidate
            if cur >= total:
                self._last_carousel_skip_reason = "last_slide"
                break
            plan_provider = getattr(self, "_plan_behavior_gesture", None)
            decision = (plan_provider("carousel_slide", "hswipe")
                        if callable(plan_provider) else {
                            "distance_scale": 1.0,
                            "velocity_scale": 1.0,
                            "dwell_scale": 1.0,
                        })
            if not self._human_horizontal_swipe(
                "left",
                distance_ratio=0.60,
                bounds=(l, t, r, b),
                distance_scale=decision["distance_scale"],
                velocity_scale=decision["velocity_scale"],
            ):
                break
            self._last_carousel_behavior = dict(decision)
            swiped += 1
            time.sleep(random.uniform(0.6, 1.2) * decision["dwell_scale"])
            if cur + 1 >= total:
                break
        if swiped:
            self.logger.debug(f"🖼️ carousel: swiped {swiped} slide(s)")
        return swiped

    @staticmethod
    def _node_bounds(node):
        match = _BOUNDS_RE.search(node.get("bounds", ""))
        if not match:
            return None
        return tuple(int(match.group(i)) for i in range(1, 5))

    def _current_framed_carousel(self, root):
        """Find an unambiguous carousel belonging to the fully framed current post.

        The header, complete media, ``N/M`` indicator and engagement row must all be
        associated within one post interval in the same hierarchy dump. Partial media
        is never clamped into an apparently valid band.
        """
        height = int(self.screen_height)
        top_limit, bottom_limit = 0, height
        headers, like_rows, medias, indexes = [], [], [], []
        media_ids = (FS.carousel_viewpager_id, FS.carousel_media_group_id)

        for node in root.iter():
            short = node.get("resource-id", "").rsplit("/", 1)[-1]
            bounds = self._node_bounds(node)
            if short == FS.action_bar_id and bounds:
                top_limit = max(top_limit, bounds[3])
            elif short == FS.tab_bar_id and bounds:
                bottom_limit = min(bottom_limit, bounds[1])
            elif short == FS.header_id and bounds:
                headers.append((bounds, node))
            elif short == FS.like_button_id and bounds:
                like_rows.append((bounds, node))
            elif short in media_ids and bounds:
                medias.append((short == FS.carousel_viewpager_id, bounds, node))
            elif short == FS.carousel_index_id:
                match = _CAROUSEL_INDEX_RE.match(
                    (node.get("text") or node.get("content-desc") or "").strip()
                )
                if match:
                    indexes.append((
                        int(match.group(1)), int(match.group(2)), bounds, node
                    ))

        visible_headers = sorted(
            (
                item for item in headers
                if item[0][1] >= top_limit and item[0][3] <= bottom_limit
            ),
            key=lambda item: item[0][1],
        )
        if not visible_headers or not like_rows or not medias or not indexes:
            self._last_carousel_skip_reason = "missing_post_anchors"
            return None

        candidates = []
        all_header_tops = sorted(bounds[1] for bounds, _node in headers)
        for preferred, media_bounds, media_node in medias:
            left, top, right, bottom = media_bounds
            if (left >= right or top >= bottom or top < top_limit
                    or bottom > bottom_limit):
                continue

            preceding = [item for item in visible_headers if item[0][1] <= top]
            if not preceding:
                continue
            header_bounds, _header_node = max(
                preceding, key=lambda item: item[0][1]
            )
            next_headers = [value for value in all_header_tops if value > header_bounds[1]]
            post_bottom = min(next_headers) if next_headers else bottom_limit
            if bottom > post_bottom:
                continue

            matching_likes = [
                bounds for bounds, _node in like_rows
                if bounds[1] >= bottom and bounds[3] <= post_bottom
                and bounds[1] >= top_limit and bounds[3] <= bottom_limit
            ]
            if not matching_likes:
                continue

            for current, total, index_bounds, index_node in indexes:
                related_in_tree = (
                    media_node in index_node.iterancestors()
                    or index_node in media_node.iterancestors()
                )
                inside_media = False
                if index_bounds:
                    center_x = (index_bounds[0] + index_bounds[2]) / 2
                    center_y = (index_bounds[1] + index_bounds[3]) / 2
                    inside_media = (
                        left <= center_x <= right and top <= center_y <= bottom
                    )
                if not (related_in_tree or inside_media):
                    continue
                if total <= 1 or current < 1 or current > total:
                    continue
                candidates.append((
                    header_bounds[1], not preferred, media_bounds, current, total
                ))

        if not candidates:
            self._last_carousel_skip_reason = "carousel_not_fully_framed"
            return None
        _header_top, _not_preferred, bounds, current, total = min(candidates)
        self._last_carousel_skip_reason = None
        return bounds, current, total

    def current_caption_text(self, root=None) -> str:
        """Raw text of the dominant on-screen post's caption — the tallest visible
        `IgTextLayoutView` text (username prefix included, as rendered). Empty string when the
        post has no caption. Call `expand_caption_if_truncated()` first to get the FULL text of
        a truncated caption. Used by the reading dwell and by the AI smart-comment hook (the
        author's actual words, passed to the model alongside the vision description)."""
        root = root if root is not None else self._dump_root()
        if root is None:
            return ""
        best_text, best_h = "", -1
        for node in root.iter():
            if node.tag != FS.caption_layout_class:
                continue
            t = node.get("text") or ""
            if not t:
                continue
            m = _BOUNDS_RE.search(node.get("bounds", ""))
            if not m:
                continue
            top, bot = int(m.group(2)), int(m.group(4))
            if bot < 0 or top > self.screen_height:
                continue
            if (bot - top) > best_h:
                best_h, best_text = bot - top, t
        return best_text

    def _caption_prose_length(self, root=None) -> int:
        """Real prose length (chars) of the dominant on-screen post's caption, with the
        username / hashtags / mentions / URLs stripped (see `caption_prose_chars`). 0 for an
        image with no real caption. Drives the reading dwell."""
        return caption_prose_chars(self.current_caption_text(root))

    def framed_post_context(self, root=None) -> Optional[dict]:
        """Everything the AI needs to know about the CURRENTLY FRAMED post, from ONE dump.

        Anchors on the framed post's full header row (`row_feed_profile_header`), whose
        content-desc already carries "author a publié un(e) photo le <date>" — author and
        publish date for free, no extra gesture. The post's WINDOW runs from that header to
        the next post's header (or the bottom of the screen), and the caption is picked
        INSIDE that window — never the tallest caption on screen, which on a busy frame can
        belong to the post below (measured: 11% of stored AI comments carried a neighbour's
        caption). The button row inside the window gives the screenshot crop its bottom edge.

        A caption whose emoji were eaten by the XML dump (see `text_lost_emoji`) is re-read
        through JSON-RPC, the same channel that already rescues mangled bios.

        Returns None when no full header is visible (post not framed — reels viewer, or
        mid-scroll): the caller must then treat the screen as UNFRAMED and not pretend.
        Keys: header_desc, author, header_bounds, buttons_bounds, caption_text,
        caption_bounds, window_bottom, post_ends_on_screen (the next post's header is on screen:
        an empty caption is then no caption, not one under the bottom of the screen).
        """
        root = root if root is not None else self._dump_root()
        if root is None:
            return None
        window = self._framed_window(root)
        if window is None:
            return None

        caption_bounds, caption_text = None, ""
        if window["captions"]:
            caption_bounds, caption_text = self._tallest_caption(window["captions"])

        return {
            "header_desc": window["header_desc"],
            # "" when the header names no handle (`framed_post_author`'s reading).
            "author": self._author_of(window) or "",
            "header_bounds": window["header_bounds"],
            "buttons_bounds": window["buttons_bounds"],
            "caption_text": caption_text,
            "caption_bounds": caption_bounds,
            "window_bottom": window["window_bottom"],
            "post_ends_on_screen": window["post_ends_on_screen"],
        }

    def _tallest_caption(self, captions: list) -> tuple:
        """The caption of a post among those of its window, (bounds, text): the tallest one. A text
        whose emoji the XML dump ate (`text_lost_emoji`) is read again through JSON-RPC."""
        bounds, text = max(captions, key=lambda c: c[0][3] - c[0][1])
        if text_lost_emoji(text):
            recovered = self._reread_caption_without_xml(bounds)
            if recovered:
                text = recovered
        return bounds, text

    def read_framed_caption(self) -> Optional[dict]:
        """The framed post's context (`framed_post_context`) with its caption read whole, as a human
        reads it before reacting: a truncated caption expanded first (its expander tapped), then the
        post brought back where it sat if the reading scrolled it (`_reframe_post_after_reading`).

        A caption the screen does not show (the post runs under the bottom: a tall video, a small
        phone) is looked for the way a human does: the post lifted until its caption or its end
        shows, read, then brought back (`_read_caption_under_the_screen`).

        The one reading of a caption before acting on its post: the AI comment grounds on it, the
        excluded terms of the account are checked on it. Adds `reframed`: False when the reading moved
        the post and the screen never showed it back (nothing should then act on this screen), and
        `post_end_seen`: True when the post was seen down to its end, on screen or by the reading (an
        empty caption is then no caption). None when no post is framed."""
        self._last_reveal_scroll_px = 0
        self.expand_caption_if_truncated()
        reframed = True
        reveal_px = getattr(self, "_last_reveal_scroll_px", 0)
        if reveal_px:
            reframed = self._reframe_post_after_reading(reveal_px)
            self._last_reveal_scroll_px = 0
        context = self.framed_post_context()
        if context is not None:
            context["reframed"] = reframed
            context["post_end_seen"] = context["post_ends_on_screen"]
            if reframed and self._caption_is_under_the_screen(context):
                self._read_caption_under_the_screen(context)
        return context

    def _caption_is_under_the_screen(self, context: dict) -> bool:
        """True when the framed post's caption cannot be read where the post sits: the post runs
        under the bottom of the list and shows no caption, or one still truncated (its expander is
        cut by the bottom). Only a post that says which it is (its header's description) and whose
        header sits in the upper half of the screen is lifted."""
        if context["post_ends_on_screen"] or not context["header_desc"]:
            return False
        if context["header_bounds"][1] > _SHOW_BUTTONS_MAX_HEADER_SHARE * self.screen_height:
            return False
        text = context["caption_text"]
        return not text or clean_post_caption(text).truncated

    def _lifted_post_zone(self, root, identity: str, header_top: int, lifted_px: int) -> Optional[dict]:
        """Where the post being read shows once reading drags lifted it by `lifted_px`, from one dump.

        Its header still on screen: its usual window, from that header to the next one. Its header
        gone above the top: what the list shows above the first header on screen (the tail of the
        post: the end of its media, its button row, its caption). `closed`: a next header ends the
        zone, so the post is seen down to its end.

        The post's own header is the one with its description AND where the drags carried it: at
        that height, or cut by the top of the list when they carried it higher. A header with its
        description anywhere else is the next post's (same author, kind and day): which post is
        read can then not be told, and None is returned. None too without a dump.
        """
        if root is None:
            return None
        rows = self._scan_post_rows(root)
        top_limit, bottom_limit, list_bounds = rows["top_limit"], rows["bottom_limit"], rows["list_bounds"]
        visible = sorted((h for h in rows["headers"] if h[0][1] >= top_limit), key=lambda h: h[0][1])
        tolerance = (_LIFTED_HEADER_TOLERANCE_H * self.screen_height
                     + _LIFTED_HEADER_TOLERANCE_SHARE * lifted_px)
        list_top = max(top_limit, list_bounds[1]) if list_bounds else top_limit
        expected_top = header_top - lifted_px
        own_top = None
        for bounds, desc in visible:
            if desc.strip() != identity:
                continue
            where_carried = abs(bounds[1] - expected_top) <= tolerance
            cut_by_the_top = expected_top < list_top and bounds[1] == list_top
            if own_top is None and (where_carried or cut_by_the_top):
                own_top = bounds[1]
            else:
                return None
        if own_top is not None:
            zone_top = own_top
            later_tops = [h[0][1] for h in visible if h[0][1] > own_top]
        else:
            zone_top = list_top
            later_tops = [h[0][1] for h in visible]
        zone_bottom = min([bottom_limit] + later_tops)
        return {
            "top": zone_top,
            "bottom": zone_bottom,
            "closed": zone_bottom < bottom_limit,
            "captions": [c for c in rows["captions"] if zone_top <= c[0][1] and c[0][3] <= zone_bottom],
        }

    def _read_caption_under_the_screen(self, context: dict) -> None:
        """Lift the framed post until its caption, or its end, shows; read the caption whole (a
        truncated one expanded); bring the post back where it sat. `context` (the framed post's, read
        before the lift) gets what was read: `caption_text`, `post_end_seen`, and `reframed` False
        when the post is not back where it sat, with the same identity.

        Each step looks at the screen (`_lifted_post_zone`): nothing is read from a zone that cannot
        be told to be this post's."""
        identity = context["header_desc"]
        header_top = context["header_bounds"][1]
        lifted_px = 0
        caption_text = None
        end_seen = False
        for _ in range(_CAPTION_LIFTS):
            lifted_px += self._reading_drag_up()
            zone = self._lifted_post_zone(self._dump_root(), identity, header_top, lifted_px)
            if zone is None:
                break
            if zone["captions"]:
                caption_text = self._tallest_caption(zone["captions"])[1]
                if clean_post_caption(caption_text).truncated:
                    self._last_reveal_scroll_px = 0
                    if not self.expand_caption_if_truncated(zone=(zone["top"], zone["bottom"])):
                        continue   # its expander is still cut by the bottom: one more lift
                    lifted_px += self._last_reveal_scroll_px
                    self._last_reveal_scroll_px = 0
                    zone = self._lifted_post_zone(self._dump_root(), identity, header_top, lifted_px)
                    if zone is None or not zone["captions"]:
                        break   # the expanded caption cannot be told to be this post's: left truncated
                    caption_text = self._tallest_caption(zone["captions"])[1]
                end_seen = True
                break
            if zone["closed"]:
                end_seen = True   # the post ends here without a caption
                break
        found = "read" if caption_text else "none" if end_seen else "not found"
        self.logger.debug(f"📖 lifted the post {lifted_px}px for a caption under the screen: {found}")
        # The way back is checked on the post's header: its caption was not on screen where it sat.
        self._reading_anchor = {"caption": "", "top": None, "header": identity, "header_top": header_top}
        back = self._reframe_post_after_reading(lifted_px)
        after = self.framed_post_context() if back else None
        if after is None or after["header_desc"] != identity:
            context["reframed"] = False
            return
        context.update(after)
        context["reframed"] = True
        context["post_end_seen"] = end_seen
        if caption_text is not None:
            context["caption_text"] = caption_text

    def _scan_post_rows(self, root) -> dict:
        """What one dump shows of the posts of a feed-style list: the bars that bound it, each
        post's header, button row, heart, counters, author line and caption, with their bounds.
        Read once, then cut into the framed post's window (`_framed_window`) or into the zone of a
        post lifted for its reading (`_lifted_post_zone`)."""
        top_limit, bottom_limit = 0, int(self.screen_height)
        list_bounds = None
        headers, buttons, captions, counters, hearts, names = [], [], [], [], [], []
        for node in root.iter():
            bounds = self._node_bounds(node)
            if not bounds:
                continue
            # One kind per node: each is kept, then the next node.
            short = node.get("resource-id", "").rsplit("/", 1)[-1]
            if short == FS.action_bar_id:
                top_limit = max(top_limit, bounds[3])
                continue
            if short == FS.tab_bar_id:
                bottom_limit = min(bottom_limit, bounds[1])
                continue
            if short == FS.post_list_id:
                list_bounds = list_bounds or bounds
                continue
            if short == FS.profile_header_id:
                headers.append((bounds, node.get("content-desc") or ""))
                continue
            if short == FS.header_id:
                names.append((bounds, node.get("text") or ""))
                continue
            if short == FS.buttons_row_id:
                buttons.append(bounds)
                continue
            if short == FS.like_button_id:
                hearts.append((bounds, is_liked_heart(node.get("selected"), node.get("content-desc"))))
                continue
            text = node.get("text") or ""
            if node.tag == FS.caption_layout_class:
                if text:
                    captions.append((bounds, text))
                continue
            if node.tag == FS.counter_button_class and count_from_counter_label(text.strip()) is not None:
                counters.append((bounds, text.strip()))
        return {
            "top_limit": top_limit, "bottom_limit": bottom_limit, "list_bounds": list_bounds,
            "headers": headers, "buttons": buttons, "captions": captions,
            "counters": counters, "hearts": hearts, "names": names,
        }

    def _framed_window(self, root) -> Optional[dict]:
        """The framed post and what lies INSIDE its window, from one dump.

        The framed post is the first header fully below the action bar; its window runs to the
        next post's header (or the bottom bar). Only what lies inside belongs to this post: its
        button row, the heart and the counters of that row, its captions, and its media between
        its header and its row. None when no header is framed (full-screen Reel viewer,
        mid-scroll).

        `list_top` and `list_bottom` bound what the list shows: a header starts to hide under the
        top (the list's own top, or the action bar over it), a post under the bottom (the list's
        end, or the bottom bar).
        """
        rows = self._scan_post_rows(root)
        top_limit, bottom_limit, list_bounds = rows["top_limit"], rows["bottom_limit"], rows["list_bounds"]
        headers, buttons, captions = rows["headers"], rows["buttons"], rows["captions"]
        counters, hearts, names = rows["counters"], rows["hearts"], rows["names"]

        visible = sorted((h for h in headers if h[0][1] >= top_limit), key=lambda h: h[0][1])
        if not visible:
            return None
        header_bounds, header_desc = visible[0]
        window_top = header_bounds[1]
        later_tops = [h[0][1] for h in visible[1:]]
        window_bottom = min([bottom_limit] + [t for t in later_tops if t > window_top])

        def _in_window(bounds):
            return window_top <= bounds[1] and bounds[3] <= window_bottom

        buttons_bounds = next((b for b in buttons if _in_window(b)), None)
        row_counters = []
        heart = None
        media_bounds = None
        if buttons_bounds is not None:
            row_counters = [
                text for bounds, text in sorted(counters, key=lambda c: c[0][0])
                if buttons_bounds[1] <= bounds[1] and bounds[3] <= buttons_bounds[3]
            ]
            heart = next((h for h in hearts
                          if buttons_bounds[1] <= h[0][1] and h[0][3] <= buttons_bounds[3]), None)
            if buttons_bounds[1] > header_bounds[3]:
                media_bounds = (header_bounds[0], header_bounds[3], header_bounds[2],
                                buttons_bounds[1])
        list_top = max(top_limit, list_bounds[1]) if list_bounds else top_limit
        list_bottom = min(bottom_limit, list_bounds[3]) if list_bounds else bottom_limit
        # The author line INSIDE the framed header: another post's line is never read.
        author_line = next((text for bounds, text in names
                            if header_bounds[1] <= bounds[1] and bounds[3] <= header_bounds[3]), "")
        return {
            "header_desc": header_desc.strip(),
            "author_line": author_line.strip(),
            "header_bounds": header_bounds,
            "list_top": list_top,
            "list_bottom": list_bottom,
            "window_bottom": window_bottom,
            # The next post's header closes the window before the bottom of the list: the whole
            # framed post, its caption included, is on screen.
            "post_ends_on_screen": window_bottom < bottom_limit,
            "buttons_bounds": buttons_bounds,
            "row_counters": row_counters,
            "captions": [c for c in captions if _in_window(c[0])],
            "heart_bounds": heart[0] if heart else None,
            "heart_liked": heart[1] if heart else None,
            "media_bounds": media_bounds,
        }

    @staticmethod
    def _author_of(window: dict) -> Optional[str]:
        """The framed post's author: the first handle of its header description ("author a publié
        ...": for a collaboration, the first account it names), else of the author line inside its
        header (a header without description). None when neither names a handle."""
        return (username_from_author_header(window["header_desc"])
                or username_from_author_header(window["author_line"]))

    def framed_post_author(self, root=None) -> Optional[str]:
        """Who the framed post is by, from one dump: the account the Feed files its like and its
        comment under (`_author_of`). Only the framed post's own header is read: the first author
        line of the screen can be the next post's (the framed one's line is out of the dump when its
        header sits just under the top of the list) or the post above's. None when no post is
        framed (mid-scroll, a full-screen Reel) or its header names no handle."""
        root = root if root is not None else self._dump_root()
        window = self._framed_window(root) if root is not None else None
        return self._author_of(window) if window is not None else None

    def framed_post_identity(self, root=None) -> Optional[str]:
        """Which post is framed: the description of its own header ("author a publié un(e)
        <kind> <place> <date>"), from one dump. Nothing else on screen is read, so a neighbour
        peeking above or below, a carousel slide, or our own like never changes it. None when no
        header is framed or it carries no description."""
        root = root if root is not None else self._dump_root()
        window = self._framed_window(root) if root is not None else None
        if window is None or not window["header_desc"]:
            return None
        return window["header_desc"]

    def framed_post_signature(self, root=None) -> Optional[str]:
        """The framed post's identity plus the counters of its own button row ("1 781 38 14 23"),
        from one dump: tells apart two posts of the same author, kind and week, which share a
        header description. The counters move with a like, so this is for telling posts apart
        during a visit, not for checking that the screen still shows the same post (use
        ``framed_post_identity``). None when no header is framed or it carries no description."""
        root = root if root is not None else self._dump_root()
        window = self._framed_window(root) if root is not None else None
        if window is None or not window["header_desc"]:
            return None
        return " | ".join([window["header_desc"]] + [" ".join(window["row_counters"])])

    def framed_post_like_target(self, root=None) -> Optional[dict]:
        """Where a like of the framed post goes, from one dump; None when the screen cannot be read.

        On a list of posts (a profile's posts, the feed, a hashtag), the post is the framed one,
        whose header (`header`, its bounds) gives the identity the guards check: `media` is its
        media between its header and its button row (for a double tap), `heart` the like button of
        that row and `liked` its state. Both are None unless that heart is on screen: the post
        above can fill most of the screen with its media and its heart, and nothing may then be
        liked there (`PostReadingMixin.show_framed_post_buttons` can bring the row up first).
        `row` is that button row, None when it is not on screen: the framed post's like counter,
        which opens its likers, is read there (`InstagramUIExtractors.find_like_count_element`).
        Off a list (the full-screen Reel viewer), {"list": False}: its single post is liked as that
        viewer does.
        """
        root = root if root is not None else self._dump_root()
        if root is None:
            return None
        list_ids = (FS.profile_header_id, FS.buttons_row_id, FS.like_button_id)
        if not any(node.get("resource-id", "").rsplit("/", 1)[-1] in list_ids for node in root.iter()):
            return {"list": False}
        window = self._framed_window(root)
        if window is None or window["heart_bounds"] is None:
            return {"list": True, "identity": window["header_desc"] if window is not None else None,
                    "header": window["header_bounds"] if window is not None else None,
                    "row": window["buttons_bounds"] if window is not None else None,
                    "media": None, "heart": None, "liked": None}
        return {
            "list": True,
            "identity": window["header_desc"],
            "header": window["header_bounds"],
            "row": window["buttons_bounds"],
            "media": window["media_bounds"],
            "heart": window["heart_bounds"],
            "liked": window["heart_liked"],
        }

    def show_framed_post_buttons(self) -> Dict[str, Any]:
        """Bring the framed post's button row on screen when its media is but the row runs under
        the bottom of the list (the like needs its heart: `framed_post_like_target`).

        ONE short 1:1 drag (`_long_drag`, the precise gesture of the framing correction, at the
        session's tempo) lifts the post until its header sits just under the top of the list: the
        row below the media shows, and the header, which says which post it is, stays on screen.
        A flick would coast by an unknown distance and could take the header away.

        No gesture when the row is already on screen, when no header is framed, when the header
        already sits at the top of the list (the post is taller than the list: header and row
        never show together), or when it sits in the lower half of the list (the post is mostly
        under the screen: bringing it up is an advance, not a look at its buttons).

        Returns {target, reason, lifted_px, header_before, header_after}: `target` is the like
        target read after the gesture, or instead of it (None when the screen cannot be read);
        `lifted_px` the travel asked of the drag (the lift, or, when the lift is under the swipe
        floor, a travel drawn between that floor and the most the header allows);
        `reason` says what was done (`row_on_screen`, `no_framed_post`, `header_at_top`,
        `post_mostly_under_screen`, `lifted`). The caller checks it is still the same post. Also
        kept as `_last_buttons_reveal` for the Lab."""
        report: Dict[str, Any] = {"target": None, "reason": "unreadable", "lifted_px": 0,
                                  "header_before": None, "header_after": None}
        self._last_buttons_reveal = report
        root = self._dump_root()
        if root is None:
            return report
        window = self._framed_window(root)
        report["target"] = self.framed_post_like_target(root)
        if window is None:
            report["reason"] = "no_framed_post"
            return report
        header_top = window["header_bounds"][1]
        report["header_before"] = header_top
        if window["heart_bounds"] is not None:
            report["reason"] = "row_on_screen"
            return report
        h = int(self.screen_height)
        list_top, list_bottom = window["list_top"], window["list_bottom"]
        if header_top - list_top > _SHOW_BUTTONS_MAX_HEADER_SHARE * (list_bottom - list_top):
            report["reason"] = "post_mostly_under_screen"
            return report
        # The most the drag may travel: the header then half under the top of the list, still read.
        room_px = (header_top - list_top
                   + _SHOW_BUTTONS_HEADER_HIDDEN_MAX * (window["header_bounds"][3] - header_top))
        floor_px = SWIPE_FLOOR_H * h
        if floor_px > room_px:
            report["reason"] = "header_at_top"
            return report
        lift_px = header_top - list_top - random.uniform(*_SHOW_BUTTONS_HEADER_MARGIN_H) * h
        # Under the floor the drag travels at least the floor: a travel drawn between the floor and
        # the room, never the floor itself every time.
        travel_px = lift_px if lift_px >= floor_px else random.uniform(floor_px, room_px)
        motor_provider = getattr(self, "_motor_modulation", None)
        motor = (cast(Dict[str, float], motor_provider("framed_post_buttons")) if callable(motor_provider)
                 else {"velocity_scale": 1.0, "settle_scale": 1.0})
        self._long_drag(
            "up", distance_px=travel_px, vel_range=_READ_DRAG_VEL_PXS, guard_start=True,
            velocity_scale=motor["velocity_scale"],
        )
        time.sleep(random.uniform(0.30, 0.50) * motor["settle_scale"])
        after = self.framed_post_like_target()
        header_after = (after or {}).get("header")
        report.update(target=after, reason="lifted", lifted_px=int(travel_px),
                      header_after=header_after[1] if header_after else None)
        self.logger.debug(f"📐 framed post's buttons shown: header {header_top} -> "
                          f"{report['header_after']} (drag {int(travel_px)}px), "
                          f"heart {'on' if (after or {}).get('heart') else 'not on'} screen")
        return report

    def show_framed_post_row_of(self, identity: Optional[str], what: str) -> Optional[Dict[str, Any]]:
        """The framed post's button row runs under the bottom of the list: bring it up
        (`show_framed_post_buttons`), then the like target of the SAME post (`identity`, its
        header's description), its heart and row on screen. What a gesture of that row needs first:
        the like (its heart), the opening of its likers (its counter).

        None, and why in the log (`what` names what is then not done), when no post is framed, no
        gesture could show the row, the post changed during it, or the heart is still off the
        screen."""
        if identity is None:
            self.logger.warning(f"No framed post: no {what}")
            return None
        shown = self.show_framed_post_buttons()
        after = shown.get("target")
        reason = shown.get("reason")
        if not isinstance(after, dict) or not after.get("list"):
            self.logger.warning(f"Screen unreadable after showing the framed post's buttons ({reason}): no {what}")
            return None
        if after.get("identity") != identity:
            self.logger.warning(
                f"Framed post changed while showing its buttons ({identity} -> {after.get('identity')}): no {what}"
            )
            return None
        if after.get("heart") is None or after.get("row") is None:
            self.logger.warning(f"Framed post's buttons still not on screen ({identity}, {reason}): no {what}")
            return None
        self.logger.debug(f"Framed post's buttons shown ({reason}): {identity}")
        return after

    def _reread_caption_without_xml(self, bounds) -> Optional[str]:
        """Re-read a caption through JSON-RPC instead of the XML dump.

        Same rescue as `_read_text_without_xml` for bios: `element.info['text']` travels as
        JSON, where emoji survive the trip the XML dump mutilates into dots. The caption
        `IgTextLayoutView` has no resource-id on v410, so the element is found by class and
        matched to the XML node by its top-left corner. Best effort: any failure keeps the
        dumped value — a caption with dots still beats no caption at all.
        """
        raw_device = getattr(self.device, "_device", None)
        if raw_device is None or bounds is None:
            return None
        try:
            query = raw_device(className=FS.caption_layout_class)
            for i in range(min(query.count, 8)):
                info = raw_device(className=FS.caption_layout_class, instance=i).info or {}
                b = info.get("bounds") or {}
                if abs(b.get("top", -9999) - bounds[1]) <= 4 and abs(b.get("left", -9999) - bounds[0]) <= 4:
                    text = (info.get("text") or "").strip()
                    return text or None
        except Exception as exc:
            self.logger.debug(f"JSON-RPC caption re-read failed: {exc}")
        return None

    def human_reading_pause(self, dwell_s: Optional[float] = None,
                            read_captions: bool = True, browse_carousels: bool = True) -> float:
        """One human reading pause on the current post. First the intelligent reading — browse a
        carousel's slides, then expand & READ a truncated caption — which already consumes real
        time. Then dwell so the TOTAL time on the post matches the CONTENT: an image is glanced at,
        a real caption is read in proportion to its prose length (hashtags excluded). Pass
        `dwell_s` to override the target (e.g. a future vision/`post_analysis` relevance score).
        `browse_carousels`/`read_captions` toggle the two intelligent-reading behaviours (a bot
        user may disable them); when off, the post is only dwelled on. Returns the total time spent
        on the post (seconds)."""
        start = time.monotonic()
        self._last_reveal_scroll_px = 0
        self._reading_anchor = None
        # None: the reading did not move the post; True: moved and verified back; False: not back.
        self.last_reading_reframed = None
        if browse_carousels:
            try:
                self.browse_carousel_slides()
            except Exception as e:
                self.logger.debug(f"carousel browse skipped: {e}")
        if read_captions:
            try:
                if random.random() < _EXPAND_CAPTION_PROB:
                    self.expand_caption_if_truncated()
            except Exception as e:
                self.logger.debug(f"caption expand skipped: {e}")
        prose = self._caption_prose_length()                 # full text now (caption expanded)
        dwell_scale = 1.0
        if dwell_s is None:
            scale_provider = getattr(self, "_reading_dwell_scale", None)
            if callable(scale_provider):
                dwell_scale = float(scale_provider("post_reading"))
            target = content_dwell(prose) * dwell_scale
        else:
            target = dwell_s
        spent = time.monotonic() - start                     # carousel/caption already took time
        remain = max(MIN_DWELL_S, target - spent)
        time.sleep(remain)
        # Done reading: scroll back up so the post (image + button row) is framed again
        # before anything acts on it (like / comment / AI screenshot).
        reveal_px = getattr(self, "_last_reveal_scroll_px", 0)
        if reveal_px >= _REFRAME_MIN_PX:
            self.last_reading_reframed = self._reframe_post_after_reading(reveal_px)
        self._last_reveal_scroll_px = 0
        total = time.monotonic() - start
        self.logger.debug(f"⏲️ reading: prose={prose}ch target={target:.1f}s "
                          f"scale={dwell_scale:.3f} active={spent:.1f}s "
                          f"dwell={remain:.1f}s total={total:.1f}s")
        return round(total, 1)


__all__ = ["PostReadingMixin"]
