"""English Instagram entries measured on the 410 corpus (English captures and Lab dumps).

Four keys were empty in English while the French one had entries, and two English entries were
wrong on a real screen: the reel-author label also matched grid cells, feed suggestions and the
view-count preview of one's own reel, and the comments composer is hinted "What do you think of
this?", which "Add a comment" never matched.

The screens are real captures of Instagram 410.0.0.53.71 in English, anonymized, read the way
production reads a dump (`parse_ui_dump`): a reel viewer with its counters, a profile grid, the
explore grid, a suggested reel and a reel row of the home feed, the preview of one's own reel,
feed posts dated 1 hour, 2 hours, 1 day and 16 hours ago, the activity page, a story viewer with
its song, and a comments sheet. Pixel 3, Pixel 3a, and a 576-pixel-wide phone.
"""

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.extractors import username_from_media_label
from taktik.core.social_media.instagram.ui.selectors import locales
from taktik.core.social_media.instagram.ui.selectors.locales import L
from taktik.core.social_media.instagram.ui.selectors.surfaces.hashtag import HASHTAG_SELECTORS
from unit.paths import CORE

ID = "com.instagram.android:id/"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"


@pytest.fixture(autouse=True)
def english():
    before = locales.active_locale()
    locales.set_active_locale("en")
    yield
    locales.set_active_locale(before)


def _screen(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _hits(xml, selectors):
    root = parse_ui_dump(xml)
    return [node for selector in selectors for node in root.xpath(selector)]


def _labels(xml):
    root = parse_ui_dump(xml)
    return [node.get(attribute) or "" for node in root.iter() for attribute in ("text", "content-desc")]


# ─────────────────────────────────────────────────── reel author label

REEL_VIEWER = _screen("ig410_en_reel_viewer.xml")
PROFILE_GRID = _screen("ig410_en_profile_follow_with_mutuals.xml")
EXPLORE_GRID = _screen("ig410_en_explore_grid.xml")
FEED_SUGGESTION = _screen("ig410_en_feed_suggested_reel.xml")
OWN_REEL_PREVIEW = _screen("ig410_en_own_reel_preview.xml")
HOME_FEED_ROW = _screen("ig410_en_home_feed_reel_row.xml")

#: What makes each screen a trap: the "Reel by" label it carries, in its own shape.
TRAPS = {
    "profile grid": (PROFILE_GRID, " at row "),
    "explore grid": (EXPLORE_GRID, " at row "),
    "feed suggestion": (FEED_SUGGESTION, "Suggested Reel by "),
    "own reel preview": (OWN_REEL_PREVIEW, ". View Count "),
    "home feed": (HOME_FEED_ROW, " likes, "),
}


def _author_label(xml):
    return _hits(xml, HASHTAG_SELECTORS.reel_author_container[-1:])


def test_the_reel_viewer_still_gives_its_author():
    nodes = _author_label(REEL_VIEWER)
    assert nodes
    label = nodes[0].get("content-desc")
    assert label.startswith("Reel by ") and label.endswith(". Double tap to play or pause.")
    assert username_from_media_label(label) == label[len("Reel by "):].split(".")[0]


@pytest.mark.parametrize("name", TRAPS)
def test_no_other_screen_answers_as_a_reel_author(name):
    screen, shape = TRAPS[name]
    assert any("Reel by" in label and shape in label for label in _labels(screen))
    assert not _author_label(screen)


# ─────────────────────────────────────────────────── like button, like counter

FEED_POST = _screen("ig410_en_feed_carousel_framed.xml")
REEL_COUNTERS = REEL_VIEWER
NOTIFICATION_ROW = _screen("ig410_en_notifications.xml")
STORY_VIEWER = _screen("ig410_en_story_viewer.xml")


def test_the_like_button_of_a_post_and_of_a_reel_is_found():
    assert _hits(FEED_POST, L("post.like_button_indicators"))
    assert _hits(REEL_COUNTERS, L("post.like_button_indicators"))


@pytest.mark.parametrize("screen, label", [(NOTIFICATION_ROW, "Like button"), (STORY_VIEWER, "Like Story")],
                         ids=["notification row", "story viewer"])
def test_a_like_control_that_is_not_a_post_does_not_answer(screen, label):
    assert label in _labels(screen)
    assert not _hits(screen, L("post.like_button_indicators"))


def test_the_reel_like_counter_is_the_only_node_taken():
    nodes = _hits(REEL_COUNTERS, L("post.like_count_selectors"))
    assert [node.get("resource-id") for node in nodes] == [f"{ID}like_count"]
    assert not _hits(FEED_POST, L("post.like_count_selectors"))


# ─────────────────────────────────────────────────── post date

@pytest.mark.parametrize("name, label", [
    ("ig410_en_feed_post_hours_ago.xml", "2 hours ago"),
    ("ig410_en_share_sheet_over_sponsored_post.xml", "1 hour ago"),
    ("ig410_en_feed_post_day_ago.xml", "1 day ago"),
    ("ig410_en_feed_suggested_reel.xml", "16 hours ago  •  See translation"),
], ids=["2 hours", "1 hour", "1 day", "with translation"])
def test_the_date_under_a_post_is_found(name, label):
    found = _hits(_screen(name), L("post.timestamp_selectors"))
    assert label in [node.get("text") for node in found]


def test_a_song_title_or_a_day_header_is_not_a_date():
    assert _hits(STORY_VIEWER, [f'//*[@resource-id="{ID}music_attribution_label"]'])
    assert "Yesterday" in _labels(NOTIFICATION_ROW)
    assert not _hits(STORY_VIEWER, L("post.timestamp_selectors"))
    assert not _hits(NOTIFICATION_ROW, L("post.timestamp_selectors"))


# ─────────────────────────────────────────────────── comments composer

COMMENTS_SHEET = _screen("ig410_en_comment_sheet.xml")


@pytest.mark.parametrize("key", ["post.comment_field_selectors", "text_input.comment_field_selectors",
                                 "post_comments.comment_composer_indicators"])
def test_the_comments_composer_is_found_by_its_hint(key):
    nodes = _hits(COMMENTS_SHEET, L(key))
    assert [node.get("resource-id") for node in nodes] == [f"{ID}layout_comment_thread_edittext_multiline"]
    assert not _hits(REEL_COUNTERS, L(key))
