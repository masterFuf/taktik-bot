"""La boucle de visionnage face a une story qui defile toute seule.

Mesure du 2026-09-07 : une story dure de 2,5 s a 27 s, l'attente du bot vaut 2 a 5 s. Elle tombe
donc regulierement APRES la fin de la slide, et le tap qui suivait en sautait une. Les proprietes
tenues ici sont celles dont la perte ramenerait ce comportement -- ou en introduirait un pire, un
compteur qui affirme des slides que personne n'a vues.
"""

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import taktik.core.social_media.instagram.actions.core.base_business.interaction_engine as ie  # noqa: E402
from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (  # noqa: E402
    InteractionEngineMixin,
)
from taktik.core.social_media.instagram.actions.atomic.story_state import (  # noqa: E402
    SlideObservation,
)


class _Detection:
    def __init__(self, ouvertures, sur_un_post=False):
        self._restantes = ouvertures
        self.sur_un_post = sur_un_post
        self.post_lu = 0

    def is_on_post_screen(self):
        self.post_lu += 1
        return self.sur_un_post

    def has_stories(self):
        return True

    def is_story_viewer_open(self):
        self._restantes -= 1
        return self._restantes >= 0

    def get_story_count_from_viewer(self):
        return (0, 0)

    def get_story_viewer_metadata(self):
        return {}


class _Clicks:
    def __init__(self):
        self.like_calls = 0
        self.fermetures = 0

    def click_story_ring(self):
        return True

    def like_story(self):
        self.like_calls += 1
        return True

    def close_story(self):
        return True

    def close_story_if_open(self, _detection):
        """La production expose cette methode ; sans elle le host retombait sur un `back` a
        l'aveugle en fin de methode, qui polluait le comptage des retours."""
        self.fermetures += 1
        return True


class _Nav:
    def __init__(self, sortie_apres=None):
        self.taps = 0
        self._sortie_apres = sortie_apres

    def navigate_to_next_story(self):
        self.taps += 1
        if self._sortie_apres is not None and self.taps >= self._sortie_apres:
            return False
        return True


class _Host(InteractionEngineMixin):
    def __init__(self, ouvertures=50, sur_un_post=False, sortie_apres=None):
        self.detection_actions = _Detection(ouvertures, sur_un_post)
        self.click_actions = _Clicks()
        self.nav_actions = _Nav(sortie_apres)
        self.retours = []
        self.device = types.SimpleNamespace(press=lambda touche: self.retours.append(touche))
        self.logger = types.SimpleNamespace(
            debug=lambda *a, **k: None, error=lambda *a, **k: None, info=lambda *a, **k: None)

    def _human_like_delay(self, *_a, **_k):
        return None

    def _record_action(self, *_a, **_k):
        return None

    def _action_timestamp(self, *_a, **_k):
        return '2026-01-01 00:00:00'

    def _recover_from_blocking_modal(self, *_a, **_k):
        return None


def _jouer(monkeypatch, observations, *, max_stories=3, sur_un_post=False, sortie_apres=None,
           do_story_like=False, fallback_like_slot=0):
    """`observations` est la suite que `observe_slide` rendra, appel apres appel."""
    monkeypatch.setattr(ie.time, 'sleep', lambda _s: None)
    monkeypatch.setattr(ie.random, 'uniform', lambda a, _b: a)
    suite = list(observations)
    monkeypatch.setattr(ie, 'observe_slide',
                        lambda *_a, **_k: suite.pop(0) if suite else suite_derniere(observations))
    host = _Host(sur_un_post=sur_un_post, sortie_apres=sortie_apres)
    res = host._view_stories_on_current_profile(
        'u', do_story_like=do_story_like, max_stories=max_stories,
        fallback_like_slot=fallback_like_slot)
    return host, res


def suite_derniere(observations):
    return observations[-1] if observations else None


def vue(label, image='aaaaaaaaaaaaaaaa'):
    return SlideObservation(viewer_open=True, label=label, image=image)


PARTIE = SlideObservation(viewer_open=False)


def test_le_tour_ou_la_slide_a_avance_seule_n_envoie_pas_de_tap(monkeypatch):
    """Le coeur du sujet : elle a avance sans nous, taper ferait sauter la nouvelle.

    Le dernier tour tape quand meme -- comportement historique inchange -- donc ce qui se verifie
    ici est qu'il y a MOINS de taps que de slides vues : celui du tour d'avancement seul manque.
    """
    host, res = _jouer(monkeypatch, [
        vue('il y a 8 heures'),   # arrivee
        vue('il y a 5 heures'),   # apres le dwell : le libelle a change -> preuve
        vue('il y a 5 heures'),   # tour suivant : rien ne bouge
        vue('il y a 5 heures'),
    ], max_stories=2)

    assert res['stories_viewed'] == 2
    assert host.nav_actions.taps < res['stories_viewed']


