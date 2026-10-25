"""`same_shown_name`: the one comparison that picks a row by the name it shows, on every platform.

Instagram picks the inbox row a reply opens, and leaves a row read in a pass, through it; TikTok
picks the conversation, the message request and the new follower it acts on. Each used to keep
a row whose name held the name asked for, or started like it (« bob » opened « bobby »).

The rows' names below are written as the screens give them: TikTok starts every inbox name with
U+200E and wraps a new follower's in U+2068...U+2069, and an XML dump writes two dots for an emoji
the selector API returns whole (`tt4314_en_inbox.xml`, 2026-10-25).
"""

import pytest

from taktik.core.shared.text import clean_shown_text, same_shown_name


class TestSameShownName:
    def test_a_name_that_starts_another_is_another_name(self):
        assert not same_shown_name("bobby", "bob")
        assert not same_shown_name("bob", "bobby")

    def test_a_name_held_by_another_is_another_name(self):
        assert not same_shown_name("Jean Dupont", "Jean")
        assert not same_shown_name("le_bob_officiel", "bob")
        assert not same_shown_name("\u200e1NE demo_fan ft AP", "demo_fan")

    def test_case_and_the_spaces_around_are_put_aside(self):
        assert same_shown_name(" Bob ", "bob")
        assert same_shown_name("Jean Dupont", "jean dupont")
        assert same_shown_name("Jean\u00a0 Dupont", "Jean Dupont")

    @pytest.mark.parametrize("shown", ["\u200elea", "\u200e\u2068lea\u2069", "\u2068lea\u2069\u200f"])
    def test_the_marks_a_row_is_laid_out_with_are_put_aside(self, shown):
        assert same_shown_name(shown, "lea")
        assert not same_shown_name(shown, "le")

    def test_a_name_read_from_a_dump_is_the_name_read_whole(self):
        assert same_shown_name("\u200edemo_fan..", "demo_fan\U0001f98b")
        assert same_shown_name("\u200edemo_fan\U0001f98b", "demo_fan..")
        assert not same_shown_name("\u200edemo_fan..", "demo_fan")

    def test_an_empty_name_is_no_one(self):
        assert not same_shown_name("", "")
        assert not same_shown_name(None, "")
        assert not same_shown_name("\u200e", "")


def test_a_shown_text_is_read_as_a_person_reads_it():
    assert clean_shown_text("\u200e\u2068name_1\u2069") == "name_1"
    assert clean_shown_text("1\u20605\u2060 \u2060j\u2060u\u2060i\u2060n") == "15 juin"
    assert clean_shown_text("20\u00a0h ") == "20 h"
    assert clean_shown_text(None) == ""
