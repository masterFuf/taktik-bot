"""The scan reads what was not read yet, and says where it stopped.

No setting bounds it any more (the old `scroll` read a dozen rows): a row is judged by its age
against the account's last scan (`UnreadRule`), the recorded identity settling the rows whose age
straddles it. The scan stops after two screens with nothing unread (once it is past the top
section, which is not in the order of time), at the end of the feed, or at `SCAN_READ_CAP`.

The screens are real activity screens, anonymized: Instagram 410 in French (Pixel 4a,
2026-09-28: the top of the list with its « À la une » section, a screen of 4-5 day rows, an older
screen of 4 week rows) and Instagram 447 in French (Pixel 6a: the top of the list with its four
sections, a screen of 2-3 day rows). Only the device primitives are replaced (the scroll gesture,
the load-more tap, the OCR expander, the emoji re-read); the loop, the reading of each screen and
the stop rules are the production ones.
"""

from datetime import datetime, timedelta, timezone

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.notifications import (
    notifications_workflow as module,
)
from taktik.core.social_media.instagram.workflows.notifications import unread_rule as rule_module
from taktik.core.social_media.instagram.workflows.notifications.unread_rule import UnreadRule
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
NOW = datetime(2000, 1, 10, tzinfo=timezone.utc)


def _screen(name):
    return parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))


TOP = _screen("ig410_fr_notifications_top.xml")
ROWS = _screen("ig410_fr_notifications_rows.xml")
OLDER = _screen("ig410_fr_notifications_older.xml")
TOP_447 = _screen("ig447_fr_notifications_feed_top.xml")
DAYS_447 = _screen("ig447_fr_notifications_feed_days.xml")
#: The first scan of the phone proof (Instagram 447 in French, Pixel 6a, 2026-11-20), five screens in a row.
WEEK_447 = [_screen(f"ig447_fr_notifications_week_{rank}.xml") for rank in range(1, 6)]
#: Distinct notifications each real screen holds, read by the production parser.
#: The ads entry at the top of « top » is not one of them.
ROWS_ON = {"top": 7, "rows": 10, "older": 10}


def _everything_known(_row):
    return True


def _since(hours, is_known=_everything_known):
    return UnreadRule.since_last_scan(NOW - timedelta(hours=hours), is_known, clock=lambda: NOW)


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


def test_the_scan_stops_on_what_was_already_read():
    """Last scan an hour ago, everything recorded: the first screen (its top section is not in
    the order of time) does not count, the next two bring nothing unread, the scan stops there."""
    wf = _Scan([TOP_447, DAYS_447, ROWS, OLDER])

    result = wf.scan(unread_rule=_since(hours=1))

    assert result["scan_stop_reason"] == "already_read"
    assert result["scan_stop_reason_params"] == {}
    assert wf.scrolls == 2  # the older screen is never reached


def test_a_new_like_from_someone_already_seen_does_not_stop_it():
    """A like or a follow is recorded by « type + person »: a new one from someone already seen has
    a known identity. Younger than the last scan, it is unread all the same, and the scan goes on
    past the 4-5 day rows to the end of the feed."""
    wf = _Scan([TOP, ROWS, OLDER])

    result = wf.scan(unread_rule=_since(hours=6 * 24))

    assert result["scan_stop_reason"] == "end_of_feed"
    assert result["count"] == ROWS_ON["top"] + ROWS_ON["rows"]  # the 4 week rows are beyond
    assert any(item["type"] == "post_like" for item in result["items"])


def test_the_first_scan_stops_at_the_end_of_the_six_days():
    """Nothing recorded: the first scan reads seven days back. « 1 sem » is at least seven days old,
    so it is beyond; the phone proof of 2026-11-20 (Pixel 6a, Instagram 447) read 71 rows of it
    while the comparison let a row exactly at the horizon through. Real screens of that pass: the
    top of the list, the days, the turn to « 1 sem », then weeks only."""
    wf = _Scan(WEEK_447)

    result = wf.scan()

    assert result["scan_stop_reason"] == "first_scan_horizon"
    assert result["scan_stop_reason_params"] == {"days": 7}
    assert wf.scrolls == 4
    assert result["items"] and not any(item["time"].endswith("sem") for item in result["items"])
    assert any(item["time"] == "6 j" for item in result["items"])


