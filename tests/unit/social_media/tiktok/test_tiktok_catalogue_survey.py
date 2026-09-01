"""Le classement des champs du catalogue, et les deux fois où il s'est trompé.

Ces règles décident ce qu'on va chercher : un champ classé « mort » envoie quelqu'un chasser un
bug, un champ classé « à capturer » envoie quelqu'un prendre un écran. Se tromper de case coûte
donc du travail réel dans la mauvaise direction — et c'est arrivé deux fois cette nuit.

**Première fois** : 52 champs rangés dans « morts », dont 45 attendaient un popup jamais apparu,
une story jamais ouverte, une vidéo déjà aimée. Un popup qui ne s'est pas montré n'est pas un
sélecteur cassé.

**Deuxième fois** : l'audit anglais comparait les champs de profil contre le MENU du profil — une
surcouche — et déclarait faux six champs qui répondent parfaitement sur le profil lui-même.

Les deux se ramènent à la même confusion, et c'est elle que ce fichier verrouille : « je ne l'ai
pas vu » n'est pas « il n'y est pas ».
"""

import pytest

from taktik.core.social_media.tiktok.diagnostics.catalogue_survey import (
    STATE_DEPENDENT_FIELDS,
    DriftVerdict,
    classify_field,
    drift,
    english_suspects,
    surface_of,
    survey,
    survival_rate,
)


# --- la mesure prime sur toute liste ------------------------------------------------------------


def test_a_field_that_answers_is_alive_whatever_the_lists_say():
    """L'ordre est le fond de l'affaire. Aucune liste curée ne doit pouvoir contredire une mesure :
    si le champ a répondu sur un écran réel, il est vivant, point."""
    assert "popup.dismiss_button" in STATE_DEPENDENT_FIELDS

    assert classify_field("popup.dismiss_button", answers_somewhere=True) == "alive"
    assert classify_field("signup.password_field", answers_somewhere=True) == "alive"


def test_a_popup_that_never_appeared_is_not_a_dead_field():
    """La première erreur, en une ligne. `popup` fait partie des surfaces vues — des popups ont bien
    été capturés — donc sans la liste d'états, tous les autres tombaient dans « morts »."""
    assert classify_field("popup.collections_close", answers_somewhere=False) == "state"


def test_a_screen_never_visited_is_a_shopping_list_not_a_bug():
    assert classify_field("signup.otp_field", answers_somewhere=False) == "to_capture"


def test_a_silent_field_on_a_photographed_screen_is_the_only_real_suspect():
    assert classify_field("search.view_all_button", answers_somewhere=False) == "dead"


def test_an_unknown_surface_is_not_quietly_called_dead():
    """Un préfixe absent des deux listes ne doit pas hériter d'un verdict par défaut : le classer
    mort inventerait un bug, le classer à capturer inventerait une capture."""
    assert classify_field("publish_composer.field", answers_somewhere=False) == "unclassified"


@pytest.mark.parametrize("nom,attendu", [
    ("inbox.unread_badge", "inbox"),
    ("publish_text.done_button", "publish_text"),
    ("sansPoint", "sansPoint"),
])
def test_the_surface_is_read_off_the_name(nom, attendu):
    assert surface_of(nom) == attendu


def test_every_field_lands_in_exactly_one_bucket():
    """Un champ compté deux fois gonfle un total et vide un autre ; un champ perdu fait mentir le
    pourcentage affiché en tête de rapport."""
    champs = {
        "inbox.a": True, "popup.collections_close": False,
        "signup.b": False, "search.c": False, "inconnu.d": False,
    }

    resultat = survey(champs)

    assert resultat.total == len(champs)
    tous = resultat.alive + resultat.state + resultat.dead + resultat.to_capture + resultat.unclassified
    assert sorted(tous) == sorted(champs)


# --- la dérive entre deux versions --------------------------------------------------------------


@pytest.mark.parametrize("avant,apres,attendu", [
    (3, 2, "both"),
    (4, 0, "died_in_new"),
    (0, 1, "died_in_old"),
    (0, 0, "silent"),
])
def test_the_drift_verdict_reads_both_versions(avant, apres, attendu):
    assert DriftVerdict("x", avant, apres).verdict == attendu


def test_a_field_silent_on_both_versions_says_nothing_about_the_bump():
    """Le piège de tout le rapport de dérive. Un champ muet des deux côtés est un écran jamais
    capturé, pas une régression — le compter comme mort ferait passer un trou de mesure pour une
    casse d'application."""
    verdicts = drift({"a": 1, "muet": 0}, {"a": 1, "muet": 0})

    assert survival_rate(verdicts) == 100


def test_the_survival_rate_counts_only_what_answered_before():
    verdicts = drift({"a": 1, "b": 1, "c": 1, "d": 1}, {"a": 1, "b": 1, "c": 1, "d": 0})

    assert survival_rate(verdicts) == 75


def test_a_corpus_where_nothing_answered_before_does_not_divide_by_zero():
    assert survival_rate(drift({}, {"a": 1})) == 100


def test_a_field_new_to_the_recent_version_is_not_a_death():
    """Écrit pour 46 et invisible sur 43 : c'est l'inverse d'une dérive, et le taux ne doit pas en
    souffrir."""
    verdicts = drift({"vieux": 1}, {"vieux": 1, "neuf": 2})

    assert survival_rate(verdicts) == 100
    assert [v.verdict for v in verdicts if v.field_name == "neuf"] == ["died_in_old"]


# --- l'audit anglais ------------------------------------------------------------------------------


def test_a_field_answering_in_french_and_silent_in_english_is_a_suspect():
    suspects = english_suspects(
        {"profile.followers_count": True},
        {"profile.followers_count": False},
        families=("profile.",),
    )

    assert suspects == ["profile.followers_count"]


def test_the_comparison_is_scoped_to_the_families_that_live_on_that_screen():
    """La deuxième erreur. Sans le cadrage, un champ `conversation.*` qui répond par accident sur
    une capture de menu ressortait comme une entrée anglaise fausse — six fois, toutes vérifiées
    bonnes sur le bon écran."""
    fr = {"conversation.message_item": True, "logout.profile_menu_button": True}
    en = {"conversation.message_item": False, "logout.profile_menu_button": True}

    assert english_suspects(fr, en, families=("logout.",)) == []
    assert english_suspects(fr, en, families=("conversation.",)) == ["conversation.message_item"]


def test_a_field_silent_in_french_too_is_not_an_english_problem():
    """Il faut que le français réponde pour que le silence anglais veuille dire quelque chose :
    sinon l'écran ne porte simplement pas ce contrôle."""
    assert english_suspects({"profile.x": False}, {"profile.x": False}, ("profile.",)) == []


def test_no_family_means_no_verdict_rather_than_every_field():
    """Un appelant qui oublie de dire quelles familles vivent sur l'écran doit obtenir RIEN, pas
    tout le catalogue — un rapport vide se remarque, un rapport de 300 lignes fausses se croit."""
    assert english_suspects({"a.b": True}, {"a.b": False}, families=()) == []
