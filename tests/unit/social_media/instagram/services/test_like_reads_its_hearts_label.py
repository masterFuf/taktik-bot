"""A like reads the label of its heart: `selected` alone no longer says a post is liked.

Measured on 2026-10-31, Instagram 447.0.0.55.81 in French, Pixel 6a and Nokia 4.2: a liked heart says
« J’aime déjà », a heart not liked « J’aime », and `selected` is false on both. Days before, the same
app on the same Pixel 6a showed every like the way the bot read it: the change came from Instagram's
servers, not from a version. The bot read `selected` only, and saw no like at all (0 of 16). What it
did then is in `test_like_plays_one_gesture.py`.

The screens are real dumps, anonymized, of a profile's posts:
- `ig447_fr_profile_posts_framed_heart_liked.xml` (Pixel 6a): the post above's heart « J’aime » at the
  top, the framed post's heart « J’aime déjà » above the bottom;
- `ig447_fr_720p_profile_posts_framed_heart_liked.xml` (Nokia 4.2): the framed post's heart « J’aime déjà »;
- `ig447_fr_720p_profile_posts_framed_heart_not_liked.xml` (Nokia 4.2): the framed post's heart « J’aime ».
`profile_posts_phone.py` replays them.
"""

import pytest

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.base.device.facade as facade_module
from profile_posts_phone import HEART_ID, PKG, ProfilePostsPhone, bounds_of, capture, like_on_phone
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.recorder.human_behavior_recorder import ContentSampler
from taktik.core.social_media.instagram.ui.labels import is_liked_heart
from taktik.core.social_media.instagram.ui.selectors.locales import en as en_locale
from taktik.core.social_media.instagram.ui.selectors.locales import fr as fr_locale
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS

LIKED_6A = capture("ig447_fr_profile_posts_framed_heart_liked.xml")
LIKED_NOKIA = capture("ig447_fr_720p_profile_posts_framed_heart_liked.xml")
NOT_LIKED_NOKIA = capture("ig447_fr_720p_profile_posts_framed_heart_not_liked.xml")
REEL_VIEWER = capture("ig410_fr_reel_viewer.xml")
NOKIA_H = 1520
PIXEL_6A_H = 2400
LIKED_LABEL = "J’aime déjà"
NOT_LIKED_LABEL = "J’aime"


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading, feed_scroll):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _phone(screen=NOT_LIKED_NOKIA, height=NOKIA_H, **kwargs):
    return ProfilePostsPhone(screen=screen, height=height, **kwargs)


def _target(screen, height):
    return like_on_phone(_phone(screen=screen, height=height)).scroll_actions.framed_post_like_target()


@pytest.mark.parametrize("screen, height", [(LIKED_6A, PIXEL_6A_H), (LIKED_NOKIA, NOKIA_H)], ids=["pixel6a", "nokia"])
def test_a_framed_heart_saying_liked_is_liked_with_selected_false(screen, height):
    hearts = [node for node in parse_ui_dump(screen).iter() if node.get("resource-id") == HEART_ID]
    assert {node.get("selected") for node in hearts} == {"false"}, "the capture is no longer the real form"

    target = _target(screen, height)

    assert target["list"] is True and target["heart"] is not None
    assert target["liked"] is True


def test_a_framed_heart_saying_like_is_not_liked():
    assert _target(NOT_LIKED_NOKIA, NOKIA_H)["liked"] is False


def test_the_same_capture_with_its_framed_heart_not_liked_is_not_liked():
    # Only its label changes; the post above's « J’aime » of this capture sits at the top.
    (framed,) = [node for node in parse_ui_dump(LIKED_6A).iter()
                 if node.get("resource-id") == HEART_ID and node.get("content-desc") == LIKED_LABEL]
    assert bounds_of(framed)[1] > PIXEL_6A_H / 2

    assert _target(LIKED_6A.replace(LIKED_LABEL, NOT_LIKED_LABEL), PIXEL_6A_H)["liked"] is False


@pytest.mark.parametrize("selected, desc, liked", [
    ("true", "Liked", True),                   # Instagram 410, English
    ("true", "J’aime", True),                  # Instagram 410, the Reel viewer's heart
    ("false", "J’aime déjà", True),            # Instagram 447, the capture's apostrophe
    ("false", "J'aime déjà", True),            # the other apostrophe
    ("false", "J’aime", False),                # lies inside « J’aime déjà »
    ("false", "J'aime", False),
    ("false", "Nombre de J'aime", False),      # another node that says « J'aime »
    ("false", "2 J’aime déjà vus", False),     # a whole match, not a piece of a sentence
    ("false", "", False),
    ("false", None, False),
])
def test_a_liked_label_is_compared_whole(selected, desc, liked):
    assert is_liked_heart(selected, desc) is liked


def test_the_english_labels_come_from_the_active_language():
    set_active_locale("en")

    assert is_liked_heart("false", "Unlike") is True
    assert is_liked_heart("false", "Liked") is True
    assert is_liked_heart("false", "Like") is False
    assert is_liked_heart("false", LIKED_LABEL) is False


def test_one_list_of_labels_for_the_list_and_for_the_xpaths_off_a_list():
    # A second list of labels is how a heart reader goes stale: `feed.already_liked_indicators` and
    # `detection.liked_button_indicators` both said « Ne plus aimer », and no heart ever did.
    assert "detection.liked_button_indicators" not in fr_locale.STRINGS
    assert "feed.already_liked_indicators" not in fr_locale.STRINGS
    assert "detection.liked_button_indicators" not in en_locale.STRINGS
    assert "feed.already_liked_indicators" not in en_locale.STRINGS
    for label in DETECTION_SELECTORS.liked_heart_labels:
        assert any(f'@content-desc="{label}"' in xpath for xpath in DETECTION_SELECTORS.liked_button_indicators)
    assert not any("contains" in xpath for xpath in DETECTION_SELECTORS.liked_button_indicators)


@pytest.mark.parametrize("screen, liked", [(LIKED_NOKIA, True), (NOT_LIKED_NOKIA, False)], ids=["liked", "not_liked"])
def test_is_post_liked_reads_the_label_too(screen, liked):
    like = like_on_phone(_phone(screen=screen))

    assert like.detection_actions.is_post_liked() is liked


def test_the_reel_viewers_heart_reads_the_label_too():
    # Only its label changes: the viewer's heart, read off a list by the same xpaths.
    heart_id = f'{PKG}:id/like_button'
    root = parse_ui_dump(REEL_VIEWER)
    (heart,) = [node for node in root.iter() if node.get("resource-id") == heart_id]
    screen = REEL_VIEWER.replace(f'content-desc="{heart.get("content-desc")}"', f'content-desc="{LIKED_LABEL}"')
    assert f'content-desc="{LIKED_LABEL}"' in screen

    assert like_on_phone(_phone(screen=screen, height=2220)).detection_actions.is_post_liked() is True


@pytest.mark.parametrize("screen, liked", [(LIKED_NOKIA, True), (NOT_LIKED_NOKIA, False)], ids=["liked", "not_liked"])
def test_the_recorder_reads_the_same_heart(screen, liked):
    assert ContentSampler(_phone(screen=screen))._is_liked() is liked
