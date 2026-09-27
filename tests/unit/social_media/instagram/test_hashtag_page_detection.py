"""Telling a hashtag page from the two screens that look like it.

IG 442 dropped `action_bar_title` from the hashtag page and renders no "posts"/"Top"/"Recent"
label at all, so the localized indicators matched NOTHING on a page that had clearly loaded.
What identifies the surface is a conjunction: a media grid, on a screen whose action-bar search
field holds a hashtag. Each half alone lies -- the grid is also Explore, and the search field
holding "#voyage" is also the search RESULTS screen.

The screens are real captures, anonymized (a hashtag keeps its "#"): the hashtag page of
Instagram 447 in French (Pixel 6a), of 410 in French and in English (Pixel 3); in 410 French, the results
listed for a hashtag typed in the search field (Pixel 3), the Explore grid (Pixel 3a) and the
results of a plain search, an account name (Pixel 3). Read the way `d.xpath()` reads a dump.
"""

from pathlib import Path

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import (
    DETECTION_SELECTORS,
)

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_FIELD = '//*[contains(@resource-id, "action_bar_search_edit_text")]'
GRID = '//*[contains(@resource-id, "grid_card_layout_container")]'


def _screen(name):
    return parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))


def _field(root):
    return root.xpath(SEARCH_FIELD)[0].get("text")


def _looks_like_a_hashtag_page(root):
    return any(root.xpath(indicator) for indicator in DETECTION_SELECTORS.hashtag_page_indicators)


@pytest.mark.parametrize("name", ["ig447_fr_hashtag_page.xml", "ig410_fr_hashtag_page.xml",
                                  "ig410_en_hashtag_page.xml"],
                         ids=["447 fr", "410 fr", "410 en"])
def test_a_hashtag_page_is_recognised(name):
    root = _screen(name)
    assert _field(root).startswith("#") and root.xpath(GRID)
    assert _looks_like_a_hashtag_page(root)


def test_the_search_results_screen_is_not_a_hashtag_page():
    # The French entry used to hold `contains(@text, "publications")`, which answered on the
    # subtitle of every hashtag row here ("18,7 m publications").
    # Same query in the same field, but a list of results instead of a grid.
    root = _screen("ig410_fr_hashtag_search_results.xml")
    assert _field(root).startswith("#") and not root.xpath(GRID)
    assert not _looks_like_a_hashtag_page(root)


def test_the_explore_grid_is_not_a_hashtag_page():
    # A grid, but nothing typed: this is Explore, and treating it as a hashtag page would make
    # a workflow engage with posts it never asked for.
    root = _screen("ig410_fr_explore_grid.xml")
    assert not _field(root).startswith("#") and root.xpath(GRID)
    assert not _looks_like_a_hashtag_page(root)


def test_a_plain_search_without_a_hashtag_is_not_a_hashtag_page():
    root = _screen("ig410_fr_account_search_results.xml")
    assert _field(root) and not _field(root).startswith("#")
    assert not _looks_like_a_hashtag_page(root)
