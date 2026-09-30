"""A profile with no post is told from one whose post count merely ends in 0.

Real French profiles of Instagram 410.0.0.53.71 (Pixel 3), anonymized. With posts, the counter's
container says "25,2 Kpublications" in its content-desc; with none, its content-desc is EMPTY and
only the value node says "0". So the French entry (content-desc "0publications") never answers
on a real profile without posts: the neutral entry of `zero_posts_indicators` (the value node
reading "0") is the one that does. The counts ending in 0 are the same real profile with another
count written in its counter, text and content-desc alike (derived).
"""

import pytest
from lxml import etree

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.selectors import locales
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
NO_POST = (FIXTURES / "ig410_fr_profile_follow_back.xml").read_text(encoding="utf-8")
WITH_POSTS = (FIXTURES / "ig410_fr_profile_follow_with_mutuals.xml").read_text(encoding="utf-8")
VALUE_ID = "com.instagram.android:id/profile_header_familiar_post_count_value"


@pytest.fixture(autouse=True)
def french():
    before = locales.active_locale()
    locales.set_active_locale("fr")
    yield
    locales.set_active_locale(before)


def _with_count(value: str) -> str:
    root = etree.fromstring(WITH_POSTS.encode("utf-8"))
    node = next(n for n in root.iter("node") if n.get("resource-id") == VALUE_ID)
    node.set("text", value)
    node.getparent().set("content-desc", f"{value}publications")
    return etree.tostring(root, encoding="unicode")


def _hits(xml, selectors):
    root = parse_ui_dump(xml)
    return [n for sel in selectors for n in root.xpath(sel)]


def test_a_profile_without_posts_is_found():
    assert _hits(NO_POST, PROFILE_SELECTORS.zero_posts_indicators)


def test_a_profile_with_posts_is_not_zero_posts():
    assert _hits(WITH_POSTS, PROFILE_SELECTORS.zero_posts_indicators) == []


@pytest.mark.parametrize("count", ["60", "250", "1 760"])
def test_a_count_ending_in_zero_is_not_zero_posts(count):
    xml = _with_count(count)
    assert _hits(xml, locales.L("profile.zero_posts_indicators")) == []
    assert _hits(xml, PROFILE_SELECTORS.zero_posts_indicators) == []
