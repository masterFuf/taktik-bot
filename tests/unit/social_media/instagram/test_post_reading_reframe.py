"""Post reframe after reading — the post (image + buttons) is framed again before acting.

Reading a caption scrolls down (reveal); without scrolling back, the double-tap band,
the generic like/comment button selectors and the AI screenshot all act on a mis-framed
screen (possibly the NEXT post). The reading pause must reframe after the dwell.
"""

from lxml import etree

import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as pr
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS


class _Host(pr.PostReadingMixin):
    screen_width = 1080
    screen_height = 2000

    def __init__(self):
        self.drags = []
        self.swipes = []
        self.hswipes = []

        class _Log:
            def debug(self, *_a, **_k): pass
            def error(self, *_a, **_k): pass
        self.logger = _Log()

    def _long_drag(self, direction="up", distance_px=None, vel_range=None, guard_start=False,
                   velocity_scale=1.0):
        assert guard_start is True
        self.drags.append((direction, distance_px))
        return True

    def _human_swipe(self, direction="up", distance_px=None, start_band=None, controlled=False,
                     guard_start=False):
        assert guard_start is True
        self.swipes.append({"direction": direction, "distance_px": distance_px,
                            "start_band": start_band, "controlled": controlled})
        return True

    def _human_horizontal_swipe(self, direction="left", **kwargs):
        self.hswipes.append({"direction": direction, **kwargs})
        return True


def _root_with_caption_below_fold():
    # fold = 0.86 * 2000 = 1720; caption bottom 1900 > fold -> needs a reveal scroll.
    xml = (f'<hierarchy><node class="{FS.caption_layout_class}" text="long caption" '
           f'bounds="[0,1500][1080,1900]" /></hierarchy>')
    return etree.fromstring(xml.encode("utf-8"))


def _root_without_overflow():
    xml = (f'<hierarchy><node class="{FS.caption_layout_class}" text="short" '
           f'bounds="[0,1500][1080,1700]" /></hierarchy>')
    return etree.fromstring(xml.encode("utf-8"))


def _root_with_carousel(index="1/3"):
    xml = (
        f'<hierarchy><node resource-id="com.instagram.android:id/{FS.header_id}" '
        f'text="author" bounds="[80,220][500,280]" />'
        f'<node resource-id="com.instagram.android:id/{FS.carousel_viewpager_id}" '
        f'bounds="[80,300][1000,1500]" />'
        f'<node resource-id="com.instagram.android:id/{FS.carousel_index_id}" '
        f'text="{index}" bounds="[850,320][940,380]" />'
        f'<node resource-id="com.instagram.android:id/{FS.like_button_id}" '
        f'bounds="[80,1520][180,1620]" /></hierarchy>'
    )
    return etree.fromstring(xml.encode("utf-8"))


def _root_with_partial_next_carousel():
    xml = (
        f'<hierarchy><node resource-id="com.instagram.android:id/{FS.header_id}" '
        f'text="current" bounds="[80,100][500,170]" />'
        f'<node resource-id="com.instagram.android:id/{FS.like_button_id}" '
        f'bounds="[80,1050][180,1140]" />'
        f'<node resource-id="com.instagram.android:id/{FS.header_id}" '
        f'text="next" bounds="[80,1220][500,1290]" />'
        f'<node resource-id="com.instagram.android:id/{FS.carousel_viewpager_id}" '
        f'bounds="[80,1310][1000,2250]" />'
        f'<node resource-id="com.instagram.android:id/{FS.carousel_index_id}" '
        f'text="1/4" bounds="[850,1330][940,1390]" />'
        f'<node resource-id="com.instagram.android:id/{FS.tab_bar_id}" '
        f'bounds="[0,1900][1080,2000]" /></hierarchy>'
    )
    return etree.fromstring(xml.encode("utf-8"))


def test_reveal_returns_total_scrolled_px(monkeypatch):
    host = _Host()
    roots = [_root_with_caption_below_fold(), _root_without_overflow()]
    monkeypatch.setattr(host, "_dump_root", lambda: roots.pop(0))
    monkeypatch.setattr(pr.time, "sleep", lambda _s: None)
    monkeypatch.setattr(pr.random, "uniform", lambda a, b: a)  # dist = 0.20 * 2000 = 400

    px = host._reveal_expanded_caption()
    assert px == 400
    assert host.drags == [("up", 400.0)]


def test_reframe_scrolls_back_down_controlled(monkeypatch):
    host = _Host()
    monkeypatch.setattr(pr.time, "sleep", lambda _s: None)
    monkeypatch.setattr(pr.random, "uniform", lambda a, b: a)  # bias = 0.95

    host._reframe_post_after_reading(400)
    assert len(host.swipes) == 1            # 400*0.95=380 <= 0.45*2000 -> one gesture
    s = host.swipes[0]
    assert s["direction"] == "down" and s["controlled"] is True
    assert abs(s["distance_px"] - 380) < 1
    assert s["start_band"] == (0.18 * 2000, 0.32 * 2000)   # starts HIGH to travel down


