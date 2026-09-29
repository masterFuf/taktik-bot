"""The comment, and the other gestures of a post's button row, go to the framed post's own row.
Never to the first button of the screen.

On a list of posts (the home feed, a profile's posts, a hashtag's), the row at the top of the screen
is often the post above's. The comment tapped the first comment button of the screen: the comments
of the post above opened, and the comment written for the framed post (its author, its caption, the
screenshot the AI read) was published under the post above. The comments thread read before a
comment (the AI's context, `post.open_comments`) and the commenters scraped from a post opened the
same way; the share button that copies a post's link was found the same way, so a comment or a
collected post was filed with the link of the post above.

The framed post is the one the like and the likers already use: its header is the first under the
top of the list, its row the first under that header (`PostReadingMixin.framed_post_like_target`,
which gives the row, `InstagramUIExtractors.framed_post_element`, which keeps what lies in it).

The screens are real dumps, anonymized:
- `ig410_fr_home_feed_likes_above_framed_post.xml` (Instagram 410, Pixel 3a, home feed): the row
  of the post above at the top of the list, the framed post's row at the bottom;
- `ig447_fr_home_feed_hidden_likes_above_framed_post.xml` (Instagram 447, Pixel 6a, home feed): the
  same, the post above hiding its likes;
- `ig410_fr_feed_heart_of_post_above_at_top.xml` (Instagram 410, Pixel 3a, home feed): a sliver of
  the post above's row (14 px) left at the top of the list;
- `ig447_fr_profile_posts_next_header_mid_screen.xml` (Instagram 447, Pixel 6a, a profile's posts):
  the post above's row mid-screen, the framed post's row at the bottom;
- `ig447_fr_profile_posts_row_below_screen.xml` (Instagram 447, Pixel 6a, a profile's posts) and
  `ig410_en_feed_carousel_framed.xml` (Instagram 410, Pixel 3a, home feed): the post above's row on
  screen, the framed post's row under the bottom of the list;
- `ig410_fr_home_feed_framed_post_hides_likes.xml` (Instagram 410, Pixel 3a): no post above;
- `ig410_en_reel_viewer.xml` and `ig410_fr_reel_viewer.xml`: the full-screen Reel viewer, off a list.

The hosts are the production ones, built by their own constructors on a phone that replays the
capture (`profile_posts_phone.py`): `CommentAction` (the comment, the Lab's `a.comment`),
`BaseBusinessAction` (the thread, the Lab's `a.popup`), `ScrapingWorkflow` (the commenters), the
Lab's `post.read_share_url` (the link).
"""

import pytest

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.core.base_business.popup_handling as popup_handling
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
import taktik.core.social_media.instagram.workflows.common.post_navigation as post_navigation
import taktik.core.social_media.instagram.workflows.scraping.post_scraping_helpers as post_scraping_helpers
from bridges.tools.lab.actions.instagram import ACTION_REGISTRY as INSTAGRAM_ACTIONS
from bridges.tools.lab.actions.instagram import register_actions as register_instagram
from bridges.tools.lab.action_test.bundles.instagram import build_instagram_action_bundle
from profile_posts_phone import PKG, ProfilePostsPhone, bounds_of, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction
from taktik.core.social_media.instagram.actions.core.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import BUTTON_SELECTORS
from taktik.core.social_media.instagram.workflows.scraping import scraping_workflow

HEADER_ID = f"{PKG}:id/row_feed_profile_header"
ROW_ID = f"{PKG}:id/row_feed_view_group_buttons"
COMMENT_ID = f"{PKG}:id/row_feed_button_comment"
SHARE_ID = f"{PKG}:id/row_feed_button_share"
LIST_ID = "android:id/list"
ACTION_BAR_ID = f"{PKG}:id/action_bar"
PIXEL_3A_H, PIXEL_6A_H = 2220, 2400

#: (capture, app language, screen height): the post above's row on screen, and the framed post's.
POST_ABOVE_AND_FRAMED_ROWS = [
    ("ig410_fr_home_feed_likes_above_framed_post.xml", "fr", PIXEL_3A_H),
    ("ig447_fr_home_feed_hidden_likes_above_framed_post.xml", "fr", PIXEL_6A_H),
    ("ig410_fr_feed_heart_of_post_above_at_top.xml", "fr", PIXEL_3A_H),
    ("ig447_fr_profile_posts_next_header_mid_screen.xml", "fr", PIXEL_6A_H),
]
#: The post above's row on screen, the framed post's under the bottom of the list.
FRAMED_ROW_UNDER_THE_SCREEN = [
    ("ig447_fr_profile_posts_row_below_screen.xml", "fr", PIXEL_6A_H),
    ("ig410_en_feed_carousel_framed.xml", "en", PIXEL_3A_H),
]
NO_POST_ABOVE = ("ig410_fr_home_feed_framed_post_hides_likes.xml", "fr", PIXEL_3A_H)
CASE_IDS = ["feed 410", "feed 447", "feed 410 sliver", "profile posts 447"]


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, popup_handling, post_navigation, post_scraping_helpers):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    yield
    set_active_locale(None)


