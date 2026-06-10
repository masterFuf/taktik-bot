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

Pure mixin — host must expose `self.device` (facade with `_device.dump_hierarchy` and
`click_coordinates`), `self.screen_height`, `self.logger`, and the `_long_drag` gesture
primitive (shared `GestureMixin`). `FeedScrollMixin` inherits this; the like workflow reaches
it through its composed `scroll_actions`.
"""

import re
import time
import random
from typing import Optional
from lxml import etree

from ....ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS
from taktik.core.shared.behavior.dwell import content_dwell, caption_prose_chars, MIN_DWELL_S

# uiautomator bounds string: "[left,top][right,bottom]" — shared with the feed engine.
_BOUNDS_RE = re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')

# Carousel index "N/M" (pattern from the centralized feed-scroll selectors).
_CAROUSEL_INDEX_RE = re.compile(FS.carousel_index_pattern)

# Reading scrolls are slow 1:1 drags (no coast) — same velocity band as the feed's drag profile.
_READ_DRAG_VEL_PXS = (1500.0, 2200.0)

# Share of reading pauses that expand a truncated caption (a human doesn't always tap 'more').
_EXPAND_CAPTION_PROB = 0.85


class PostReadingMixin:
    """Mixin: human reading of the on-screen post (caption expand/read, carousel browse,
    content-aware dwell). Host must expose `self.device`, `self.screen_height`, `self.logger`
    and `_long_drag`."""

    def _dump_root(self):
        """One hierarchy dump → parsed lxml root (or None). Used by the reading actions; called
        during a multi-second reading pause, so its freeze overlaps the dwell (invisible)."""
        try:
            xml = self.device._device.dump_hierarchy()
            return etree.fromstring(xml.encode("utf-8"))
        except Exception as e:
            self.logger.debug(f"dump_root failed: {e}")
            return None

    def expand_caption_if_truncated(self) -> bool:
        """If the dominant on-screen post has a truncated caption, tap its '… plus'/'… more'
        expander to read the full text — like a human pausing on a post. On v410 the caption
        is an empty-resource-id `IgTextLayoutView` whose dedicated expander is a child Button with
        content-desc EXACTLY 'plus' (FR) / 'more' (EN). We click that exact button (a random point
        in its bounds, humanised) — never `contains('plus')`, so the Sponsored 'En savoir plus' /
        'Learn more' ad CTA (a link) is excluded. Returns True if a caption was expanded."""
        root = self._dump_root()
        if root is None:
            return False
        best = None  # (visible_height, (l, t, r, b))
        for node in root.iter():
            if node.get("class", "") != FS.caption_layout_class:
                continue
            target = None
            for child in node.iter():
                if child is node:
                    continue
                if (child.get("class") == "android.widget.Button"
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
            # rank by the caption layout's visible height → the dominant, fully-shown post's caption
            vis_h = int(ml.group(4)) - int(ml.group(2))
            if best is None or vis_h > best[0]:
                best = (vis_h, (l, t, r, b))
        if best is None:
            return False
        l, t, r, b = best[1]
        x = random.randint(min(l + 1, r), max(l + 1, r - 1))
        y = random.randint(min(t + 1, b), max(t + 1, b - 1))
        self.device.click_coordinates(x, y)
        self.logger.debug(f"📖 expanded truncated caption at ({x},{y})")
        # The expanded text usually runs below the fold (the expander sat low). Scroll a little to
        # read it, like a human reading on (gentle, smooth), instead of "opening" a caption nobody
        # can see. No-op if the whole caption already fits.
        time.sleep(random.uniform(0.4, 0.8))   # let it expand + a beat before reading
        self._reveal_expanded_caption()
        return True

    def _reveal_expanded_caption(self, max_scrolls: int = 2) -> int:
        """After expanding a caption, gently scroll so its now-visible text comes INTO view — a
        human reads it, they don't open a caption that stays below the fold. Each scroll is a slow
        drag (smooth) with a reading beat; stops once no caption extends below the fold. Returns
        the number of reading scrolls done."""
        fold = int(0.86 * self.screen_height)
        done = 0
        for _ in range(max_scrolls):
            root = self._dump_root()
            if root is None:
                break
            below = None    # tallest caption whose bottom runs past the fold
            for node in root.iter():
                if node.get("class", "") != FS.caption_layout_class:
                    continue
                m = _BOUNDS_RE.search(node.get("bounds", ""))
                if not m:
                    continue
                t, b = int(m.group(2)), int(m.group(4))
                if b > fold and (below is None or (b - t) > below):
                    below = b - t
            if below is None:
                break
            self._long_drag("up", distance_px=random.uniform(0.20, 0.30) * self.screen_height,
                            vel_range=_READ_DRAG_VEL_PXS)
            done += 1
            time.sleep(random.uniform(0.7, 1.4))   # read the revealed lines
        if done:
            self.logger.debug(f"📖 scrolled {done}x to read the expanded caption")
        return done

    def browse_carousel_slides(self) -> int:
        """If the dominant on-screen post is a multi-slide carousel, swipe through 1-2 slides like
        a human. Detect via `carousel_viewpager`/`carousel_media_group` + the authoritative 'N/M'
        index text (`carousel_index_indicator_text_view`); swipe horizontally INSIDE the media band
        (vertical centre, |dy|≈0, travel ~60% width → pages the slide, never opens the post, never
        reads as a story-swipe), stop at the last slide. Returns the number of slides advanced."""
        VIEWPAGER, MEDIA, INDEX = (FS.carousel_viewpager_id, FS.carousel_media_group_id,
                                   FS.carousel_index_id)
        swiped = 0
        for _ in range(2):   # at most 2 slides
            root = self._dump_root()
            if root is None:
                break
            band = None        # (prefer_viewpager, vis_h, (l, t, r, b))
            cur = total = None
            for node in root.iter():
                short = node.get("resource-id", "").rsplit("/", 1)[-1]
                if short == INDEX:
                    mm = _CAROUSEL_INDEX_RE.match(
                        (node.get("text") or node.get("content-desc") or "").strip())
                    if mm:
                        cur, total = int(mm.group(1)), int(mm.group(2))
                    continue
                if short not in (VIEWPAGER, MEDIA):
                    continue
                m = _BOUNDS_RE.search(node.get("bounds", ""))
                if not m:
                    continue
                l, t, r, b = (int(m.group(i)) for i in range(1, 5))
                t = max(t, int(0.06 * self.screen_height))
                b = min(b, int(0.92 * self.screen_height))
                if b - t <= 0:
                    continue
                pref = short == VIEWPAGER
                if band is None or (pref, b - t) > (band[0], band[1]):
                    band = (pref, b - t, (l, t, r, b))
            if band is None or cur is None or total is None or cur >= total:
                break
            l, t, r, b = band[2]
            w = r - l
            y = (t + b) // 2 + random.randint(-10, 10)
            x_start = int(l + (0.80 + random.uniform(-0.03, 0.03)) * w)
            x_end = int(l + (0.20 + random.uniform(-0.03, 0.03)) * w)
            raw = getattr(self.device, "_device", None)
            if raw is not None and hasattr(raw, "swipe"):
                raw.swipe(x_start, y, x_end, y, duration=random.uniform(0.20, 0.35))
            else:
                self.device.swipe_coordinates(x_start, y, x_end, y, 0.28)
            swiped += 1
            time.sleep(random.uniform(0.6, 1.2))   # look at the slide
            if cur + 1 >= total:
                break
        if swiped:
            self.logger.debug(f"🖼️ carousel: swiped {swiped} slide(s)")
        return swiped

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
            if node.get("class", "") != FS.caption_layout_class:
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
        target = dwell_s if dwell_s is not None else content_dwell(prose)
        spent = time.monotonic() - start                     # carousel/caption already took time
        remain = max(MIN_DWELL_S, target - spent)
        time.sleep(remain)
        total = spent + remain
        self.logger.debug(f"⏲️ reading: prose={prose}ch target={target:.1f}s active={spent:.1f}s "
                          f"dwell={remain:.1f}s total={total:.1f}s")
        return round(total, 1)


__all__ = ["PostReadingMixin"]
