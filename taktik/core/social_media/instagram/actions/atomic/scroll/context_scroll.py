"""Context-specific scroll actions (followers list, comments, feed, post grid, smart scroll)."""

import re
import time
import random
from typing import Optional, Dict, Any, List
from loguru import logger
from lxml import etree

from ...core.base_action import BaseAction
from ....ui.selectors.surfaces.post.comments import POST_COMMENTS_SELECTORS
from .human_gesture import sample_burst_gap

# uiautomator bounds string: "[left,top][right,bottom]"
_BOUNDS_RE = re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')

# Feed-scroll tunables. These are SEEDS to calibrate on the Lab from the measured coast and
# landing (logged every call). Key insight (proven from real dumps): the feed advance is OS
# FLING INERTIA, not finger distance — a real fling coasts ~3x past the finger, so a strong
# flick's finger travel is small (~0.3h) yet it reveals a whole post (pitch ~0.9h). The old
# burst-of-tiny-flicks moved content ~1:1 with the finger (no coast) → "3 mini-scrolls per
# post". See taktik-docs/bot/security/feed-scroll-engineering.md (iteration #16).
_FLICK_FINGER_H = (0.30, 0.40)      # decisive flick finger travel (× screen height)
_FLICK_VEL_PXS = (9000.0, 13000.0)  # flick release velocity px/s (>> Android fling floor)
_DRAG_FINGER_H = (0.80, 0.90)       # continuous-drag finger travel (× screen height)
_DRAG_VEL_PXS = (1500.0, 2200.0)    # drag velocity px/s (slow → 1:1 track, no coast)
_MODE_WEIGHTS = (("flick", 0.55), ("drag", 0.35), ("skim", 0.10))
# A post is "framed" only when its header sits in the very top of the screen — otherwise the
# previous post still fills the top and we stopped "in the middle of a post". So GOOD is tight,
# and any miss is pulled to _LAND_TARGET by a precise drag (below).
_LAND_GOOD_MAX = 0.12               # incoming header y / h ≤ this ⇒ post framed at top (done)
_LAND_TARGET = 0.05                 # where the correction drag lands the header (just under the top)
# Carousel index "N/M"
_CAROUSEL_INDEX_RE = re.compile(r"^(\d+)\s*/\s*(\d+)$")

# Reading-time model (content-aware dwell). A human GLANCES at an image but READS a caption,
# and the read time scales with the real PROSE length — hashtags/mentions/URLs are not "read"
# and must not inflate the count. Tunable seeds.
_GLANCE_S = (1.2, 3.5)       # look at the media (image/video) — not reading
_READ_CPS = (13.0, 22.0)     # chars/second reading speed (skim-ish); sampled per post
_READ_CAP_S = 16.0           # nobody fully reads a wall of text — they skim
_MIN_DWELL_S = 1.0
_LINGER_PROB = 0.12          # occasionally zone out / really into it
_LINGER_S = (3.0, 10.0)
_URL_RE = re.compile(r"https?://\S+")
_TAG_RE = re.compile(r"[#@]\S+")
_EXPAND_LABEL_RE = re.compile(r"\b(?:plus|more|moins|less)\s*$", re.IGNORECASE)


def _caption_prose_chars(text: str) -> int:
    """Length of the REAL prose in a feed caption: drop the leading username token, strip URLs,
    hashtags and @mentions (a wall of `#tags` is not reading), and the trailing expand/collapse
    label ('plus'/'more'/'moins'/'less'). Returns the remaining character count — what a human
    actually reads, used to size the reading dwell."""
    if not text:
        return 0
    body = text.split(" ", 1)
    body = body[1] if len(body) > 1 else ""     # everything after the username
    body = _URL_RE.sub(" ", body)
    body = _TAG_RE.sub(" ", body)
    body = _EXPAND_LABEL_RE.sub("", body.strip())
    body = re.sub(r"\s+", " ", body).strip()
    return len(body)


