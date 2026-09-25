"""English Instagram entries measured on the 410 corpus (English captures and Lab dumps).

Four keys were empty in English while the French one had entries, and two English entries were
wrong on a real screen: the reel-author label also matched grid cells, feed suggestions and the
view-count preview of one's own reel, and the comments composer is hinted "What do you think of
this?", which "Add a comment" never matched. The screens below reproduce the structure of the
captured ones with invented names.
"""

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.extractors import username_from_media_label
from taktik.core.social_media.instagram.ui.selectors import locales
from taktik.core.social_media.instagram.ui.selectors.locales import L
from taktik.core.social_media.instagram.ui.selectors.surfaces.hashtag import HASHTAG_SELECTORS

ID = "com.instagram.android:id/"


@pytest.fixture(autouse=True)
def english():
    before = locales.active_locale()
    locales.set_active_locale("en")
    yield
    locales.set_active_locale(before)


def _screen(body, selected_tab=None):
    tabs = ""
    if selected_tab:
        tabs = f"""
  <node class="android.widget.LinearLayout" resource-id="{ID}tab_bar" bounds="[0,1907][1080,2028]">
    <node class="android.widget.FrameLayout" resource-id="{ID}feed_tab" content-desc="Home"
          selected="{str(selected_tab == 'feed_tab').lower()}" bounds="[0,1907][216,2028]"/>
    <node class="android.widget.FrameLayout" resource-id="{ID}search_tab" content-desc="Search and explore"
          selected="{str(selected_tab == 'search_tab').lower()}" bounds="[648,1907][864,2028]"/>
    <node class="android.widget.FrameLayout" resource-id="{ID}profile_tab" content-desc="Profile"
          selected="{str(selected_tab == 'profile_tab').lower()}" bounds="[864,1907][1080,2028]"/>
  </node>"""
    return f"""<hierarchy>
<node class="android.widget.FrameLayout" package="com.instagram.android" bounds="[0,0][1080,2160]">
  {body}{tabs}
</node>
</hierarchy>"""


def _node(cls, rid="", desc="", text="", hint=""):
    return (f'<node class="android.widget.{cls}" package="com.instagram.android" resource-id="{ID if rid else ""}{rid}"'
            f' content-desc="{desc}" text="{text}" hint="{hint}" bounds="[0,0][100,100]"/>')


def _hits(xml, selectors):
    root = parse_ui_dump(xml)
    return [node for selector in selectors for node in root.xpath(selector)]


# ─────────────────────────────────────────────────── reel author label

VIEWER_LABEL = "Reel by demo_author. Double tap to play or pause."

REEL_VIEWER = _screen(
    _node("FrameLayout", "clips_viewer_container")
    + _node("ViewGroup", "clips_media_component", VIEWER_LABEL)
    + _node("ImageView", "like_button", "Like")
)
PROFILE_GRID = _screen(
    _node("Button", "image_button", "Reel by Jane Demo at row 1, column 1")
    + _node("Button", "image_button", "Photo by Jane Demo at Row 1, Column 2"),
    selected_tab="profile_tab",
)
EXPLORE_GRID = _screen(
    _node("FrameLayout", "grid_card_layout_container", "Reel by Demo Studio at row 2, column 1")
    + _node("ImageView", "image_preview", "Reel by demo_author at Row 3, Column 3"),
    selected_tab="search_tab",
)
FEED_SUGGESTION = _screen(
    _node("FrameLayout", "row_feed_photo_imageview", "Suggested Reel by Demo Brand, 1,234 likes, 5 comments, May 6")
)
OWN_REEL_PREVIEW = _screen(
    _node("ImageView", "preview_clip_thumbnail", "Reel by demo_author. View Count 0. Double tap to play or pause."),
    selected_tab="profile_tab",
)
HOME_FEED_ROW = _screen(
    _node("FrameLayout", "row_feed_photo_imageview", "Reel by demo_author, 67 likes, 2 hours ago"),
    selected_tab="feed_tab",
)


def _author_label(xml):
    return _hits(xml, HASHTAG_SELECTORS.reel_author_container[-1:])


