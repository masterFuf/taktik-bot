"""The scan's `scroll` setting bounds the scrolls of the activity list.

The setting is promised everywhere: the Lab (« Screens to scroll (scan) »), the page and the
planner node send `scroll`, the contract declares it « Screens scrolled below the first one »
(default 3), and `cmd_scan` reads it as « how many extra screens to scroll (0 = visible only) ».
The loop had become `range(max(max_scrolls + 1, 12))`: below 11, the setting changed nothing,
and a scan asked for 1 screen made 12 scrolls on the phone.

The screens are real activity screens (Instagram 410 in French, Pixel 4a, 2026-09-28),
anonymized: the top of the list, a screen of rows, an older screen. Only the device primitives
are replaced (the scroll gesture, the load-more tap, the OCR expander, the emoji re-read); the
loop, the reading of each screen and the stop rules are the production ones.
"""

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.selectors import NOTIFICATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.notifications import (
    notifications_workflow as module,
)
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"


def _screen(name):
    return parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))


TOP = _screen("ig410_fr_notifications_top.xml")
ROWS = _screen("ig410_fr_notifications_rows.xml")
OLDER = _screen("ig410_fr_notifications_older.xml")
#: Distinct notifications each real screen holds, read by the production parser (none is shared
#: between two screens; the top screen shows one of its nine rows twice).
ROWS_ON = {"top": 8, "rows": 10, "older": 10}


class _Scan(module.NotificationsEngagementWorkflow):
    """The real workflow; the phone shows ``screens[scrolls]`` (the last one once the list ends)."""

    def __init__(self, screens, loaded_by_show_more=()):
        super().__init__(device=None, device_id="test")
        self.screens = list(screens)
        self.loaded_by_show_more = list(loaded_by_show_more)
        self.scrolls = 0
        self.show_more_taps = 0

    def _dump_root(self):
        return self.screens[min(self.scrolls, len(self.screens) - 1)]

    def _element_exists(self, selectors):
        root = self._dump_root()
        return any(root.xpath(selector) for selector in selectors)

    # --- device primitives replaced ---
    def _optimize_locale(self):
        return None

    def ensure_notifications_screen(self):
        return True

    def _scroll_down(self, times=1):
        self.scrolls += times

    def _tap_show_more(self):
        """The load-more entry at the end of the list: older rows appear below it."""
        if not self.loaded_by_show_more:
            return False
        self.show_more_taps += 1
        self.screens.extend(self.loaded_by_show_more)
        self.loaded_by_show_more = []
        return True

    def _expand_one_more(self):
        return False

    def _resolve_emoji_text(self, parsed_text):
        return None


@pytest.fixture(autouse=True)
def _french_without_waits(monkeypatch):
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


LONG_LIST = [TOP, ROWS, OLDER]


def test_one_screen_asked_means_one_scroll():
    """The run of the Lab on the Pixel 3 (`scroll=1`) made 12 scrolls."""
    wf = _Scan(LONG_LIST)

    result = wf.scan(max_scrolls=1)

    assert wf.scrolls == 1
    assert result["count"] == ROWS_ON["top"] + ROWS_ON["rows"]


def test_zero_reads_the_visible_screen_only():
    """« 0 = visible only »: no gesture at all."""
    wf = _Scan(LONG_LIST)

    result = wf.scan(max_scrolls=0)

    assert wf.scrolls == 0
    assert wf.show_more_taps == 0
    assert result["count"] == ROWS_ON["top"]


def test_the_default_three_reads_four_screens_at_most():
    """The first screen, then three scrolled below it; the fourth scroll is never made."""
    wf = _Scan(LONG_LIST + [TOP])

    wf.scan(max_scrolls=3)

    assert wf.scrolls == 3


def test_a_short_list_still_ends_on_two_empty_rounds():
    """A list that fits on one screen ends by itself, before the setting is spent."""
    wf = _Scan([TOP])

    result = wf.scan(max_scrolls=10)

    assert wf.scrolls == 2
    assert result["count"] == ROWS_ON["top"]


def test_the_load_more_entry_is_read_inside_the_bound():
    """On a short list, the older rows come from the load-more entry; they are read when the
    setting leaves a scroll to reveal them."""
    wf = _Scan([TOP, TOP], loaded_by_show_more=[OLDER])

    result = wf.scan(max_scrolls=2)

    assert wf.show_more_taps == 1
    assert wf.scrolls == 2
    assert result["count"] == ROWS_ON["top"] + ROWS_ON["older"]


def test_the_load_more_entry_is_not_tapped_once_the_scrolls_are_spent():
    """Tapping it then would load rows that the scan never reads."""
    wf = _Scan([TOP, TOP], loaded_by_show_more=[OLDER])

    wf.scan(max_scrolls=1)

    assert wf.show_more_taps == 0
    assert wf.scrolls == 1
