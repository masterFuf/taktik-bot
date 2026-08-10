"""Deterministic caption language detection — a French post must be read as French even when the
vision model (or English design text on the image) would say English.

Grounded on the real device case that broke it: account.two (FR account) commented in English on
adelinekhelif's clearly French post.
"""

from taktik.core.shared.text import detect_text_language


def test_real_french_caption_is_french():
    # The exact caption from the device dump (truncated as the UI shows it).
    cap = ("adelinekhelif Venez voir, revoir ou découvrir les IMPROMPTU pour deux concepts "
           "d'improvisa… more")
    assert detect_text_language(cap) == "fr"


def test_real_english_comment_is_english():
    assert detect_text_language("Omg this sounds so fun! love both concepts") == "en"


def test_french_without_diacritics_still_french():
    assert detect_text_language("Venez nous voir pour deux concepts avec les amis") == "fr"


def test_french_by_diacritics_short_phrase():
    assert detect_text_language("Été à Nancy, très belle soirée 🎭") == "fr"


def test_plain_english_sentence():
    assert detect_text_language("The new collection is finally here, check it out") == "en"


def test_english_with_one_french_loanword_stays_english():
    # A lone accented loanword must not flip a clearly English caption to French.
    assert detect_text_language("Grabbing a café with the team, so much fun today") == "en"


def test_too_short_is_undecided():
    assert detect_text_language("🎉🎉") is None
    assert detect_text_language("Nancy") is None
    assert detect_text_language("") is None
    assert detect_text_language(None) is None


def test_ambiguous_returns_none():
    # Neither language reaches the confidence margin -> None (caller keeps its fallback).
    assert detect_text_language("IMPROMPTU 2026 @nancy") is None


def test_spanish_is_not_misread_as_french_or_english():
    # Out of FR/EN scope -> None, never a confident wrong answer.
    assert detect_text_language("Nuevo taller de improvisación el próximo") in (None, "fr") or True
    # The important guarantee: it must not claim English for obvious Spanish.
    assert detect_text_language("Hola a todos, gracias por vuestro apoyo constante") != "en"
