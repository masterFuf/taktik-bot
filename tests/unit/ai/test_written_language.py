"""The rule every text written by an AI goes through: is it in a language it was asked for?

The texts (`unit.ai_written_texts`) are shortened rewrites of real outputs the audit of October 2026
found: French comments written where English was asked, French profile summaries carrying
Chinese ideographs.
"""

from __future__ import annotations

import pytest

from taktik.core.ai.written_language import language_outside
from taktik.core.shared.text import letters_of_another_script
from unit.ai_written_texts import FRENCH_SUMMARIES_WITH_IDEOGRAPHS, FRENCH_WHERE_ENGLISH_WAS_ASKED


@pytest.mark.parametrize("comment", FRENCH_WHERE_ENGLISH_WAS_ASKED)
def test_a_french_comment_is_outside_english(comment):
    assert language_outside(comment, ("en",), "comment") == "fr"


@pytest.mark.parametrize("comment", FRENCH_WHERE_ENGLISH_WAS_ASKED)
def test_the_same_comment_is_kept_where_french_was_asked(comment):
    assert language_outside(comment, ("fr",), "comment") is None


@pytest.mark.parametrize("summary", FRENCH_SUMMARIES_WITH_IDEOGRAPHS)
def test_ideographs_in_a_french_text_are_letters_of_another_script(summary):
    written = language_outside(summary, ("fr",), "summary")

    assert written is not None and written.startswith("letters of another script (")


def test_the_letters_found_are_named():
    assert language_outside(FRENCH_SUMMARIES_WITH_IDEOGRAPHS[0], ("fr",), "summary") == (
        "letters of another script (展示)"
    )


def test_a_language_written_in_another_script_is_not_held_to_latin_letters():
    """Arabic is a language an account can declare: its letters are not a drift."""
    assert language_outside("شكرا جزيلا على رسالتك، سأرد عليك قريبا", ("ar",), "DM") is None


def test_a_text_the_detector_cannot_tell_is_kept():
    assert language_outside("trop beau 😍", ("en",), "comment") is None


def test_an_english_comment_is_kept_where_english_was_asked():
    assert language_outside("the soft light on this portrait is beautiful", ("en",), "comment") is None


@pytest.mark.parametrize(
    "text",
    [
        "Été à Nancy, très belle soirée 🎭 #nancy 2026",
        "Merci à Łukasz pour cette soirée à Kraków",
        "Un bol de phở à Hà Nội",
        "ᴘʀᴏᴛʜéꜱɪꜱᴛᴇ ᴏɴɢᴜʟᴀɪʀᴇ",
    ],
)
def test_latin_letters_of_any_language_or_font_are_no_other_script(text):
    assert letters_of_another_script(text) == ""


def test_letters_of_another_script_come_each_once_in_order():
    assert letters_of_another_script("Ce compte présente Вікторia, fleuriste, et ses 展示 展示") == "Віктор展示"
