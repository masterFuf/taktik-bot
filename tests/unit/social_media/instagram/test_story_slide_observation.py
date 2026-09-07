"""Savoir si la slide a change pendant qu'on la regardait — sans jamais l'inventer.

Une story dure de 2,5 s a 27 s : mesure du 2026-09-07 sur 50 stories et quatre appareils, deux
familles nettes (images 2,5-5,5 s, videos 13-27 s) et rien entre les deux. L'attente du bot, elle,
vaut 2 a 5 s. Elle tombe donc parfois APRES la fin de la slide, et le tap qui suivait en sautait
une sans que personne le voie — ou pire, partait dans la grille du profil une fois la visionneuse
refermee.

Le meme banc a montre qu'aucun signal ne suffit seul : le libelle rate les slides postees dans la
meme heure, et l'image ne distingue pas une video animee d'une transition (les deux distributions
se recouvrent entierement). D'ou les quatre verdicts, et surtout le quatrieme : `unsure` est ce qui
reste quand on refuse de trancher a la place de la mesure.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from taktik.core.social_media.instagram.actions.atomic.story_state import (  # noqa: E402
    SEUIL_IMAGE_DIFFERENTE,
    SlideObservation,
    compare_slides,
    observe_slide,
)

PLEIN = 'ffffffffffffffff'
VIDE = '0000000000000000'
PRESQUE_PLEIN = 'fffffffffffffffe'   # un seul bit d'ecart : la meme image re-encodee


# --- les preuves ------------------------------------------------------------------------------

def test_le_viewer_disparu_tranche_seul():
    assert compare_slides(SlideObservation(True, 'il y a 8 heures', PLEIN),
                          SlideObservation(False)) == 'gone'


def test_un_libelle_qui_change_prouve_l_avancement():
    """Le seul signal qui PROUVE : c'est Instagram qui l'ecrit, pas nous qui le deduisons."""
    assert compare_slides(SlideObservation(True, 'Story de x, il y a 8 heures', PLEIN),
                          SlideObservation(True, 'Story de x, il y a 5 heures', PLEIN)) == 'advanced'


def test_la_preuve_prime_sur_l_image():
    """Libelle change ET image identique : c'est quand meme une nouvelle slide."""
    assert compare_slides(SlideObservation(True, '8 heures', PLEIN),
                          SlideObservation(True, '5 heures', PLEIN)) == 'advanced'


def test_le_viewer_parti_prime_sur_tout():
    assert compare_slides(SlideObservation(True, '8 heures', PLEIN),
                          SlideObservation(False, '5 heures', VIDE)) == 'gone'


# --- l'indice ---------------------------------------------------------------------------------

def test_une_image_franchement_differente_ne_prouve_rien():
    """64 bits d'ecart : l'ecran a change. Mais une video aussi change — donc on doute."""
    assert compare_slides(SlideObservation(True, '8 heures', VIDE),
                          SlideObservation(True, '8 heures', PLEIN)) == 'unsure'


def test_un_re_encodage_de_la_meme_image_ne_declenche_rien():
    assert compare_slides(SlideObservation(True, '8 heures', PLEIN),
                          SlideObservation(True, '8 heures', PRESQUE_PLEIN)) == 'same'


def test_le_seuil_d_image_est_celui_annonce():
    """Sous le seuil : rien. Au seuil : doute. La frontiere est celle que le module documente."""
    juste_dessous = format((1 << (SEUIL_IMAGE_DIFFERENTE - 1)) - 1, '016x')
    au_seuil = format((1 << SEUIL_IMAGE_DIFFERENTE) - 1, '016x')

    assert compare_slides(SlideObservation(True, 'x', VIDE),
                          SlideObservation(True, 'x', juste_dessous)) == 'same'
    assert compare_slides(SlideObservation(True, 'x', VIDE),
                          SlideObservation(True, 'x', au_seuil)) == 'unsure'


