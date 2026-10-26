"""Ce que le telephone voit du reseau au demarrage d'un run : la mesure de latence.

Une mesure, pas une decision : rien ne lit encore cette valeur pour rallonger une attente. Elle
existe parce que « le reseau etait-il lent ? » n'a jamais eu de reponse mesuree -- et c'est par
inference que les 65 likes non realises du week-end du 05-06/09 ont failli etre attribues au
mauvais coupable.

Ici, la sonde du coeur (`taktik/core/shared/device/network_probe.py`) : ce que son shell envoie au
telephone, et un parsing qui doit survivre aux deux formats de `ping` (celui qui imprime la ligne de
resume, et toybox qui parfois ne l'imprime pas). La porte du reseau que le coeur ouvre au depart
d'un run, pour les ponts comme pour la CLI, et qui decide sur cette mesure, est tenue par
`tests/unit/shared/device/test_network_door.py`.
"""

import subprocess
import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE))

from taktik.core.shared.device import adb, network_probe  # noqa: E402
from unit.android_shell import adb_line, phone_words  # noqa: E402
from unit.ping_outputs import (  # noqa: E402
    PING_ABSENT,
    PING_COMPLET,
    PING_INJOIGNABLE,
    PING_SANS_RESUME,
    PING_TOUT_PERDU,
)


@pytest.fixture
def ping(monkeypatch):
    """Remplace l'appel ADB : ces tests portent sur la lecture, pas sur le telephone."""

    def _installer(sortie):
        monkeypatch.setattr(network_probe, '_shell', lambda device_id, cmd, timeout=15: sortie)

    return _installer


# --- ce que le shell du telephone recoit ------------------------------------------------------

def test_la_commande_arrive_entiere_au_telephone(monkeypatch):
    """La panne qui rendait toutes les sondes muettes, et qu'aucun test ne voyait.

    `adb shell` colle ses arguments avec des espaces et envoie UNE ligne de commande, sans les
    requoter : `["sh", "-c", "ping -c 3 1.1.1.1"]` arrivait comme `sh -c ping -c 3 1.1.1.1`, ou
    `sh -c ping` lance ping sans aucun argument. Mesure sur appareil le 2026-09-06 : chaque sonde
    de ce module rendait le texte d'usage de ping ou rien -- donc `read_public_ip` rendait None sur
    toute la flotte, et une rotation d'IP ne pouvait jamais etre verifiee.

    Ce qui compte est ce que le telephone RECOIT, pas ce que la sonde demande : le test rejoue le
    trajet sur les arguments avec lesquels adb est lance (la porte `shared/device/adb.py` quote).
    """
    lances = []

    def _run(argv, **kwargs):
        lances.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "ok", "")

    monkeypatch.setattr(adb.subprocess, "run", _run)

    commande = "printf 'GET / HTTP/1.1' | toybox nc -w 8 ifconfig.me 80"
    network_probe._shell('SERIE', commande)

    (argv,) = lances
    assert phone_words(adb_line(argv)) == ['sh', '-c', commande]


def test_le_shell_ne_leve_jamais(monkeypatch):
    def _explose(device_id, args, timeout=10):
        raise OSError('adb absent')

    monkeypatch.setattr(network_probe, 'run_adb_shell_process', _explose)

    assert network_probe._shell('SERIE', 'ping -c 1 1.1.1.1') == ''


# --- la lecture ------------------------------------------------------------------------------

def test_la_moyenne_vient_de_la_ligne_de_resume(ping):
    ping(PING_COMPLET)

    mesure = network_probe.measure_network_baseline('SERIE')

    assert mesure == {'rtt_ms': 24.9, 'packet_loss_pct': 0.0, 'received': 3, 'unreachable': False}


def test_sans_ligne_de_resume_les_paquets_suffisent(ping):
    """toybox ne l'imprime pas toujours ; les temps par paquet sont quand meme la."""
    ping(PING_SANS_RESUME)

    mesure = network_probe.measure_network_baseline('SERIE')

    assert mesure['rtt_ms'] == 150.0
    assert mesure['received'] == 2
    assert mesure['packet_loss_pct'] is None


def test_une_perte_totale_reste_une_mesure(ping):
    """« Rien ne repond » est une reponse, et c'est meme la plus parlante des trois."""
    ping(PING_TOUT_PERDU)

    mesure = network_probe.measure_network_baseline('SERIE')

    assert mesure == {'rtt_ms': None, 'packet_loss_pct': 100.0, 'received': 0, 'unreachable': False}


def test_un_reseau_injoignable_est_une_mesure_pas_une_sortie_illisible(ping):
    """Sans route, ping ne mesure rien, mais il dit pourquoi : ce n'est pas « illisible ».

    Pixel 3, 28/09 : la mesure rendait None, journalise « Network baseline unreadable » en DEBUG,
    et les runs tournaient sur le contenu en cache, sans rien dire.
    """
    ping(PING_INJOIGNABLE)

    mesure = network_probe.measure_network_baseline('SERIE')

    assert mesure == {'rtt_ms': None, 'packet_loss_pct': None, 'received': 0, 'unreachable': True}


def test_une_sortie_muette_ne_donne_rien(ping):
    ping('')

    assert network_probe.measure_network_baseline('SERIE') is None


def test_une_sortie_illisible_ne_donne_rien(ping):
    ping(PING_ABSENT)

    assert network_probe.measure_network_baseline('SERIE') is None
