"""Deterministic caption language detection — a French post must be read as French even when the
vision model (or English design text on the image) would say English.

Grounded on the real device case that broke it: account.two (FR account) commented in English on
adelinekhelif's clearly French post.
"""

import pytest

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


# ── The four other languages ────────────────────────────────────────────────
#
# A caption the detector cannot name takes the "undetected" branch and is commented in the
# account's own language; one it names wrongly as French is commented in French.


@pytest.mark.parametrize(
    "caption, expected",
    [
        ("Nuestra nueva colección ya está disponible, ven a verla a la tienda este sábado", "es"),
        ("Hola a todos, gracias por vuestro apoyo constante", "es"),
        ("Unsere neue Kollektion ist endlich da, schaut am Samstag im Laden vorbei", "de"),
        ("Letzte Woche haben wir mit dem Team einen neuen Kurs für Kinder gestartet", "de"),
        ("Oggi è stata una giornata bellissima con tutti gli amici della scuola", "it"),
        ("A nova coleção já está disponível, venha conhecer na loja neste sábado", "pt"),
        ("Muito obrigada pelo carinho de vocês, foi um dia incrível com a nossa equipa", "pt"),
    ],
)
def test_each_of_the_four_other_languages_is_named(caption, expected):
    assert detect_text_language(caption) == expected


def test_italian_is_no_longer_read_as_french():
    """"la", "un", "il" and the grave accents are French words and letters too: with only French
    and English to choose from, an Italian caption came back French, with confidence — and a
    French account commented in French under it, on Instagram as well, because the image
    guard only speaks when the caption says nothing."""
    assert detect_text_language("Il nostro nuovo menù è arrivato, venite a trovarci con gli amici") == "it"


def test_a_word_cut_at_a_letter_the_reader_does_not_know_is_no_longer_french():
    """The old word pattern stopped at "á": "está" was read as the French "est", "coleção" as
    "coleç" plus "o". A Portuguese caption scored French points from its own broken words."""
    assert detect_text_language("Ela está aqui com a gente, que alegria") == "pt"
    assert detect_text_language("Não está bom, não") == "pt"


def test_german_umlauts_are_no_longer_french_letters():
    """ä, ö and ü sat in the French accent list: a German caption scored 1.5 French points per
    umlaut. German counts the same umlauts, so it lost when a caption had more umlauts than
    German words."""
    assert detect_text_language("Schöne Grüße aus München an alle") == "de"
    assert detect_text_language("Über Zürich, schöne Grüße") == "de"


# ── What must NOT move: French and English keep their verdict ───────────────


@pytest.mark.parametrize(
    "caption, expected",
    [
        # A place name carries a foreign letter, never a foreign word.
        ("Soirée magique à Málaga avec toute la bande", "fr"),
        ("Sunset over Zürich with my love", "en"),
        ("Un week-end à São Paulo, on repart quand ?", "fr"),
        # A shared function word ("la", "de", "que") is not a Spanish word on its own.
        ("La vie est belle quand on est ensemble", "fr"),
        ("Merci à tous pour cette soirée, grazie mille les amis", "fr"),
    ],
)
def test_french_and_english_captions_keep_their_verdict(caption, expected):
    assert detect_text_language(caption) == expected


@pytest.mark.parametrize(
    "caption",
    [
        "Le lien ci-dessous pour réserver",
        "Le lien ci-dessous 👇",
        "Si j'avais su que ce serait si beau",
        "Si tu avais su",
        "Profession de foi",
        "Massage du dos et des épaules",
        "Rendez-vous au 12 ter rue de la Paix",
        "Onde de choc",
        "Hier à Zürich",
        "Tag un ami qui adore la montagne",
    ],
)
def test_a_short_french_caption_is_never_taken_by_a_word_french_also_writes(caption):
    """"su", "ci", "foi", "dos", "ter", "onde", "hier" are French words too. Counted for Spanish,
    Italian, Portuguese or German, a single one of them beat a short French caption that had only
    one or two French words to show."""
    assert detect_text_language(caption) not in {"es", "de", "it", "pt"}


def test_a_foreign_letter_alone_is_not_a_language():
    """A new language needs one of its own words: "Zürich", "Málaga" or "São Paulo" alone are
    names, not German, Spanish or Portuguese prose."""
    assert detect_text_language("Zürich Málaga São Paulo") is None


def test_english_articles_are_not_spanish_words():
    """"a" and "no" are English words before they are Spanish or Portuguese ones: counted for
    those languages too, a short English caption naming Los Angeles came back Spanish."""
    assert detect_text_language("I'm a street musician living in Los Angeles, no days off") == "en"
    assert detect_text_language("I'm a street musician living in Los Angeles") != "es"


def test_a_mixed_caption_stays_with_french_or_english_unless_another_language_clearly_wins():
    """An English caption quoting a German title keeps English: the other language must have one
    and a half times the points of French and English to take the caption from them."""
    caption = (
        'Impressions of my master project "Räume der Tabus". The exhibition took place in a '
        "former factory, and all the photos are by my friends"
    )
    assert detect_text_language(caption) == "en"


def test_a_bilingual_caption_keeps_the_language_we_write_in_when_neither_half_dominates():
    """A German/English caption with as many German words as English ones keeps English, as it
    always did: no language of the four takes a caption from French or English without one and a
    half times their points, and a tie is not a reason to answer None."""
    caption = (
        "Umbau mit Respekt vor der Geschichte, und mit viel Liebe zum Detail. "
        "A renovation with respect for the history of the house and its details"
    )
    assert detect_text_language(caption) == "en"