class ContextScrollMixin(BaseAction):
    """Mixin: context-specific scrolls (followers, comments, feed, grid) + load more + smart scroll."""

    def scroll_followers_list_down(self, duration: float = 0.8, distance_ratio: float = 0.30) -> bool:
        self.logger.debug("👥 Scrolling followers list down")
        
        try:
            center_x = self.screen_width // 2
            start_y = int(self.screen_height * 0.70)
            end_y = int(start_y - self.screen_height * distance_ratio)
            
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration)
            
            self._human_like_delay('scroll')
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling followers list: {e}")
            return False
    
    def scroll_comments_down(self) -> bool:
        """Scroll down in the comments bottom sheet view."""
        self.logger.debug("💬 Scrolling comments list down")
        
        try:
            # Try to scroll within the comments RecyclerView (sticky_header_list)
            # The comments view is a bottom sheet that covers most of the screen
            # We need to scroll within its bounds, not the full screen
            comments_list = self.device.xpath(POST_COMMENTS_SELECTORS.comments_list_selector())
            
            if comments_list.exists:
                # Get the bounds of the comments list
                try:
                    info = comments_list.info
                    bounds = info.get('bounds', {})
                    if bounds:
                        left = bounds.get('left', 0)
                        top = bounds.get('top', 162)
                        right = bounds.get('right', self.screen_width)
                        bottom = bounds.get('bottom', int(self.screen_height * 0.83))
                        
                        # Scroll within the comments list bounds
                        center_x = (left + right) // 2
                        start_y = top + int((bottom - top) * 0.75)
                        end_y = top + int((bottom - top) * 0.25)
                        
                        self.logger.debug(f"💬 Scrolling in comments bounds: ({center_x}, {start_y}) → ({center_x}, {end_y})")
                        self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.6)
                        self._human_like_delay('scroll')
                        return True
                except Exception as e:
                    self.logger.debug(f"Could not get comments list bounds: {e}")
            
            # Fallback: scroll in the bottom sheet area (typically y=200 to y=1200)
            center_x = self.screen_width // 2
            # Comments bottom sheet typically starts around y=160 and ends around y=1260
            start_y = int(self.screen_height * 0.75)  # ~1140 on 1520 screen
            end_y = int(self.screen_height * 0.30)    # ~456 on 1520 screen
            
            self.logger.debug(f"💬 Fallback scroll: ({center_x}, {start_y}) → ({center_x}, {end_y})")
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.6)
            self._human_like_delay('scroll')
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling comments list: {e}")
            return False
    
    def scroll_post_grid_down(self) -> bool:
        self.logger.debug("📸 Scrolling post grid down")
        
        try:
            center_x = self.screen_width // 2
            start_y = int(self.screen_height * 0.75)
            end_y = int(self.screen_height * 0.25)
            
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.5)
            
            self._human_like_delay('scroll')
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling post grid: {e}")
            return False
    
    def scroll_feed_down(self) -> bool:
        self.logger.debug("📱 Scrolling feed down")
        
        try:
            center_x = self.screen_width // 2
            start_y = int(self.screen_height * 0.7)
            end_y = int(self.screen_height * 0.3)
            
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.5)
            
            self._human_like_delay('scroll')
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling feed: {e}")
            return False

    # ── Intelligent feed scroll: snap to next post, human gesture ──────────────────

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
        top_bar_bottom: Optional[int] = None
        tab_top: Optional[int] = None
        has_feed_marker = False
        has_clips_root = False
        has_profile = False   # we mis-tapped onto a profile (e.g. the post author)
        video_band: Optional[tuple] = None  # (top, bottom) of the inline playing video/reel
        # An actual playing video/reel embedded in the feed (NOT `clips_tab`, which is just
        # the Reels nav button and is always present).
        _video_ids = ("video_container", "clips_video_container", "clips_media_component")
        _profile_ids = ("row_profile_header", "profile_header_follow_button", "profile_viewpager",
                        "profile_tabs_container")
        try:
            xml = self.device._device.dump_hierarchy()
            root = etree.fromstring(xml.encode("utf-8"))
            for node in root.iter():
                # Ad marker: the "Sponsorisé(e)" / "Sponsored" label lives in a content-desc
                # (on the media or a label), often on a node without a resource-id → check first.
                cd = node.get("content-desc") or ""
                if cd and ("sponsoris" in cd.lower() or "sponsored" in cd.lower()):
                    ma = _BOUNDS_RE.search(node.get("bounds", ""))
                    if ma:
                        ad_tops.append(int(ma.group(2)))
                rid = node.get("resource-id", "")
                if not rid:
                    continue
                short = rid.rsplit("/", 1)[-1]
                if short == "root_clips_layout":
                    has_clips_root = True
                if short in _profile_ids:
                    has_profile = True
                if short in ("row_feed_photo_profile_name", "main_feed_action_bar", "reels_tray_container", "tab_bar"):
                    has_feed_marker = True
                m = _BOUNDS_RE.search(node.get("bounds", ""))
                if not m:
                    continue
                top, bottom = int(m.group(2)), int(m.group(4))
                if short == "row_feed_photo_profile_name":
                    headers.append(top)
                    user = (node.get("text") or node.get("content-desc") or "").strip()
                    posts.append((top, user))
                elif short == "row_feed_button_like":
                    likes.append(top)
                elif short == "main_feed_action_bar":
                    top_bar_bottom = bottom
                elif short == "tab_bar":  # tab_bar_shadow has no top we care about
                    tab_top = top
                elif short in _video_ids:
                    if video_band is None or (bottom - top) > (video_band[1] - video_band[0]):
                        video_band = (top, bottom)
        except Exception as e:
            self.logger.debug(f"feed anchor read failed: {e}")
            return {"headers": [], "posts": [], "likes": [], "ad_tops": [],
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
            "top": top_bar_bottom if top_bar_bottom is not None else int(self.screen_height * 0.10),
            "tab": tab_top if tab_top is not None else int(self.screen_height * 0.92),
            "on_feed": on_feed,
            # Where we are when off-feed, so recovery can be targeted (profile vs reel viewer).
            "surface": surface,
            "video_band": video_band,
        }

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
                self._tap_xpath('//*[@content-desc="Retour" or @content-desc="Back"'
                                ' or @content-desc="Revenir en arrière"]')
                # 2) the Home/feed bottom tab if the nav bar is present
                or self._tap_xpath('//*[contains(@resource-id,"feed_tab")]')
                or self._tap_xpath('//*[@content-desc="Accueil" or @content-desc="Home"]')
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

    def _dominant_is_ad(self, anchors: Dict[str, Any]) -> bool:
        """Is the dominant on-screen post a Sponsored ad? An ad marker ("Sponsorisé(e)"/
        "Sponsored" content-desc) is attributed to the dominant post when it sits between that
        post's header and the next post's header. (A full-screen sponsored reel has no feed
        header → any ad marker counts.) Used to SKIP ads while browsing, never interact."""
        ads = anchors.get("ad_tops") or []
        if not ads:
            return False
        headers = sorted(y for y in anchors.get("headers", []) if y >= 0)
        if not headers:
            return True
        hdr = headers[0]
        nxt = next((y for y in headers if y > hdr), self.screen_height * 3)
        lo = hdr - 0.08 * self.screen_height
        return any(lo <= at < nxt for at in ads)

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

    def _incoming_header_ratio(self, anchors: Dict[str, Any]) -> Optional[float]:
        """y/h of the dominant incoming post header = the topmost header on screen. Near 0 means
        the next post is pinned at the top (revealed cleanly); > _LAND_GOOD_MAX means it is
        still low/half-shown (the previous post fills the top — "half-and-half"). None when no
        header is on screen (e.g. a full-screen reel)."""
        on = [y for y in anchors.get("headers", []) if y >= 0]
        if not on:
            return None
        return min(on) / float(self.screen_height)

    def scroll_feed_to_next_post(self, max_gestures: int = 3, skip_ads: bool = True,
                                 max_ad_skips: int = 3) -> Dict[str, Any]:
        """ONE decisive human gesture that reveals the next post — never a burst of mini-flicks.

        Why this shape (proven by measuring real Lab dumps + a multi-agent analysis, iteration
        #16): the old code did several small flicks per call, and our "fling" did not actually
        fling — `swipe_points` over an ease-OUT bezier released at low terminal velocity, so the
        feed tracked the finger ~1:1 (measured coast ratio ~1.0) and STOPPED on lift. Result:
        each tiny flick moved ~0.2h of content, so it took ~3 of them to pass one ~0.9h post →
        exactly the "petits à-coups / 3 mini-scrolls per post" the user rejected.

        A human does ONE of two things to bring the next post up, and we reproduce both:
          - **flick** (default ~55%): one quick STRONG flick whose momentum coasts ~one post
            (`_strong_flick` → straight high-velocity `raw.swipe` → real OS fling, coast ~3x).
          - **drag** (~35%): keep the finger down and push continuously (`_long_drag` → slow
            `raw.drag`, 1:1 track, lands where the finger stops).
          - **skim** (~10%): the genuine "scroll past several posts" burst — 2-3 strong flicks
            spaced by the real inter-flick gap (so each coast dies, no catch). Distinct from
            reveal-one-post; this is the only branch that chains gestures.

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
            elif mode == "skim":
                n = random.choices((2, 3), weights=(60, 40))[0]
                for i in range(n):
                    self._strong_flick("up", distance_px=random.uniform(*_FLICK_FINGER_H) * h,
                                       vel_range=_FLICK_VEL_PXS)
                    gestures += 1
                    if i < n - 1:
                        time.sleep(sample_burst_gap())   # let each coast die → no catch
                settle = random.uniform(0.45, 0.70)
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

            # SKIP ADS DIRECTLY. If we landed on a Sponsored post, don't waste gestures framing or
            # reading it — advance straight past it (smooth coasting flicks) to the next real post,
            # the moment we recognise it. We never frame, read or touch an ad.
            while (skip_ads and anchors["on_feed"] and self._dominant_is_ad(anchors)
                   and ads_skipped < max_ad_skips):
                ads_skipped += 1
                self._strong_flick("up", distance_px=random.uniform(*_FLICK_FINGER_H) * h,
                                   vel_range=_FLICK_VEL_PXS)
                time.sleep(random.uniform(0.45, 0.65))
                anchors = self._read_feed_anchors()
                dumps += 1
                if not anchors["on_feed"]:
                    anchors, used = self._recover_to_feed(anchors)
                    dumps += used

            on_feed = anchors["on_feed"]
            is_ad = on_feed and self._dominant_is_ad(anchors)   # still an ad only if the cap was hit
            land = self._incoming_header_ratio(anchors)
            corrected = False
            # Frame the (non-ad) post header at the top → the previous post must not still fill the
            # top ("milieu d'un post"). ONE PRECISE 1:1 drag lifts the header to the top, reliable
            # where the variable flick was not; moving LESS than one pitch it frames whatever post
            # is topmost and can never skip. Skipped if the post is still an ad (we're leaving it).
            if not is_ad and on_feed and land is not None and land > _LAND_GOOD_MAX:
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

            # STOP-ON-METADATA. A post is "fully shown" only when its engagement bar (likes /
            # comments) is on screen — the header only proves a NEW post started. For a tall or
            # video post the bar is still below the fold after framing, so creep up with GENTLE
            # coasting flicks (smooth deceleration to rest, never an abrupt halt) until the bar
            # appears = the whole post has been seen (header first, then engagement). Capped so we
            # never loop; skipped for ads (no point revealing an ad's metadata — we skip it).
            meta_vis, like_ratio = self._metadata_visible(anchors)
            reveal = 0
            while on_feed and not on_reel and not is_ad and not meta_vis and reveal < 2:
                self._strong_flick("up", distance_px=random.uniform(0.20, 0.28) * h,
                                   vel_range=_FLICK_VEL_PXS)
                reveal += 1
                time.sleep(random.uniform(0.45, 0.65))   # coast to a smooth rest, then measure
                anchors = self._read_feed_anchors()
                dumps += 1
                on_feed = anchors["on_feed"]
                on_reel = on_feed and not anchors["headers"] and anchors.get("video_band") is not None
                is_ad = on_feed and self._dominant_is_ad(anchors)
                land = self._incoming_header_ratio(anchors)
                meta_vis, like_ratio = self._metadata_visible(anchors)

            new_user = anchors["posts"][0][1] if anchors.get("posts") else None
            advanced = bool(on_feed and new_user is not None
                            and new_user != getattr(self, "_last_top_username", None))
            if on_feed:
                self._last_top_username = new_user
            # "Post shown in full" = the engagement bar is visible (the header was seen on the way up).
            full_post = bool(on_feed and meta_vis)
            self.logger.debug(
                f"📰 feed scroll: mode={mode} flicks={gestures} reveal={reveal} ads_skipped={ads_skipped} "
                f"land={land} corrected={corrected} full_post={full_post} meta={meta_vis} ad={is_ad} "
                f"advanced={advanced} on_feed={on_feed} surface={anchors.get('surface')} dumps={dumps}")
            return {"advanced": advanced, "on_feed": on_feed, "on_reel": on_reel, "mode": mode,
                    "land_ratio": round(land, 3) if land is not None else None,
                    "corrected": corrected, "reveal": reveal, "full_post": full_post,
                    "metadata_visible": meta_vis, "is_ad": is_ad, "ads_skipped": ads_skipped,
                    "like_ratio": round(like_ratio, 3) if like_ratio is not None else None,
                    "surface": anchors.get("surface"), "gestures": gestures, "dumps": dumps}
        except Exception as e:
            self.logger.error(f"scroll_feed_to_next_post failed: {e}")
            return {"advanced": False, "on_feed": False, "on_reel": False, "mode": None,
                    "gestures": 0, "dumps": dumps, "error": str(e)}

    # ----- Intelligent reading (run during a reading pause, on the dominant on-screen post) ---

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
        """If the dominant on-screen feed post has a truncated caption, tap its '… plus'/'… more'
        expander to read the full text — like a human pausing on a post. On v410 the feed caption
        is an empty-resource-id `IgTextLayoutView` whose dedicated expander is a child Button with
        content-desc EXACTLY 'plus' (FR) / 'more' (EN). We click that exact button (a random point
        in its bounds, humanised) — never `contains('plus')`, so the Sponsored 'En savoir plus' /
        'Learn more' ad CTA (a link) is excluded. Returns True if a caption was expanded."""
        root = self._dump_root()
        if root is None:
            return False
        LAYOUT = "com.instagram.ui.widget.textview.IgTextLayoutView"
        labels = ("plus", "more")
        best = None  # (visible_height, (l, t, r, b))
        for node in root.iter():
            if node.get("class", "") != LAYOUT:
                continue
            target = None
            for child in node.iter():
                if child is node:
                    continue
                if (child.get("class") == "android.widget.Button"
                        and child.get("clickable") == "true"
                        and (child.get("content-desc") or "").strip() in labels):
                    target = child
                    break
            if target is None:   # fallback: a truncated layout whose text ends with the label
                txt = (node.get("text") or "").rstrip()
                if not (txt.endswith(" plus") or txt.endswith(" more")):
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
        LAYOUT = "com.instagram.ui.widget.textview.IgTextLayoutView"
        fold = int(0.86 * self.screen_height)
        done = 0
        for _ in range(max_scrolls):
            root = self._dump_root()
            if root is None:
                break
            below = None    # tallest caption whose bottom runs past the fold
            for node in root.iter():
                if node.get("class", "") != LAYOUT:
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
        VIEWPAGER, MEDIA, INDEX = ("carousel_viewpager", "carousel_media_group",
                                   "carousel_index_indicator_text_view")
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
        `_caption_prose_chars`). 0 for an image with no real caption. Drives the reading dwell."""
        root = root if root is not None else self._dump_root()
        if root is None:
            return 0
        LAYOUT = "com.instagram.ui.widget.textview.IgTextLayoutView"
        best_text, best_h = "", -1
        for node in root.iter():
            if node.get("class", "") != LAYOUT:
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
        return _caption_prose_chars(best_text)

    def _content_dwell(self, prose_len: int) -> float:
        """How long a human dwells on a post, FROM ITS CONTENT — an image is glanced at (~1-3s,
        "I like it"), a caption is READ in proportion to its PROSE length (hashtags excluded), and
        once in a while they linger. This replaces a content-blind constant: no more 14s on a plain
        image. (A future vision/`post_analysis` layer can override this via `human_reading_pause`.)"""
        glance = random.uniform(*_GLANCE_S)
        reading = 0.0
        if prose_len >= 12:     # below ~12 chars there's nothing to "read"
            reading = min(prose_len / random.uniform(*_READ_CPS), _READ_CAP_S)
        total = glance + reading
        if random.random() < _LINGER_PROB:
            total += random.uniform(*_LINGER_S)
        return total

    def human_reading_pause(self, dwell_s: Optional[float] = None) -> float:
        """One human reading pause on the current post. First the intelligent reading — browse a
        carousel's slides, then expand & READ a truncated caption — which already consumes real
        time. Then dwell so the TOTAL time on the post matches the CONTENT: an image is glanced at,
        a real caption is read in proportion to its prose length (hashtags excluded). Pass
        `dwell_s` to override the target (e.g. a future vision/`post_analysis` relevance score).
        Returns the total time spent on the post (seconds)."""
        start = time.monotonic()
        try:
            self.browse_carousel_slides()
        except Exception as e:
            self.logger.debug(f"carousel browse skipped: {e}")
        try:
            if random.random() < 0.85:
                self.expand_caption_if_truncated()
        except Exception as e:
            self.logger.debug(f"caption expand skipped: {e}")
        prose = self._caption_prose_length()                 # full text now (caption expanded)
        target = dwell_s if dwell_s is not None else self._content_dwell(prose)
        spent = time.monotonic() - start                     # carousel/caption already took time
        remain = max(_MIN_DWELL_S, target - spent)
        time.sleep(remain)
        total = spent + remain
        self.logger.debug(f"⏲️ reading: prose={prose}ch target={target:.1f}s active={spent:.1f}s "
                          f"dwell={remain:.1f}s total={total:.1f}s")
        return round(total, 1)

    def browse_feed(self, steps: int = 6, skip_ads: bool = True,
                    skip_prob: float = 0.18, read_first: bool = True) -> Dict[str, Any]:
        """A human feed-browsing session over `steps` READ posts.

        First, the post ALREADY on screen when we arrive (e.g. just opened the feed) is fully
        visible — a human reads it (or skips) before scrolling on. If `read_first`, we read it in
        place (revealing its metadata first if needed); if it's an ad we just move on.

        Then, for each remaining post: advance to the next post (stopping smoothly once its
        engagement bar is in view — `scroll_feed_to_next_post`, which also SKIPS ads directly) and
        take a reading pause (carousel + caption + dwell, long-tailed, never constant). Now and then
        (`skip_prob`) we skim past 1-2 posts without reading them, like a human; the advances coast
        and settle smoothly so even a skip ends on a cleanly framed post, never a brutal stop.

        Stops early if pushed off-feed and unrecoverable. Returns
        {steps, off_feed, pauses_s, ads_skipped, skipped_posts}."""
        done = 0
        off_feed = False
        pauses: List[float] = []
        ads_skipped = 0
        skipped_posts = 0

        # The post already on screen: read it in place (or skip if it is an ad / can't be revealed).
        if read_first:
            cur = self._read_feed_anchors()
            if cur.get("on_feed") and not self._dominant_is_ad(cur):
                if not self._metadata_visible(cur)[0]:
                    self._reveal_current_metadata()          # scroll a little to see it whole
                pauses.append(round(self.human_reading_pause(), 1))
                done += 1
            elif cur.get("on_feed") and self._dominant_is_ad(cur):
                ads_skipped += 1                              # arrived on an ad → don't read it

        guard = 0
        max_iters = max(1, steps) * 6 + 12   # backstop against a feed that is all ads
        while done < max(1, steps) and guard < max_iters:
            guard += 1
            res = self.scroll_feed_to_next_post(skip_ads=skip_ads)
            ads_skipped += res.get("ads_skipped", 0)
            if not res.get("on_feed"):
                off_feed = True
                break
            if skip_ads and res.get("is_ad"):       # cap hit, still an ad → move on, don't read
                continue
            if random.random() < skip_prob:          # a human skim past 1-2 posts (no reading)
                for _ in range(random.choice((1, 2))):
                    r2 = self.scroll_feed_to_next_post(skip_ads=skip_ads)
                    ads_skipped += r2.get("ads_skipped", 0)
                    if not r2.get("on_feed"):
                        off_feed = True
                        break
                    if not r2.get("is_ad"):
                        skipped_posts += 1
                if off_feed:
                    break
            pauses.append(round(self.human_reading_pause(), 1))   # read THIS post
            done += 1
        self.logger.debug(f"📰 browse_feed: read={done} off_feed={off_feed} ads_skipped={ads_skipped} "
                          f"skipped={skipped_posts} pauses={pauses}")
        return {"steps": done, "off_feed": off_feed, "pauses_s": pauses,
                "ads_skipped": ads_skipped, "skipped_posts": skipped_posts}

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
