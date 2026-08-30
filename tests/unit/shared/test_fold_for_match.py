"""Le repli partagé : ce sur quoi deux lectures d'un même texte se mettront toujours d'accord.

Écrit une seule fois parce qu'il n'arrêtait pas d'être réécrit. Il décide si un post relu est le
même post, si une légende correspond à un mot de niche, et — c'est ce qui l'a fait sortir dans un
module commun — si le nom affiché en tête d'une conversation est bien la personne à qui on voulait
écrire.

Le défaut mesuré sur appareil le 2026-08-30 : l'en-tête affiche `Allocin(gl)és` là où le pseudo est
`allocingles`. Le garde d'envoi comparait les deux littéralement — ni l'un ni l'autre ne se contient
— et refusait donc d'écrire à exactement la bonne personne. Le message n'est jamais parti, et le
Welcome DM tenait ce chemin pour non vérifié depuis.
"""

import pytest

from taktik.core.shared.text import fold_for_match


@pytest.mark.parametrize("shown,handle", [
    ("Allocin(gl)és", "allocingles"),      # le cas qui a bloqué l'envoi
    ("Kéo", "keo"),
    ("  Marvin.Ndiaye  ", "marvinndiaye"),
    ("@allocingles", "allocingles"),
    ("Lea 🔥", "lea"),                     # emoji intact
    ("Lea ..", "lea"),                     # le même, mangé par le dump
])
def test_a_display_name_folds_onto_its_handle(shown, handle):
    assert fold_for_match(shown) == fold_for_match(handle)


def test_two_different_people_do_not_fold_together():
    assert fold_for_match("Allocinés") != fold_for_match("Marvin")


def test_nothing_folds_to_nothing():
    """Une chaîne vide doit rester vide : un garde qui accepte le vide accepte tout."""
    assert fold_for_match("") == ""
    assert fold_for_match(None) == ""
    assert fold_for_match("🔥 ✨ !!!") == ""


def test_the_fold_is_documented_as_unsafe_for_keying():
    """Il replie `keo.2` et `keo2` ensemble. C'est voulu pour RECONNAÎTRE, et c'est exactement
    pourquoi il ne doit pas servir à distinguer deux comptes voisins."""
    assert fold_for_match("keo.2") == fold_for_match("keo2")
