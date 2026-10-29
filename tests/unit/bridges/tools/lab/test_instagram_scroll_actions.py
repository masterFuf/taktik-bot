"""The Cartography drag probe exercises the real guarded production primitive.

The screens are real dumps of Instagram 447.0.0.55.81 in French on a Pixel 6a (1080 x 2400),
anonymized: a post opened from a profile with its whole action row; a home feed whose only whole
Share button is at the top, the next post's row being cut by the tab bar at the bottom; and a home
feed whose only action row is cut by the tab bar.
"""

import random
from types import SimpleNamespace

import taktik.core.shared.behavior.gesture_primitives as gp
from bridges.tools.lab.actions.instagram.scroll import scroll_feed_drag, scroll_feed_next
from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.social_media.instagram.actions.atomic.scroll.base_scroll import BaseScrollMixin
from unit.paths import CORE


FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
WHOLE_ROW = (FIXTURES / "ig447_fr_profile_post_collab_carousel_action_row.xml").read_text(encoding="utf-8")
WHOLE_ABOVE_CUT = (FIXTURES / "ig447_fr_home_feed_whole_share_above_cut_row.xml").read_text(encoding="utf-8")
ONLY_CUT = (FIXTURES / "ig447_fr_home_feed_share_row_cut_by_tab_bar.xml").read_text(encoding="utf-8")


class _Log:
    def debug(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class _Raw:
    """The phone: its screen as dumped, and the paths it was handed."""

    def __init__(self, xml):
        self.xml = xml
        self.paths = []

    def dump_hierarchy(self):
        return self.xml

    def swipe_points(self, points, _duration):
        self.paths.append([list(point) for point in points])


class _Popup:
    def __init__(self, results):
        self.results = list(results)

    def _detect_blocking_modal(self):
        return self.results.pop(0)


def _probe(xml, modals, monkeypatch):
    monkeypatch.setattr(gp.time, "sleep", lambda _seconds: None)
    random.seed(3)
    scroll = object.__new__(BaseScrollMixin)
    scroll.device = BaseDeviceFacade(_Raw(xml))
    scroll.logger = _Log()
    scroll.screen_width, scroll.screen_height = 1080, 2400
    return scroll, scroll_feed_drag(SimpleNamespace(scroll=scroll, popup=_Popup(modals)), {})


def test_feed_drag_requests_share_center_and_rejects_no_modal(monkeypatch):
    scroll, result = _probe(WHOLE_ROW, [None, None], monkeypatch)

    assert result["success"] is True
    assert result["details"]["share_bounds"] == (632, 1359, 695, 1480)
    assert result["details"]["requested_start"] == (663, 1419)
    assert result["details"]["gesture_start"]["adjusted"] is True
    assert result["details"]["modal_after"] is None
    final = result["details"]["gesture_start"]["final"]
    assert scroll.device._device.paths[0][0] == list(final)


def test_feed_drag_fails_if_direct_share_sheet_opens(monkeypatch):
    _scroll, result = _probe(WHOLE_ROW, [None, "direct_share_sheet"], monkeypatch)

    assert result["success"] is False
    assert result["details"]["modal_after"] == "direct_share_sheet"


def test_feed_drag_aims_at_a_whole_share_not_the_part_an_edge_cuts(monkeypatch):
    """The nearest Share to the probe's aim is the next post's, cut by the tab bar: its visible
    part is not the button, and its centre is a finger's width above the tab bar."""
    _scroll, result = _probe(WHOLE_ABOVE_CUT, [None, None], monkeypatch)

    assert result["details"]["share_bounds"] == (442, 260, 505, 381)
    assert result["details"]["requested_start"] == (473, 320)
    assert result["success"] is True


def test_feed_drag_is_not_applicable_when_every_share_is_cut(monkeypatch):
    """The Lab run of the 6a that went red asked a start on a one-pixel sliver of Share at the
    bottom of the list, below the band where a gesture may start: nothing there to test."""
    scroll, result = _probe(ONLY_CUT, [None], monkeypatch)

    assert result["success"] is False
    assert result["details"]["not_applicable"].startswith("no whole share button")
    assert scroll.device._device.paths == []


def test_feed_next_exposes_the_real_session_memory_snapshot():
    class _MemoryScroll:
        def scroll_feed_to_next_post(self, **_kwargs):
            return {
                "on_feed": True,
                "on_reel": False,
                "mode": "flick",
                "gestures": 1,
                "dumps": 1,
                "land_ratio": 0.18,
                "corrected": False,
                "full_post": True,
                "metadata_visible": True,
                "advance_decision": {"mode": "flick", "style": "brisk", "energy": 0.64},
            }

        def _behavior_snapshot(self):
            return {"style": "brisk", "gesture_count": 3, "burst_remaining": 4}

    result = scroll_feed_next(SimpleNamespace(scroll=_MemoryScroll()), {})

    assert result["success"] is True
    assert "style=brisk" in result["message"]
    assert "energy=0.64" in result["message"]
    assert result["details"]["behavior_state"]["gesture_count"] == 3
