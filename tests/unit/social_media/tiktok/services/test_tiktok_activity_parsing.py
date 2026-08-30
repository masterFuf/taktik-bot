"""Lire une ligne de la page Activité de TikTok.

Chaque chaîne ci-dessous a été relevée sur un vrai écran le 2026-08-30, 35 lignes en français et
les 35 mêmes en anglais. Elles sont gardées telles quelles, marques invisibles comprises, parce
que c'est exactement ce qui rend la lecture difficile :

- chaque nom est enveloppé dans des **isolats bidi** `\\u2068…\\u2069` — un cadeau plutôt qu'une
  gêne, puisqu'ils disent où un nom commence et finit là où aucune découpe sur les virgules ne le
  dirait (les noms contiennent des virgules, des « et », et des emoji) ;
- la **date est espacée lettre par lettre** par des liants `\\u2060` : `1⁠5⁠ ⁠j⁠u⁠i⁠n` s'affiche
  « 15 juin ». Lue brute, chaque date est une chaîne différente ;
- les emoji sont mangés par le dump, donc `tristan.cld34..` est un nom et non une donnée abîmée.

Le corpus a servi deux fois : il a révélé un type que je n'avais pas vu (`a aimé 12 publications`,
rapporté en `unknown` plutôt que rangé sous le premier verbe à moitié ressemblant), et il a
attrapé un motif qui contenait un vrai caractère backspace au lieu d'une frontière de mot.
"""

import pytest

from taktik.core.social_media.tiktok.services.notifications.activity import (
    clean_row_text,
    parse_activity_row,
)


# Les lignes réelles, français puis anglais, une par type mesuré.
LIKE_VIDEO_FR = "‎⁨nicolas_vln⁩ ‎a aimé ta vidéo. ‎‭1⁠1⁠ ⁠j⁠u⁠i⁠n⁠‭"
LIKE_VIDEO_EN = "‎⁨nicolas_vln⁩ ‎liked your video. ‎‭1⁠1⁠ ⁠J⁠u⁠n⁠‭"
MANY_FR = "‎⁨BR Rénovation⁩, ⁨#Remaxx#⁩ et 45 autres ‎a aimé ta vidéo. ‎‭2⁠0⁠ ⁠j⁠u⁠i⁠n⁠‭"
MANY_EN = "‎⁨BR Rénovation⁩, ⁨#Remaxx#⁩ and 45 others ‎liked your video. ‎‭2⁠0⁠ ⁠J⁠u⁠n⁠‭"
SAVE_FR = "‎⁨alanrchn29⁩ ‎a enregistré ta vidéo. ‎‭1⁠3⁠ ⁠j⁠u⁠i⁠n⁠‭"
LIKE_COMMENT_FR = "‎⁨Carl Turriff⁩ ‎a aimé ton commentaire. ‎‭1⁠ ⁠j⁠u⁠i⁠l⁠.⁠‭"
PROFILE_VIEW_FR = "‎⁨CarsiBerlinFF⁩, ⁨Dave ....⁩ et ⁨stff19⁩ ‎ont vu ton profil. ‎‭1⁠4⁠ ⁠a⁠o⁠û⁠t⁠‭"
REPOST_FR = "‎⁨JHuiles⁩ ‎a republié ta vidéo. ‎‭1⁠9⁠ ⁠j⁠u⁠i⁠l⁠.⁠‭"
APPROVED_FR = "‎⁨vic............⁩ ‎a approuvé ta demande d'abonnement. ‎‭2⁠0⁠ ⁠h⁠‭"
COMMENT_FR = "‎⁨NOXX⁩ ‎a commenté : Pas du tout, je sais pas d'où sont sortis ces arguments."
LIKED_POSTS_FR = "‎⁨bluey fans⁩ ‎a aimé 12 publications. ‎‭1⁠1⁠ ⁠j⁠u⁠i⁠n⁠‭"
LIKED_POSTS_EN = "‎⁨bluey fans⁩ ‎liked 12 posts. ‎‭1⁠1⁠ ⁠J⁠u⁠n⁠‭"


# --- le type de la ligne ---------------------------------------------------------------------


