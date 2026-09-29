"""« Already liked? » read before a like: a reading that fails is « unknown », never « not liked ».

The walk of a profile's posts asks whether the framed post is liked before it decides to like it
(`LikeOrchestration._is_post_already_liked`, which the Lab's `post.is_liked` calls too). When the
reading raised (a gesture or a dump failing on the phone), it answered « not liked », logged at
debug only: a value passing for a measure. The walk then liked: on a post liked already the like
path counted it as a like given (a ledger row, the session counter, `on_like`), and off a list its
heart tap took the like back. A screen that could not be read at all fell back on « any heart
selected on the screen », which a failed dump answers « no ».

Now the reading is « unknown » (None) and said at warning level; the walk likes nothing on it, and
the Lab reports « no answer ».

Off a list (the full-screen Reel viewer), the same reading of the viewer's heart
(`DetectionActions.is_post_liked`) answered « no » when its screen photo failed (a failed photo
finds nothing): the like then tapped that heart, which takes back a like given before, or given by
its own double tap a moment earlier (the check after the double tap failing the same way).

The screens are real dumps of the Pixel 3a (Instagram 410), anonymized, replayed by
`profile_posts_phone.py`:
- `ig410_en_profile_posts_video_row_below_screen.xml` (English, a profile's posts): the framed
  post's heart under the bottom;
- `ig410_en_profile_posts_video_row_shown.xml`: the same post after the production drag, its heart
  on screen, turned on here as a like turns it (the likecadre captures, one mapping);
- `ig410_fr_reel_viewer.xml` (French): the Reel viewer, its heart turned on and off here as a like
  and a tap on it do (derived: only its `selected` changes).
"""

import pytest
from loguru import logger
from lxml import etree

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.business.actions.like.orchestration as orchestration
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from bridges.tools.lab.actions.instagram import ACTION_REGISTRY as INSTAGRAM_ACTIONS
from bridges.tools.lab.actions.instagram import register_actions as register_instagram
from bridges.tools.lab.action_test.bundles.instagram import build_instagram_action_bundle
from profile_posts_phone import HEART_ID, PKG, ProfilePostsPhone, bounds_of, capture, like_on_phone
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

ROW_BELOW = capture("ig410_en_profile_posts_video_row_below_screen.xml")
ROW_SHOWN = capture("ig410_en_profile_posts_video_row_shown.xml")
#: How much further up the content of ROW_SHOWN sits than ROW_BELOW's (its header's bottom).
ROW_SHOWN_OFFSET = 523 - 347
PIXEL_3A_H = 2220
REEL_VIEWER = capture("ig410_fr_reel_viewer.xml")
VIEWER_HEART_ID = f"{PKG}:id/like_button"
(VIEWER_HEART,) = [bounds_of(node) for node in parse_ui_dump(REEL_VIEWER).iter()
                   if node.get("resource-id") == VIEWER_HEART_ID]


@pytest.fixture(autouse=True)
def _english_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading, feed_scroll, orchestration):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("en")
    yield
    set_active_locale(None)


@pytest.fixture
def warnings():
    """The WARNING lines logged while the test runs."""
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="WARNING")
    yield lines
    logger.remove(sink)


def _heart_of(xml):
    (heart,) = [node for node in parse_ui_dump(xml).iter() if node.get("resource-id") == HEART_ID]
    left, top, right, bottom = bounds_of(heart)
    return f"[{left},{top}][{right},{bottom}]"


def _phone_with_the_framed_post_liked():
    """The framed post, liked, its heart under the bottom until the row is shown."""
    phone = ProfilePostsPhone(screen=ROW_BELOW, height=PIXEL_3A_H, further=(ROW_SHOWN, ROW_SHOWN_OFFSET))
    phone._liked_further_hearts.add(_heart_of(ROW_SHOWN))
    return phone


def _phone_that_cannot_read_its_screen():
    """The framed post, liked, its heart on screen; every dump fails, as when the uiautomator2
    server stops answering."""
    phone = ProfilePostsPhone(screen=ROW_SHOWN, height=PIXEL_3A_H)
    phone._liked_hearts.add(_heart_of(ROW_SHOWN))

    def dump_fails(*_args, **_kwargs):
        raise ConnectionError("uiautomator2 server not answering")

    phone.dump_hierarchy = dump_fails
    return phone


def _drag_fails(*_args, **_kwargs):
    raise ConnectionError("uiautomator2 server not answering")


def test_the_captures_show_a_liked_post():
    like = like_on_phone(_phone_with_the_framed_post_liked())
    assert like._is_post_already_liked() is True


def test_a_gesture_failing_while_showing_the_row_leaves_it_unknown(warnings):
    phone = _phone_with_the_framed_post_liked()
    like = like_on_phone(phone)
    like.scroll_actions._long_drag = _drag_fails

    assert like._is_post_already_liked() is None

    assert phone.taps == []
    assert any("unknown" in line for line in warnings), warnings


def test_an_unreadable_screen_leaves_it_unknown(warnings):
    phone = _phone_that_cannot_read_its_screen()
    like = like_on_phone(phone)

    assert like._is_post_already_liked() is None

    assert phone.taps == []
    assert any("unknown" in line for line in warnings), warnings


