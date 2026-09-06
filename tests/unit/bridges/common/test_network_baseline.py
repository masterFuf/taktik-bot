"""Ce que le telephone voit du reseau au demarrage d'un run.

Une mesure, pas une decision : rien ne lit encore cette valeur pour rallonger une attente. Elle
existe parce que « le reseau etait-il lent ? » n'a jamais eu de reponse mesuree -- et c'est par
inference que les 65 likes non realises du week-end du 05-06/09 ont failli etre attribues au
mauvais coupable.

Deux proprietes comptent ici. La premiere : le parsing doit survivre aux deux formats de `ping`
(celui qui imprime la ligne de resume, et toybox qui parfois ne l'imprime pas). La seconde, plus
importante : cette mesure est posee sur la porte que TOUS les bridges traversent au demarrage de
session -- elle ne doit donc, sous aucune panne, changer ce que cette porte repond.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from bridges.common.device import network as network_module  # noqa: E402
from bridges.common.device import network_probe  # noqa: E402
from taktik.core.shared.telemetry import (  # noqa: E402
    clear_telemetry_sink,
    configure_telemetry_sink,
)

PING_COMPLET = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=23.4 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=24.9 ms
64 bytes from 1.1.1.1: icmp_seq=3 ttl=57 time=26.4 ms

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 23.418/24.905/26.377/1.207 ms"""

PING_SANS_RESUME = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=100.0 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=200.0 ms"""

PING_TOUT_PERDU = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2015ms"""


@pytest.fixture
def ping(monkeypatch):
    """Remplace l'appel ADB : ces tests portent sur la lecture, pas sur le telephone."""

    def _installer(sortie):
        monkeypatch.setattr(network_probe, '_shell', lambda device_id, cmd, timeout=15: sortie)

    return _installer


@pytest.fixture
def metriques():
    recues = []
    configure_telemetry_sink(recues.append)
    yield recues
    clear_telemetry_sink()


# --- ce que le shell du telephone recoit ------------------------------------------------------

def test_la_commande_arrive_quotee_au_telephone(monkeypatch):
    """La panne qui rendait toutes les sondes muettes, et qu'aucun test ne voyait.

    `adb shell` colle ses arguments avec des espaces et envoie UNE ligne de commande, sans les
    requoter : `["sh", "-c", "ping -c 3 1.1.1.1"]` arrive comme `sh -c ping -c 3 1.1.1.1`, ou
    `sh -c ping` lance ping sans aucun argument. Mesure sur appareil le 2026-09-06 : chaque sonde
    de ce module rendait le texte d'usage de ping ou rien -- donc `read_public_ip` rendait None sur
    toute la flotte, et une rotation d'IP ne pouvait jamais etre verifiee.
    """
    vus = []

    class _Resultat:
        stdout = 'ok'
        stderr = ''

    monkeypatch.setattr(
        network_probe, 'run_adb_shell_process',
        lambda device_id, args, timeout=10: vus.append(args) or _Resultat(),
    )

    commande = "printf 'GET / HTTP/1.1' | toybox nc -w 8 ifconfig.me 80"
    network_probe._shell('SERIE', commande)

    assert vus[0][:2] == ['sh', '-c']
    # Un seul mot pour le shell du telephone, quotes internes comprises.
    assert vus[0][2].startswith("'") and vus[0][2].endswith("'")
    assert len(vus[0]) == 3


def test_le_shell_ne_leve_jamais(monkeypatch):
    def _explose(device_id, args, timeout=10):
        raise OSError('adb absent')

    monkeypatch.setattr(network_probe, 'run_adb_shell_process', _explose)

    assert network_probe._shell('SERIE', 'ping -c 1 1.1.1.1') == ''


# --- la lecture ------------------------------------------------------------------------------

def test_la_moyenne_vient_de_la_ligne_de_resume(ping):
    ping(PING_COMPLET)

    mesure = network_probe.measure_network_baseline('SERIE')

    assert mesure == {'rtt_ms': 24.9, 'packet_loss_pct': 0.0, 'received': 3}


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

    assert mesure == {'rtt_ms': None, 'packet_loss_pct': 100.0, 'received': 0}


def test_une_sortie_muette_ne_donne_rien(ping):
    ping('')

    assert network_probe.measure_network_baseline('SERIE') is None


def test_une_sortie_illisible_ne_donne_rien(ping):
    ping('/system/bin/sh: ping: not found')

    assert network_probe.measure_network_baseline('SERIE') is None


# --- l'emission ------------------------------------------------------------------------------

def test_la_mesure_voyage(monkeypatch, metriques):
    monkeypatch.setattr(
        network_module, 'measure_network_baseline',
        lambda device_id: {'rtt_ms': 42.0, 'packet_loss_pct': 0.0, 'received': 3},
    )

    network_module._emit_network_baseline('SERIE')

    emises = [m for m in metriques if m.category == 'network_probe']
    assert len(emises) == 1
    assert emises[0].action == 'session_baseline'
    assert emises[0].target == 'SERIE'
    assert emises[0].detail == {'rtt_ms': 42.0, 'packet_loss_pct': 0.0, 'replies': 3}


def test_sans_appareil_on_ne_mesure_rien(monkeypatch, metriques):
    def _jamais(device_id):
        raise AssertionError('aucune mesure ne doit partir sans appareil')

    monkeypatch.setattr(network_module, 'measure_network_baseline', _jamais)

    network_module._emit_network_baseline('')

    assert metriques == []


# --- ce que la porte commune doit continuer a repondre ----------------------------------------

def test_une_sonde_qui_explose_ne_bloque_pas_le_run(monkeypatch, metriques):
    """La porte est traversee par TOUS les bridges au demarrage : elle ne doit rien casser."""

    def _explose(device_id):
        raise RuntimeError('appareil injoignable')

    monkeypatch.setattr(network_module, 'measure_network_baseline', _explose)

    assert network_module.enforce_pre_session_ip_rotation({}, 'SERIE') is True
    assert metriques == []


def test_la_rotation_non_demandee_repond_toujours_oui(monkeypatch):
    monkeypatch.setattr(
        network_module, 'measure_network_baseline',
        lambda device_id: {'rtt_ms': 42.0, 'packet_loss_pct': 0.0, 'received': 3},
    )
    appels = []
    monkeypatch.setattr(
        network_module, 'perform_network_reset',
        lambda *a, **k: appels.append(a) or pytest.fail('aucune rotation ne devait etre tentee'),
    )

    assert network_module.enforce_pre_session_ip_rotation(
        {'networkReset': {'enabled': False}}, 'SERIE') is True
    assert appels == []


def test_la_mesure_precede_la_rotation(monkeypatch):
    """Mesurer APRES aurait lu le reseau du nouvel operateur, pas celui ou le run va tourner.

    Elle doit aussi partir meme quand aucune rotation n'est demandee -- sinon la baseline
    n'existerait que sur les runs qui changent d'IP.
    """
    ordre = []
    monkeypatch.setattr(
        network_module, 'measure_network_baseline',
        lambda device_id: ordre.append('mesure') or {
            'rtt_ms': 10.0, 'packet_loss_pct': 0.0, 'received': 3},
    )
    monkeypatch.setattr(
        network_module, 'perform_network_reset',
        lambda *a, **k: ordre.append('rotation') or network_module.NetworkResetOutcome(
            verdict='verified', method='data', old_ip='1.1.1.1', new_ip='2.2.2.2',
            attempts=1, commands_ok=True),
    )

    assert network_module.enforce_pre_session_ip_rotation(
        {'networkReset': {'enabled': True}}, 'SERIE') is True
    assert ordre == ['mesure', 'rotation']
