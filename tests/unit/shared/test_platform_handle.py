"""A pseudo is a handle only as it stands: nothing is cleaned into one.

The forms refused below were all stored as pseudos before the check existed (a button label, a
handle followed by spaces, control characters, a biography squeezed into one word, a TikTok
display name). Every value here is invented.
"""

import pytest

from taktik.core.shared.text import handle_from_screen_text, is_platform_handle


@pytest.mark.parametrize("value", [
    "lina.photo", "a", "x" * 30, "Atelier_Nord", "_marc.studio_", "studio2026",
])
def test_an_instagram_handle_is_accepted(value):
    assert is_platform_handle(value, "instagram") is True


@pytest.mark.parametrize("value", [
    None, "", "Send message", "Envoyer un message", "lina.photo   ", " lina.photo",
    "atelier_vend\x1c\x10e", "M�dia", "café", "@lina.photo", "x" * 31,
    "podcastetcritiquesdédiés", "lina‍photo",
])
def test_anything_else_is_no_instagram_handle(value):
    assert is_platform_handle(value, "instagram") is False


@pytest.mark.parametrize("value, expected", [
    (".lina.b", True),
    ("axel...moi", True),
    ("x" * 24, True),
    ("x", False),
    ("x" * 25, False),
    ("‍إستي ✰", False),
    ("Lina B", False),
])
def test_tiktok_bounds_are_its_own(value, expected):
    assert is_platform_handle(value, "tiktok") is expected


@pytest.mark.parametrize("text, handle", [
    ("@lina.photo", "lina.photo"),
    ("  lina.photo  ", "lina.photo"),
    ("‎lina.photo‏", "lina.photo"),
    ("⁨@lina.photo⁩", "lina.photo"),
])
def test_what_a_screen_puts_around_a_handle_is_removed(text, handle):
    assert handle_from_screen_text(text, "instagram") == handle


@pytest.mark.parametrize("text", [
    None, "", "@", "Send message", "Envoyer un message",
    "Podcast et critiques animé par @lina.photo @marc_studio",
    "Lina ✨ Photo",
])
def test_a_sentence_or_a_name_is_refused_not_cleaned(text):
    assert handle_from_screen_text(text, "instagram") is None


def test_a_tiktok_nickname_is_not_its_handle():
    assert handle_from_screen_text("‍إستي ✰", "tiktok") is None
    assert handle_from_screen_text("@.lina.b", "tiktok") == ".lina.b"
