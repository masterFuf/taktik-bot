"""La porte du reseau d'un run (`taktik/core/shared/device/network_door.py`).

Un telephone sans aucune route ne lance pas son run : il lirait le cache du telephone et ecrirait
des profils vides comme des mesures (Pixel 3, 28/09). La porte est ouverte par le coeur (les lanceurs
Instagram, le demarrage de session TikTok), donc par la CLI comme par les ponts : les deux chemins
sont tenus par les bancs `tests/unit/one_path/` (« a phone without network »).

Ici, ce que la porte repond a chaque mesure : la lecture elle-meme est celle de la sonde
(`tests/unit/shared/device/test_network_baseline.py`).
"""

import pytest

from taktik.core.shared.device import network_door
from taktik.core.shared.telemetry import clear_telemetry_sink, configure_telemetry_sink

INJOIGNABLE = {'rtt_ms': None, 'packet_loss_pct': None, 'received': 0, 'unreachable': True}
LISIBLE = {'rtt_ms': 42.0, 'packet_loss_pct': 0.0, 'received': 3, 'unreachable': False}


@pytest.fixture
def metriques():
    recues = []
    configure_telemetry_sink(recues.append)
    yield recues
    clear_telemetry_sink()


@pytest.fixture
def sonde(monkeypatch):
    """La mesure que la porte lit, a la place du ping du telephone."""

    def _installer(reponse):
        monkeypatch.setattr(network_door, 'measure_network_baseline', reponse)

    return _installer


def test_un_telephone_sans_route_ne_lance_pas_son_run(sonde, metriques):
    sonde(lambda device_id: dict(INJOIGNABLE))

    with pytest.raises(network_door.NetworkUnreachableError) as refus:
        network_door.open_network_door('SERIE')

    assert refus.value.error_code == 'NETWORK_UNREACHABLE'
    assert refus.value.device_id == 'SERIE'
    # Le motif est dans le message : un hote qui imprime l'exception (la CLI) dit le meme.
    assert 'NETWORK_UNREACHABLE' in str(refus.value)
    assert metriques == []


def test_la_mesure_lisible_voyage_et_le_run_part(sonde, metriques):
    sonde(lambda device_id: dict(LISIBLE))

    assert network_door.open_network_door('SERIE') == LISIBLE

    assert len(metriques) == 1
    assert metriques[0].category == 'network_probe'
    assert metriques[0].action == 'session_baseline'
    assert metriques[0].target == 'SERIE'
    assert metriques[0].detail == {'rtt_ms': 42.0, 'packet_loss_pct': 0.0, 'replies': 3}


def test_la_mesure_avant_une_rotation_porte_son_moment(sonde, metriques):
    sonde(lambda device_id: dict(LISIBLE))

    network_door.open_network_door('SERIE', moment=network_door.BEFORE_IP_ROTATION)

    assert [metrique.action for metrique in metriques] == ['before_ip_rotation']


def test_une_mesure_illisible_ne_bloque_pas(sonde, metriques):
    """Illisible n'est pas injoignable : un telephone sans ping garde son run."""
    sonde(lambda device_id: None)

    assert network_door.open_network_door('SERIE') is None
    assert metriques == []


def test_une_sonde_qui_explose_ne_bloque_pas_le_run(sonde, metriques):
    def _explose(device_id):
        raise RuntimeError('appareil injoignable')

    sonde(_explose)

    assert network_door.open_network_door('SERIE') is None
    assert metriques == []


def test_sans_appareil_on_ne_mesure_rien(sonde, metriques):
    def _jamais(device_id):
        raise AssertionError('aucune mesure ne doit partir sans appareil')

    sonde(_jamais)

    assert network_door.open_network_door('') is None
    assert metriques == []
