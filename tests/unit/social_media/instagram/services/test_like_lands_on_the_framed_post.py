"""A like lands on the framed post, the one whose header gives the identity the guards check, or
nowhere.

Measured on a Pixel 6a (Instagram 447 in French, a public profile, 10 advances in its post list):
the double tap aimed at a fixed band of the SCREEN (30-70 % wide, 30-52 % high), whatever sat
there. In 5 advances out of 10 the centre of that band lay on the post above the framed one, and on
the screens below it runs over that post's button row and caption. The heart the button path
tapped was the first one on the screen, and "already liked" was any selected heart on the screen:
the post above's, when it is the post just liked.

The screens are real dumps, anonymized, of that list at rest:
- `ig447_fr_profile_posts_next_header_mid_screen.xml`: the previous post's photo and button row
  at the top, the framed post's header at 38 %, its photo, its button row above the bottom;
- `ig447_fr_profile_posts_row_below_screen.xml`: the previous post's carousel and button row at
  the top, the framed post's header at 46 %, its photo running under the bottom of the list, its
  button row off the screen.
`profile_posts_phone.py` replays them; a tap on a heart, or a double tap on a post, likes that post
as Instagram does.
"""

import pytest

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.services.like.orchestration as orchestration
import taktik.core.social_media.instagram.actions.base.device.facade as facade_module
from profile_posts_phone import HEADER_ID, HEART_ID, PKG, ProfilePostsPhone, bounds_of, capture, like_on_phone
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

ROW_ON_SCREEN = capture("ig447_fr_profile_posts_next_header_mid_screen.xml")
ROW_BELOW_SCREEN = capture("ig447_fr_profile_posts_row_below_screen.xml")
BUTTONS_ID = f"{PKG}:id/row_feed_view_group_buttons"


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading, feed_scroll, orchestration):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _host(phone):
    """The production like of a list on the replayed phone, with the production scroll owner."""
    return like_on_phone(phone)


def _double_tap_drawn(monkeypatch, drawn: bool):
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: drawn)


def _framed_post_geometry(xml):
    """The framed post of the capture: its header, and what lies under it down to the next one."""
    from lxml import etree

    root = etree.fromstring(xml.encode("utf-8"))
    headers = sorted(bounds_of(n) for n in root.iter() if n.get("resource-id") == HEADER_ID)
    header = headers[0]
    rows = [bounds_of(n) for n in root.iter()
            if n.get("resource-id") == BUTTONS_ID and bounds_of(n)[1] > header[1]]
    hearts = [(bounds_of(n), n.get("selected")) for n in root.iter()
              if n.get("resource-id") == HEART_ID]
    return header, (rows[0] if rows else None), hearts


def test_the_double_tap_lands_on_the_framed_posts_own_photo(monkeypatch):
    _double_tap_drawn(monkeypatch, True)
    phone = ProfilePostsPhone(screen=ROW_ON_SCREEN, likes_on_tap=True)
    header, row, _hearts = _framed_post_geometry(ROW_ON_SCREEN)

    assert _host(phone).like_current_post() is orchestration.FramedLike.LIKED

    assert [kind for kind, _x, _y in phone.taps] == ["double_tap"]
    _kind, x, y = phone.taps[0]
    # In the middle of its own photo, away from the edges where Instagram draws its badges.
    photo_top, photo_bottom = header[3], row[1]
    middle = (photo_top + (photo_bottom - photo_top) // 4, photo_bottom - (photo_bottom - photo_top) // 4)
    assert middle[0] <= y <= middle[1], (
        f"double tap at y={y}: the middle of the framed post's photo runs from {middle[0]} to {middle[1]}")
    # Its own heart turned, never the post above's.
    hearts = _framed_post_geometry(phone.dump_hierarchy())[2]
    assert [selected for bounds, selected in hearts if bounds[1] > header[1]] == ["true"]
    assert [selected for bounds, selected in hearts if bounds[1] < header[1]] == ["false"]


def test_the_button_path_taps_the_framed_posts_own_heart(monkeypatch):
    _double_tap_drawn(monkeypatch, False)
    phone = ProfilePostsPhone(screen=ROW_ON_SCREEN, likes_on_tap=True)
    header, row, hearts = _framed_post_geometry(ROW_ON_SCREEN)
    own_heart = next(bounds for bounds, _selected in hearts if bounds[1] > header[1])

    assert _host(phone).like_current_post() is orchestration.FramedLike.LIKED

    assert [kind for kind, _x, _y in phone.taps] == ["tap"]
    _kind, x, y = phone.taps[0]
    assert own_heart[0] <= x <= own_heart[2] and own_heart[1] <= y <= own_heart[3], (
        f"tap at ({x}, {y}), the framed post's heart is {own_heart}")


@pytest.mark.parametrize("double_tap", [True, False], ids=["double_tap", "heart"])
def test_no_like_when_the_framed_posts_heart_cannot_be_shown(monkeypatch, double_tap):
    # The framed post's photo starts at 46 % and runs under the bottom; its heart is below. On
    # the screen: the post above, its carousel, its heart. The like drags the post up to show its
    # row, but this capture holds nothing under its bottom (as when a post is taller than the
    # list): its heart never shows, and nothing is liked, the post above least of all.
    _double_tap_drawn(monkeypatch, double_tap)
    phone = ProfilePostsPhone(screen=ROW_BELOW_SCREEN, likes_on_tap=True)
    like = _host(phone)

    assert like.like_current_post() is orchestration.FramedLike.NOT_LIKED

    assert phone.taps == [], "a like went to a screen whose framed post's heart is not on it"
    assert [kind for kind, *_rest in like.scroll_actions.gestures] == ["drag"]


def test_the_post_above_liked_does_not_make_the_framed_post_liked(monkeypatch):
    # The walk has just liked the post above: its selected heart is still at the top.
    phone = ProfilePostsPhone(screen=ROW_ON_SCREEN, likes_on_tap=True)
    header, _row, hearts = _framed_post_geometry(ROW_ON_SCREEN)
    above = next(bounds for bounds, _selected in hearts if bounds[1] < header[1])
    phone._liked_hearts.add(f"[{above[0]},{above[1]}][{above[2]},{above[3]}]")
    host = _host(phone)

    assert host._is_post_already_liked() is False

    _double_tap_drawn(monkeypatch, True)
    assert host.like_current_post() is orchestration.FramedLike.LIKED
    hearts_after = _framed_post_geometry(phone.dump_hierarchy())[2]
    assert [selected for bounds, selected in hearts_after if bounds[1] > header[1]] == ["true"]
