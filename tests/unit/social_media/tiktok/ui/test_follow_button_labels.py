"""The label that proves a TikTok unfollow: a row button that offers to follow again.

Compared by equality: "Follow" is a prefix of "Following", so a containment test would read
"we follow them" as "we do not", and count a tap that did nothing as an unfollow.
"""

import pytest

from taktik.core.social_media.tiktok.ui.labels import classify_follow_button, is_follow_button
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale


@pytest.fixture(params=["fr", "en", None])
def locale(request):
    set_active_locale(request.param)
    yield request.param
    set_active_locale(None)


def test_following_is_never_read_as_follow(locale):
    assert is_follow_button("Following") is False
    assert is_follow_button("Suivis") is False


@pytest.mark.parametrize("lang, label, state", [
    ("fr", "Suivre", "follow"),
    ("fr", "Suivre en retour", "follow"),
    ("fr", "Suivis", "following"),
    ("fr", "Ami(e)s", "friends"),
    ("en", "Follow", "follow"),
    ("en", "Follow back", "follow"),
    ("en", "Following", "following"),
    ("en", "Friends", "friends"),
])
def test_each_row_state_is_read_in_its_language(lang, label, state):
    set_active_locale(lang)
    try:
        assert classify_follow_button(label) == state
    finally:
        set_active_locale(None)


def test_an_unknown_label_is_no_state():
    assert classify_follow_button("") is None
    assert classify_follow_button("Message") is None