def test_une_slide_stable_fait_taper_comme_avant(monkeypatch):
    host, res = _jouer(monkeypatch, [vue('8 h'), vue('8 h'), vue('8 h'), vue('8 h'), vue('8 h')],
                       max_stories=2)

    assert host.nav_actions.taps >= 1
    assert res['stories_viewed'] == 2


def test_la_visionneuse_refermee_arrete_la_boucle_sans_taper(monkeypatch):
    host, res = _jouer(monkeypatch, [vue('8 h'), PARTIE], max_stories=3)

    assert host.nav_actions.taps == 0
    assert res['stories_viewed'] == 1


def test_un_doute_ne_compte_pas_une_seconde_slide(monkeypatch):
    """L'image bouge, rien ne le prouve : compter serait exactement le bot qui invente."""
    host, res = _jouer(monkeypatch, [
        vue('8 h', '0000000000000000'),
        vue('8 h', 'ffffffffffffffff'),   # doute
        vue('8 h', 'ffffffffffffffff'),   # puis plus rien -> on tape
        vue('8 h', 'ffffffffffffffff'),
        vue('8 h', 'ffffffffffffffff'),
    ], max_stories=1)

    assert res['stories_viewed'] == 1


def test_un_doute_ne_mange_pas_le_budget_de_slides(monkeypatch):
    """Le budget porte sur les slides VUES, pas sur les tours de boucle."""
    host, res = _jouer(monkeypatch, [
        vue('8 h', '0000000000000000'),
        vue('8 h', 'ffffffffffffffff'),   # doute : un tour repris
        vue('8 h', 'ffffffffffffffff'),
        vue('8 h', 'ffffffffffffffff'),
        vue('8 h', 'ffffffffffffffff'),
        vue('8 h', 'ffffffffffffffff'),
        vue('8 h', 'ffffffffffffffff'),
    ], max_stories=3)

    assert res['stories_viewed'] == 3


def test_un_ecran_illisible_ne_change_rien_au_comportement(monkeypatch):
    """Ne pas savoir n'est pas un evenement : on retombe sur regarder-puis-taper."""
    host, res = _jouer(monkeypatch, [None, None, None, None, None, None], max_stories=2)

    assert res['stories_viewed'] == 2
    assert host.nav_actions.taps >= 1


def test_une_story_qui_defile_entierement_seule_est_comptee_juste(monkeypatch):
    host, res = _jouer(monkeypatch, [
        vue('8 h'), vue('7 h'), vue('6 h'), PARTIE,
    ], max_stories=5)

    assert host.nav_actions.taps == 0
    assert res['stories_viewed'] == 3


# --- le filet : le tap final a ouvert une publication -------------------------------------------
#
# Entre la garde de `navigate_to_next_story` et l'injection du tap, la story peut se terminer. Le
# tap tombe alors sur le profil, dans la bande qui porte la grille. Mesure du 08/09 : les six
# pertes de grille qui restent suivent TOUTES une story.

def test_une_publication_ouverte_par_le_tap_final_est_refermee(monkeypatch):
    host, _res = _jouer(monkeypatch, [vue('8 h')] * 8,
                        max_stories=1, sur_un_post=True, sortie_apres=1)

    assert host.retours == ['back']


def test_rien_n_est_referme_quand_on_est_bien_revenu_au_profil(monkeypatch):
    host, _res = _jouer(monkeypatch, [vue('8 h')] * 8,
                        max_stories=1, sur_un_post=False, sortie_apres=1)

    assert host.retours == []


def test_le_like_de_secours_ne_part_pas_apres_un_retour_de_publication(monkeypatch):
    """Le filet passe AVANT le like de secours, et l'annule.

    Le slot planifie (5) n'est jamais atteint sur une story d'une slide : sans publication ouverte,
    le secours tire pour qu'un story-like promis arrive quand meme. Mais apres un retour de
    publication la visionneuse n'est plus la — ce like partirait sur le PROFIL.
    """
    sans_post, _ = _jouer(monkeypatch, [vue('8 h')] * 8, max_stories=1,
                          sortie_apres=1, do_story_like=True, fallback_like_slot=5)
    assert sans_post.click_actions.like_calls == 1, "le secours doit tirer dans le cas normal"

    avec_post, _ = _jouer(monkeypatch, [vue('8 h')] * 8, max_stories=1, sur_un_post=True,
                          sortie_apres=1, do_story_like=True, fallback_like_slot=5)

    assert avec_post.retours == ['back']
    assert avec_post.click_actions.like_calls == 0
