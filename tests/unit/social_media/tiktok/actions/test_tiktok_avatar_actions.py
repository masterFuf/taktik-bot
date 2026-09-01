"""Choisir la bonne image quand le conteneur en porte deux.

TikTok ne donne aucune URL pour la photo de profil et aucun identifiant sur le nœud : la seule
façon de l'avoir est de la découper d'une capture. Le conteneur qui l'entoure porte exactement
deux images — l'avatar, et le badge « + » d'ajout à la story posé dessus. Prendre la plus grande
écarte le badge sans avoir à le nommer, et sans dépendre de l'ordre du dump.

Mesuré le 2026-08-30 : 252×252 contre 63×63 sur 46.6.3, 294×294 contre 73×73 sur 43.1.4. Les deux
versions posent d'ailleurs l'avatar de côtés opposés, à droite sur l'une, à gauche sur l'autre.
"""

import pytest

from taktik.core.social_media.tiktok.actions.atomic.detection.avatar_actions import AvatarActions


class _SilentLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class _Node:
    def __init__(self, left, top, size):
        self.info = {"bounds": {"left": left, "top": top,
                                "right": left + size, "bottom": top + size}}


class _Result:
    def __init__(self, nodes):
        self._nodes = nodes

    def all(self):
        return self._nodes


class _Screen:
    """Un écran dont chaque sélecteur du catalogue rend ce qu'on lui dit.

    Il rend aussi sa TAILLE, parce que le seuil minimum d'un avatar en est derive : un chiffre en
    pixels encode un seul telephone et rejetterait la vraie photo sur un ecran moins dense.
    1080 de large est la mesure d'origine, celle sur laquelle les tailles de ces tests sont ecrites.
    """

    def __init__(self, by_selector, size=(1080, 2400)):
        self.by_selector = by_selector
        self._size = size

    def get_screen_size(self):
        return self._size

    def xpath(self, selector):
        for fragment, nodes in self.by_selector.items():
            if fragment in selector:
                return _Result(nodes)
        return _Result([])


def _actions(screen) -> AvatarActions:
    actions = AvatarActions.__new__(AvatarActions)
    actions.device = screen
    actions.logger = _SilentLogger()
    from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS
    actions.profile_selectors = PROFILE_SELECTORS
    return actions


# --- choisir -------------------------------------------------------------------------------------


def test_the_badge_never_wins_over_the_avatar():
    """Le cas réel : le conteneur rend l'avatar ET le badge, dans un ordre qu'on ne choisit pas."""
    screen = _Screen({":id/ss_": [_Node(1000, 500, 63), _Node(786, 306, 252)]})

    assert _actions(screen)._largest_avatar_bounds() == (786, 306, 1038, 558)


def test_the_order_of_the_dump_does_not_decide():
    avatar_first = _Screen({":id/ss_": [_Node(786, 306, 252), _Node(1000, 500, 63)]})
    badge_first = _Screen({":id/ss_": [_Node(1000, 500, 63), _Node(786, 306, 252)]})

    assert (_actions(avatar_first)._largest_avatar_bounds()
            == _actions(badge_first)._largest_avatar_bounds())


def test_the_other_build_is_found_too():
    """43.1.4 pose l'avatar à gauche, sous un autre conteneur, et en 294 px."""
    screen = _Screen({":id/b5s": [_Node(56, 399, 294), _Node(235, 578, 73)]})

    assert _actions(screen)._largest_avatar_bounds() == (56, 399, 350, 693)


# --- refuser -------------------------------------------------------------------------------------


def test_a_badge_alone_is_not_an_avatar():
    """Sous le plancher, rien n'est rendu : une vignette de 63 px découpée et présentée comme une
    photo de profil est pire que pas de photo du tout."""
    screen = _Screen({":id/ss_": [_Node(1000, 500, 63)]})

    assert _actions(screen)._largest_avatar_bounds() is None


def test_a_screen_without_the_container_gives_nothing():
    assert _actions(_Screen({}))._largest_avatar_bounds() is None


def test_a_node_without_readable_bounds_is_skipped_not_crashed_on():
    class _Broken:
        info = {"bounds": {"left": "?", "top": 0}}

    screen = _Screen({":id/ss_": [_Broken(), _Node(786, 306, 252)]})

    assert _actions(screen)._largest_avatar_bounds() == (786, 306, 1038, 558)


# --- le seuil suit l'écran, pas un téléphone ------------------------------------------------


@pytest.mark.parametrize("largeur,attendu", [(720, 72.0), (1080, 108.0), (1440, 144.0)])
def test_the_minimum_follows_the_screen_width(largeur, attendu):
    """Un seuil en PIXELS encode un seul téléphone.

    L'avatar mesure environ 0,24 de la largeur et le badge à côté un quart de ça, soit 0,06 : un
    seuil à 0,10 passe entre les deux sur n'importe quelle densité. Écrit en dur à 100 px, il
    aurait rejeté la vraie photo sur un écran moins dense — le filtre censé écarter le badge aurait
    écarté l'avatar.
    """
    actions = _actions(_Screen({}, size=(largeur, largeur * 2)))

    assert actions._min_avatar_side() == pytest.approx(attendu)


def test_an_unreadable_screen_falls_back_to_the_old_literal():
    """Le repli n'est juste nulle part, mais il est joignable : sans taille d'écran, rien d'autre
    n'est calculable et refuser de choisir empêcherait toute capture."""
    class _Muet:
        def get_screen_size(self):
            raise RuntimeError("pas de device")

    actions = _actions(_Screen({}))
    actions.device = _Muet()

    assert actions._min_avatar_side() == 100.0


def test_a_small_screen_still_accepts_its_avatar():
    """La moitié qui compte : sur un 720 de large, un avatar de 90 px passe — le littéral 100 le
    rejetait, et la capture d'avatar rendait vide sans rien dire."""
    petit = _Screen({":id/ss_": [_Node(40, 300, 90)]}, size=(720, 1600))

    assert _actions(petit)._largest_avatar_bounds() is not None