def test_a_failed_reading_of_the_framed_post_is_not_replaced_by_the_whole_screen(warnings):
    # The framed post's reading fails once and the next photo works: its answer is not asked of
    # every heart of the screen instead, whose first selected one can be the post above's.
    phone = ProfilePostsPhone(screen=ROW_SHOWN, height=PIXEL_3A_H)
    phone._liked_hearts.add(_heart_of(ROW_SHOWN))
    replay = phone.dump_hierarchy
    failures = [ConnectionError("uiautomator2 server not answering")]

    def fails_once(*args, **kwargs):
        if failures:
            raise failures.pop()
        return replay(*args, **kwargs)

    phone.dump_hierarchy = fails_once
    like = like_on_phone(phone)

    assert like._is_post_already_liked() is None

    assert any("unknown" in line for line in warnings), warnings


def test_the_lab_reports_no_answer_when_the_row_could_not_be_shown():
    # `post.is_liked` calls the production reading: a « no » there was a false answer.
    register_instagram()
    phone = _phone_with_the_framed_post_liked()
    bundle = build_instagram_action_bundle(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))
    bundle.like.scroll_actions._long_drag = _drag_fails

    result = INSTAGRAM_ACTIONS["post.is_liked"](bundle, {})

    assert (result["success"], result["details"]["found"]) == (False, None), result


# --- off a list: the full-screen Reel viewer -------------------------------------------------------


def _inside(point, bounds):
    x, y = point
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


class _ViewerPhone(ProfilePostsPhone):
    """The Reel viewer replayed. Its heart turns on with a double tap on the video or a tap on it,
    and off with a tap on it when on, as Instagram does. `fail_next_dumps` dumps fail, as when the
    uiautomator2 server stops answering for a moment; `stops_after_double_tap` makes it so right
    after a double tap."""

    def __init__(self, liked=False, stops_after_double_tap=False):
        super().__init__(screen=REEL_VIEWER, height=PIXEL_3A_H)
        self.liked = liked
        self.fail_next_dumps = 0
        self.stops_after_double_tap = stops_after_double_tap

    def dump_hierarchy(self, *_args, **_kwargs):
        if self.fail_next_dumps:
            self.fail_next_dumps -= 1
            raise ConnectionError("uiautomator2 server not answering")
        root = etree.fromstring(REEL_VIEWER.encode("utf-8"))
        for node in root.iter():
            if node.get("resource-id") == VIEWER_HEART_ID:
                node.set("selected", "true" if self.liked else "false")
        return etree.tostring(root, encoding="unicode")

    def click(self, x, y):
        self.taps.append(("tap", x, y))
        if _inside((x, y), VIEWER_HEART):
            self.liked = not self.liked

    def double_click(self, x, y, duration=0.1):
        self.taps.append(("double_tap", x, y))
        self.liked = True
        if self.stops_after_double_tap:
            self.fail_next_dumps = 1


def _then_the_server_stops_once(phone, owner, name):
    """After `owner.name` has answered, the next dump fails once."""
    real = getattr(owner, name)

    def answered_then_stops(*args, **kwargs):
        answer = real(*args, **kwargs)
        phone.fail_next_dumps = 1
        return answer

    setattr(owner, name, answered_then_stops)


def test_off_a_list_an_unread_heart_is_unknown(warnings):
    set_active_locale("fr")
    phone = _ViewerPhone(liked=True)
    like = like_on_phone(phone)
    _then_the_server_stops_once(phone, like, "_framed_like_target")

    assert like._is_post_already_liked() is None

    assert phone.taps == []
    assert any("unknown" in line for line in warnings), warnings


def test_off_a_list_the_like_does_not_tap_a_heart_it_could_not_read(monkeypatch, warnings):
    set_active_locale("fr")
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: False)
    phone = _ViewerPhone(liked=True)
    like = like_on_phone(phone)
    _then_the_server_stops_once(phone, like.detection_actions, "is_on_post_screen")

    assert like.like_current_post() is False

    assert phone.taps == [], "the heart of a liked post was tapped: its like taken back"
    assert phone.liked is True
    assert any("unknown" in line for line in warnings), warnings


def test_off_a_list_a_double_tap_whose_check_fails_is_not_undone_by_a_heart_tap(monkeypatch, warnings):
    set_active_locale("fr")
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: True)
    phone = _ViewerPhone(liked=False, stops_after_double_tap=True)
    like = like_on_phone(phone)

    assert like.like_current_post() is False

    assert [kind for kind, _x, _y in phone.taps] == ["double_tap"], phone.taps
    assert phone.liked is True, "the heart tap took back the like the double tap gave"
    assert any("unknown" in line for line in warnings), warnings


def test_off_a_list_a_readable_screen_still_likes_and_reads_liked():
    set_active_locale("fr")
    phone = _ViewerPhone(liked=False)
    like = like_on_phone(phone)

    assert like._is_post_already_liked() is False
    assert like.like_current_post() is True
    assert phone.liked is True
    assert like._is_post_already_liked() is True
