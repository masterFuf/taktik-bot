"""A re-read that comes back truncated is a FAILED read, not a better one.

The XML dump loses emoji to dots but keeps accents. The JSON-RPC re-read meant to rescue those
emoji can hand back a UTF-16 string truncated to its low bytes, which loses the accents TOO. On the
2026-08-27 run, of 49 bios written that day not one came back with an intact astral emoji: 21 came
back truncated, 18 kept the dots. Accepting the truncated one makes the bio worse than it was.

The shapes below are verbatim from the production base, and each was reproduced exactly with
`s.encode('utf-16-le')[::2].decode('utf-8', 'replace')`.
"""

from taktik.core.shared.text import text_is_truncated_utf16, text_lost_emoji


class TestTruncatedUtf16:
    def test_accent_eaten_by_truncation(self):
        # "Cadeaux Personnalisés" as stored for @by_salma_ypmt.
        assert text_is_truncated_utf16('Cadeaux Personnalis�s') is True

    def test_emoji_low_byte_survives_as_punctuation(self):
        # A pin emoji: 0x3D '=' is the low byte of \ud83d, the second surrogate is replaced.
        assert text_is_truncated_utf16('Chateaubriant 44  =�') is True

    def test_reproduces_from_a_real_string(self):
        original = '\U0001F4CD Metz'
        truncated = original.encode('utf-16-le')[::2].decode('utf-8', 'replace')
        assert truncated.startswith('=�')
        assert text_is_truncated_utf16(truncated) is True

    def test_dotted_text_is_not_truncated(self):
        # The dump's own scar: emoji gone, accents intact. This one is worth keeping.
        assert text_is_truncated_utf16('Photographe .. Metz') is False

    def test_clean_text_with_emoji(self):
        assert text_is_truncated_utf16('Photographe \U0001F4CD Metz') is False

    def test_clean_text_with_accents(self):
        assert text_is_truncated_utf16('Gâteaux personnalisés à Metz') is False

    def test_empty_and_none(self):
        assert text_is_truncated_utf16('') is False
        assert text_is_truncated_utf16(None) is False


class TestTheTwoScarsAreDistinct:
    """The two detectors must not answer for each other — they drive opposite decisions."""

    def test_dotted_is_only_dotted(self):
        dotted = 'Photographe .. Metz'
        assert text_lost_emoji(dotted) is True
        assert text_is_truncated_utf16(dotted) is False

    def test_truncated_is_only_truncated(self):
        truncated = 'Cadeaux Personnalis�s'
        assert text_is_truncated_utf16(truncated) is True
        assert text_lost_emoji(truncated) is False
