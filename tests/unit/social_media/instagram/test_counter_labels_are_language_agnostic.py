"""Reel counters and author: read the VALUE, not the sentence around it.

The element is found by resource-id, which is language-neutral — but its value used to be
read with an English sentence pattern ("Like number is16"). On a French phone, which says
"Nombre de J'aime : 14", every reel therefore reported ZERO likes, and the whole hashtag run
was filtered out as "too few likes" whatever threshold the operator set. Same trap on the
author ("Reel by X" vs "Reel de X"), which silently disabled the 7-day dedup.

The strings below are copied verbatim from real UI dumps (Instagram 410.0.0.53.71, French
phone, hashtag #esthétique, 31/07/2026).
"""

import pytest

from taktik.core.social_media.instagram.ui.extractors import (
    count_from_counter_label,
    username_from_media_label,
)


@pytest.mark.parametrize("label,expected", [
    # --- verbatim from the dumps (fr) ---
    ("Nombre de J’aime : 14. Voir les J’aime", 14),
    ("Nombre de J’aime : 12. Voir les J’aime", 12),
    ("Nombre de J’aime : 56. Voir les J’aime", 56),
    ("Nombre de commentaires : 6. Voir les commentaires", 6),
    # --- the English form that used to be the only one understood ---
    ("Like number is16. View likes", 16),
    ("Comment number is 8. View comments", 8),
])
def test_reads_the_counter_whatever_the_language(label, expected):
    assert count_from_counter_label(label) == expected


@pytest.mark.parametrize("label,expected", [
    ("Nombre de J’aime : 1 234. Voir les J’aime", 1234),   # espace de milliers
    ("Nombre de J’aime : 1 234. Voir", 1234),               # espace insécable
    ("Nombre de J’aime : 12,3 k. Voir les J’aime", 12300),  # suffixe k
    ("Like number is1.2M. View likes", 1200000),
])
def test_reads_thousands_and_suffixes(label, expected):
    assert count_from_counter_label(label) == expected


def test_a_letter_after_the_number_is_not_a_suffix():
    """"12 Kommentare" is twelve comments, not twelve thousand."""
    assert count_from_counter_label("Anzahl der Kommentare: 12 Kommentare") == 12


def test_only_the_first_number_counts():
    """A label mentioning two figures must not concatenate their digits."""
    assert count_from_counter_label("14 J’aime, 2 commentaires") == 14


@pytest.mark.parametrize("label", ["", None, "Voir les J’aime", "Commentaire"])
def test_unreadable_is_none_not_zero(label):
    """Zero likes and "I could not read it" are different facts — one filters the post out."""
    assert count_from_counter_label(label) is None


@pytest.mark.parametrize("label,expected", [
    # --- verbatim from the dumps (fr) ---
    ("Reel de dolce_cocoon. Appuyez deux fois pour lire ou mettre en pause.", "dolce_cocoon"),
    ("Reel de leprestige_coiffure. Appuyez deux fois pour lire ou mettre en pause.", "leprestige_coiffure"),
    ("Reel de adesthetique__. Appuyez deux fois pour lire ou mettre en pause.", "adesthetique__"),
    ("Reel de sourinails_au_salon_daubagne. Appuyez deux fois", "sourinails_au_salon_daubagne"),
    # --- other locales ---
    ("Reel by john_doe. Double-tap to play or pause.", "john_doe"),
    ("Reel von marie.dupont. Zweimal tippen", "marie.dupont"),
])
def test_reads_the_author_whatever_the_language(label, expected):
    assert username_from_media_label(label) == expected


def test_a_dot_inside_a_username_is_not_the_end_of_the_sentence():
    assert username_from_media_label("Reel de marie.dupont. Appuyez deux fois") == "marie.dupont"


@pytest.mark.parametrize("label", ["", None, "Photo", "Reel"])
def test_no_author_when_the_label_says_nothing(label):
    assert username_from_media_label(label) is None
