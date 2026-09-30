"""End-of-list detection (followers/following lists).

Rule: a scroll that reveals no NEW username is NOT proof of the end of the list (a small
scroll, an overlap, or the list resumed after interacting with a profile legitimately shows no
session-new username). End-of-list must be detected ONLY when the list is genuinely stuck — the
exact same page repeated, or an empty screen. Running out of profiles worth interacting with is a
separate decision (`max_consecutive_known_usernames` in the workflow loop).
"""

from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector


def test_no_new_username_does_not_end_the_list():
    """The former bug: 5 scrolls with no session-new username falsely stopped the session."""
    d = ScrollEndDetector(repeats_to_end=5)
    d.notify_new_page(["a", "b", "c", "d", "e"])
    # Distinct pages (no two identical) that each reveal NO new username (all subsets of the first).
    for page in (["a", "b"], ["a", "c"], ["a", "d"], ["a", "e"], ["b", "c"], ["b", "d"]):
        d.notify_new_page(page)
    assert d.is_the_end() is False


def test_identical_pages_detect_the_real_end():
    """The exact same page rendered repeatedly = the scroll is stuck = real end."""
    d = ScrollEndDetector(repeats_to_end=5)
    for _ in range(6):
        d.notify_new_page(["a", "b", "c"])
    assert d.is_the_end() is True


def test_empty_pages_detect_the_real_end():
    d = ScrollEndDetector(repeats_to_end=5)
    for _ in range(8):
        d.notify_new_page([])
    assert d.is_the_end() is True


def test_discovering_new_usernames_keeps_going():
    d = ScrollEndDetector(repeats_to_end=5)
    for batch in (["a", "b"], ["c", "d"], ["e", "f"], ["g", "h"], ["i", "j"], ["k", "l"]):
        d.notify_new_page(batch)
    assert d.is_the_end() is False


def test_reworking_the_same_visible_page_must_not_end_the_list():
    """Regression (virgileimages run: stopped at 24/472 followers, scroll was fine).

    The direct-followers loop works a visible page ONE follower at a time (process one -> break ->
    re-scan the SAME visible page -> process the next). If every one of those identical re-scans is
    fed to the detector, the "same page N times" counter trips is_the_end() after 5 re-scans of a
    single page even though the scroll never actually got stuck. The fix notifies the detector ONLY
    once a page is exhausted, so re-scans of a page still being worked never reach it. This models
    that discipline: one notify per DISTINCT exhausted page keeps the list alive across many pages,
    exactly where the old every-iteration notify would have falsely ended it.
    """
    d = ScrollEndDetector(repeats_to_end=5)
    # 8 distinct exhausted pages, each notified once (the loop internally re-scanned each ~9 times
    # while interacting, but the detector only ever sees each page a single time).
    for page in (
        ["a", "b"], ["c", "d"], ["e", "f"], ["g", "h"],
        ["i", "j"], ["k", "l"], ["m", "n"], ["o", "p"],
    ):
        d.notify_new_page(page)
    assert d.is_the_end() is False
