"""A like plays one gesture, and a run stops when its likes no longer show.

Measured on 2026-10-31, Instagram 447.0.0.55.81 in French, Pixel 6a and Nokia 4.2: no like seen at all
(0 of 16), because a liked heart no longer said it the way the bot read it
(`test_like_reads_its_hearts_label.py`). What the bot then did is what these tests hold:

- after a double tap not seen, it tapped the heart: that tap took back the like just given;
- after a tap not seen, the like stayed and was not counted: the caps no longer held;
- nothing said so: 168 likes taken back in one evening.

A heart can say liked in a way the bot has not met, the next time Instagram changes it: the phone below
says so with a label it reads nowhere, and the run must neither undo the like nor go on blind.

The screens are real dumps, anonymized, of a profile's posts, replayed by `profile_posts_phone.py`:
`ig447_fr_720p_profile_posts_framed_heart_not_liked.xml` (its framed heart « J’aime »),
`ig447_fr_720p_profile_posts_framed_heart_liked.xml` (its framed heart « J’aime déjà »),
`ig447_fr_profile_posts_row_below_screen.xml` (the framed post's heart under the bottom).
"""

import pytest
from loguru import logger

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.base.device.facade as facade_module
import taktik.core.social_media.instagram.services.like.orchestration as orchestration
from profile_posts_phone import ProfilePostsPhone, capture, like_on_phone
from taktik.core.shared.diagnostics import like_confirmation, run_halt
from taktik.core.social_media.instagram.services.like.orchestration import FramedLike
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.automation.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.workflows.common.session import stop_reasons

LIKED_NOKIA = capture("ig447_fr_720p_profile_posts_framed_heart_liked.xml")
NOT_LIKED_NOKIA = capture("ig447_fr_720p_profile_posts_framed_heart_not_liked.xml")
#: The framed heart cannot be shown on this one: a like plays no gesture.
ROW_BELOW_SCREEN = capture("ig447_fr_profile_posts_row_below_screen.xml")
NOKIA_H = 1520
PIXEL_6A_H = 2400
LIKED_LABEL = "J’aime déjà"
#: A liked heart saying it in a way the bot has not met.
A_LABEL_NOT_MET_YET = "Publication aimée"


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading, feed_scroll, orchestration):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


@pytest.fixture
def warnings():
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="WARNING")
    yield lines
    logger.remove(sink)


def _gesture_drawn(monkeypatch, double_tap: bool):
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: double_tap)


def _phone(screen=NOT_LIKED_NOKIA, height=NOKIA_H, **kwargs):
    return ProfilePostsPhone(screen=screen, height=height, **kwargs)


def _kinds(phone):
    return [kind for kind, _x, _y in phone.taps]


# --- one gesture per like -----------------------------------------------------------------------


@pytest.mark.parametrize("double_tap, gesture", [(True, "double_tap"), (False, "tap")], ids=["double_tap", "heart"])
def test_a_like_seen_by_its_label_is_filed_once(monkeypatch, double_tap, gesture):
    _gesture_drawn(monkeypatch, double_tap)
    phone = _phone(likes_on_tap=True, liked_label=LIKED_LABEL)
    like = like_on_phone(phone)

    assert like.like_framed_post(record_as="author_one") is FramedLike.LIKED

    assert _kinds(phone) == [gesture], "one gesture per like"
    assert like.rows == [("author_one", "LIKE", 1)]
    assert like.session_actions == [("like_posts", "author_one")]


def test_a_double_tap_whose_heart_says_nothing_is_not_followed_by_a_tap(monkeypatch, warnings):
    # The very defect: the double tap gave the like, its heart says it in a way that is not read.
    # The tap that followed took it back.
    _gesture_drawn(monkeypatch, True)
    phone = _phone(likes_on_tap=True, liked_label=A_LABEL_NOT_MET_YET)
    like = like_on_phone(phone)

    assert like.like_framed_post(record_as="author_one") is FramedLike.NOT_LIKED

    assert _kinds(phone) == ["double_tap"], "the heart was tapped after a double tap not seen"
    assert phone._liked_hearts, "the like the double tap gave was taken back"
    assert like.rows == [] and like.session_actions == []
    assert any("not confirmed" in line for line in warnings), warnings


def test_a_double_tap_instagram_did_not_take_is_not_followed_by_a_tap(monkeypatch):
    _gesture_drawn(monkeypatch, True)
    phone = _phone(likes_on_tap=False)
    like = like_on_phone(phone)

    assert like.like_framed_post(record_as="author_one") is FramedLike.NOT_LIKED

    assert _kinds(phone) == ["double_tap"]
    assert like.rows == [] and like.session_actions == []


