"""Switching a comments thread's sort order, on a phone that is not in English.

The control used to be the single English content-desc "For you". On a French phone it matched
nothing, so the menu was never opened -- and the caller went on believing it had switched the
sort while the thread stayed on its default. The menu's own options were looked up by a
hardcoded English map, which failed the same way one step later.

The screens are captures of Instagram 447 in French (Pixel 6a, 2026-09-27), anonymized: the
comments sheet of a post (the control's label lives in the TEXT of a child View with no
content-desc), the sort menu it opens (an option carries its label on content-desc AND on a child
TextView), and the home feed, whose header says "Pour vous" too.
"""

from pathlib import Path

from lxml import etree

from taktik.core.social_media.instagram.ui.selectors.surfaces.post.comments import (
    POST_COMMENTS_SELECTORS,
)

FIXTURES = Path(__file__).parent / "fixtures"
COMMENTS_SHEET = (FIXTURES / "ig447_fr_comment_sheet.xml").read_text(encoding="utf-8")
SORT_MENU = (FIXTURES / "ig447_fr_comment_sort_menu.xml").read_text(encoding="utf-8")
# The feed's own header says "Pour vous" as well, and it has no comment sorting: the control
# must not be found there.
FEED = (FIXTURES / "ig447_fr_home_feed.xml").read_text(encoding="utf-8")


def _count(xml, selector):
    return len(etree.fromstring(xml.encode()).xpath(selector))


def test_the_sort_control_is_found_on_a_french_comments_sheet():
    assert _count(COMMENTS_SHEET, POST_COMMENTS_SELECTORS.comment_sort_button) == 1


def test_a_feed_header_saying_the_same_words_is_not_the_sort_control():
    assert _count(FEED, '//*[@text="Pour vous"]') == 1
    assert _count(FEED, POST_COMMENTS_SELECTORS.comment_sort_button) == 0


def test_every_sort_option_is_reachable_in_the_language_the_menu_uses():
    # French for the first two, English for Meta Verified -- which stays English on a French
    # phone, which is why both labels of each pair are tried rather than one guessed.
    for labels in POST_COMMENTS_SELECTORS.sort_options.values():
        found = [
            label
            for label in labels
            if _count(SORT_MENU, POST_COMMENTS_SELECTORS.sort_option_selector(label))
        ]
        assert found, f"none of {labels} matched the menu"
