"""Instagram INTELLIGENT feed scroll — one cohesive capability.

`FeedScrollMixin` browses the feed like a human: it advances ONE decisive gesture per post (real
OS fling), frames the post and stops only once its engagement bar (metadata) is in view, skips
Sponsored ads and Suggested/recommended units, expands & reads truncated captions, browses carousel
slides, and dwells for a content-aware time. It is a pure mixin: the host class (`ScrollActions`)
provides `self.device`, `self.screen_width/height`, `self.logger`, and the humanized gesture
primitives (`_strong_flick`/`_long_drag`, from the shared `GestureMixin`).

Internal sections: PERCEPTION (read the feed state + recover to it) · ENGINE (advance to the next
real post) · READING (caption/carousel + dwell) · SESSION (`browse_feed`). UI signatures come from
the centralized `FeedScrollSelectors`; the humanized gesture/dwell toolkit lives in
`taktik.core.shared.behavior`. Full design log: `taktik-docs/bot/security/feed-scroll-engineering.md`.
"""

import re
import time
import random
from typing import Optional, Dict, Any, List
from lxml import etree

from ....ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS
from taktik.core.shared.behavior.dwell import content_dwell, caption_prose_chars, MIN_DWELL_S

# uiautomator bounds string: "[left,top][right,bottom]"
_BOUNDS_RE = re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')

# Feed-scroll tunables. These are SEEDS to calibrate on the Lab from the measured coast and
# landing (logged every call). Key insight (proven from real dumps): the feed advance is OS
# FLING INERTIA, not finger distance — a real fling coasts ~3x past the finger, so a strong
# flick's finger travel is small (~0.3h) yet it reveals a whole post (pitch ~0.9h).
_FLICK_FINGER_H = (0.30, 0.40)      # decisive flick finger travel (× screen height)
_FLICK_VEL_PXS = (9000.0, 13000.0)  # flick release velocity px/s (>> Android fling floor)
_DRAG_FINGER_H = (0.80, 0.90)       # continuous-drag finger travel (× screen height)
_DRAG_VEL_PXS = (1500.0, 2200.0)    # drag velocity px/s (slow → 1:1 track, no coast)
# Flick is the workhorse: it coasts (real OS fling), matches the real human data (which has NO
# long drags — humans flick), and a FAST fling escapes a feed video's touch region. The slow
# `drag` is kept only as a rare variant; on a full-screen video it can be captured by the player.
# A geste-level `skim` (2 flicks at once) was REMOVED (#27): it overshot organic posts into the
# ad/suggestion block and counted as a `filler_run`, falsely tripping `reached_tail` — and it is
# redundant with `browse_feed.skip_prob`, which skips a post by advancing to a REAL one (no junk
# overshoot). The gesture is now always ONE decisive advance.
_MODE_WEIGHTS = (("flick", 0.85), ("drag", 0.15))
# A post is "framed" only when its header sits in the very top of the screen — otherwise the
# previous post still fills the top and we stopped "in the middle of a post".
_LAND_GOOD_MAX = 0.12               # incoming header y / h ≤ this ⇒ post framed at top (done)
_LAND_TARGET = 0.05                 # where the correction drag lands the header (just under the top)
# Session exhaustion: the followed feed is declared spent only after this many CONSECUTIVE gestures
# that saw nothing but ads/suggestions. One filler run (a normal 2-3 ad block between real posts) is
# NOT the tail — at 2 runs in a row we have glided past ~4-6 junk units with no organic post, which a
# human reads as "you're all caught up" and stops. A real post anywhere in between resets the count.
_TAIL_FILLER_RUNS = 2
# Carousel index "N/M" (pattern from the centralized feed-scroll selectors)
_CAROUSEL_INDEX_RE = re.compile(FS.carousel_index_pattern)


