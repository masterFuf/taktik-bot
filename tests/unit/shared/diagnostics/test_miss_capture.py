"""La politique de capture : quand on écrit, ce qu'on note, et ce qu'on ne perturbe pas.

Le module existait et n'était atteint que par `_wait_for_element`. Un second appelant est arrivé
— la grille de profil introuvable, 87 fois sur les runs du 04 au 06/09 — et il n'a pas les mêmes
besoins : il veut le FICHIER (c'est l'écran qu'on vient chercher, pas une empreinte de plus) et il
ne doit pas perturber la série de blocage, qui compte le MÊME sélecteur qui échoue d'affilée.

Les propriétés tenues ici sont celles dont la perte se verrait des semaines plus tard, dans un
dossier de captures qu'on ouvrirait une par une, ou par une garde de blocage qui ne se déclenche
plus parce qu'un autre appelant remet son compteur à 1.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from taktik.core.shared.diagnostics import miss_capture  # noqa: E402
from taktik.core.shared.telemetry import (  # noqa: E402
    clear_telemetry_sink,
    configure_telemetry_sink,
)


@pytest.fixture(autouse=True)
def repartir_a_zero():
    miss_capture.reinitialiser()
    yield
    miss_capture.reinitialiser()
    clear_telemetry_sink()


@pytest.fixture
def captures(monkeypatch):
    """Intercepte `capture_surface` : ces tests portent sur la POLITIQUE, pas sur l'écriture."""
    appels = []

    def _faux_capture_surface(device, **kwargs):
        appels.append(kwargs)
        return {
            'layoutFingerprint': 'abc123',
            'surface': kwargs.get('surface'),
            'platform': kwargs.get('platform'),
            'foregroundPackage': 'com.instagram.android',
            'appVersion': '',
            'xmlPath': '/tmp/ecran.xml',
            'screenshotPath': '/tmp/ecran.png',
            'layoutChanged': True,
            'lossy': False,
        }

    monkeypatch.setattr(miss_capture, 'capture_surface', _faux_capture_surface)
    return appels


@pytest.fixture
def metriques():
    recues = []
    configure_telemetry_sink(recues.append)
    yield recues
    clear_telemetry_sink()


# --- ce que l'appelant note en plus du sélecteur -------------------------------------------

def test_le_contexte_est_note_a_cote_du_selecteur(captures):
    miss_capture.capturer_echec(
        object(), selectors=['//vignette'], platform='instagram', contexte='grille_absente',
    )

    assert captures[0]['action_outcome'] == 'cherchait|1|//vignette|grille_absente'


def test_sans_contexte_la_note_ne_change_pas(captures):
    """Le chemin historique (`_wait_for_element`) doit produire exactement la même note qu'avant."""
    miss_capture.capturer_echec(object(), selectors=['//a', '//b'], platform='tiktok')

    assert captures[0]['action_outcome'] == 'cherchait|2|//a'
    assert captures[0]['force_files'] is False


# --- la série de blocage ---------------------------------------------------------------------

def test_un_appelant_qui_ne_compte_pas_ne_casse_pas_la_serie(captures):
    """Le vrai risque de l'ajout d'un second appelant : éteindre la garde de blocage.

    Elle compte le même sélecteur qui échoue d'affilée. Un appel intercalé sur un AUTRE sélecteur
    remettrait ce compte à 1 — et la garde s'éteindrait juste au moment où la boucle s'installe.
    """
    for _ in range(3):
        miss_capture.capturer_echec(object(), selectors=['//bouton-retour'])
    assert miss_capture.repetitions() == 3

    miss_capture.capturer_echec(
        object(), selectors=['//vignette'], contexte='grille_absente', compter_serie=False,
    )

    assert miss_capture.repetitions() == 3

    miss_capture.capturer_echec(object(), selectors=['//bouton-retour'])
    assert miss_capture.repetitions() == 4


def test_un_appelant_ordinaire_compte_toujours(captures):
    miss_capture.capturer_echec(object(), selectors=['//a'])
    miss_capture.capturer_echec(object(), selectors=['//a'])

    assert miss_capture.repetitions() == 2


def test_le_seuil_de_blocage_se_declenche_toujours(captures):
    for _ in range(miss_capture.SEUIL_BLOCAGE):
        miss_capture.capturer_echec(object(), selectors=['//a'])

    assert miss_capture.blocage_a_signaler() is True
    assert miss_capture.blocage_a_signaler() is False


# --- les fichiers ------------------------------------------------------------------------------

def test_forcer_les_fichiers_les_demande(captures):
    """Sans ça, `capture_surface` n'écrit que si la forme a changé — on garderait une empreinte."""
    miss_capture.capturer_echec(object(), selectors=['//vignette'], forcer_fichiers=True)

    assert captures[0]['force_files'] is True


def test_le_plafond_par_run_reste_partage(captures):
    for _ in range(miss_capture.MAX_PAR_RUN + 4):
        miss_capture.capturer_echec(object(), selectors=['//a'], compter_serie=False)

    assert len(captures) == miss_capture.MAX_PAR_RUN


# --- la porte unique : capture + signalement ---------------------------------------------------

def test_la_porte_capture_et_emet(captures, metriques):
    record = miss_capture.signaler_ecran_inconnu(
        object(),
        selectors=['//vignette'],
        platform='instagram',
        action='grid_absent',
        contexte='grille_absente',
        compter_serie=False,
        forcer_fichiers=True,
    )

    assert record is not None
    assert captures[0]['force_files'] is True

    emis = [m for m in metriques if m.category == 'screen_capture']
    assert len(emis) == 1
    assert emis[0].action == 'grid_absent'
    assert emis[0].target == '//vignette'
    assert emis[0].detail['context'] == 'grille_absente'
    assert emis[0].detail['xml_path'] == '/tmp/ecran.xml'
    assert emis[0].detail['lossy'] is False


def test_la_porte_garde_la_forme_historique_du_selector_miss(captures, metriques):
    """`_wait_for_element` passait ces champs en ligne : le consommateur Electron les lit encore."""
    miss_capture.signaler_ecran_inconnu(object(), selectors=['//a', '//b'], platform='tiktok')

    emis = [m for m in metriques if m.category == 'screen_capture'][0]
    assert emis.action == 'selector_miss'
    assert 'context' not in emis.detail
    assert set(emis.detail) == {
        'fingerprint', 'surface', 'platform', 'foreground_package', 'app_version',
        'xml_path', 'screenshot_path', 'layout_changed', 'lossy',
    }


def test_la_porte_reste_muette_quand_rien_n_a_ete_capture(monkeypatch, metriques):
    monkeypatch.setattr(miss_capture, 'capture_surface', lambda device, **kwargs: None)

    assert miss_capture.signaler_ecran_inconnu(object(), selectors=['//a']) is None
    assert [m for m in metriques if m.category == 'screen_capture'] == []


def test_un_ecran_illisible_ne_fait_jamais_echouer_un_run(monkeypatch, metriques):
    def _explose(device, **kwargs):
        raise RuntimeError('appareil deconnecte')

    monkeypatch.setattr(miss_capture, 'capture_surface', _explose)

    assert miss_capture.signaler_ecran_inconnu(object(), selectors=['//a']) is None
    assert [m for m in metriques if m.category == 'screen_capture'] == []
