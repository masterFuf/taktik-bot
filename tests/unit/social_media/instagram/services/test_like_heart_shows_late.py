"""A heart that says liked late is still seen, and still never tapped again.

Measured on 2026-11-27, Instagram 410 in French on a Pixel 3a, a list of a profile's posts: 11 likes not
seen in one run, every one on a video, 8 of them after a double tap. The run stopped on the third in a
row (`like_confirmation`). On the phone afterwards, the three posts of that stop all said « J’aime
déjà »: the likes had been given. The heart had been read once, a few tenths of a second after the
gesture, before the slow phone playing the video showed it turned. Those likes were neither counted
nor capped, and the run stopped for nothing.

The like now reads the heart again, a bounded number of times, while it does not say liked. It never
taps it again: a tap on a liked heart takes the like back (`test_like_plays_one_gesture.py`).

The screen is the real dump of `test_like_plays_one_gesture.py`, replayed by `profile_posts_phone.py`
with a heart that turns only `heart_shows_after_s` after the like, and a dump that costs what one
costs on the Pixel 3a.
"""

import pytest
from loguru import logger

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.base.device.facade as facade_module
import taktik.core.social_media.instagram.services.like.orchestration as orchestration
from profile_posts_phone import ProfilePostsPhone, capture, like_on_phone
from taktik.core.social_media.instagram.services.like.orchestration import FramedLike
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

NOT_LIKED_NOKIA = capture("ig447_fr_720p_profile_posts_framed_heart_not_liked.xml")
NOKIA_H = 1520
LIKED_LABEL = "J’aime déjà"
#: One dump on the Pixel 3a of that run: 220 to 240 ms on average.
DUMP_S_PIXEL_3A = 0.23
#: Later than the one reading the like made before: the heart of that run's videos.
HEART_LATE_S = 0.6


@pytest.fixture
def phone_time(monkeypatch):
    """The sleeps of the code under test pass on the phone's clock."""
    holder = {}

    def sleep(seconds):
        holder["phone"].sleep(seconds)

    for module in (facade_module, shared_facade_module, post_reading, feed_scroll, orchestration):
        monkeypatch.setattr(module.time, "sleep", sleep)
    set_active_locale("fr")
    yield holder
    set_active_locale(None)


@pytest.fixture
def warnings():
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="WARNING")
    yield lines
    logger.remove(sink)


def _slow_phone(phone_time, heart_shows_after_s, likes_on_tap=True):
    phone = ProfilePostsPhone(screen=NOT_LIKED_NOKIA, height=NOKIA_H, dump_s=DUMP_S_PIXEL_3A,
                              likes_on_tap=likes_on_tap, liked_label=LIKED_LABEL,
                              heart_shows_after_s=heart_shows_after_s)
    phone_time["phone"] = phone
    return phone


def _kinds(phone):
    return [kind for kind, _x, _y in phone.taps]


@pytest.mark.parametrize("double_tap, gesture", [(True, "double_tap"), (False, "tap")], ids=["double_tap", "heart"])
def test_a_heart_that_turns_late_is_seen_and_filed_once(monkeypatch, phone_time, warnings, double_tap, gesture):
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: double_tap)
    phone = _slow_phone(phone_time, HEART_LATE_S)
    like = like_on_phone(phone)

    assert like.like_framed_post(record_as="author_one") is FramedLike.LIKED

    assert _kinds(phone) == [gesture], "the heart was tapped again"
    assert like.rows == [("author_one", "LIKE", 1)]
    assert not any("not confirmed" in line for line in warnings), warnings


def test_a_heart_that_never_turns_is_still_not_seen_after_a_bounded_wait(monkeypatch, phone_time, warnings):
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: True)
    phone = _slow_phone(phone_time, 0.0, likes_on_tap=False)
    like = like_on_phone(phone)

    assert like.like_framed_post(record_as="author_one") is FramedLike.NOT_LIKED

    assert _kinds(phone) == ["double_tap"], "the heart was tapped after a gesture not seen"
    assert like.rows == []
    assert any("not confirmed" in line for line in warnings), warnings
    assert phone.clock < 3.0, f"the like waited {phone.clock:.1f} s for its heart"
