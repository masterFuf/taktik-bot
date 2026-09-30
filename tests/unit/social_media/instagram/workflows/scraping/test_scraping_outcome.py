"""Le verdict d'un scraping porte sur la surface atteinte, jamais sur le nombre collecté.

Le piège que ces tests gardent fermé : `success = total_scraped > 0` ferait échouer des runs
parfaitement sains. Une cible dont tous les profils sont déjà en base rend zéro nouveau profil et
a très bien fonctionné.
"""

import pytest

from taktik.core.social_media.instagram.workflows.scraping.outcome import (
    COMPLETED,
    NOTHING_TO_SCRAPE,
    TARGET_NEVER_REACHED,
    scraping_outcome,
)


def test_surface_atteinte_et_recolte_pleine():
    assert scraping_outcome(
        sources_reached=2, sources_skipped=0, sources_failed=0, total_scraped=140
    ) == {"success": True, "completion_reason": COMPLETED}


def test_surface_atteinte_et_recolte_vide_reste_un_succes():
    # La liste s'est ouverte et n'a rien donné de neuf : le bot a fait son travail.
    assert scraping_outcome(
        sources_reached=1, sources_skipped=0, sources_failed=0, total_scraped=0
    ) == {"success": True, "completion_reason": NOTHING_TO_SCRAPE}


def test_surface_jamais_atteinte_est_un_echec():
    # Le cas du constat : la grille du hashtag ne s'est jamais ouverte, et le run se déclarait
    # réussi avec zéro profil.
    assert scraping_outcome(
        sources_reached=0, sources_skipped=0, sources_failed=3, total_scraped=0
    ) == {"success": False, "completion_reason": TARGET_NEVER_REACHED}


def test_une_seule_source_atteinte_suffit_a_reussir():
    # Deux cibles sur trois injoignables, mais une a donné : le run a produit quelque chose.
    assert scraping_outcome(
        sources_reached=1, sources_skipped=0, sources_failed=2, total_scraped=40
    ) == {"success": True, "completion_reason": COMPLETED}


def test_tout_ecarte_pour_une_raison_connue():
    # Trois cibles, trois comptes privés : rien n'a échoué, il n'y avait rien à prendre.
    assert scraping_outcome(
        sources_reached=0, sources_skipped=3, sources_failed=0, total_scraped=0
    ) == {"success": True, "completion_reason": NOTHING_TO_SCRAPE}


def test_un_prive_et_un_injoignable_reste_un_echec():
    # L'échec de navigation ne doit pas être absous par le compte privé qui le précédait.
    assert scraping_outcome(
        sources_reached=0, sources_skipped=1, sources_failed=1, total_scraped=0
    ) == {"success": False, "completion_reason": TARGET_NEVER_REACHED}


def test_boucle_jamais_entree():
    # Temps de session écoulé ou plafond déjà atteint avant le premier tour : rien n'a échoué.
    assert scraping_outcome(
        sources_reached=0, sources_skipped=0, sources_failed=0, total_scraped=0
    ) == {"success": True, "completion_reason": NOTHING_TO_SCRAPE}


@pytest.mark.parametrize("collectes", [0, 1, 500])
def test_le_nombre_collecte_ne_decide_jamais_du_succes(collectes):
    # Seule la raison change avec le nombre ; le succès, lui, suit la surface.
    verdict = scraping_outcome(
        sources_reached=1, sources_skipped=0, sources_failed=0, total_scraped=collectes
    )
    assert verdict["success"] is True