def _framed_post_rows(name):
    """(framed post's row, the rows above its header) of a capture: the framed post's header is the
    first under the top of the list (the list's own top, or the action bar over it); its row is the
    first row under that header."""
    root = parse_ui_dump(capture(name))
    tops = [bounds_of(n)[1] for n in root.iter() if n.get("resource-id") == LIST_ID]
    tops += [bounds_of(n)[3] for n in root.iter() if n.get("resource-id") == ACTION_BAR_ID]
    list_top = max(tops)
    header_top = min(bounds_of(n)[1] for n in root.iter()
                     if n.get("resource-id") == HEADER_ID and bounds_of(n)[1] >= list_top)
    rows = [bounds_of(n) for n in root.iter() if n.get("resource-id") == ROW_ID]
    below = [row for row in rows if row[1] > header_top]
    return (min(below, key=lambda row: row[1]) if below else None), [row for row in rows if row[1] < header_top]


def _touch_target(name, button_id, row):
    """The touch target of a row button: the clickable parent of its image, inside `row`."""
    root = parse_ui_dump(capture(name))
    for node in root.iter():
        if node.get("resource-id") == button_id:
            left, top, right, bottom = bounds_of(node)
            if row[1] <= top and bottom <= row[3]:
                return bounds_of(node.getparent())
    raise AssertionError(f"no {button_id} in the row {row} of {name}")


def _phone(name, height):
    return ProfilePostsPhone(screen=capture(name), height=height)


def _facade(phone):
    return DeviceFacade(CloneAwareDeviceProxy(phone, PKG))


def _taps(phone):
    return [(x, y) for _kind, x, y in phone.taps]


def _inside(point, bounds):
    x, y = point
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


def _assert_first_tap_on_the_framed_post(phone, name, button_id):
    framed_row, rows_above = _framed_post_rows(name)
    assert rows_above, f"{name}: the case needs the post above's row on screen"
    target = _touch_target(name, button_id, framed_row)
    taps = _taps(phone)
    assert taps, f"nothing tapped: the framed post's button is {target}"
    assert _inside(taps[0], target), (
        f"tap at {taps[0]}: the framed post's button is {target}, the post above's row is {rows_above}")


# --- the comment ---------------------------------------------------------------------------------


@pytest.mark.parametrize("name,lang,height", POST_ABOVE_AND_FRAMED_ROWS, ids=CASE_IDS)
def test_the_comment_opens_on_the_framed_posts_own_button(name, lang, height):
    set_active_locale(lang)
    phone = _phone(name, height)

    assert CommentAction(_facade(phone))._click_comment_button() is True

    assert len(_taps(phone)) == 1
    _assert_first_tap_on_the_framed_post(phone, name, COMMENT_ID)


@pytest.mark.parametrize("name,lang,height", FRAMED_ROW_UNDER_THE_SCREEN, ids=["profile posts 447", "feed 410"])
def test_no_comment_when_the_framed_posts_row_is_under_the_screen(name, lang, height):
    # The post above's button is on screen and the framed post's is not: a comment is written for
    # the framed post, so nothing is tapped rather than the post above's button.
    set_active_locale(lang)
    framed_row, rows_above = _framed_post_rows(name)
    assert framed_row is None and rows_above
    phone = _phone(name, height)

    assert CommentAction(_facade(phone))._click_comment_button() is False

    assert phone.taps == [], "a comment was opened on the post above"


def test_without_a_post_above_the_framed_posts_button_as_before():
    name, lang, height = NO_POST_ABOVE
    set_active_locale(lang)
    phone = _phone(name, height)

    assert CommentAction(_facade(phone))._click_comment_button() is True

    framed_row, _rows_above = _framed_post_rows(name)
    assert len(_taps(phone)) == 1 and _inside(_taps(phone)[0], _touch_target(name, COMMENT_ID, framed_row))


