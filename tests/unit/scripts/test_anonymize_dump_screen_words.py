"""The anonymizer learns the words of the screens, and the forms a capture writes them in
(decision D14 of 2026-09-27).

Every fixture of the second lot of real captures needed words put back by hand: app labels the
selectors do not hold ("Trié par Par défaut", "Appuyez deux fois pour lire ou mettre en pause"), a
possessive ("<pseudo>'s story"), a count glued to its label ("295followers"), a resource reference
(`@2131974114`); and a handle made of letters and a long digit run lost its digits only
("marie123456" came out "marie000000"). The words a reviewed fixture keeps are now learned, and the
forms are read.

The values below are single attribute values, the unit the anonymizer works on, not screens.
"""

import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE / "scripts" / "lab"))

import anonymize_dump  # noqa: E402


def _value(text: str) -> str:
    return anonymize_dump.Anonymizer().value(text)


def test_a_handle_of_letters_and_digits_goes_whole():
    assert _value("marie123456") == "user_1"


def test_a_long_digit_run_alone_is_zeroed():
    assert _value("Code 12345678").endswith("00000000")


def test_the_words_a_reviewed_fixture_keeps_are_learned():
    assert _value("Trié par Par défaut") == "Trié par Par défaut"
    assert _value("Reel de karine.v. Appuyez deux fois pour lire ou mettre en pause.") == (
        "Reel de user_1. Appuyez deux fois pour lire ou mettre en pause.")


def test_a_possessive_keeps_its_mark():
    assert _value("karine.v's story, 1 of 3, Unseen.") == "user_1's story, 1 of 3, Unseen."


def test_a_count_glued_to_its_label_stays():
    assert _value("295followers") == "295followers"


def test_a_resource_reference_stays():
    assert _value("@2131974114") == "@2131974114"


def test_the_placeholders_are_not_learned():
    labels, pairs = anonymize_dump.vocabulary()

    placeholder = anonymize_dump.PLACEHOLDER.fullmatch
    assert not any(placeholder(word) for word in labels)
    assert not any(placeholder(word) for pair in pairs for word in pair)