# --- ce qu'on ne sait pas -----------------------------------------------------------------------

def test_sans_reference_on_ne_conclut_pas_a_un_changement():
    assert compare_slides(None, SlideObservation(True, '8 heures', PLEIN)) == 'same'


def test_une_observation_manquante_est_un_doute_pas_une_sortie():
    """Ne pas avoir pu lire l'ecran n'est pas la preuve que la story est finie."""
    assert compare_slides(SlideObservation(True, '8 heures', PLEIN), None) == 'unsure'


def test_une_image_illisible_ne_declenche_pas_de_doute():
    assert compare_slides(SlideObservation(True, '8 heures', None),
                          SlideObservation(True, '8 heures', None)) == 'same'


def test_un_libelle_absent_des_deux_cotes_laisse_l_image_decider():
    assert compare_slides(SlideObservation(True, None, VIDE),
                          SlideObservation(True, None, PLEIN)) == 'unsure'


# --- la lecture sur appareil ---------------------------------------------------------------------

class _Element:
    def __init__(self, desc):
        self.attrib = {'content-desc': desc}


class _XPath:
    def __init__(self, existe, element=None):
        self.exists = existe
        self._element = element

    def get(self, timeout=0):
        if self._element is None:
            raise RuntimeError('introuvable')
        return self._element


class _Device:
    """Un ecran ou le viewer est ouvert et porte un libelle."""

    def __init__(self, viewer=True, desc='Story de x, il y a 8 heures'):
        self.viewer, self.desc = viewer, desc

    def xpath(self, selector):
        if 'reel_viewer_root' in selector:
            return _XPath(self.viewer)
        return _XPath(self.viewer, _Element(self.desc) if self.desc else None)


def test_le_viewer_ferme_ne_coute_aucune_capture(monkeypatch):
    """Pas de story a l'ecran : inutile de payer une capture pour s'en assurer."""
    import taktik.core.shared.vision.screen_text as screen_text

    def _interdit(*_a, **_k):
        raise AssertionError('aucune capture ne doit etre prise')

    monkeypatch.setattr(screen_text, 'screenshot_pil', _interdit)

    vue = observe_slide(_Device(viewer=False))

    assert vue.viewer_open is False
    assert vue.label is None


def test_sans_image_demandee_on_ne_capture_pas(monkeypatch):
    import taktik.core.shared.vision.screen_text as screen_text
    monkeypatch.setattr(screen_text, 'screenshot_pil',
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError('capture interdite')))

    vue = observe_slide(_Device(), with_image=False)

    assert vue.viewer_open is True
    assert vue.label == 'Story de x, il y a 8 heures'
    assert vue.image is None


def test_un_appareil_illisible_rend_None_et_non_un_viewer_ferme():
    """Ne pas avoir pu lire n'est pas « la story est finie » — les confondre l'arretait a tort."""
    class _Casse:
        def xpath(self, _selector):
            raise RuntimeError('appareil injoignable')

    assert observe_slide(_Casse()) is None


def test_un_viewer_reellement_absent_est_une_lecture_pas_une_ignorance():
    vue = observe_slide(_Device(viewer=False))

    assert vue is not None
    assert vue.viewer_open is False


def test_une_capture_impossible_laisse_le_libelle_utilisable(monkeypatch):
    """Le libelle est la preuve : il doit survivre a une capture ratee."""
    import taktik.core.shared.vision.screen_text as screen_text
    monkeypatch.setattr(screen_text, 'screenshot_pil', lambda *_a, **_k: None)

    vue = observe_slide(_Device())

    assert vue.viewer_open is True
    assert vue.label == 'Story de x, il y a 8 heures'
    assert vue.image is None


@pytest.mark.parametrize('desc', ['', None])
def test_un_libelle_vide_ne_devient_pas_une_chaine_vide(desc):
    vue = observe_slide(_Device(desc=desc), with_image=False)

    assert vue.label is None
