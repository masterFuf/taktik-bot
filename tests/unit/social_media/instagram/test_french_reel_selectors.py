"""Two French entries measured on the 410 corpus: the play control of a paused reel, and the
reel media label the hashtag workflow reads its author from.

On the home feed the same "Reel de" label names the author's DISPLAY name, not the handle; the
hashtag entry must not read it there.

The screens are real dumps, anonymized: Instagram 410 in French on a Pixel 3a (a reel paused and
a reel playing, June; the home feed with a reel row, June), Instagram 447 in French on a Pixel 6a
(the posts of a profile opened from its grid, no tab bar, 2026-09-27), and Instagram 410 in
English (the home feed with a reel row, a reel playing).
"""

from pathlib import Path

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.extractors import username_from_media_label
from taktik.core.social_media.instagram.ui.language import filter_selectors
from taktik.core.social_media.instagram.ui.selectors import locales
from taktik.core.social_media.instagram.ui.selectors.surfaces.hashtag import HASHTAG_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import (
    POST_REELS_SELECTORS,
    POST_SELECTORS,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


PAUSED_REEL = _capture("ig410_fr_reel_viewer_paused.xml")
PLAYING_REEL = _capture("ig410_fr_reel_viewer.xml")
HOME_FEED = _capture("ig410_fr_home_feed_reel_row.xml")
LIST_OUTSIDE_HOME = _capture("ig447_fr_profile_posts_list.xml")
HOME_FEED_EN = _capture("ig410_en_home_feed_reel_row.xml")
REEL_VIEWER_EN = _capture("ig410_en_reel_viewer.xml")


@pytest.fixture
def french():
    before = locales.active_locale()
    locales.set_active_locale("fr")
    yield
    locales.set_active_locale(before)


def _hits(xml, selectors):
    root = parse_ui_dump(xml)
    return [node for selector in selectors for node in root.xpath(selector)]


# ─────────────────────────────────────────────────── play control

def test_the_play_control_of_a_paused_reel_is_found_in_french(french):
    assert _hits(PAUSED_REEL, POST_SELECTORS.video_controls)
    assert not _hits(PLAYING_REEL, POST_SELECTORS.video_controls)


def test_the_reels_catalogue_keeps_a_french_play_control_once_filtered():
    """`POST_REELS_SELECTORS.video_controls` is a field: the language filter, not `L()`,
    decides what production keeps."""
    kept = filter_selectors(list(POST_REELS_SELECTORS.video_controls), "fr")
    assert _hits(PAUSED_REEL, kept)


# ─────────────────────────────────────────────────── reel author label

def _author(xml):
    nodes = _hits(xml, HASHTAG_SELECTORS.reel_author_container[-1:])
    return username_from_media_label(nodes[0].get("content-desc")) if nodes else None


def test_the_reel_viewer_gives_its_author(french):
    assert _author(PLAYING_REEL) == "user_1"
    assert _author(PAUSED_REEL) == "user_1"


def test_the_home_feed_label_is_not_read_as_a_reel_author(french):
    """The home feed names the display name: "Reel de <prénom> <nom>, 60 J'aime, ...". A one-word
    display name reads like a handle and would be filed as the author."""
    assert "Reel de " in HOME_FEED
    assert not _hits(HOME_FEED, HASHTAG_SELECTORS.reel_author_container[-1:])
    assert _author(HOME_FEED) is None


def test_the_same_label_outside_the_home_tab_is_still_read(french):
    assert _author(LIST_OUTSIDE_HOME) == "name_1"


def test_the_english_home_feed_label_is_not_read_as_a_reel_author():
    before = locales.active_locale()
    locales.set_active_locale("en")
    try:
        assert "Reel by " in HOME_FEED_EN
        assert not _hits(HOME_FEED_EN, HASHTAG_SELECTORS.reel_author_container[-1:])
        assert _author(REEL_VIEWER_EN) == "name_14"
    finally:
        locales.set_active_locale(before)
