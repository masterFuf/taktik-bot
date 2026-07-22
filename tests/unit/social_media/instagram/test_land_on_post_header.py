"""land_on_post_header frames the topmost post at the top after an advance (no half-and-half),
reusing the feed's 1:1 lift-drag, and is a safe no-op when no post header is detected.
"""

import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as fs
from taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll import FeedScrollMixin


class _Host(FeedScrollMixin):
    def __init__(self, header_seq, screen_height=2000):
        # header_seq: list of header-y (px) returned by successive _read_feed_anchors calls
        # (None = no header on screen).
        self.screen_height = screen_height
        self._seq = list(header_seq)
        self.drags = []

        class _Log:
            def debug(self, *a, **k): pass
            def info(self, *a, **k): pass
        self.logger = _Log()

    def _read_feed_anchors(self):
        y = self._seq.pop(0) if self._seq else None
        return {"headers": ([y] if y is not None else [])}

    def _long_drag(self, direction, distance_px=0, vel_range=None, guard_start=False,
                   velocity_scale=1.0):
        assert guard_start is True
        self.drags.append((direction, round(distance_px)))
        return True


def _patch(monkeypatch):
    monkeypatch.setattr(fs.time, "sleep", lambda _s: None)
    monkeypatch.setattr(fs.random, "uniform", lambda a, b: a)


def test_no_correction_when_already_framed(monkeypatch):
    _patch(monkeypatch)
    h = _Host([int(0.04 * 2000)])          # header near the top (ratio 0.04 ≤ 0.12)
    res = h.land_on_post_header()
    assert h.drags == []                   # no correction needed
    assert res["framed"] is True and res["corrected"] is False


def test_corrects_when_landed_mid_post(monkeypatch):
    _patch(monkeypatch)
    # First read: header at 0.5h (half-and-half) → one lift drag of (0.5-0.05)*h; then framed.
    h = _Host([int(0.5 * 2000), int(0.05 * 2000)])
    res = h.land_on_post_header()
    assert len(h.drags) == 1
    assert h.drags[0][0] == "up"
    assert h.drags[0][1] == round((0.5 - 0.05) * 2000)   # 1:1 content px to the target
    assert res["corrected"] is True and res["framed"] is True


def test_noop_when_no_header_detected(monkeypatch):
    _patch(monkeypatch)
    h = _Host([None])                      # e.g. a reel / unrecognised surface
    res = h.land_on_post_header()
    assert h.drags == []                   # never drags blindly
    assert res["framed"] is False and res["corrected"] is False


def test_single_correction_cap(monkeypatch):
    _patch(monkeypatch)
    # Stays mid-post on both reads → only ONE correction attempt (default cap), never loops.
    h = _Host([int(0.6 * 2000), int(0.4 * 2000)])
    h.land_on_post_header()
    assert len(h.drags) == 1


def test_session_policy_can_defer_a_moderate_correction(monkeypatch):
    _patch(monkeypatch)
    h = _Host([int(0.30 * 2000)])
    h._decide_post_framing = lambda **_kwargs: {
        "correct": False,
        "needed": True,
        "probability": 0.42,
        "reason": "deferred",
    }

    res = h.land_on_post_header()

    assert h.drags == []
    assert res["corrected"] is False
    assert res["framed"] is False
    assert res["framing_decision"]["reason"] == "deferred"


def test_tiny_selected_correction_is_accepted_instead_of_becoming_a_touch_slop_jolt(monkeypatch):
    _patch(monkeypatch)
    h = _Host([int(0.15 * 2000)])
    h._decide_post_framing = lambda **_kwargs: {
        "correct": True,
        "needed": True,
        "probability": 0.7,
        "reason": "selected",
        "reaction_delay_s": 0.0,
        "target_ratio": 0.10,
    }

    res = h.land_on_post_header()

    assert h.drags == []
    assert res["corrected"] is False
    assert res["framing_decision"]["reason"] == "accepted_below_smooth_drag_floor"
