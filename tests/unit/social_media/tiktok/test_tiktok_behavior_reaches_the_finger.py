"""La mémoire de session doit atteindre l'objet qui bouge le doigt.

Mesuré sur un run For You reel (Pixel 6 Pro, 2026-09-02) : le moteur choisissait des vitesses de
1.069 et 1.083, et chaque flick s'executait a exactement 1.0. Les styles tournaient
(steady/brisk/deliberate), l'energie derivait, les distances variaient — et le geste ignorait tout.

La cause n'est pas dans le moteur, elle est dans le CHAINAGE. `SharedBaseAction.__init__` fait :

    if isinstance(device, BaseDeviceFacade):  self.device = device
    else:                                     self.device = self._device_facade_class(device)

Un workflow recoit un `DeviceManager` brut, donc **chaque action fabrique son propre facade**.
Quatre actions, quatre facades distincts, et aucun n'est le `device` du workflow. Poser l'etat sur
`self.device` ne touchait donc rien de ce qui bouge un doigt : `_motor` ne trouvait aucun etat et
rendait son repli `(1.0, 1.0)`.

Ce que ce fichier verrouille tient en une phrase : **l'etat doit etre sur le facade, pas seulement
sur l'action**. Les deux se ressemblent a la lecture et l'un des deux ne sert a rien.
"""

import pytest

from taktik.core.shared.behavior.session_state import BehaviorSessionState
from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.social_media.tiktok.actions.business.workflows._internal.base_workflow import (
    BaseTikTokWorkflow,
)

ACTIONS = ("click", "navigation", "scroll", "detection")


class DeviceBrut:
    """Ce qu'un workflow recoit vraiment : ni un facade, ni rien qu'une action puisse annoter."""


@pytest.fixture
def workflow():
    return BaseTikTokWorkflow(DeviceBrut())


class TestLEtatAtteintLeFacade:
    def test_chaque_action_enveloppe_le_device_dans_son_propre_facade(self, workflow):
        """Le fait qui rend le reste necessaire. Si un jour les actions partagent un facade, ce
        test tombe et quelqu'un relira la suite au lieu de la croire acquise."""
        facades = {id(getattr(workflow, nom).device) for nom in ACTIONS}
        assert len(facades) == len(ACTIONS), "les actions partagent un facade : relire ce fichier"
        for nom in ACTIONS:
            assert isinstance(getattr(workflow, nom).device, BaseDeviceFacade)
            assert getattr(workflow, nom).device is not workflow.device

    @pytest.mark.parametrize("nom", ACTIONS)
    def test_le_facade_de_chaque_action_porte_l_etat(self, workflow, nom):
        facade = getattr(workflow, nom).device
        assert facade.behavior_state is workflow.behavior_state

    @pytest.mark.parametrize("nom", ACTIONS)
    def test_l_action_elle_meme_le_porte_aussi(self, workflow, nom):
        """`choose_scroll_mode` lit l'etat de l'ACTION — c'est lui qui marchait, et c'est ce qui
        rendait la panne invisible : le journal montrait un moteur qui planifiait."""
        assert getattr(workflow, nom).behavior_state is workflow.behavior_state


class TestLesEchellesArriventAuGeste:
    """Le test de bout en bout, en une assertion : le facade rend-il autre chose que son repli ?"""

    def test_le_moteur_ne_rend_plus_le_repli(self, workflow):
        echelles = {workflow.scroll.device._motor("tiktok_feed_advance") for _ in range(12)}
        assert echelles != {(1.0, 1.0)}, (
            "_motor rend son repli : l'etat n'est pas sur le facade, et chaque flick partira "
            "a vitesse 1.0 quoi que le moteur ait choisi"
        )

    def test_un_facade_sans_etat_rend_bien_le_repli(self, workflow):
        """L'autre moitie de la mesure. Sans elle, un `_motor` qui rendrait toujours des valeurs
        variables passerait le test precedent sans rien prouver."""
        facade = getattr(workflow, "scroll").device
        facade.behavior_state = None
        assert facade._motor("tiktok_feed_advance") == (1.0, 1.0)

    def test_les_gestes_planifies_dependent_aussi_du_facade(self, workflow):
        """`_plan_gesture` sert les scrolls de liste et les swipes horizontaux ; il lit l'etat au
        meme endroit et tombait donc dans le meme trou."""
        plans = {workflow.scroll.device._plan_gesture("tiktok_list_scroll_down", "controlled_swipe")
                 for _ in range(12)}
        assert plans != {(1.0, 1.0)}


class TestUneMemoireParRun:
    def test_deux_workflows_ne_partagent_pas_leur_memoire(self):
        """Deux telephones tournent en meme temps. Une memoire partagee ferait deriver le style de
        l'un au rythme de l'autre — deux comptes qui se fatiguent en meme temps, ce qui est
        exactement le motif qu'on cherche a ne pas produire."""
        a, b = BaseTikTokWorkflow(DeviceBrut()), BaseTikTokWorkflow(DeviceBrut())
        assert a.behavior_state is not b.behavior_state
        assert a.scroll.device.behavior_state is not b.scroll.device.behavior_state

    def test_l_etat_est_bien_une_session(self, workflow):
        assert isinstance(workflow.behavior_state, BehaviorSessionState)