def test_the_reel_viewer_still_gives_its_author():
    nodes = _author_label(REEL_VIEWER)
    assert nodes
    assert username_from_media_label(nodes[0].get("content-desc")) == "demo_author"


@pytest.mark.parametrize("screen", [PROFILE_GRID, EXPLORE_GRID, FEED_SUGGESTION, OWN_REEL_PREVIEW, HOME_FEED_ROW],
                         ids=["profile grid", "explore grid", "feed suggestion", "own reel preview", "home feed"])
def test_no_other_screen_answers_as_a_reel_author(screen):
    assert not _author_label(screen)


# ─────────────────────────────────────────────────── like button, like counter

FEED_POST = _screen(
    _node("FrameLayout", "row_feed_photo_imageview", "Photo by demo_author, 3 likes")
    + _node("Button", "row_feed_button_like", "Like")
    + _node("Button", "", text="3")
    + _node("Button", "row_feed_button_comment", "Comment"),
    selected_tab="feed_tab",
)
REEL_COUNTERS = _screen(
    _node("ViewGroup", "clips_media_component", VIEWER_LABEL)
    + _node("ImageView", "like_button", "Like")
    + _node("Button", "like_count", "Like number is648. View likes", "Like number is648. View likes")
    + _node("Button", "comment_count", "Comment number is9. View comments", "Comment number is9. View comments")
)
NOTIFICATION_ROW = _screen(
    _node("TextView", "", text="demo_author mentioned you in a comment: nice. 8h")
    + _node("ImageView", "", "Like button")
    + _node("TextView", "", text="Reply")
)
STORY_VIEWER = _screen(
    _node("FrameLayout", "reel_viewer_root")
    + _node("ImageView", "toolbar_like_button", "Like Story")
)


def test_the_like_button_of_a_post_and_of_a_reel_is_found():
    assert _hits(FEED_POST, L("post.like_button_indicators"))
    assert _hits(REEL_COUNTERS, L("post.like_button_indicators"))


@pytest.mark.parametrize("screen", [NOTIFICATION_ROW, STORY_VIEWER], ids=["notification row", "story viewer"])
def test_a_like_control_that_is_not_a_post_does_not_answer(screen):
    assert not _hits(screen, L("post.like_button_indicators"))


def test_the_reel_like_counter_is_the_only_node_taken():
    nodes = _hits(REEL_COUNTERS, L("post.like_count_selectors"))
    assert [node.get("resource-id") for node in nodes] == [f"{ID}like_count"]
    assert not _hits(FEED_POST, L("post.like_count_selectors"))


# ─────────────────────────────────────────────────── post date

def test_the_date_under_a_post_is_found():
    for label in ("2 hours ago", "1 hour ago", "1 day ago", "3 days ago  •  See translation"):
        screen = _screen(_node("TextView", "", label, label), selected_tab="feed_tab")
        assert _hits(screen, L("post.timestamp_selectors")), label


def test_a_song_title_or_a_day_header_is_not_a_date():
    story = _screen(_node("TextView", "music_attribution_label", "Demo Band • Sunday Morning", "Demo Band • Sunday Morning"))
    header = _screen(_node("TextView", "activity_feed_header_row", text="Yesterday"))
    assert not _hits(story, L("post.timestamp_selectors"))
    assert not _hits(header, L("post.timestamp_selectors"))


# ─────────────────────────────────────────────────── comments composer

COMMENTS_SHEET = _screen(
    _node("TextView", "title_text_view", text="Comments")
    + _node("AutoCompleteTextView", "layout_comment_thread_edittext_multiline",
            text="What do you think of this?", hint="What do you think of this?")
)


@pytest.mark.parametrize("key", ["post.comment_field_selectors", "text_input.comment_field_selectors",
                                 "post_comments.comment_composer_indicators"])
def test_the_comments_composer_is_found_by_its_hint(key):
    nodes = _hits(COMMENTS_SHEET, L(key))
    assert [node.get("resource-id") for node in nodes] == [f"{ID}layout_comment_thread_edittext_multiline"]
    assert not _hits(REEL_COUNTERS, L(key))
