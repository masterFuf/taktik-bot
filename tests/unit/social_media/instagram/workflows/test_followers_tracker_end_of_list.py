"""What the tracker must mean by "the same followers, again".

The bug this file locks out, measured on the runs of 2026-09-09: `is_end_of_list` compared the
last five entries of `visible_history`, and that history is fed on EVERY scan. The direct loop
deliberately rescans the same page while it still holds a fresh follower (process one -> back ->
rescan), so five identical entries could pile up with the list never having been scrolled once.

Evidence from the run of cca_gzk on @raffaelthielmann: the five entries that ended it all carry
`scroll_count = 26` — the same scroll. The run stopped at 55 usernames of a 1 002-follower list.
Across the eighteen runs filed `end_of_list_repeated`, the verdict always followed 9 to 19
consecutive scans with no scroll between them, and never a scroll that brought nothing.

So the tests below pin the QUESTION, not the counter: "did N scrolls fail to bring anything
new", never "did I look N times".
"""

import json

import pytest

import taktik.core.social_media.instagram.actions.business.workflows.common.followers_tracker as tracker_module
from taktik.core.social_media.instagram.actions.business.workflows.common.followers_tracker import (
    FollowersTracker,
)


PAGE_A = [f"user_a{i:02d}" for i in range(10)]
PAGE_B = [f"user_b{i:02d}" for i in range(10)]


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    """A real tracker, writing its journal into the test's own directory."""
    monkeypatch.setattr(tracker_module, "get_app_data_dir", lambda: str(tmp_path))
    return FollowersTracker("bot_account", "target_account")


def _walk_a_list(tracker, pages_per_scroll):
    """Feed the tracker the way the loop does: scroll, then scan that page one or more times."""
    for page, scans in pages_per_scroll:
        tracker.log_scroll("down")
        for _ in range(scans):
            tracker.log_visible_followers(list(page), "scan")


def _fifty_distinct_pages():
    """Enough unique usernames to clear the tracker's own `< 50 seen` guard."""
    return [([f"seen_{i}_{j}" for j in range(10)], 1) for i in range(12)]


def test_rescanning_one_page_is_not_a_finished_list(tracker):
    """THE bug: the loop rereads a page it is still working through, and that is not an end.

    Twelve real scrolls first, so both existing guards (10 scrolls, 50 usernames seen) are
    cleared and cannot be what makes the assertion pass.
    """
    _walk_a_list(tracker, _fifty_distinct_pages())
    assert tracker.is_end_of_list() is False

    # The page the loop is chewing through, read six times without ever scrolling again.
    for _ in range(6):
        tracker.log_visible_followers(list(PAGE_A), "scan")

    assert tracker.is_end_of_list() is False, (
        "six readings of one page, no scroll between them: nothing says the list ended"
    )


def test_five_scrolls_that_bring_nothing_are_a_finished_list(tracker):
    """The signal the detector is FOR must still fire — otherwise the fix is a mute button."""
    _walk_a_list(tracker, _fifty_distinct_pages())

    _walk_a_list(tracker, [(PAGE_A, 1)] * 5)

    assert tracker.is_end_of_list() is True


def test_the_same_page_read_many_times_between_real_scrolls_still_ends(tracker):
    """Scrolls that bring nothing keep their meaning even when each page is read several times.

    This is the shape of a genuine end of list on a slow phone: the loop scrolls, sees the same
    rows, rescans them while it decides, scrolls again. Collapsing per scroll must not lose it.
    """
    _walk_a_list(tracker, _fifty_distinct_pages())

    _walk_a_list(tracker, [(PAGE_A, 3)] * 5)

    assert tracker.is_end_of_list() is True


def test_a_scroll_that_brings_new_rows_breaks_the_run(tracker):
    """One productive scroll in the middle and the streak is not five scrolls any more."""
    _walk_a_list(tracker, _fifty_distinct_pages())

    _walk_a_list(tracker, [(PAGE_A, 1), (PAGE_A, 1), (PAGE_B, 1), (PAGE_A, 1), (PAGE_A, 1)])

    assert tracker.is_end_of_list() is False


def test_the_two_historical_guards_are_untouched(tracker):
    """`< 10 scrolls` and `< 50 usernames seen` are what IG-FEED-007 added. Keep them."""
    _walk_a_list(tracker, [(PAGE_A, 1)] * 5)
    assert tracker.is_end_of_list() is False, "under ten scrolls, never an end of list"

    # Ten scrolls now done, but PAGE_A alone is only 10 distinct usernames.
    _walk_a_list(tracker, [(PAGE_A, 1)] * 6)
    assert tracker.is_end_of_list() is False, "under fifty usernames seen, never an end of list"


def test_the_journal_says_how_many_scans_backed_the_verdict(tracker, tmp_path):
    """The next diagnosis must not need the run log to tell scans from scrolls."""
    _walk_a_list(tracker, _fifty_distinct_pages())
    _walk_a_list(tracker, [(PAGE_A, 2)] * 5)

    assert tracker.is_end_of_list() is True

    written = tracker.log_file.read_text(encoding="utf-8")
    verdict = json.loads(
        [line for line in written.splitlines() if '"END_OF_LIST_DETECTED"' in line][-1]
    )
    # 12 pages walked once + 5 pages read twice = 22 scans over 17 scrolls. Reading the journal
    # must show both, because the whole bug was the two being confused.
    assert verdict["scans"] == 22
    assert verdict["pages_after_scroll"] == 17
    assert verdict["scroll_count"] == 17