def test_the_first_scan_reads_seven_days_back():
    first = UnreadRule.for_first_scan()

    assert first.verdict({"time": "5 j"}) == rule_module.UNREAD
    assert first.verdict({"time": "6 j"}) == rule_module.UNREAD
    assert first.verdict({"time": "7 j"}) == rule_module.BEYOND
    assert first.verdict({"time": "1 sem"}) == rule_module.BEYOND
    assert first.verdict({"time": "2 sem"}) == rule_module.BEYOND
    wf = _Scan([TOP, ROWS, OLDER])
    result = wf.scan()
    assert result["count"] == ROWS_ON["top"] + ROWS_ON["rows"]


def test_the_read_cap_stops_the_scan_and_says_so(monkeypatch):
    monkeypatch.setattr(module, "SCAN_READ_CAP", 12)
    wf = _Scan([TOP, ROWS, OLDER])

    result = wf.scan(unread_rule=_since(hours=24 * 60))

    assert result["scan_stop_reason"] == "read_cap"
    assert result["count"] == 12
    # The app's sentence says the cap the engine used: sent with the reason, never copied into the app.
    assert result["scan_stop_reason_params"] == {"rows": 12}


class _ScanWithoutHeaders(_Scan):
    """The same screens, their time-section headers not read (an id the phone no longer shows)."""

    def _dump_screen(self):
        rows, _headers = super()._dump_screen()
        return rows, []


def test_the_read_cap_bounds_the_reading_when_the_sections_are_not_read(monkeypatch):
    """Without the section headers, « two screens with nothing unread » never counts, and a row
    beyond the horizon is not kept: a cap on the rows kept bounded nothing, and the scan read on to
    the end of the feed. Last scan an hour ago, so the 4-5 day and 4 week rows are beyond it: the
    cap counts every row read, the 12th is on the second screen."""
    monkeypatch.setattr(module, "SCAN_READ_CAP", 12)
    wf = _ScanWithoutHeaders([TOP, ROWS, OLDER])

    result = wf.scan(unread_rule=_since(hours=1))

    assert result["scan_stop_reason"] == "read_cap"
    assert wf.scrolls == 1  # the 4 week screen is never reached


def test_show_more_is_tapped_when_it_is_the_only_way_on():
    wf = _Scan([TOP_447, TOP_447], loaded_by_show_more=[DAYS_447])

    result = wf.scan()

    assert wf.show_more_taps == 1
    assert result["scan_stop_reason"] == "end_of_feed"
    assert any(item["time"] == "3 j" for item in result["items"])


def test_the_ads_entry_at_the_top_of_the_feed_is_not_a_notification():
    """« Publicités » / « Activité récente liée à vos publicités. » opens the ads activity: no age,
    no actor. A second scan with nothing new announced it as « 1 notification » (Pixel 6a,
    Instagram 447, 2026-11-20). The grouped likes of a reel on the same screen are real `other`
    notifications and stay."""
    for screen in (TOP_447, TOP):
        result = _Scan([screen]).scan()

        texts = [item["text"] for item in result["items"]]
        assert not any("publicités" in text.lower() for text in texts)
        assert result["by_type"].get("other", 0) == sum(item["type"] == "other" for item in result["items"])
    others = [item for item in _Scan([TOP_447]).scan()["items"] if item["type"] == "other"]
    assert [item["time"] for item in others] == ["5 h", "16 h"]


def test_the_ads_entry_is_left_out_in_english_too():
    """Instagram 410 in English: the same entry, its words anonymized but « Recent activity »."""
    set_active_locale("en")
    result = _Scan([_screen("ig410_en_notifications_filter_sheet.xml")]).scan()

    texts = [item["text"] for item in result["items"]]
    assert not any("Recent activity" in text for text in texts)
    assert any("posted for the first time" in text for text in texts)


def test_rows_whose_age_straddles_the_last_scan_are_settled_by_their_identity():
    """Last scan 5 h 30 ago: « 5 h » (5 h to 6 h old) may be either side; its identity decides."""
    known = _since(hours=5.5)
    unknown = _since(hours=5.5, is_known=lambda _row: False)

    assert known.verdict({"time": "5 h"}) == rule_module.READ
    assert unknown.verdict({"time": "5 h"}) == rule_module.UNREAD
    assert known.verdict({"time": "4 h"}) == rule_module.UNREAD
    assert known.verdict({"time": "6 h"}) == rule_module.BEYOND
    assert known.verdict({"time": ""}) == rule_module.READ  # no age: the identity decides
