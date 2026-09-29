"""The Lab's `post.is_liked` answers what the production like reads before it likes: the heart of the
framed post's own row, selected or not.

Found by the Lab auto-test on a Pixel 6a (Instagram 447 in French, 2026-09-29): `post.is_liked`
answered "yes" twice on the home feed while every heart on the screen was empty. It asked whether a
like BUTTON was on the screen (`PostInteractionMixin.is_post_already_liked`, which no production path
called), and every post carries one: the answer was "yes" on any post.

The screen is a real dump, anonymized (`ig447_fr_profile_posts_next_header_mid_screen.xml`): the
previous post's button row at the top, the framed post's header at 38 %, its own row above the
bottom, both hearts empty. `profile_posts_phone.py` replays it; a like turns its heart selected.
"""

from types import SimpleNamespace

import pytest

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.business.actions.like.orchestration as orchestration
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from bridges.tools.lab.actions.instagram.post import is_liked
from profile_posts_phone import HEADER_ID, HEART_ID, ProfilePostsPhone, bounds_of, capture, like_on_phone
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

ROW_ON_SCREEN = capture("ig447_fr_profile_posts_next_header_mid_screen.xml")


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading, feed_scroll, orchestration):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _lab_bundle(phone):
    """What the Lab hands its actions on this phone: the production like and its click actions."""
    like = like_on_phone(phone)
    return SimpleNamespace(like=like, click=like.click_actions, device=like.device)


def _heart_above_the_framed_post(xml):
    from lxml import etree

    root = etree.fromstring(xml.encode("utf-8"))
    header_top = min(bounds_of(n)[1] for n in root.iter() if n.get("resource-id") == HEADER_ID)
    return next(n.get("bounds") for n in root.iter()
                if n.get("resource-id") == HEART_ID and bounds_of(n)[1] < header_top)


def test_no_heart_selected_is_not_liked():
    lab = _lab_bundle(ProfilePostsPhone(screen=ROW_ON_SCREEN))

    assert is_liked(lab, {}) is False


def test_the_post_above_liked_does_not_make_the_framed_post_liked():
    phone = ProfilePostsPhone(screen=ROW_ON_SCREEN)
    phone._liked_hearts.add(_heart_above_the_framed_post(ROW_ON_SCREEN))
    lab = _lab_bundle(phone)

    assert is_liked(lab, {}) is False


def test_the_framed_post_liked_is_liked(monkeypatch):
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: False)
    phone = ProfilePostsPhone(screen=ROW_ON_SCREEN, likes_on_tap=True)
    lab = _lab_bundle(phone)
    assert lab.like.like_current_post() is True

    assert is_liked(lab, {}) is True
