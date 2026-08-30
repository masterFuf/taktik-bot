"""La couche session atteint enfin les gestes de TikTok.

Le moteur d'humanisation partagé décide de deux choses très différentes. Les gestes eux-mêmes
— où taper dans un élément, quelle courbe suit un scroll — étaient déjà humanisés côté TikTok, et
plutôt mieux que côté Instagram par endroits. Ce qui manquait est la couche au-dessus : la
**mémoire de la passe**. Un run enchaînait des gestes chacun tiré indépendamment, sans rien de
commun de l'un à l'autre — humain vu de près, script vu de loin.

Trois branchements manquaient, et ce fichier les verrouille :

- l'objet qui **bouge réellement le doigt** — la façade — ne recevait jamais l'état de session ;
- `human_scroll`, l'entrée verticale, n'acceptait pas les échelles moteur que la primitive
  dessous attendait pourtant depuis toujours (`human_hswipe`, elle, les passait) ;
- l'entrée dans une grille de profil était **toujours la case 0**.

Chaque branchement se replie sur le comportement d'avant quand il n'y a pas de mémoire de
session : c'est ce que la moitié « sans état » de chaque test vérifie.
"""

import pytest

from taktik.core.shared.behavior.session_state import BehaviorSessionState


# --- les échelles moteur traversent enfin le scroll vertical -------------------------------------


class _Host:
    screen_height = 2400

    def __init__(self):
        self.calls = []

    def _strong_flick(self, direction=None, distance_px=None, velocity_scale=1.0):
        self.calls.append(("flick", distance_px, velocity_scale))
        return True

    def _human_swipe(self, direction=None, distance_px=None, controlled=False, velocity_scale=1.0):
        self.calls.append(("swipe", distance_px, velocity_scale))
        return True


class _Facade:
    """La vraie méthode partagée, posée sur un hôte de test."""

    from taktik.core.shared.device.facade import BaseDeviceFacade
    human_scroll = BaseDeviceFacade.human_scroll
    _PAGE_TO_GESTURE = BaseDeviceFacade._PAGE_TO_GESTURE

    def __init__(self):
        self.host = _Host()

    def _gesture_host(self):
        return self.host


def test_the_scales_reach_the_primitive():
    """Elles les acceptait depuis toujours ; seule l'entrée verticale ne les passait pas."""
    f = _Facade()

    f.human_scroll("down", distance_ratio=0.3, distance_scale=1.2, velocity_scale=0.9)

    kind, distance, velocity = f.host.calls[0]
    assert kind == "swipe"
    assert distance == pytest.approx(0.3 * 2400 * 1.2)
    assert velocity == 0.9


def test_a_caller_that_passes_nothing_behaves_exactly_as_before():
    f = _Facade()

    f.human_scroll("down", distance_ratio=0.3)

    _, distance, velocity = f.host.calls[0]
    assert distance == pytest.approx(0.3 * 2400)
    assert velocity == 1.0


@pytest.mark.parametrize("scale,expected", [(0.01, 0.2), (99.0, 3.0), (1.5, 1.5)])
def test_an_absurd_distance_scale_is_clamped(scale, expected):
    """Une échelle vient d'un état de session ; une valeur folle ne doit pas produire un geste qui
    traverse trois écrans ou qui ne bouge pas."""
    f = _Facade()

    f.human_scroll("down", distance_ratio=0.3, distance_scale=scale)

    assert f.host.calls[0][1] == pytest.approx(0.3 * 2400 * expected)


def test_a_coasting_scroll_carries_them_too():
    f = _Facade()

    f.human_scroll("down", coast=True, velocity_scale=1.1)

    assert f.host.calls[0][0] == "flick"
    assert f.host.calls[0][2] == 1.1


# --- la façade TikTok lit le style de la passe ----------------------------------------------------


def _tiktok_facade():
    from taktik.core.social_media.tiktok.actions.core.device_facade import DeviceFacade

    return DeviceFacade.__new__(DeviceFacade)


def test_without_session_memory_the_motor_is_neutral():
    """Le repli qui garantit qu'aucun appelant existant ne change de comportement."""
    facade = _tiktok_facade()

    assert facade._motor("peu importe") == (1.0, 1.0)


def test_with_session_memory_the_motor_follows_the_style():
    facade = _tiktok_facade()
    facade.behavior_state = BehaviorSessionState(seed=7)

    distance, velocity = facade._motor("tiktok_scroll_down")

    assert 0.5 < distance < 2.0
    assert 0.5 < velocity < 2.0


def test_a_broken_state_does_not_break_the_gesture():
    """Un état qui lève doit coûter un geste neutre, jamais un run interrompu au milieu."""
    class _Angry:
        def motor_modulation(self, **_):
            raise RuntimeError("boom")

    facade = _tiktok_facade()
    facade.behavior_state = _Angry()

    assert facade._motor("x") == (1.0, 1.0)


# --- flick ou drag sur le fil ---------------------------------------------------------------------


def _base_action():
    from taktik.core.social_media.tiktok.actions.core.base_action import BaseAction

    return BaseAction.__new__(BaseAction)


def test_without_session_memory_the_feed_still_flicks():
    assert _base_action()._advance_mode("tiktok_feed_advance") is True


def test_the_session_can_choose_a_drag_instead_of_a_flick():
    class _State:
        def __init__(self, mode):
            self.mode = mode

        def choose_scroll_mode(self, *, context, base_drag_probability=0.15):
            return {"mode": self.mode}

    action = _base_action()

    action.behavior_state = _State("drag")
    assert action._advance_mode("tiktok_feed_advance") is False

    action.behavior_state = _State("flick")
    assert action._advance_mode("tiktok_feed_advance") is True


def test_both_gestures_come_out_over_a_run():
    """La moitié qui compte : une décision qui rendrait toujours la même chose laisserait
    exactement le motif qu'on retire."""
    action = _base_action()
    action.behavior_state = BehaviorSessionState(seed=3)

    modes = [action._advance_mode("tiktok_feed_advance") for _ in range(120)]

    assert any(modes), "jamais de flick"
    assert not all(modes), "jamais de drag — la variation ne sort pas"
