"""A carousel must come out in the caller's order.

Device report (2026-07-26): three slides pushed as 01, 02, 03 were published as 03, 02, 01.

Two facts combine to produce that. The gallery grid is date-sorted DESCENDING, so grid #1 is the
media pushed LAST; and Instagram numbers a carousel in TAP ORDER, not in grid order. Tapping
1, 2, 3 therefore selects the newest first and reverses the slides.

Walking the positions from `count` down to 1 taps the oldest of the freshly pushed media first,
which is `media_paths[0]`, and restores the caller's order.
"""
from taktik.core.social_media.instagram.workflows.publish.post_workflow import (
    InstagramPostWorkflow,
)


class TapOrderSpy(InstagramPostWorkflow):
    """Records which grid positions get tapped, in order."""

    def __init__(self):
        self.device = None
        self.device_id = "test-device"
        self._log = lambda *a, **k: None
        self._status = lambda *a, **k: None
        self.package_name = "com.instagram.android"
        self.post_type = "carousel"
        self.story_via_feed = False
        self._a = {}
        self.grid_taps = []
        self._selected = 0

    def _tap(self, selectors, timeout: float = 4.0) -> bool:
        # The grid selector carries its position; the multi-select button does not.
        text = str(selectors)
        if "gallery_grid_item" in text or "GRID:" in text:
            self.grid_taps.append(self._position_of(text))
            self._selected += 1
        return True

    @staticmethod
    def _position_of(text):
        # Positions appear as an XPath index, e.g. `(...)[3]`.
        import re
        found = re.findall(r"\[(\d+)\]", text)
        return int(found[-1]) if found else None

    def _clear_gallery_selection(self, max_taps: int = 12) -> None:
        self._selected = 0

    def _selected_media_count(self) -> int:
        return self._selected


def test_positions_are_tapped_from_the_oldest_pushed_to_the_newest():
    workflow = TapOrderSpy()
    assert workflow._select_carousel(3) is True

    # Grid #3 is the FIRST media the caller gave us, so it must be tapped first.
    assert workflow.grid_taps == [3, 2, 1], (
        "tapping 1,2,3 reverses the carousel: grid #1 is the media pushed last"
    )


def test_the_order_holds_for_a_ten_slide_carousel():
    workflow = TapOrderSpy()
    workflow._select_carousel(10)
    assert workflow.grid_taps == [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]


def test_a_two_slide_carousel_is_still_a_carousel():
    workflow = TapOrderSpy()
    assert workflow._select_carousel(2) is True
    assert workflow.grid_taps == [2, 1]


def test_a_single_selected_medium_is_refused():
    """Below two media Instagram publishes a plain post, which is not what was asked for."""
    workflow = TapOrderSpy()

    def only_one(selectors, timeout=4.0):
        text = str(selectors)
        if "gallery_grid_item" in text and workflow._selected >= 1:
            return False
        return TapOrderSpy._tap(workflow, selectors, timeout)

    workflow._tap = only_one
    assert workflow._select_carousel(3) is False