def test_reframe_splits_long_return_into_two_gestures(monkeypatch):
    host = _Host()
    monkeypatch.setattr(pr.time, "sleep", lambda _s: None)
    monkeypatch.setattr(pr.random, "uniform", lambda a, b: b)  # bias = 1.15

    host._reframe_post_after_reading(1000)  # 1150 > 900 -> two gestures
    assert len(host.swipes) == 2
    assert all(s["direction"] == "down" for s in host.swipes)
    assert abs(sum(s["distance_px"] for s in host.swipes) - 1150) < 1


def test_reading_pause_reframes_after_dwell(monkeypatch):
    host = _Host()
    calls = []
    monkeypatch.setattr(pr.time, "sleep", lambda _s: None)
    monkeypatch.setattr(pr.random, "random", lambda: 0.0)      # always expand
    monkeypatch.setattr(pr, "content_dwell", lambda _p: 0.0)

    def fake_expand():
        host._last_reveal_scroll_px = 500
        return True
    monkeypatch.setattr(host, "expand_caption_if_truncated", fake_expand)
    monkeypatch.setattr(host, "browse_carousel_slides", lambda: 0)
    monkeypatch.setattr(host, "_caption_prose_length", lambda root=None: 0)
    monkeypatch.setattr(host, "_reframe_post_after_reading", lambda px: calls.append(px))

    host.human_reading_pause()
    assert calls == [500]                  # reframed with the revealed distance
    assert host._last_reveal_scroll_px == 0  # reset for the next post


def test_reading_pause_skips_reframe_below_threshold(monkeypatch):
    host = _Host()
    calls = []
    monkeypatch.setattr(pr.time, "sleep", lambda _s: None)
    monkeypatch.setattr(pr.random, "random", lambda: 0.0)
    monkeypatch.setattr(pr, "content_dwell", lambda _p: 0.0)

    def fake_expand():
        host._last_reveal_scroll_px = 50   # tiny reveal: post still framed
        return True
    monkeypatch.setattr(host, "expand_caption_if_truncated", fake_expand)
    monkeypatch.setattr(host, "browse_carousel_slides", lambda: 0)
    monkeypatch.setattr(host, "_caption_prose_length", lambda root=None: 0)
    monkeypatch.setattr(host, "_reframe_post_after_reading", lambda px: calls.append(px))

    host.human_reading_pause()
    assert calls == []


def test_automatic_reading_dwell_uses_the_session_attention_scale(monkeypatch):
    host = _Host()
    sleeps = []
    ticks = iter((100.0, 100.0, 112.0))
    monkeypatch.setattr(pr.time, "sleep", sleeps.append)
    monkeypatch.setattr(pr.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(pr, "content_dwell", lambda _prose: 10.0)
    monkeypatch.setattr(host, "_caption_prose_length", lambda root=None: 80)
    host._reading_dwell_scale = lambda _context: 1.2

    total = host.human_reading_pause(read_captions=False, browse_carousels=False)

    assert sleeps == [12.0]
    assert total == 12.0


def test_carousel_uses_shared_horizontal_engine_and_session_scales(monkeypatch):
    host = _Host()
    roots = [_root_with_carousel(), _root_without_overflow()]
    sleeps = []
    decision = {
        "distance_scale": 1.04,
        "velocity_scale": 0.90,
        "dwell_scale": 1.20,
        "style": "deliberate",
    }
    host._plan_behavior_gesture = lambda context, gesture: (
        decision if (context, gesture) == ("carousel_slide", "hswipe") else None
    )
    monkeypatch.setattr(host, "_dump_root", lambda: roots.pop(0))
    monkeypatch.setattr(pr.time, "sleep", sleeps.append)
    monkeypatch.setattr(pr.random, "uniform", lambda lower, _upper: lower)

    count = host.browse_carousel_slides()

    assert count == 1
    assert host.hswipes == [{
        "direction": "left",
        "distance_ratio": 0.60,
        "bounds": (80, 300, 1000, 1500),
        "distance_scale": 1.04,
        "velocity_scale": 0.90,
    }]
    assert sleeps == [0.6 * 1.20]
    assert host._last_carousel_behavior["style"] == "deliberate"


def test_partial_next_carousel_is_not_browsed(monkeypatch):
    host = _Host()
    monkeypatch.setattr(host, "_dump_root", _root_with_partial_next_carousel)

    assert host.browse_carousel_slides() == 0
    assert host.hswipes == []
    assert host._last_carousel_skip_reason == "carousel_not_fully_framed"


def test_carousel_without_its_engagement_row_is_ambiguous(monkeypatch):
    host = _Host()
    root = _root_with_carousel()
    for node in list(root):
        if node.get("resource-id", "").endswith(FS.like_button_id):
            root.remove(node)
    monkeypatch.setattr(host, "_dump_root", lambda: root)

    assert host.browse_carousel_slides() == 0
    assert host.hswipes == []
    assert host._last_carousel_skip_reason == "missing_post_anchors"
