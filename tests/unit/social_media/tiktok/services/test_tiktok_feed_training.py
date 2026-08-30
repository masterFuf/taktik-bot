"""Ce qu'un passage d'entraînement décide d'une vidéo.

La décision est volontairement séparée de l'écran : c'est la partie qui mérite d'être testée
exhaustivement, et elle n'a besoin d'aucun téléphone — seulement des trois choses que l'écran
vidéo donne déjà (légende, son, nom d'affichage de l'auteur).

Le repli est le même que celui de la clé de post, pour la même raison : ce qui sort d'un écran ne
revient pas identique. Le dump transforme un emoji en deux points, une légende porte des
apostrophes courbes, et un hashtag s'écrit `#Fitness` aussi souvent que `fitness`.
"""

import pytest

from taktik.core.social_media.tiktok.services.feed.training import (
    matches_niche,
    normalise_keywords,
    training_decision,
)


# --- ce qui compte comme « dans la niche » --------------------------------------------------------


@pytest.mark.parametrize("caption", [
    "Ma séance du matin #fitness",
    "FITNESS motivation",
    "#Fitness 🔥",
    "fitness.",
    "Programme  fitness  du jour",
])
def test_the_spellings_a_caption_actually_uses(caption):
    """Casse, accents, ponctuation, hashtag, emoji : une même niche s'écrit de dix façons."""
    assert matches_niche([caption], ["fitness"]) is True


def test_an_accented_keyword_matches_an_unaccented_caption_and_the_reverse():
    assert matches_niche(["Ma seance de musculation"], ["musculation"]) is True
    assert matches_niche(["Ma séance de musculation"], ["musculation"]) is True


def test_the_sound_and_the_author_count_as_much_as_the_caption():
    """Une vidéo sans légende n'est pas une vidéo sans sujet : le son la trahit souvent."""
    assert matches_niche([None, "Son : Fitness Motivation par DJ", None], ["fitness"]) is True
    assert matches_niche(["", "", "coach_fitness_paris"], ["fitness"]) is True


def test_a_keyword_matches_inside_a_longer_word():
    """Un opérateur qui tape une niche nomme un sujet, pas un jeton."""
    assert matches_niche(["Ma séance de musculation"], ["muscu"]) is True


def test_an_unrelated_video_does_not_match():
    assert matches_niche(["Recette de gâteau au chocolat"], ["fitness"]) is False


# --- ce qu'on refuse de deviner --------------------------------------------------------------------


def test_without_keywords_nothing_is_in_the_niche():
    """Le sens sûr, et il vaut d'être explicite : sans niche déclarée, tout serait « dans la
    niche » et une session entière enverrait des signaux positifs sur rien de précis."""
    assert matches_niche(["n'importe quoi"], []) is False
    assert matches_niche(["n'importe quoi"], None) is False


def test_a_video_with_nothing_readable_does_not_match():
    assert matches_niche([None, "", None], ["fitness"]) is False


def test_keywords_are_shown_as_the_matcher_will_use_them():
    """Un filtre qui réécrit son entrée en silence est un filtre que personne ne peut déboguer."""
    assert normalise_keywords(["#Fitness 🔥", "  Muscu  ", "", "fitness"]) == ["fitness", "muscu"]


# --- la décision ------------------------------------------------------------------------------------


def test_an_in_niche_video_is_watched():
    assert training_decision(["#fitness du jour"], ["fitness"]) == "watch"


def test_an_off_niche_video_is_rejected_by_default():
    """« Pas intéressé » est le seul signal que TikTok traite comme une déclaration."""
    assert training_decision(["Recette de gâteau"], ["fitness"]) == "reject"


def test_rejection_can_be_switched_off():
    """Le rejet apparaît dans l'historique « pas intéressé » du compte : sur un compte client,
    ce n'est pas anodin, et un passage doit pouvoir se contenter du signal faible."""
    assert training_decision(["Recette"], ["fitness"], reject_off_niche=False) == "skip"


def test_watching_wins_over_rejecting_when_both_could_apply():
    """Une vidéo dans la niche n'est jamais rejetée, quel que soit le réglage."""
    assert training_decision(["#fitness"], ["fitness"], reject_off_niche=True) == "watch"
