"""A like on a list of posts shows the framed post's button row first when its heart runs under the
bottom of the list, then likes THAT post, checked on its header and on its heart; or likes nothing.

The heart of the framed post is the only proof that a like took, and the only "already liked" to
trust: before, no like at all when it was under the bottom. On the Pixel 3a (Instagram 410,
English, the posts of a public profile, 2026-09-28), 2 of 14 advances ended so, both on a video
(taller than a photo); on the home feed, so does the first post under the stories tray. The rule
since 2026-09-28: a short humanized scroll to show the row, then the like, verified on the heart;
never an unverified double tap.

The screens are real dumps of that phone, anonymized with one mapping (a word has the same
replacement in all of them), replayed by `profile_posts_phone.py`:
- `ig410_en_profile_posts_video_row_below_screen.xml`: the framed post (a video) has its header
  149 px under the top of the list, its video runs under the bottom, no button row on screen;
- `ig410_en_profile_posts_video_row_shown.xml`: the same list after the production drag (199 px, the
  swipe floor): the header partly under the top of the list, the same description, its row and heart
  at the bottom. Its content sits 176 px further up (the header's bottom went from 523 to 347);
- `ig410_en_profile_posts_next_photo_framed.xml`: the next post of that list framed, its heart on
  screen;
- `ig410_fr_post_opened_from_grid.xml`: a video whose header sits at the top of the list and whose
  row is under the bottom: taller than the list, its header and heart never show together.
"""

import pytest
from lxml import etree

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.services.like.orchestration as orchestration
import taktik.core.social_media.instagram.actions.base.device.facade as facade_module
from profile_posts_phone import HEADER_ID, HEART_ID, ProfilePostsPhone, bounds_of, capture, like_on_phone
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

ROW_BELOW = capture("ig410_en_profile_posts_video_row_below_screen.xml")
ROW_SHOWN = capture("ig410_en_profile_posts_video_row_shown.xml")
NEXT_POST = capture("ig410_en_profile_posts_next_photo_framed.xml")
TALLER_THAN_THE_LIST = capture("ig410_fr_post_opened_from_grid.xml")
#: How much further up the content of ROW_SHOWN sits than ROW_BELOW's (its header's bottom).
ROW_SHOWN_OFFSET = 523 - 347
PIXEL_3A_H = 2220
LIST_TOP, LIST_BOTTOM = 231, 2088


@pytest.fixture(autouse=True)
def _english_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading, feed_scroll, orchestration):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("en")
    yield
    set_active_locale(None)


def _double_tap_drawn(monkeypatch, drawn: bool):
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: drawn)


def _screen(xml):
    """(framed header's description, (bounds, selected) of each heart) of a screen."""
    root = etree.fromstring(xml.encode("utf-8"))
    headers = sorted((bounds_of(n)[1], n.get("content-desc")) for n in root.iter()
                     if n.get("resource-id") == HEADER_ID)
    hearts = [(bounds_of(n), n.get("selected")) for n in root.iter() if n.get("resource-id") == HEART_ID]
    return (headers[0][1] if headers else None), hearts


def _phone(further=ROW_SHOWN):
    return ProfilePostsPhone(screen=ROW_BELOW, height=PIXEL_3A_H, likes_on_tap=True,
                             further=(further, ROW_SHOWN_OFFSET))


def test_the_captures_show_the_case():
    below_identity, below_hearts = _screen(ROW_BELOW)
    shown_identity, shown_hearts = _screen(ROW_SHOWN)
    assert below_hearts == [], "the framed post's heart is under the bottom, no other heart on screen"
    assert shown_identity == below_identity and len(shown_hearts) == 1
    assert _screen(NEXT_POST)[0] != below_identity


@pytest.mark.parametrize("double_tap", [True, False], ids=["double_tap", "heart"])
def test_the_like_shows_the_row_then_likes_the_framed_post(monkeypatch, double_tap):
    _double_tap_drawn(monkeypatch, double_tap)
    phone = _phone()
    like = like_on_phone(phone)

    assert like.like_current_post() is orchestration.FramedLike.LIKED

    drags = like.scroll_actions.gestures
    assert [(kind, direction) for kind, direction, _px in drags] == [("drag", "up")]
    assert drags[0][2] < (LIST_BOTTOM - LIST_TOP) / 2, f"{drags[0][2]} px: not a short drag"
    assert [kind for kind, _x, _y in phone.taps] == (["double_tap"] if double_tap else ["tap"])
    identity, hearts = _screen(phone.dump_hierarchy())
    assert identity == _screen(ROW_BELOW)[0], "the like went to another post"
    assert [selected for _bounds, selected in hearts] == ["true"], "the framed post's heart did not turn"


def test_the_walk_reads_already_liked_on_the_shown_row(monkeypatch):
    # The walk asks "already liked?" before it decides to like: the row is shown to answer.
    phone = _phone()
    shown_heart = _screen(ROW_SHOWN)[1][0][0]
    phone._liked_further_hearts.add(f"[{shown_heart[0]},{shown_heart[1]}][{shown_heart[2]},{shown_heart[3]}]")
    like = like_on_phone(phone)

    assert like._is_post_already_liked() is True

    assert [kind for kind, *_rest in like.scroll_actions.gestures] == ["drag"]
    assert phone.taps == []


def test_no_like_when_the_post_changed_while_showing_its_row(monkeypatch):
    # Whatever moved the list (a relayout, a late load), the screen after the drag frames the next
    # post: its heart is on screen, and it must not be liked.
    _double_tap_drawn(monkeypatch, False)
    phone = _phone(further=NEXT_POST)
    like = like_on_phone(phone)

    assert like.like_current_post() is orchestration.FramedLike.NOT_LIKED

    assert phone.taps == [], "a like went to a post other than the one framed before the drag"


@pytest.mark.parametrize("double_tap", [True, False], ids=["double_tap", "heart"])
def test_no_drag_and_no_like_for_a_post_taller_than_the_list(monkeypatch, double_tap):
    # Its header is at the top of the list: any drag takes the header away before the row shows.
    _double_tap_drawn(monkeypatch, double_tap)
    phone = ProfilePostsPhone(screen=TALLER_THAN_THE_LIST, height=PIXEL_3A_H, likes_on_tap=True)
    set_active_locale("fr")
    like = like_on_phone(phone)

    assert like.like_current_post() is orchestration.FramedLike.NOT_LIKED

    assert like.scroll_actions.gestures == [] and phone.taps == []
    assert like.scroll_actions._last_buttons_reveal["reason"] == "header_at_top"
