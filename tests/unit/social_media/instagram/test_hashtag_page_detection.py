"""Telling a hashtag page from the two screens that look like it.

IG 442 dropped `action_bar_title` from the hashtag page and renders no "posts"/"Top"/"Recent"
label at all, so the localized indicators matched NOTHING on a page that had clearly loaded.
What identifies the surface is a conjunction: a media grid, on a screen whose action-bar search
field holds a hashtag. Each half alone lies -- the grid is also Explore, and the search field
holding "#voyage" is also the search RESULTS screen.

The fixtures below keep only the nodes that decide the question, with the ids seen on device.
"""

from lxml import etree

from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import (
    DETECTION_SELECTORS,
)

_SEARCH_FIELD = (
    '<node class="android.widget.EditText" bounds="[147,161][900,253]"'
    ' resource-id="com.instagram.android:id/action_bar_search_edit_text" text="{text}"/>'
)
_GRID_CARD = (
    '<node class="android.view.ViewGroup" bounds="[0,300][360,660]"'
    ' resource-id="com.instagram.android:id/grid_card_layout_container"/>'
)
_RESULT_ROW = (
    '<node class="android.widget.TextView" bounds="[0,300][1080,400]"'
    ' resource-id="com.instagram.android:id/row_hashtag_textview_tag_name" text="#voyage"/>'
)


def _screen(*nodes):
    return etree.fromstring(("<hierarchy>" + "".join(nodes) + "</hierarchy>").encode())


def _looks_like_a_hashtag_page(root):
    return any(root.xpath(indicator) for indicator in DETECTION_SELECTORS.hashtag_page_indicators)


def test_a_hashtag_page_is_recognised():
    root = _screen(_SEARCH_FIELD.format(text="#voyage"), _GRID_CARD, _GRID_CARD)
    assert _looks_like_a_hashtag_page(root)


def test_the_search_results_screen_is_not_a_hashtag_page():
    # Same query in the same field, but a list of results instead of a grid.
    root = _screen(_SEARCH_FIELD.format(text="#voyage"), _RESULT_ROW)
    assert not _looks_like_a_hashtag_page(root)


def test_the_explore_grid_is_not_a_hashtag_page():
    # A grid, but nothing typed: this is Explore, and treating it as a hashtag page would make
    # a workflow engage with posts it never asked for.
    root = _screen(_SEARCH_FIELD.format(text=""), _GRID_CARD, _GRID_CARD)
    assert not _looks_like_a_hashtag_page(root)


def test_a_plain_search_without_a_hashtag_is_not_a_hashtag_page():
    root = _screen(_SEARCH_FIELD.format(text="voyage"), _GRID_CARD)
    assert not _looks_like_a_hashtag_page(root)
