"""`scroll.controlled_step` measures how far the content moved, from anchors it can tell apart.

The probe reads the labels of the scrolled content before and after one production scroll and
pairs them. It used to pair them by label alone, and a post's labels ("Like", "Comment", "More
actions for this post", the author's name) come back with every post: after a scroll of about one
post, the label of the next post was taken for the one that left, and a forward scroll was
measured as a move backwards (-373 px on the feed, -618 px on a profile's posts, the two failures of
the Lab auto-test of the 29th). A label pairs only when it shows once before and once after, and a
move against the gesture is set aside, never counted as the content moving back. An element whose
box touches the edge of the scrolling list, before or after, is cut by it: the box is what shows of
it, its centre is not the element's, and it is set aside too (the +887 px left on the feed was a
photo cut by the bottom of the list before the scroll and by its top after it, for about 1330 px of travel).

The screens are the probe's own readings from that auto-test (Instagram 410 in English, Pixel 3a,
1080x2220), the screen before and after its gesture, anonymized together (`scripts/anonymize_dump.py`,
one name per person across the pair); the gesture is the only thing that changes the screen.
"""

from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY as INSTAGRAM_ACTIONS
from bridges.compat.diagnostics.actions.instagram import register_actions as register_instagram
from bridges.compat.diagnostics.runtime.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale as instagram_locale

FIXTURES = Path(__file__).resolve().parents[3] / "social_media" / "instagram" / "fixtures"


def _dump(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class _Phone:
    """uiautomator2 as the probe reads it: `xpath()` over the screen of the moment."""

    wait_timeout = 0.2
    info = {"displayWidth": 1080, "displayHeight": 2220}

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": "com.instagram.android", "activity": "com.instagram.mainactivity.InstagramMainActivity"}

    def window_size(self):
        return (1080, 2220)


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    register_instagram()
    instagram_locale("en")
    yield
    instagram_locale(None)


def _probe(scene):
    """Runs the Lab action; its production scroll turns the screen into the capture after it."""
    phone = _Phone(_dump(f"{scene}_before.xml"))
    bundle = build_instagram_action_bundle(create_instagram_device_facade(phone))
    gestures = []

    def scroll(direction, distance_ratio):
        gestures.append((direction, distance_ratio))
        phone.xml = _dump(f"{scene}_after.xml")

    bundle.device.human_scroll = scroll
    result = INSTAGRAM_ACTIONS["scroll.controlled_step"](bundle, {"distance_ratio": "0.62"})
    assert gestures == [("down", 0.62)]
    return result


def test_on_the_feed_the_header_of_the_post_that_left_is_not_taken_for_the_next_one():
    # Before: the header of a suggested post and the top of its photo. After: the photo, then the
    # header of the next post, whose "More actions" button and author's name (named again in the
    # caption) are the only ones on screen, as the first post's were before.
    result = _probe("ig410_en_controlled_scroll_feed")
    details = result["details"]

    assert details["contrary_shifts_px"] == [-523, -373]
    assert details["shifts_px"] == []
    assert "measured_px" not in details
    assert result["success"] is False and result["message"].startswith("non concluant: 0 ancre")


def test_a_photo_cut_by_the_edge_of_the_list_is_not_an_anchor():
    # The suggested photo runs off the bottom of the list before the scroll and off its top after
    # it: what the dump gives is the visible part, whose centre moved 887 px, not the photo.
    result = _probe("ig410_en_controlled_scroll_feed")
    details = result["details"]

    assert details["edge_cut_shifts_px"] == [887]
    assert "1 coupee(s) par le bord" in result["message"]


def test_on_a_profiles_posts_the_row_of_the_next_post_is_not_taken_for_the_one_that_left():
    result = _probe("ig410_en_controlled_scroll_profile_posts")
    details = result["details"]

    # The button row of the video that left sits under the top of the list, cut to a few pixels:
    # cut by the edge, like the "Turn sound on" button cut by the bottom before the scroll.
    assert details["contrary_shifts_px"] == [-707, -707]
    assert details["edge_cut_shifts_px"] == [-618, -618, -618, 1344]
    assert details["shifts_px"] == []
    assert "measured_px" not in details
    assert result["success"] is False and result["message"].startswith("non concluant: 0 ancre")


def test_a_label_shown_twice_on_a_screen_is_not_paired():
    # After the scroll, the button row of the post that moved up and the row of the next post are
    # both on screen: "Like", "Comment", "Send post" twice each, and the author's name of the post
    # that moved up. Paired by label, their first occurrence gave short moves (219, 369 px) that
    # belong to no element.
    result = _probe("ig410_en_controlled_scroll_feed_two_rows")
    details = result["details"]

    # The photo that leaves by the top of the list (1137 px) is cut by it: two anchors are left,
    # fewer than the three the probe needs.
    assert details["shifts_px"] == [1344, 1344]
    assert details["edge_cut_shifts_px"] == [1137]
    assert details["contrary_shifts_px"] == []
    assert result["success"] is False and result["message"].startswith("non concluant: 2 ancre")
