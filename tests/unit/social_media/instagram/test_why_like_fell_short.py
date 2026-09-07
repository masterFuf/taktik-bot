"""Le motif affiche quand un like n'atteint pas son seuil doit etre le VRAI.

Le message disait « (not enough posts) » quelle que soit la cause. Sur @silvia_gi_sen le 06/09 il
l'a dit d'un profil qui a **1004 publications** : la grille ne s'etait pas ouverte, parce qu'un tap
d'avancement de story avait ouvert une publication par-dessus le profil. Un operateur qui lit ce
journal conclut « ce compte n'a pas assez de contenu » et cherche au mauvais endroit.

L'etape d'echec remontait deja jusqu'a l'appelant ; elle n'etait pas lue.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (  # noqa: E402
    why_like_fell_short,
)


def test_un_echec_technique_est_nomme_avec_son_etape():
    motif = why_like_fell_short(
        technical_failure=True, failure_stage='post_entry', posts_count=1004, min_likes=1,
    )

    assert 'grid could not be opened' in motif
    assert 'post_entry' in motif
    assert 'post(s)' not in motif


def test_un_echec_technique_sans_etape_reste_honnete():
    motif = why_like_fell_short(
        technical_failure=True, failure_stage=None, posts_count=None, min_likes=1,
    )

    assert 'unknown stage' in motif


def test_un_echec_technique_prime_sur_un_compte_faible():
    """L'echec explique tout le reste : un compte de publications lu pendant l'echec ne vaut rien."""
    motif = why_like_fell_short(
        technical_failure=True, failure_stage='post_entry', posts_count=0, min_likes=1,
    )

    assert 'grid could not be opened' in motif


def test_un_profil_reellement_trop_court_est_nomme_ainsi():
    motif = why_like_fell_short(
        technical_failure=False, failure_stage=None, posts_count=1, min_likes=3,
    )

    assert motif == 'the profile only has 1 post(s)'


def test_un_nombre_de_publications_inconnu_n_accuse_personne():
    """`None` veut dire « on ne sait pas », jamais « zero » — la regle deja tenue par le plan."""
    motif = why_like_fell_short(
        technical_failure=False, failure_stage=None, posts_count=None, min_likes=1,
    )

    assert motif == 'the likes did not land'


def test_un_profil_fourni_mais_des_likes_qui_ratent():
    motif = why_like_fell_short(
        technical_failure=False, failure_stage=None, posts_count=400, min_likes=2,
    )

    assert motif == 'the likes did not land'


@pytest.mark.parametrize('valeur', ['', 'beaucoup', object()])
def test_un_compte_illisible_ne_fait_jamais_lever(valeur):
    assert why_like_fell_short(
        technical_failure=False, failure_stage=None, posts_count=valeur, min_likes=1,
    ) == 'the likes did not land'
