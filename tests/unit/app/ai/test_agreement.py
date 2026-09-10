"""A determiner is the only thing this may ever change, and only towards the noun's gender.

Four mechanisms were built against the same narrow problem — every hard mistake the cheap
generation model makes is a determiner disagreeing with its noun. Three made things worse and
are gone: an LLM proofreader rewrote correct text, a lower temperature kept the mistakes and
tripled repeated openings, and asking the model itself for a gender broke five correct comments
out of six. All three consulted the source that had written the text.

This one consults a dictionary, and only where a second authority agrees with it. Measured on
1 370 generated comments: 4 corrections, 4 correct, 0 correct texts damaged.
"""

import pytest

from taktik.core.app.ai import agreement


# ── the mistakes the model actually makes ───────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("la combo caramel et lait onctueux c'est un délice",
     "le combo caramel et lait onctueux c'est un délice"),
    ("La combo bière + oignons ça doit être un régal 🍺",
     "Le combo bière + oignons ça doit être un régal 🍺"),
    ("le mood de la néon c'est trop bien 🖤", "le mood du néon c'est trop bien 🖤"),
])
def test_a_disagreeing_determiner_is_corrected(text, expected):
    assert agreement.apply(text, "fr")[0] == expected


def test_a_contracted_determiner_is_corrected_whole():
    """"de la néon" must become "du néon", never "de le néon".

    Without the longest-match rule the `le`/`la` family matches INSIDE "de la" and produces two
    words that are not French. A contracted determiner is replaced entire or not at all.
    """
    fixed, notes = agreement.apply("le mood de la néon", "fr")
    assert fixed == "le mood du néon"
    assert notes == ["de la néon -> du néon"]


def test_the_writers_capitalisation_survives():
    """Half our comments open lowercase on purpose, and the determiner is often the first word."""
    assert agreement.apply("La combo est top", "fr")[0] == "Le combo est top"
    assert agreement.apply("la combo est top", "fr")[0] == "le combo est top"


# ── what must never be touched ──────────────────────────────────────────────────────────────
def test_correct_text_comes_back_byte_identical():
    """The load-bearing property, and the one the three earlier mechanisms failed.

    Each of these was BROKEN by a previous version: "ce dont" became "cette dont", "Ce coin"
    became "Cette coin", "du live" became "de la live", "la box" became "le box".
    """
    for text in (
        "c'est exactement ce dont j'ai besoin",
        "Ce coin doit être sacrément douillet",
        "l'énergie du live et l'ambiance de la soirée",
        "la box a l'air vraiment complète et gourmande",
        "Le face à face est super fluide",
        "l'ambiance est apaisante avec cette lumière dorée 🌅",
    ):
        assert agreement.apply(text, "fr") == (text, [])


def test_an_elided_determiner_is_never_expanded():
    """"l'ambiance" carries NO gender and is already right; rewriting it would create a mistake."""
    text = "l'ambiance et l'angle sont dingues"
    assert agreement.apply(text, "fr") == (text, [])


def test_a_word_the_lexicon_does_not_know_is_left_alone():
    """An unresolved gender is not a mistake. Skipping costs a correction we never made;
    guessing costs one we introduced."""
    text = "le truc et la bidule sont incroyables"
    assert agreement.apply(text, "fr") == (text, [])


def test_a_noun_with_two_genders_never_ships():
    """`tour`, `mode`, `manche`, `page` change meaning with their gender, and Lexique states that
    ambiguity itself by leaving the field empty. Correcting them would fabricate a mistake."""
    words = agreement.lexicon("fr")
    for ambiguous in ("tour", "mode", "manche", "page", "livre", "poste", "voile", "somme"):
        assert ambiguous not in words, ambiguous


def test_words_that_are_not_only_nouns_never_ship():
    """This is what removes `dont`, `super`, `magnifique` and the ordinals — from the dictionary's
    own part-of-speech data, with no hand-kept list to maintain."""
    words = agreement.lexicon("fr")
    for other in ("dont", "super", "magnifique", "deuxième", "premier", "belle", "grand"):
        assert other not in words, other


def test_the_words_modern_usage_disputes_never_ship():
    """`box`, `typo` and `french` carry a gender in Lexique that today's usage contradicts, and
    correcting them fabricated a mistake. The second authority is what removes them."""
    words = agreement.lexicon("fr")
    for disputed in ("box", "typo", "french", "media", "colo"):
        assert disputed not in words, disputed


# ── the other languages ─────────────────────────────────────────────────────────────────────
def test_a_language_without_grammatical_gender_is_untouched():
    """The app is international. English, Chinese, Japanese and Turkish have no determiner
    gender at all — nothing to check, not a gap to fill later."""
    for language in ("en", "zh", "ja", "ko", "tr", "fi", "hu", "id"):
        text = "the vibe is unreal"
        assert agreement.apply(text, language) == (text, [])
        assert agreement.profile_for(language).checks is False


def test_a_gendered_language_without_a_lexicon_is_refused_with_a_reason():
    """Spanish, Portuguese, Italian and Dutch have the problem and no validated lexicon yet.

    Shipping the mechanism for them without one would read as coverage it does not have — the
    failure this whole module is shaped against.
    """
    for language in ("es", "pt", "it", "nl", "de", "ar"):
        profile = agreement.profile_for(language)
        assert profile.checks is False
        assert profile.unsupported_reason
        assert agreement.apply("la problema", language)[1] == []

    reasons = agreement.unchecked_languages()
    assert "case" in reasons["de"]
    assert set(reasons) >= {"de", "ar", "en", "zh", "es", "pt"}


def test_an_unknown_language_is_not_an_error():
    """A language nobody has looked at reads as None — a different answer from "declined"."""
    assert agreement.profile_for("sw") is None
    assert agreement.apply("kitu fulani", "sw") == ("kitu fulani", [])
    assert agreement.apply("n'importe quoi", "") == ("n'importe quoi", [])


def test_the_lexicon_carries_its_attribution():
    """Lexique 3.83 is CC BY-SA 4.0: the file is a derivative and must say so, in the repository
    that ships it — which is public."""
    from pathlib import Path
    text = (Path(agreement.__file__).with_name("data") / "agreement_fr.tsv").read_text(
        encoding="utf-8")
    assert "Lexique 3.83" in text and "CC BY-SA 4.0" in text
    assert "lexique.org" in text