class FeedScrollMixin:
    """Mixin: the intelligent Instagram feed scroll (perception, engine, reading, session). Host
    must expose `self.device`, `self.screen_width/height`, `self.logger`, and the gesture
    primitives `_strong_flick`/`_long_drag` (from the shared `GestureMixin`)."""

    # ── PERCEPTION: read the feed state, and recover to the feed ───────────────────

    def _read_feed_anchors(self) -> Dict[str, Any]:
        """One hierarchy dump → feed post anchors (header tops, like-row tops), the fixed
        top-bar / tab-bar boundaries (device px), and a surface flag.

        `on_feed` is False when we are NOT on the scrollable feed — most importantly the
        full-screen Reels viewer (`root_clips_layout` present *without* any feed marker).
        The feed itself can embed an inline reel (clips_* AND feed markers together), which
        stays on_feed=True; only the standalone reel viewer flips it False."""
        headers: List[int] = []
        posts: List[tuple] = []      # (header_top_y, username) to identify the dominant post
        likes: List[int] = []
        ad_tops: List[int] = []      # tops of "Sponsorisé(e)" / "Sponsored" markers (ad posts)
        sugg_tops: List[int] = []    # tops of "Suggestions" / "Suggested" markers (recommended posts/reels)
        top_bar_bottom: Optional[int] = None
        tab_top: Optional[int] = None
        has_feed_marker = False
        has_clips_root = False
        has_profile = False   # we mis-tapped onto a profile (e.g. the post author)
        video_band: Optional[tuple] = None  # (top, bottom) of the inline playing video/reel
        # All UI signatures come from FS (FeedScrollSelectors). NB: `clips_tab` is just the Reels
        # nav button (always present) — the actual inline video is `FS.video_ids`.
        try:
            xml = self.device._device.dump_hierarchy()
            root = etree.fromstring(xml.encode("utf-8"))
            for node in root.iter():
                # Ad marker: the "Sponsorisé(e)" / "Sponsored" label lives in a content-desc
                # (on the media or a label), often on a node without a resource-id → check first.
                cd = node.get("content-desc") or ""
                cdl = cd.lower()
                if cd and any(tok in cdl for tok in FS.ad_desc_tokens):
                    ma = _BOUNDS_RE.search(node.get("bounds", ""))
                    if ma:
                        ad_tops.append(int(ma.group(2)))
                # Suggested/recommended unit ("Suggestion Photo de…", "Suggested reels …"): IG
                # inserts these in the feed (often once the followed posts run out). We skip them
                # like ads — a normal user does not engage with the recommendation tail.
                if cd and (cdl.startswith(FS.suggested_desc_prefixes)
                           or any(s in cdl for s in FS.suggested_desc_contains)):
                    ma = _BOUNDS_RE.search(node.get("bounds", ""))
                    if ma:
                        sugg_tops.append(int(ma.group(2)))
                rid = node.get("resource-id", "")
                if not rid:
                    continue
                short = rid.rsplit("/", 1)[-1]
                if short == FS.secondary_label_id:
                    if (node.get("text") or "").strip().lower().startswith(FS.suggested_label_prefix):
                        ms = _BOUNDS_RE.search(node.get("bounds", ""))
                        if ms:
                            sugg_tops.append(int(ms.group(2)))
                if short == FS.clips_root_id:
                    has_clips_root = True
                if short in FS.profile_ids:
                    has_profile = True
                if short in FS.feed_marker_ids:
                    has_feed_marker = True
                m = _BOUNDS_RE.search(node.get("bounds", ""))
                if not m:
                    continue
                top, bottom = int(m.group(2)), int(m.group(4))
                if short == FS.header_id:
                    headers.append(top)
                    user = (node.get("text") or node.get("content-desc") or "").strip()
                    posts.append((top, user))
                elif short == FS.like_button_id:
                    likes.append(top)
                elif short == FS.action_bar_id:
                    top_bar_bottom = bottom
                elif short == FS.tab_bar_id:  # tab_bar_shadow has no top we care about
                    tab_top = top
                elif short in FS.video_ids:
                    if video_band is None or (bottom - top) > (video_band[1] - video_band[0]):
                        video_band = (top, bottom)
        except Exception as e:
            self.logger.debug(f"feed anchor read failed: {e}")
            return {"headers": [], "posts": [], "likes": [], "ad_tops": [], "sugg_tops": [],
                    "top": int(self.screen_height * 0.10),
                    "tab": int(self.screen_height * 0.92), "on_feed": False, "video_band": None,
                    "surface": "unknown"}
        on_feed = has_feed_marker and not (has_clips_root and not has_feed_marker)
        surface = ("feed" if on_feed else "profile" if has_profile
                   else "reel" if has_clips_root else "other")
        return {
            "headers": sorted(headers),
            "posts": sorted(posts),
            "likes": sorted(likes),
            "ad_tops": sorted(ad_tops),
            "sugg_tops": sorted(sugg_tops),
            "top": top_bar_bottom if top_bar_bottom is not None else int(self.screen_height * 0.10),
            "tab": tab_top if tab_top is not None else int(self.screen_height * 0.92),
            "on_feed": on_feed,
            # Where we are when off-feed, so recovery can be targeted (profile vs reel viewer).
            "surface": surface,
            "video_band": video_band,
        }

    def _dump_root(self):
        """One hierarchy dump → parsed lxml root (or None). Used by the reading actions; called
        during a multi-second reading pause, so its freeze overlaps the dwell (invisible)."""
        try:
            xml = self.device._device.dump_hierarchy()
            return etree.fromstring(xml.encode("utf-8"))
        except Exception as e:
            self.logger.debug(f"dump_root failed: {e}")
            return None

    def _tap_xpath(self, xpath: str) -> bool:
        """Best-effort click on the first match of an xpath; False if absent/failed."""
        try:
            el = self.device.xpath(xpath)
            if el.exists:
                el.click()
                return True
        except Exception as e:
            self.logger.debug(f"tap {xpath[:40]} failed: {e}")
        return False

    def _recover_to_feed(self, anchors: Dict[str, Any], max_attempts: int = 3):
        """Return (anchors, dumps) after trying to get back to the feed from wherever a mis-tap
        left us (a profile, the Reels viewer, …). The previous code pressed device.back() 3×
        blindly — which on a profile with an overlay was swallowed (3 identical dumps). Here we
        use TARGETED, verified, escalating strategies and stop as soon as we are back on feed.
        """
        dumps = 0
        for _ in range(max_attempts):
            if anchors.get("on_feed"):
                return anchors, dumps
            self.logger.debug(f"📰 off-feed (surface={anchors.get('surface')}) — recovering")
            acted = (
                # 1) the in-app top-left back arrow (a real click, not a swallowed key event)
                self._tap_xpath(FS.back_button_xpath)
                # 2) the Home/feed bottom tab if the nav bar is present
                or self._tap_xpath(FS.feed_tab_xpath)
                or self._tap_xpath(FS.home_tab_xpath)
            )
            if not acted:
                # 3) last resort: system back
                try:
                    self.device.back()
                except Exception:
                    pass
            time.sleep(random.uniform(0.6, 1.0))
            anchors = self._read_feed_anchors()
            dumps += 1
        return anchors, dumps

    def _metadata_visible(self, anchors: Dict[str, Any]):
        """Is the dominant (topmost) on-screen post's ENGAGEMENT BAR visible above the tab bar?
        The like/comment row (`row_feed_button_like`/`_comment`) — not the header — is the real
        proof a post is shown in FULL: the header only tells us a new post started, the metadata
        at the bottom tells us we actually display the whole post. Returns (visible, like_y/h).
        None ratio when the dominant post has no engagement bar on screen (e.g. a tall post whose
        bar is below the fold, or a full-screen reel)."""
        headers = sorted(y for y in anchors.get("headers", []) if y >= 0)
        if not headers:
            return (False, None)
        hdr = headers[0]
        tab = anchors.get("tab") or int(0.92 * self.screen_height)
        below = sorted(ly for ly in anchors.get("likes", []) if ly >= hdr)
        if not below:
            return (False, None)
        ly = below[0]
        return (ly <= tab, ly / float(self.screen_height))

    def _dominant_has_marker(self, anchors: Dict[str, Any], tops_key: str) -> bool:
        """Is a marker (`tops_key`) attributed to the DOMINANT on-screen post — i.e. it sits
        between that post's header and the next post's header? (No feed header but markers present
        = a full-screen unit → counts.) Shared by the ad and suggested-content detectors."""
        tops = anchors.get(tops_key) or []
        if not tops:
            return False
        headers = sorted(y for y in anchors.get("headers", []) if y >= 0)
        if not headers:
            return True
        hdr = headers[0]
        nxt = next((y for y in headers if y > hdr), self.screen_height * 3)
        lo = hdr - 0.08 * self.screen_height
        return any(lo <= t < nxt for t in tops)

    def _dominant_is_ad(self, anchors: Dict[str, Any]) -> bool:
        """The dominant on-screen post is a Sponsored ad ("Sponsorisé(e)"/"Sponsored")."""
        return self._dominant_has_marker(anchors, "ad_tops")

    def _dominant_is_suggested(self, anchors: Dict[str, Any]) -> bool:
        """The dominant on-screen post is a Suggested/recommended unit ("Suggestions" label /
        "Suggestion …" media). IG inserts these (and suggested reels) in the feed; we skip them
        like ads — a normal user does not engage with the recommendation tail."""
        return self._dominant_has_marker(anchors, "sugg_tops")

    def _incoming_header_ratio(self, anchors: Dict[str, Any]) -> Optional[float]:
        """y/h of the dominant incoming post header = the topmost header on screen. Near 0 means
        the next post is pinned at the top (revealed cleanly); > _LAND_GOOD_MAX means it is
        still low/half-shown (the previous post fills the top — "half-and-half"). None when no
        header is on screen (e.g. a full-screen reel)."""
        on = [y for y in anchors.get("headers", []) if y >= 0]
        if not on:
            return None
        return min(on) / float(self.screen_height)

    # ── ENGINE: advance to the next real post ──────────────────────────────────────

    def _reveal_current_metadata(self, max_scrolls: int = 2) -> int:
        """Scroll a little (gentle, smooth) so the CURRENT post's engagement bar comes into view —
        used on the first post already on screen when we arrive on the feed. Stops as soon as the
        bar is visible (or it's an ad / off-feed). Returns the number of scrolls done."""
        done = 0
        for _ in range(max_scrolls):
            a = self._read_feed_anchors()
            if (not a.get("on_feed") or self._dominant_is_ad(a)
                    or self._metadata_visible(a)[0]):
                break
            self._strong_flick("up", distance_px=random.uniform(0.18, 0.26) * self.screen_height,
                               vel_range=_FLICK_VEL_PXS)
            done += 1
            time.sleep(random.uniform(0.45, 0.65))
        return done

    def scroll_feed_to_next_post(self, max_gestures: int = 3, skip_ads: bool = True,
                                 skip_suggested: bool = True, max_ad_skips: int = 2) -> Dict[str, Any]:
        """ONE decisive human gesture that reveals the next post — never a burst of mini-flicks.

        Why this shape (proven by measuring real Lab dumps + a multi-agent analysis, iteration
        #16): the old code did several small flicks per call, and our "fling" did not actually
        fling — `swipe_points` over an ease-OUT bezier released at low terminal velocity, so the
        feed tracked the finger ~1:1 (measured coast ratio ~1.0) and STOPPED on lift. Result:
        each tiny flick moved ~0.2h of content, so it took ~3 of them to pass one ~0.9h post →
        exactly the "petits à-coups / 3 mini-scrolls per post" the user rejected.

        A human does ONE of two things to bring the next post up, and we reproduce both:
          - **flick** (default ~85%): one quick STRONG flick whose momentum coasts ~one post
            (`_strong_flick` → straight high-velocity `raw.swipe` → real OS fling, coast ~3x).
          - **drag** (~15%): keep the finger down and push continuously (`_long_drag` → slow
            `raw.drag`, 1:1 track, lands where the finger stops).
        The gesture is always ONE decisive advance to the next post — a multi-flick "skim" was
        removed (#27) because it overshot organic posts into the ad/suggestion block and falsely
        tripped feed-exhaustion. Skipping a post WITHOUT reading is `browse_feed.skip_prob`, which
        advances to a REAL next post (no junk overshoot).

        Then ONE settle + dump measures where the incoming post's header landed (`land_ratio`).
        If it is not framed at the very top (the previous post still fills the top = "stopped in
        the middle of a post"), exactly ONE **precise 1:1 drag** lifts that header to the top —
        reliable where the variable flick was not. Because the drag moves less than one post
        pitch, it just frames whatever post is currently topmost; it can never skip. So every
        call ends on a cleanly framed post (a full post shown from its top), never mid-post.
        If we land on a Sponsored ad and `skip_ads`, we advance straight past it (smooth) without
        framing/reading it. Off-feed → targeted recovery.
        Returns {advanced, on_feed, on_reel, mode, land_ratio, corrected, reveal, full_post,
        metadata_visible, is_ad, ads_skipped, surface, gestures, dumps}."""
        h = self.screen_height
        dumps = 0
        ads_skipped = 0
        try:
            modes, weights = zip(*_MODE_WEIGHTS)
            mode = random.choices(modes, weights=weights)[0]
            gestures = 0
            if mode == "drag":
                self._long_drag("up", distance_px=random.uniform(*_DRAG_FINGER_H) * h,
                                vel_range=_DRAG_VEL_PXS)
                gestures = 1
                settle = random.uniform(0.15, 0.30)
            else:  # flick (default)
                self._strong_flick("up", distance_px=random.uniform(*_FLICK_FINGER_H) * h,
                                   vel_range=_FLICK_VEL_PXS)
                gestures = 1
                settle = random.uniform(0.45, 0.70)
            time.sleep(settle)   # let the fling coast settle before measuring (natural glance beat)

            anchors = self._read_feed_anchors()      # single dump: surface check + landing
            dumps += 1
            if not anchors["on_feed"]:                # a mis-tap left the feed → recover (rare)
                anchors, used = self._recover_to_feed(anchors)
                dumps += used

            # ADVANCE TO A REAL, NEW POST — but only a HUMAN number of skips. We flick past anything
            # we don't engage with (Sponsored ADS, SUGGESTED/recommended units) or a gesture that
            # didn't advance (video-stuck). BUT a human does NOT frantically scroll through a whole
            # block of recommendations: a run of 2-3 ads/suggestions between two real posts is normal
            # and we glide past it, but we do NOT mitraille through a wall of them. So we skip at most
            # `max_ad_skips` junk units per gesture; beyond that we stop ON the junk and flag
            # `filler_run` (this single gesture only saw filler). Whether the followed feed is truly
            # EXHAUSTED is a session-level call (`browse_feed` counts consecutive filler runs) — a
            # single block of ads must not end the session, there may be a real post right behind it.
            ref_user = getattr(self, "_last_top_username", None)
            ads_skipped = sugg_skipped = stuck = 0
            filler_run = False
            while anchors["on_feed"]:
                cur_user = anchors["posts"][0][1] if anchors.get("posts") else None
                is_ad = skip_ads and self._dominant_is_ad(anchors)
                is_sugg = skip_suggested and self._dominant_is_suggested(anchors)
                reached_new = cur_user is not None and cur_user != ref_user
                if not is_ad and not is_sugg and (reached_new or ref_user is None):
                    break                              # a real, NEW post we want to read → done
                if is_ad or is_sugg:
                    if ads_skipped + sugg_skipped >= max_ad_skips:
                        filler_run = True              # capped on a block of ads/suggestions
                        break
                    if is_ad:
                        ads_skipped += 1
                    else:
                        sugg_skipped += 1
                else:                                  # didn't advance (video-stuck) — retry a flick
                    if stuck >= 2:
                        break
                    stuck += 1
                self._strong_flick("up", distance_px=random.uniform(*_FLICK_FINGER_H) * h,
                                   vel_range=_FLICK_VEL_PXS)
                time.sleep(random.uniform(0.45, 0.65))
                anchors = self._read_feed_anchors()
                dumps += 1
                if not anchors["on_feed"]:
                    anchors, used = self._recover_to_feed(anchors)
                    dumps += used

            on_feed = anchors["on_feed"]
            is_ad = on_feed and self._dominant_is_ad(anchors)
            is_sugg = on_feed and skip_suggested and self._dominant_is_suggested(anchors)
            skippable = is_ad or is_sugg               # still ad/suggested only if the cap was hit

            land = self._incoming_header_ratio(anchors)
            corrected = False
            # Frame the post header at the top → the previous post must not still fill the top
            # ("milieu d'un post"). ONE PRECISE 1:1 drag lifts the header to the top, reliable where
            # the variable flick was not; moving LESS than one pitch it frames whatever post is
            # topmost and can never skip. Skipped if the post is still ad/suggested (we're leaving it).
            if not skippable and on_feed and land is not None and land > _LAND_GOOD_MAX:
                lift_px = (land - _LAND_TARGET) * h          # 1:1 content px to bring the header to the top
                self._long_drag("up", distance_px=lift_px, vel_range=_DRAG_VEL_PXS)
                corrected = True
                time.sleep(random.uniform(0.30, 0.50))
                anchors = self._read_feed_anchors()
                dumps += 1
                land = self._incoming_header_ratio(anchors)

            on_feed = anchors["on_feed"]
            on_reel = on_feed and not anchors["headers"] and anchors.get("video_band") is not None
            is_ad = on_feed and self._dominant_is_ad(anchors)
            is_sugg = on_feed and skip_suggested and self._dominant_is_suggested(anchors)
            skippable = is_ad or is_sugg

            # STOP-ON-METADATA. A post is "fully shown" only when its engagement bar (likes /
            # comments) is on screen — the header only proves a NEW post started. For a tall or
            # video post the bar is still below the fold after framing, so creep up with GENTLE
            # coasting flicks (smooth deceleration to rest, never an abrupt halt) until the bar
            # appears = the whole post has been seen. Capped; skipped for ads/suggested (we leave them).
            meta_vis, like_ratio = self._metadata_visible(anchors)
            reveal = 0
            while on_feed and not on_reel and not skippable and not meta_vis and reveal < 2:
                self._strong_flick("up", distance_px=random.uniform(0.20, 0.28) * h,
                                   vel_range=_FLICK_VEL_PXS)
                reveal += 1
                time.sleep(random.uniform(0.45, 0.65))   # coast to a smooth rest, then measure
                anchors = self._read_feed_anchors()
                dumps += 1
                on_feed = anchors["on_feed"]
                on_reel = on_feed and not anchors["headers"] and anchors.get("video_band") is not None
                is_ad = on_feed and self._dominant_is_ad(anchors)
                is_sugg = on_feed and skip_suggested and self._dominant_is_suggested(anchors)
                skippable = is_ad or is_sugg
                land = self._incoming_header_ratio(anchors)
                meta_vis, like_ratio = self._metadata_visible(anchors)

            new_user = anchors["posts"][0][1] if anchors.get("posts") else None
            advanced = bool(on_feed and new_user is not None
                            and new_user != getattr(self, "_last_top_username", None))
            if on_feed:
                self._last_top_username = new_user
            # filler_run = this gesture only ever saw filler — we hit a block of ads/suggestions and
            # capped the skips, OR we simply ended on an ad/suggested unit. NOT terminal on its own:
            # `browse_feed` decides the feed is exhausted only after several filler runs in a row.
            filler_run = filler_run or (on_feed and skippable)
            # "Post shown in full" = a real (non ad/suggested) post whose engagement bar is visible.
            full_post = bool(on_feed and meta_vis and not skippable)
            self.logger.debug(
                f"📰 feed scroll: mode={mode} flicks={gestures} stuck_retry={stuck} reveal={reveal} "
                f"ads_skipped={ads_skipped} sugg_skipped={sugg_skipped} filler_run={filler_run} land={land} "
                f"corrected={corrected} full_post={full_post} meta={meta_vis} ad={is_ad} sugg={is_sugg} "
                f"advanced={advanced} on_feed={on_feed} surface={anchors.get('surface')} dumps={dumps}")
            return {"advanced": advanced, "on_feed": on_feed, "on_reel": on_reel, "mode": mode,
                    "land_ratio": round(land, 3) if land is not None else None,
                    "corrected": corrected, "reveal": reveal, "stuck_retry": stuck,
                    "full_post": full_post, "metadata_visible": meta_vis, "is_ad": is_ad,
                    "is_suggested": is_sugg, "filler_run": filler_run,
                    "ads_skipped": ads_skipped, "suggested_skipped": sugg_skipped,
                    "like_ratio": round(like_ratio, 3) if like_ratio is not None else None,
                    "surface": anchors.get("surface"), "gestures": gestures, "dumps": dumps}
        except Exception as e:
            self.logger.error(f"scroll_feed_to_next_post failed: {e}")
            return {"advanced": False, "on_feed": False, "on_reel": False, "mode": None,
                    "gestures": 0, "dumps": dumps, "error": str(e)}

    # ── READING: caption / carousel + content-aware dwell (during a reading pause) ──

    def expand_caption_if_truncated(self) -> bool:
        """If the dominant on-screen feed post has a truncated caption, tap its '… plus'/'… more'
        expander to read the full text — like a human pausing on a post. On v410 the feed caption
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
            if t < 0 or b > 0.93 * self.screen_height:   # must be fully on the feed, off the tab bar
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
                            vel_range=_DRAG_VEL_PXS)
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

    def _caption_prose_length(self, root=None) -> int:
        """Real prose length (chars) of the dominant on-screen post's caption — the tallest visible
        `IgTextLayoutView` text, with the username / hashtags / mentions / URLs stripped (see
        `caption_prose_chars`). 0 for an image with no real caption. Drives the reading dwell."""
        root = root if root is not None else self._dump_root()
        if root is None:
            return 0
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
        return caption_prose_chars(best_text)

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
                if random.random() < 0.85:
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

    # ── SESSION: a human browsing rhythm over N read posts ─────────────────────────

    def browse_feed(self, steps: int = 6, skip_ads: bool = True,
                    skip_prob: float = 0.12, read_first: bool = True,
                    skip_suggested: bool = True, read_captions: bool = True,
                    browse_carousels: bool = True) -> Dict[str, Any]:
        """A human feed-browsing session over `steps` READ posts.

        First, the post ALREADY on screen when we arrive (e.g. just opened the feed) is fully
        visible — a human reads it (or skips) before scrolling on. If `read_first`, we read it in
        place (revealing its metadata first if needed); if it's an ad/suggested we just move on.

        Then, for each remaining post: advance to the next post (stopping smoothly once its
        engagement bar is in view — `scroll_feed_to_next_post`, which also SKIPS ads/suggestions)
        and take a reading pause (carousel + caption + dwell, long-tailed, never constant). Now and
        then (`skip_prob`) we skim past 1-2 posts without reading them, like a human; the advances
        coast and settle smoothly so even a skip ends on a cleanly framed post, never a brutal stop.

        `skip_ads`/`skip_suggested` toggle skipping Sponsored ads / Suggested units; `read_captions`/
        `browse_carousels` toggle the intelligent reading during each pause — all four are bot-user
        options surfaced as Lab scenario controls.

        Stops early if pushed off-feed and unrecoverable. Returns
        {steps, off_feed, reached_tail, pauses_s, ads_skipped, suggested_skipped, skipped_posts}."""
        done = 0
        off_feed = False
        pauses: List[float] = []
        ads_skipped = 0
        sugg_skipped = 0
        skipped_posts = 0

        # The post already on screen: read it in place (only if it is a real post — not an ad /
        # suggested unit, which we never engage with).
        if read_first:
            cur = self._read_feed_anchors()
            real = (cur.get("on_feed") and not self._dominant_is_ad(cur)
                    and not (skip_suggested and self._dominant_is_suggested(cur)))
            if real:
                if not self._metadata_visible(cur)[0]:
                    self._reveal_current_metadata()          # scroll a little to see it whole
                pauses.append(round(self.human_reading_pause(
                    read_captions=read_captions, browse_carousels=browse_carousels), 1))
                done += 1

        guard = 0
        reached_tail = False
        filler_runs = 0                  # consecutive gestures that saw only ads/suggestions
        max_iters = max(1, steps) * 3 + 6
        while done < max(1, steps) and guard < max_iters:
            guard += 1
            res = self.scroll_feed_to_next_post(skip_ads=skip_ads, skip_suggested=skip_suggested)
            ads_skipped += res.get("ads_skipped", 0)
            sugg_skipped += res.get("suggested_skipped", 0)
            if not res.get("on_feed"):
                off_feed = True
                break
            if res.get("filler_run"):     # only ads/suggestions this gesture — glide past, don't read
                filler_runs += 1          # a 2-3 ad block is normal; a WALL of them = feed exhausted
                if filler_runs >= _TAIL_FILLER_RUNS:
                    reached_tail = True    # caught up — a human stops here, no frantic scrolling
                    break
                continue                   # try once more: a real post may sit right behind the block
            filler_runs = 0                # reached a real post → reset the exhaustion counter
            if random.random() < skip_prob:          # a human occasionally skips ONE post (no reading)
                r2 = self.scroll_feed_to_next_post(skip_ads=skip_ads, skip_suggested=skip_suggested)
                ads_skipped += r2.get("ads_skipped", 0)
                sugg_skipped += r2.get("suggested_skipped", 0)
                if not r2.get("on_feed"):
                    off_feed = True
                    break
                if r2.get("filler_run"):
                    filler_runs += 1
                    if filler_runs >= _TAIL_FILLER_RUNS:
                        reached_tail = True
                        break
                    continue               # skipped onto a junk block — advance again, don't read it
                filler_runs = 0
                skipped_posts += 1
            pauses.append(round(self.human_reading_pause(                 # read THIS post
                read_captions=read_captions, browse_carousels=browse_carousels), 1))
            done += 1
        self.logger.debug(f"📰 browse_feed: read={done} off_feed={off_feed} reached_tail={reached_tail} "
                          f"ads_skipped={ads_skipped} "
                          f"sugg_skipped={sugg_skipped} skipped={skipped_posts} pauses={pauses}")
        return {"steps": done, "off_feed": off_feed, "reached_tail": reached_tail, "pauses_s": pauses,
                "ads_skipped": ads_skipped, "suggested_skipped": sugg_skipped,
                "skipped_posts": skipped_posts}
