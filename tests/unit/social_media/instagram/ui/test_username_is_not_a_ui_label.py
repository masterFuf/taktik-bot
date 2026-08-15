"""A row's action label must never be persisted as a username.

When the username extractor lands on the wrong TextView it reads the action label sitting
next to the handle. "Suivre" and "Follow" are valid handles in SHAPE, so only the word can
tell them apart — the guard is language-dependent by nature.

The guard existed but could not fire in French. It compared against a list typed with the
ASCII apostrophe (`j'aime`) while Instagram renders the TYPOGRAPHIC one (`J’aime`, U+2019),
so the comparison was false every time and the label was stored as an account. No exception,
no log line: a French run simply collected accounts named after buttons.

Both sides now fold through `normalize_ui_label`, and the words live in the locale
catalogues instead of inline in the extractor.
"""

import pytest

from taktik.core.social_media.instagram.ui.labels import is_ui_label
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors


@pytest.fixture
def extractors():
    """No device is touched: only the pure validation path is exercised."""
    return InstagramUIExtractors(device=None)


@pytest.mark.parametrize("label", [
    "J’aime",           # U+2019 — what the phone actually renders
    "J'aime",           # U+0027 — what a catalogue is typed with
    "Je n’aime plus",
    "Suivre",
    "Abonnés",
    "Commentaires",
    "Vues",
    "Follow",
    "Following",
    "Likes",
    "Views",
    "  follow  ",       # padding and case are folded too
    "FOLLOW",
])
def test_an_interface_label_is_never_a_username(label, extractors):
    assert is_ui_label(label) is True
    assert extractors.is_valid_username(label) is False


@pytest.mark.parametrize("handle", [
    "kevin",
    "j_aime",          # contains a label word but is not one
    "likes_paris",     # substring of a label — an exact match must not reject it
    "followers.club",
    "_kevin_",         # leading underscore: a real Instagram handle
    "a.b",
])
def test_a_real_handle_survives_the_guard(handle, extractors):
    assert is_ui_label(handle) is False
    assert extractors.is_valid_username(handle) is True


@pytest.mark.parametrize("value,valid", [
    ("_kevin_", True),    # was rejected by the local copy, which required alphanumeric first
    ("a..b", False),      # was accepted by the local copy; Instagram forbids the sequence
    (".kevin", False),
    ("kevin.", False),
    ("k" * 30, True),
    ("k" * 31, False),
    ("", False),
    (None, False),
])
def test_shape_follows_the_shared_validator(value, valid, extractors):
    """Shape is delegated, so the extractor cannot drift from the rest of the bot."""
    assert extractors.is_valid_username(value) is valid
