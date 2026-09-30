"""The French locale must classify the labels TikTok actually puts on a French screen.

`profile.stat_label_followers` held only "Abonné", a plausible translation. Measured on three
real profiles across both app versions: TikTok's French UI writes that label in ENGLISH
("Follower" singular, "Followers" plural) while writing "Suivis" and "J'aime" in French. The
result was `followers_count = 0` for every profile read on a French phone -- silently, because
the other two stats came through and two numbers out of three looked right.

These cases are transcribed from real captures, not from a dictionary.
"""

import pytest

from taktik.core.social_media.tiktok.ui.labels import classify_profile_stat_label
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale


@pytest.fixture(autouse=True)
def restore_locale():
    yield
    set_active_locale(None)


# (label as it appears on screen, what it counts) -- taken from:
#   tt_v431pro_profile.xml      43.1.4, own profile      "Suivis" / "Follower" / "J'aime"
#   tt_v466_profile.xml         46.6.3, own profile      "Suivis" / "Followers" / "J'aime"
#   tt_visited_profile_4314.xml 43.1.4, visited profile  "Suivis" / "Followers" / "J'aime"
FRENCH_SCREEN_LABELS = [
    ("Suivis", "following"),
    ("Follower", "followers"),
    ("Followers", "followers"),
    ("J'aime", "likes"),
]


@pytest.mark.parametrize("label,expected", FRENCH_SCREEN_LABELS)
def test_a_french_screen_is_classified_with_the_french_locale_active(label, expected):
    set_active_locale("fr")
    assert classify_profile_stat_label(label) == expected


@pytest.mark.parametrize("label,expected", FRENCH_SCREEN_LABELS)
def test_the_same_labels_survive_without_any_locale_active(label, expected):
    """The union is what runs when detection failed; it must not be stricter than a locale."""
    set_active_locale(None)
    assert classify_profile_stat_label(label) == expected


@pytest.mark.parametrize("label,expected", [
    ("Following", "following"),
    ("Followers", "followers"),
    ("Likes", "likes"),
])
def test_an_english_screen_still_classifies_with_the_english_locale(label, expected):
    set_active_locale("en")
    assert classify_profile_stat_label(label) == expected


@pytest.mark.parametrize("locale,label", [
    ("fr", "Suivis"), ("fr", "Following"), ("en", "Following"), (None, "Suivis"), (None, "Following"),
])
def test_following_is_never_read_as_followers(locale, label):
    """The two words share a stem; testing followers first would count the wrong number.

    Only the pairs a locale can actually meet are listed: an English screen has no reason to
    write "Suivis", and demanding it would pin behaviour nothing depends on.
    """
    set_active_locale(locale)
    assert classify_profile_stat_label(label) == "following"
