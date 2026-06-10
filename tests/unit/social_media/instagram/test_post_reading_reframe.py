"""Post reframe after reading — the post (image + buttons) is framed again before acting.

Reading a caption scrolls down (reveal); without scrolling back, the double-tap band,
the generic like/comment button selectors and the AI screenshot all act on a mis-framed
screen (possibly the NEXT post). The reading pause must reframe after the dwell.
"""

from lxml import etree

import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as pr
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS as FS


class _Host(pr.PostReadingMixin):
    screen_height = 2000

    def __init__(self):
        self.drags = []
        self.swipes = []

        class _Log:
            def debug(self, *_a, **_k): pass
            def error(self, *_a, **_k): pass
        self.logger = _Log()

    def _long_drag(self, direction="up", distance_px=None, vel_range=None):
        self.drags.append((direction, distance_px))
        return True

    def _human_swipe(self, direction="up", distance_px=None, start_band=None, controlled=False):
        self.swipes.append({"direction": direction, "distance_px": distance_px,
                            "start_band": start_band, "controlled": controlled})
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
