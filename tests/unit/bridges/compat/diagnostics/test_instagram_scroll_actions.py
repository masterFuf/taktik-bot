"""The Cartography drag probe exercises the real guarded production primitive."""

from types import SimpleNamespace

from bridges.compat.diagnostics.actions.instagram.scroll import scroll_feed_drag, scroll_feed_next


class _Scroll:
    screen_height = 2280

    def __init__(self):
        self.calls = []
        self._last_gesture_start = {}

    def _post_action_bounds(self, role):
        assert role == "share"
        return [(190, 1800, 330, 1960)]

    def _long_drag(self, direction, start_point=None, guard_start=False):
        self.calls.append((direction, start_point, guard_start))
        self._last_gesture_start = {
            "requested": start_point,
            "final": (620, start_point[1]),
            "adjusted": True,
            "source": "ui_bounds",
        }
        return True


class _Popup:
    def __init__(self, results):
        self.results = list(results)

    def _detect_blocking_modal(self):
        return self.results.pop(0)


def test_feed_drag_requests_share_center_and_rejects_no_modal():
    scroll = _Scroll()
    bundle = SimpleNamespace(scroll=scroll, popup=_Popup([None, None]))

    result = scroll_feed_drag(bundle, {})

    assert result["success"] is True
    assert scroll.calls == [("up", (260, 1880), True)]
    assert result["details"]["gesture_start"]["adjusted"] is True
    assert result["details"]["modal_after"] is None


def test_feed_drag_fails_if_direct_share_sheet_opens():
    scroll = _Scroll()
    bundle = SimpleNamespace(scroll=scroll, popup=_Popup([None, "direct_share_sheet"]))

    result = scroll_feed_drag(bundle, {})

    assert result["success"] is False
    assert result["details"]["modal_after"] == "direct_share_sheet"


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
