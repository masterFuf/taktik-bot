"""End-of-list detection (followers/following lists).

Kevin's rule: a scroll that reveals no NEW username is NOT proof of the end of the list (a small
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
