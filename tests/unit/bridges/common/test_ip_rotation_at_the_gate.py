"""La rotation d'IP que les ponts font avant le run (`bridges/common/network.py`).

La mesure du reseau du run n'est plus prise ici : le coeur la prend quand le run demarre, pour les
ponts et la CLI (`tests/unit/shared/device/test_network_door.py`, et les bancs
`tests/unit/one_path/`). Le pont ne mesure que pour sa rotation : un telephone sans route n'a pas
d'IP a changer, et couper sa radio finirait en rotation ratee (`NETWORK_RESET_FAILED`) apres une
longue attente, la ou le motif est `NETWORK_UNREACHABLE`.
"""

import pytest

from bridges.common import network as network_module
from taktik.core.shared.device import network_door
from taktik.core.shared.telemetry import clear_telemetry_sink, configure_telemetry_sink

INJOIGNABLE = {'rtt_ms': None, 'packet_loss_pct': None, 'received': 0, 'unreachable': True}


@pytest.fixture
def metriques():
    recues = []
    configure_telemetry_sink(recues.append)
    yield recues
    clear_telemetry_sink()


def test_sans_rotation_demandee_le_pont_ne_mesure_rien(monkeypatch):
    """La mesure du run est celle du coeur : le pont n'en prend pas une deuxieme a cote."""
    monkeypatch.setattr(
        network_door, 'measure_network_baseline',
        lambda device_id: pytest.fail('le pont ne mesure plus le reseau du run'),
    )
    monkeypatch.setattr(
        network_module, 'perform_network_reset',
        lambda *a, **k: pytest.fail('aucune rotation ne devait etre tentee'),
    )

    assert network_module.enforce_pre_session_ip_rotation({'networkReset': {'enabled': False}}, 'SERIE') is True
    assert network_module.enforce_pre_session_ip_rotation({}, 'SERIE') is True


def test_un_telephone_sans_reseau_ne_tente_aucune_rotation(monkeypatch, metriques):
    """Une mesure « injoignable » arrete le run avant la rotation, avec son code (Pixel 3, 28/09)."""
    monkeypatch.setattr(network_door, 'measure_network_baseline', lambda device_id: dict(INJOIGNABLE))
    erreurs = []
    monkeypatch.setattr(network_module, 'send_error', lambda message, error_code=None, **k: erreurs.append(error_code))
    monkeypatch.setattr(
        network_module, 'perform_network_reset',
        lambda *a, **k: pytest.fail('aucune rotation ne devait etre tentee sans reseau'),
    )

    assert network_module.enforce_pre_session_ip_rotation(
        {'networkReset': {'enabled': True}}, 'SERIE') is False
    assert erreurs == ['NETWORK_UNREACHABLE']


def test_une_mesure_illisible_ne_bloque_pas_la_rotation(monkeypatch):
    """Illisible n'est pas injoignable : un telephone sans ping garde sa rotation."""
    monkeypatch.setattr(network_door, 'measure_network_baseline', lambda device_id: None)
    rotations = []
    monkeypatch.setattr(
        network_module, 'perform_network_reset',
        lambda *a, **k: rotations.append(k.get('method')) or network_module.NetworkResetOutcome(
            verdict='verified', method='data', old_ip='1.1.1.1', new_ip='2.2.2.2',
            attempts=1, commands_ok=True),
    )

    assert network_module.enforce_pre_session_ip_rotation({'networkReset': {'enabled': True}}, 'SERIE') is True
    assert rotations == ['data']


def test_la_mesure_precede_la_rotation(monkeypatch, metriques):
    """Couper la radio d'un telephone sans route n'apprend rien : la mesure passe d'abord, et dit son
    moment (`before_ip_rotation`), distinct de la mesure du run que le coeur prend ensuite."""
    ordre = []
    monkeypatch.setattr(
        network_door, 'measure_network_baseline',
        lambda device_id: ordre.append('mesure') or {'rtt_ms': 10.0, 'packet_loss_pct': 0.0, 'received': 3},
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
    assert [metrique.action for metrique in metriques if metrique.category == 'network_probe'] == \
        ['before_ip_rotation']
