"""The likers of the framed post open from its own like counter: the button just after its heart, in
its own button row. Never the first number of the screen.

On a list of posts, the row at the top of the screen is often the post above's. When that post
hides its likes, the first number of its row is its comment count: opening "the likers" tapped it
and opened the comments of the post above (Pixel 6a, Instagram 447 in French, the Lab's likers
context). When it shows them, its like count opened the likers of the post above. And a framed
post that hides its likes had its own comment count tapped.

The screens are real dumps, anonymized:
- `ig447_fr_home_feed_hidden_likes_above_framed_post.xml` (Instagram 447, Pixel 6a): at the top,
  the row of the post above, which hides its likes ("2" is its comment count); the framed post's
  header at 17 %, its row lower down with "9" just after its heart;
- `ig410_fr_home_feed_likes_above_framed_post.xml` (Instagram 410, Pixel 3a): at the top, the row
  of the post above with "4" just after its heart; the framed post's row at the bottom, "743";
- `ig410_fr_home_feed_framed_post_hides_likes.xml` (Instagram 410, Pixel 3a): the framed post hides
  its likes, its row has no number after its heart ("11" is its comment count);
- `ig410_fr_reel_viewer.xml`: the full-screen Reel viewer, off a list, its own counter.

The host is the one the Lab's `post.open_likers` runs, `BaseBusinessAction`, built by its own
constructor on a phone that replays the capture (`profile_posts_phone.py`).
"""

import pytest

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.core.base_business.popup_handling as popup_handling
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from profile_posts_phone import PKG, ProfilePostsPhone, bounds_of, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.core.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

ROW_ID = f"{PKG}:id/row_feed_view_group_buttons"
HEADER_ID = f"{PKG}:id/row_feed_profile_header"

HIDDEN_LIKES_ABOVE_447 = "ig447_fr_home_feed_hidden_likes_above_framed_post.xml"
LIKES_ABOVE_410 = "ig410_fr_home_feed_likes_above_framed_post.xml"
FRAMED_POST_HIDES_LIKES_410 = "ig410_fr_home_feed_framed_post_hides_likes.xml"
REEL_VIEWER_410 = "ig410_fr_reel_viewer.xml"


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, popup_handling):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _lab_host(phone):
    """The Lab's `a.popup`: the production host of `_open_likers_popup`, its pacing cut."""
    host = BaseBusinessAction(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))
    host._human_like_delay = lambda *_args, **_kwargs: None
    return host


def _phone(name, height):
    return ProfilePostsPhone(screen=capture(name), height=height)


def _counter_right_after_the_framed_heart(name):
    """The framed post's like counter in the capture: its header is the first on screen, its row
    the first under that header, the counter the row's button just after the heart's ViewGroup."""
    from taktik.core.shared.device.ui_dump import parse_ui_dump

    root = parse_ui_dump(capture(name))
    header_top = min(bounds_of(n)[1] for n in root.iter() if n.get("resource-id") == HEADER_ID)
    row = min((n for n in root.iter()
               if n.get("resource-id") == ROW_ID and bounds_of(n)[1] > header_top),
              key=lambda n: bounds_of(n)[1])
    heart_slot = next(child for child in row if any(
        d.get("resource-id", "").endswith("/row_feed_button_like") for d in child.iter()))
    return heart_slot.getnext()


def _tapped(phone):
    return [(x, y) for _kind, x, y in phone.taps]


def _inside(point, bounds):
    x, y = point
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


@pytest.mark.parametrize("name,height,count", [
    (HIDDEN_LIKES_ABOVE_447, 2400, "9"),
    (LIKES_ABOVE_410, 2220, "743"),
])
def test_the_likers_open_from_the_framed_posts_own_counter(name, height, count):
    counter = _counter_right_after_the_framed_heart(name)
    assert counter.get("text") == count
    phone = _phone(name, height)

    _lab_host(phone)._open_likers_popup(is_reel=False)

    assert len(_tapped(phone)) == 1, f"one tap expected, got {phone.taps}"
    assert _inside(_tapped(phone)[0], bounds_of(counter)), (
        f"tap at {_tapped(phone)[0]}: the framed post's like counter ({count}) is {bounds_of(counter)}")


def test_no_likers_when_the_framed_post_hides_its_likes():
    # Its row has no number after its heart: its first number is its comment count, which opens
    # its comments, not its likers.
    phone = _phone(FRAMED_POST_HIDES_LIKES_410, 2220)

    opened = _lab_host(phone)._open_likers_popup(is_reel=False)

    assert opened is False
    assert phone.taps == [], "a tap went to a post that shows no like count"


def test_off_a_list_the_reel_viewers_own_counter_still_opens_its_likers():
    phone = _phone(REEL_VIEWER_410, 2220)
    from taktik.core.shared.device.ui_dump import parse_ui_dump

    counter = next(n for n in parse_ui_dump(capture(REEL_VIEWER_410)).iter()
                   if n.get("resource-id") == f"{PKG}:id/like_count")

    _lab_host(phone)._open_likers_popup(is_reel=True)

    assert len(_tapped(phone)) == 1 and _inside(_tapped(phone)[0], bounds_of(counter))


def test_without_a_reader_of_the_framed_post_no_counter_is_guessed():
    # Which row is the framed post's is the framed post's reader's to say: an extractor built
    # without it cannot tell, and opens no likers rather than those of the first row.
    phone = _phone(HIDDEN_LIKES_ABOVE_447, 2400)
    extractors = InstagramUIExtractors(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))

    assert extractors.find_like_count_element() is None


def test_every_host_gives_its_extractor_the_framed_post_reader():
    # The Lab's host is replayed above; the others (the scraping workflow) are held here: an
    # extractor built without the reader opens no likers at all.
    import ast
    from pathlib import Path

    core = Path(__file__).resolve().parents[4]
    missing = []
    for folder in ("taktik", "bridges"):
        for path in (core / folder).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
                if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "InstagramUIExtractors"
                        and "framed_post" not in {keyword.arg for keyword in node.keywords}):
                    missing.append(f"{path.relative_to(core)}:{node.lineno}")
    assert missing == [], f"extractors built without the framed post's reader: {missing}"