def test_off_a_list_the_reel_viewers_own_comment_button():
    set_active_locale("en")
    phone = _phone("ig410_en_reel_viewer.xml", PIXEL_3A_H)
    viewer_button = next(bounds_of(n) for n in parse_ui_dump(capture("ig410_en_reel_viewer.xml")).iter()
                         if n.get("resource-id") == f"{PKG}:id/comment_button")

    assert CommentAction(_facade(phone))._click_comment_button() is True

    assert len(_taps(phone)) == 1 and _inside(_taps(phone)[0], viewer_button)


# --- the thread read before a comment, and the Lab's post.open_comments --------------------------


@pytest.mark.parametrize("name,lang,height", POST_ABOVE_AND_FRAMED_ROWS, ids=CASE_IDS)
def test_the_thread_opens_on_the_framed_posts_own_button(name, lang, height):
    set_active_locale(lang)
    phone = _phone(name, height)

    # The replayed screen does not change after the tap: what the thread check then finds is not
    # this test's subject, the tap is.
    BaseBusinessAction(_facade(phone))._open_comments_thread()

    assert len(_taps(phone)) == 1
    _assert_first_tap_on_the_framed_post(phone, name, COMMENT_ID)


@pytest.mark.parametrize("name,lang,height", FRAMED_ROW_UNDER_THE_SCREEN, ids=["profile posts 447", "feed 410"])
def test_no_thread_opened_when_the_framed_posts_row_is_under_the_screen(name, lang, height):
    set_active_locale(lang)
    phone = _phone(name, height)

    assert BaseBusinessAction(_facade(phone))._open_comments_thread() == popup_handling.COMMENTS_NO_BUTTON

    assert phone.taps == []


def test_off_a_list_the_thread_opens_on_the_reel_viewers_own_button():
    set_active_locale("fr")
    phone = _phone("ig410_fr_reel_viewer.xml", PIXEL_3A_H)
    viewer_button = next(bounds_of(n) for n in parse_ui_dump(capture("ig410_fr_reel_viewer.xml")).iter()
                         if n.get("resource-id") == f"{PKG}:id/comment_button")

    BaseBusinessAction(_facade(phone))._open_comments_thread()

    assert len(_taps(phone)) == 1 and _inside(_taps(phone)[0], viewer_button)


# --- the commenters a scraping reads ------------------------------------------------------------


class _DeviceManager:
    """What a scraping gets from its host: the connected phone (the bare uiautomator2 device)."""

    def __init__(self, device):
        self.device = device


@pytest.mark.parametrize("name,lang,height", POST_ABOVE_AND_FRAMED_ROWS, ids=CASE_IDS)
def test_the_commenters_are_scraped_from_the_framed_post(name, lang, height, monkeypatch):
    monkeypatch.setattr(scraping_workflow, "get_local_database", lambda: None)
    set_active_locale(lang)
    phone = _phone(name, height)
    workflow = scraping_workflow.ScrapingWorkflow(_DeviceManager(phone), {})
    # The reading loop of the open thread is not this test's subject: the tap that opens it is.
    workflow._scrape_list = lambda **_kwargs: []

    workflow._scrape_post_commenters(max_count=5, source_name="post")

    _assert_first_tap_on_the_framed_post(phone, name, COMMENT_ID)


# --- the share button that copies the post's link ----------------------------------------------


@pytest.mark.parametrize("name,lang,height", POST_ABOVE_AND_FRAMED_ROWS, ids=CASE_IDS)
def test_the_link_is_copied_from_the_framed_posts_own_share_button(name, lang, height):
    # The production reading of a post's link (`get_post_url_from_share`), as the Lab runs it: the
    # comment files it, the profile-posts scraping collects it. The replayed screen opens no share
    # sheet: no link comes back, and the first tap is the subject.
    register_instagram()
    set_active_locale(lang)
    phone = _phone(name, height)

    INSTAGRAM_ACTIONS["post.read_share_url"](build_instagram_action_bundle(_facade(phone)), {})

    _assert_first_tap_on_the_framed_post(phone, name, SHARE_ID)


# --- the reader --------------------------------------------------------------------------------


def test_without_a_reader_of_the_framed_post_no_button_is_guessed():
    set_active_locale("fr")
    phone = _phone("ig410_fr_home_feed_likes_above_framed_post.xml", PIXEL_3A_H)
    extractors = InstagramUIExtractors(_facade(phone))

    assert extractors.framed_post_element(BUTTON_SELECTORS.comment_button, "comment button") is None
