"""The XML dump turns emoji into dots — detect it, and re-read outside XML.

UIAutomator serialises the hierarchy through AOSP's ``AccessibilityNodeInfoDumper``,
whose ``stripInvalidXMLChars`` walks the string one UTF-16 code unit at a time and
replaces anything XML-illegal with ``"."``. Surrogates are illegal, so an astral emoji
(a surrogate PAIR) becomes exactly two dots while a BMP symbol survives untouched.
"""

from taktik.core.social_media.instagram.actions.atomic.detection.profile_extraction import (
    _text_lost_emoji,
)


def test_astral_emoji_becomes_an_even_dot_run():
    # "🎬🎥 Film" dumped by UIAutomator: two emoji -> four dots.
    assert _text_lost_emoji(".... Film")


def test_dot_followed_by_variation_selector_is_a_mangled_emoji():
    # A variation selector only ever trails an emoji, so a dot before one is a leftover.
    assert _text_lost_emoji("..️Language")
    assert _text_lost_emoji("..︎Dm for bookings")


def test_bmp_symbols_survive_and_do_not_trigger():
    # One code unit each: the dumper leaves them alone, nothing to recover.
    assert not _text_lost_emoji("Dm for bookings ❤︎")
    assert not _text_lost_emoji("☁️ Certifiee @studio")
    assert not _text_lost_emoji("Soft glow • minimal care")


def test_plain_text_does_not_trigger():
    assert not _text_lost_emoji("Actress | Singer | Writer")
    assert not _text_lost_emoji("")
    assert not _text_lost_emoji(None)


def test_real_ellipsis_triggers_and_that_is_accepted():
    # A false positive costs one extra ~60ms read and nothing else; measured at ~1.2% of
    # bios on the real base. Being wrong here is cheaper than missing a mangled emoji.
    assert _text_lost_emoji("Photographer... and traveler")
