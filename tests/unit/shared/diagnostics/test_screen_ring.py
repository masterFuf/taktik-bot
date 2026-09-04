"""L'anneau des ecrans : ce qu'il garde, ce qu'il replie, ce qu'il refuse.

Trois proprietes portent tout l'interet du module, et chacune peut se perdre sans que rien ne
casse : le repli des repetitions (sinon six emplacements montrent six fois le meme ecran), la
difference de squelette (sinon on lit deux etiquettes hexadecimales au lieu d'une phrase), et le
refus silencieux d'un dump illisible (sinon chaque dump casse devient une etape du parcours).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from taktik.core.shared.diagnostics import screen_ring  # noqa: E402


def ecran(*entrees: str) -> str:
    noeuds = ''.join(f'<node resource-id="com.x:id/{entree}" />' for entree in entrees)
    return f'<hierarchy>{noeuds}</hierarchy>'


@pytest.fixture(autouse=True)
def anneau_vide():
    screen_ring.reinitialiser()
    yield
    screen_ring.reinitialiser()


def test_un_ecran_repete_ne_consomme_quune_place():
    for _ in range(40):
        screen_ring.noter(ecran('feed', 'tab_home'), platform='instagram')

    assert len(screen_ring.derniers()) == 1
    assert screen_ring.derniers()[0]['repetitions'] == 40


def test_le_compteur_de_repetitions_dit_combien_de_tours_sur_la_page():
    """« On est reste 40 tours sur cette page » est le diagnostic, pas un detail de stockage."""
    for _ in range(3):
        screen_ring.noter(ecran('feed'), platform='instagram')
    screen_ring.noter(ecran('profile'), platform='instagram')

    assert 'x3' in screen_ring.resume()[0]
    assert 'x' not in screen_ring.resume()[1].split('  ')[0]


def test_la_difference_de_squelette_se_lit_comme_une_phrase():
    screen_ring.noter(ecran('feed', 'tab_home'))
    screen_ring.noter(ecran('profile', 'tab_home'))

    dernier = screen_ring.derniers()[-1]
    assert dernier['entered'] == ['profile']
    assert dernier['left'] == ['feed']
    assert '+profile' in screen_ring.resume()[-1]
    assert '-feed' in screen_ring.resume()[-1]


def test_le_premier_ecran_na_pas_de_difference():
    """Rien n'a precede : annoncer que tout est « apparu » serait un mensonge de lecture."""
    screen_ring.noter(ecran('feed'))

    assert screen_ring.derniers()[0]['entered'] == []
    assert screen_ring.derniers()[0]['left'] == []


def test_un_dump_illisible_est_ignore_sans_lever():
    screen_ring.noter(ecran('feed'))
    screen_ring.noter('')
    screen_ring.noter(None)
    screen_ring.noter('pas du xml du tout <<<')

    assert len(screen_ring.derniers()) == 1


def test_lanneau_est_plafonne_et_garde_les_plus_recents():
    for index in range(screen_ring.CAPACITE + 4):
        screen_ring.noter(ecran(f'page{index}'))

    gardes = screen_ring.derniers()
    assert len(gardes) == screen_ring.CAPACITE
    assert gardes[-1]['skeleton'] == ['page9']


def test_la_remise_a_zero_vide_tout():
    screen_ring.noter(ecran('feed'))
    screen_ring.reinitialiser()

    assert screen_ring.derniers() == []
    assert screen_ring.resume() == []


def test_derniers_rend_une_copie():
    """Le dossier d'incident serialise ce tableau ; le muter ne doit pas toucher l'anneau."""
    screen_ring.noter(ecran('feed'))
    copie = screen_ring.derniers()
    copie[0]['fingerprint'] = 'saccage'

    assert screen_ring.derniers()[0]['fingerprint'] != 'saccage'
