"""La mesure du reseau posee sur la porte que TOUS les ponts traversent au demarrage de session.

Elle ne doit, sous aucune panne, changer ce que cette porte repond : la mesure voyage par la
telemetrie, ne part pas sans appareil, precede la rotation d'IP, et une sonde qui explose ne bloque
pas le run. La lecture de la mesure elle-meme (la sonde du coeur) est tenue par
`tests/unit/shared/device/test_network_baseline.py`.
"""

import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE))

from bridges.common import network as network_module  # noqa: E402
from taktik.core.shared.telemetry import (  # noqa: E402
    clear_telemetry_sink,
    configure_telemetry_sink,
)


@pytest.fixture
def metriques():
    recues = []
    configure_telemetry_sink(recues.append)
    yield recues
    clear_telemetry_sink()


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