def test_a_tap_whose_heart_says_nothing_is_not_counted(monkeypatch, warnings):
    _gesture_drawn(monkeypatch, False)
    phone = _phone(likes_on_tap=True, liked_label=A_LABEL_NOT_MET_YET)
    like = like_on_phone(phone)

    assert like.like_framed_post(record_as="author_one") is FramedLike.NOT_LIKED

    assert _kinds(phone) == ["tap"]
    assert phone._liked_hearts, "the like is there"
    assert like.rows == [] and like.session_actions == []
    assert any("not confirmed" in line for line in warnings), warnings


def test_a_post_liked_already_by_its_label_gets_no_gesture(monkeypatch):
    _gesture_drawn(monkeypatch, True)
    phone = _phone(screen=LIKED_NOKIA)
    like = like_on_phone(phone)

    assert like.like_framed_post(record_as="author_one") is FramedLike.ALREADY_LIKED

    assert phone.taps == [] and like.rows == []


# --- the run stops when its likes no longer show -----------------------------------------------


def _like_not_seen(times=1):
    """Likes played on a phone that does not show them, with a host of their own each time."""
    for _ in range(times):
        phone = _phone(likes_on_tap=False)
        assert like_on_phone(phone).like_framed_post() is FramedLike.NOT_LIKED
        assert phone.taps, "no gesture was played"


def _halt_code():
    return (run_halt.arret_demande() or {}).get("code")


def test_three_likes_not_seen_in_a_row_stop_the_run(monkeypatch):
    _gesture_drawn(monkeypatch, True)

    _like_not_seen(like_confirmation.UNCONFIRMED_LIKES_BEFORE_HALT - 1)
    assert _halt_code() is None

    _like_not_seen()

    assert _halt_code() == "like_unconfirmed"
    reason = stop_reasons.for_halt(run_halt.arret_demande())
    assert reason.code == "like_unconfirmed"
    assert stop_reasons.terminal_status(reason) == stop_reasons.STATUS_INTERRUPTED


def test_two_not_seen_then_a_like_seen_do_not(monkeypatch):
    _gesture_drawn(monkeypatch, True)

    _like_not_seen(2)
    seen = _phone(likes_on_tap=True, liked_label=LIKED_LABEL)
    assert like_on_phone(seen).like_framed_post() is FramedLike.LIKED
    _like_not_seen(2)

    assert _halt_code() is None


def test_a_post_liked_already_counts_neither_way(monkeypatch):
    _gesture_drawn(monkeypatch, True)
    already = like_on_phone(_phone(screen=LIKED_NOKIA))

    _like_not_seen(2)
    assert already.like_framed_post() is FramedLike.ALREADY_LIKED
    assert _halt_code() is None, "a post liked already counted as a like not seen"

    _like_not_seen()
    assert _halt_code() == "like_unconfirmed", "a post liked already started the count again"


def test_a_like_without_a_gesture_does_not_count(monkeypatch):
    # Its heart cannot be shown: no gesture, nothing that could have shown.
    _gesture_drawn(monkeypatch, True)
    for _ in range(like_confirmation.UNCONFIRMED_LIKES_BEFORE_HALT):
        phone = _phone(screen=ROW_BELOW_SCREEN, height=PIXEL_6A_H, likes_on_tap=True)
        assert like_on_phone(phone).like_current_post() is FramedLike.NOT_LIKED
        assert phone.taps == []

    assert _halt_code() is None


def test_the_count_covers_the_feed_and_a_profiles_posts_together(monkeypatch):
    # The Feed likes through `like_framed_post`, a profile's posts through `like_current_post`, each
    # with its own host: a run goes from one to the other.
    _gesture_drawn(monkeypatch, True)
    feed = object.__new__(FeedBusiness)
    feed.logger = logger
    feed.like_business = like_on_phone(_phone(likes_on_tap=False))
    profile_posts = like_on_phone(_phone(likes_on_tap=False))

    assert feed._like_current_post(record_as="author_one") is False
    assert profile_posts.like_current_post() is FramedLike.NOT_LIKED
    assert _halt_code() is None
    assert feed._like_current_post(record_as="author_one") is False

    assert _halt_code() == "like_unconfirmed"


def test_the_walk_of_a_profiles_posts_stops_on_the_third(monkeypatch):
    _gesture_drawn(monkeypatch, True)
    _like_not_seen(2)
    like = like_on_phone(_phone(likes_on_tap=False))
    like._stop_if_action_blocked = lambda *_a, **_k: False

    assert like._run_engagement_sequence(("like",), "author_one", None, {}) == (False, False)

    assert run_halt.arret_demande() is not None
