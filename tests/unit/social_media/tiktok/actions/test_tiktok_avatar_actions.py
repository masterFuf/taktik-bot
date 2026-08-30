"""Choisir la bonne image quand le conteneur en porte deux.

TikTok ne donne aucune URL pour la photo de profil et aucun identifiant sur le nœud : la seule
façon de l'avoir est de la découper d'une capture. Le conteneur qui l'entoure porte exactement
deux images — l'avatar, et le badge « + » d'ajout à la story posé dessus. Prendre la plus grande
écarte le badge sans avoir à le nommer, et sans dépendre de l'ordre du dump.

Mesuré le 2026-08-30 : 252×252 contre 63×63 sur 46.6.3, 294×294 contre 73×73 sur 43.1.4. Les deux
versions posent d'ailleurs l'avatar de côtés opposés, à droite sur l'une, à gauche sur l'autre.
"""

import pytest

from taktik.core.social_media.tiktok.actions.atomic.avatar_actions import AvatarActions


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
    """Un écran dont chaque sélecteur du catalogue rend ce qu'on lui dit."""

    def __init__(self, by_selector):
        self.by_selector = by_selector

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
