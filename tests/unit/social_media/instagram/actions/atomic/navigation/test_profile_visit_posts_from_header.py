"""The profile visit takes a profile's visible posts from its header's posts count.

The visit read the posts count in the header, then counted the thumbnails on screen for the
filters (`count_visible_posts`). On a profile without posts that count still found the avatar and
the header's other images (3 on the capture below), so `visible_posts_count` was never 0 and the
filters' "No visible posts" penalty never applied. The count also showed the posts grid first: a
tap on a profile left on its Reels. A public profile shows every post it counts, so the header's
count is the visible posts (Kevin's decision, 2026-09-28); a header that cannot be read is not a
profile without posts.

The screens are real dumps, anonymised (Instagram 410.0.0.53.71): a public French profile we
follow, without posts, and a private one (Pixel 3), a public English profile on its grid and the
same profile left on its Reels (Pixel 3a). The last test's screen is DERIVED from the first French
one: its posts counter is removed, the read a header that could not be read gets. They are replayed behind the facade and
the clone-aware proxy by the phone of `test_profile_grid_shown_before_read.py`, which lists every
tap.
"""

from lxml import etree

from taktik.core.shared.filtering import apply_comprehensive_filter
from taktik.core.social_media.instagram.services.profile.extraction import (
    ProfileExtraction,
)

from test_profile_grid_shown_before_read import VISITED_EN, _Phone, _capture, _clock, _facade  # noqa: F401 (fixture)

WITHOUT_POSTS_FR = _capture("ig410_fr_profile_following.xml")
POSTS_COUNTER_ID = "com.instagram.android:id/profile_header_post_count_front_familiar"


def _visit(phone):
    """The production visit of the profile on screen, as the automation calls it."""
    return ProfileExtraction(_facade(phone)).get_complete_profile_info(
        username="visited", navigate_if_needed=False, emit_ipc=False, save_to_db=False,
    )


def _without_posts_counter(xml):
    root = etree.fromstring(xml.encode("utf-8"))
    for node in root.xpath(f'//node[@resource-id="{POSTS_COUNTER_ID}"]'):
        node.getparent().remove(node)
    return etree.tostring(root, encoding="unicode")


def test_a_public_profile_without_posts_has_no_visible_posts():
    info = _visit(_Phone({"profile": WITHOUT_POSTS_FR}, "profile"))

    assert info["posts_count"] == 0
    assert info["visible_posts_count"] == 0
    assert info["has_posts"] is False
    assert "No visible posts" in apply_comprehensive_filter(info, {})["reasons"]


def test_the_visible_posts_of_a_profile_are_its_header_count():
    info = _visit(_Phone(VISITED_EN, "Grid view"))

    assert info["posts_count"] == 4934
    assert info["visible_posts_count"] == 4934
    assert info["has_posts"] is True


def test_the_visit_taps_nothing_to_count_the_posts():
    # A visited profile left on its Reels: counting the thumbnails tapped its grid tab first.
    phone = _Phone(VISITED_EN, "Reels")

    info = _visit(phone)

    assert phone.taps == []
    assert info["visible_posts_count"] == 4934


def test_a_private_profile_is_not_penalised_for_the_posts_it_hides():
    # "Ce compte est privé", 0 publications in its header (Pixel 3, 410, French).
    info = _visit(_Phone({"profile": _capture("ig410_fr_profile_follow_back.xml")}, "profile"))

    assert info["is_private"] is True
    assert info["visible_posts_count"] == 0
    assert "No visible posts" not in apply_comprehensive_filter(info, {"allow_private": True})["reasons"]


def test_a_header_that_cannot_be_read_is_not_a_profile_without_posts():
    info = _visit(_Phone({"profile": _without_posts_counter(WITHOUT_POSTS_FR)}, "profile"))

    assert info["visible_posts_count"] is None
    assert info["has_posts"] is None
    verdict = apply_comprehensive_filter(info, {})
    assert "No visible posts" not in verdict["reasons"]
    assert verdict["filter_details"]["behavior_filters"]["content_visibility"] == "unknown"