@pytest.mark.parametrize("row,kind", [
    (LIKE_VIDEO_FR, "like_video"),
    (LIKE_VIDEO_EN, "like_video"),
    (SAVE_FR, "save_video"),
    (LIKE_COMMENT_FR, "like_comment"),
    (PROFILE_VIEW_FR, "profile_view"),
    (REPOST_FR, "repost"),
    (APPROVED_FR, "follow_request_approved"),
    (COMMENT_FR, "comment"),
    (LIKED_POSTS_FR, "like_posts"),
    (LIKED_POSTS_EN, "like_posts"),
])
def test_each_measured_kind_is_recognised(row, kind):
    assert parse_activity_row(row).kind == kind


def test_liking_a_comment_is_not_liking_a_video():
    """« a aimé ton commentaire » contient « a aimé » : l'ordre du vocabulaire est ce qui les
    sépare, et une inversion ferait passer tous les likes de commentaire pour des likes de vidéo."""
    assert parse_activity_row(LIKE_COMMENT_FR).kind == "like_comment"


def test_an_unrecognised_row_says_so_instead_of_guessing():
    """TikTok ajoute des types sans prévenir. Deviner, c'est ranger un type neuf sous le premier
    verbe à moitié ressemblant — c'est ainsi qu'on découvre six mois plus tard qu'on a compté des
    choses qui n'existaient pas."""
    row = parse_activity_row("‎⁨quelquun⁩ ‎a fait quelque chose de neuf. ‎2 j")

    assert row.kind == "unknown"
    assert row.usernames == ["quelquun"]


# --- qui, et combien -------------------------------------------------------------------------


def test_the_isolates_delimit_the_names():
    row = parse_activity_row(MANY_FR)

    assert row.usernames == ["BR Rénovation", "#Remaxx#"]
    assert row.others_count == 45
    assert row.actor_count == 47


def test_the_count_of_others_is_read_in_both_languages():
    assert parse_activity_row(MANY_EN).others_count == 45


def test_three_named_people_are_all_kept():
    row = parse_activity_row(PROFILE_VIEW_FR)

    assert row.usernames == ["CarsiBerlinFF", "Dave ....", "stff19"]
    assert row.others_count == 0


def test_a_name_eaten_by_the_dump_is_still_a_name():
    """`vic............` est un pseudo tout en emoji passé par le dump XML. Le jeter parce qu'il
    ne ressemble à rien reviendrait à perdre la personne."""
    assert parse_activity_row(APPROVED_FR).usernames == ["vic............"]


# --- la date ------------------------------------------------------------------------------------


@pytest.mark.parametrize("row,label", [
    (LIKE_VIDEO_FR, "11 juin"),
    (MANY_FR, "20 juin"),
    (APPROVED_FR, "20 h"),
    (LIKE_VIDEO_EN, "11 Jun"),
])
def test_the_date_is_read_through_its_letter_spacing(row, label):
    """Sans retirer les liants, chaque date est une chaîne unique et illisible."""
    assert parse_activity_row(row).age_label == label


def test_the_date_stays_a_label_and_is_not_parsed():
    """L'écran ne donne pas d'année. En fabriquer une serait inventer ce qu'il n'a jamais dit."""
    assert parse_activity_row(LIKE_VIDEO_FR).age_label == "11 juin"


# --- le contenu ----------------------------------------------------------------------------------


def test_a_comment_row_carries_what_was_written():
    row = parse_activity_row(COMMENT_FR)

    assert row.kind == "comment"
    assert row.comment.startswith("Pas du tout, je sais pas")


def test_a_bulk_like_carries_how_many():
    assert parse_activity_row(LIKED_POSTS_FR).post_count == 12
    assert parse_activity_row(LIKED_POSTS_EN).post_count == 12


# --- ce à quoi on peut répondre ------------------------------------------------------------------


def test_a_profile_view_is_a_signal_and_not_an_invitation():
    """Ces gens n'ont rien fait à quoi répondre. Les traiter comme les autres ferait écrire à des
    passants."""
    assert parse_activity_row(PROFILE_VIEW_FR).is_engaging is False
    assert parse_activity_row(LIKE_VIDEO_FR).is_engaging is True


# --- le nettoyage ---------------------------------------------------------------------------------


def test_the_row_cleans_up_to_what_a_human_reads():
    assert clean_row_text(LIKE_VIDEO_FR) == "nicolas_vln a aimé ta vidéo. 11 juin"


def test_an_empty_row_is_not_a_crash():
    for value in ("", "   ", None):
        row = parse_activity_row(value)
        assert row.kind == "unknown"
        assert row.usernames == []
