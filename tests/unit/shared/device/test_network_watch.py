"""The network watch of a run (`taktik/core/shared/device/network_watch.py`).

The door measures the phone's network when the run starts; the watch measures it again from a thread
of its own and sets the stop latch (`network_lost`) once a lost network is confirmed. The rule is
tested through `tick()`, one measure at a time, with no thread: the real probe reads the real answers
of ping (`unit.ping_outputs`, the C57S's « connect: Network is unreachable » among them). The thread
itself is tested last, on a fast clock, and is joined before the test ends.
"""

import threading

import pytest

from taktik.core.shared.device import network_door, network_probe, network_watch
from taktik.core.shared.diagnostics import run_halt
from unit.ping_outputs import (
    PING_ABSENT,
    PING_COMPLET,
    PING_INJOIGNABLE,
    PING_SANS_RESUME,
    PING_TOUT_PERDU,
)

#: What the door measured at the start of the run of October 2026 (3/3 replies), and on a network that
#: lets no ping through from the start (a route, 0/3).
DEPART_EN_LIGNE = {'rtt_ms': 377.3, 'packet_loss_pct': 0.0, 'received': 3, 'unreachable': False}
DEPART_SANS_ICMP = {'rtt_ms': None, 'packet_loss_pct': 100.0, 'received': 0, 'unreachable': False}


@pytest.fixture(autouse=True)
def _verrou_leve():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


@pytest.fixture
def telephone(monkeypatch):
    """The phone's ping answers, one per measure, in order; the last one repeats."""
    reponses = []

    def _shell(device_id, command, timeout=15):
        assert command == network_probe._PING_BURST
        return reponses.pop(0) if len(reponses) > 1 else reponses[0]

    monkeypatch.setattr(network_probe, '_shell', _shell)

    def _repondra(*sorties):
        reponses[:] = list(sorties)

    return _repondra


def _veille(depart=DEPART_EN_LIGNE):
    return network_watch.NetworkWatch('SERIE', depart)


def _ticks(veille, n):
    return [veille.tick() for _ in range(n)]


# --- the rule, one measure at a time ----------------------------------------------------------

def test_sans_route_confirme_le_run_s_arrete(telephone):
    """The run of October 2026: airplane mode and Wi-Fi off after the door's measure."""
    telephone(PING_INJOIGNABLE)
    veille = _veille()

    assert veille.tick() is False
    assert run_halt.arret_demande() is None
    assert veille.next_wait() == network_watch.CONFIRMATION_DELAY_S

    assert veille.tick() is True
    arret = run_halt.arret_demande()
    assert arret['code'] == run_halt.NETWORK_LOST
    assert arret['device_id'] == 'SERIE'
    assert 'no route' in arret['detail']


def test_une_coupure_breve_ne_fait_rien(telephone):
    """A Wi-Fi to 4G switch drops the route a second: the confirmation absorbs it."""
    telephone(PING_INJOIGNABLE, PING_COMPLET)
    veille = _veille()

    assert _ticks(veille, 2) == [False, False]
    assert run_halt.arret_demande() is None
    assert veille.next_wait() == network_watch.MEASURE_INTERVAL_S


def test_rien_ne_revient_alors_que_le_depart_repondait(telephone):
    """A route, and 0 of 3 replies, on a network that let ping through at the start."""
    telephone(PING_TOUT_PERDU)

    assert _ticks(_veille(DEPART_EN_LIGNE), 2) == [False, True]
    assert run_halt.arret_demande()['code'] == run_halt.NETWORK_LOST


def test_un_reseau_qui_bloque_le_ping_des_le_depart_ne_declenche_rien(telephone):
    """Seen at the start (0 replies): only the loss of the route can say something then."""
    telephone(PING_TOUT_PERDU)

    assert _ticks(_veille(DEPART_SANS_ICMP), 3) == [False, False, False]
    assert run_halt.arret_demande() is None


def test_une_mesure_illisible_ne_conclut_rien(telephone):
    """adb that does not answer (an empty output) or a shell without ping: no conclusion either way.
    A phone gone is `device_disconnected`'s business."""
    telephone('', PING_ABSENT, '')

    assert _ticks(_veille(), 3) == [False, False, False]
    assert run_halt.arret_demande() is None


def test_une_mesure_illisible_n_est_pas_une_confirmation(telephone):
    telephone(PING_INJOIGNABLE, '', PING_INJOIGNABLE)
    veille = _veille()

    assert _ticks(veille, 3) == [False, False, False]
    assert run_halt.arret_demande() is None


def test_un_reseau_lent_reste_un_reseau(telephone):
    telephone(PING_SANS_RESUME)

    assert _ticks(_veille(), 3) == [False, False, False]
    assert run_halt.arret_demande() is None


def test_un_run_deja_arrete_n_est_plus_veille(telephone):
    """Another stop was seen first (the desktop gone): its motive stays, the watch has nothing to add."""
    telephone(PING_INJOIGNABLE)
    run_halt.demander_arret(run_halt.DESKTOP_GONE, "desktop pid 12: exited")

    assert _veille().tick() is True
    assert run_halt.arret_demande()['code'] == run_halt.DESKTOP_GONE


# --- the door starts it, at the start of a session only ---------------------------------------

@pytest.fixture
def veilles_demarrees(monkeypatch):
    demarrees = []
    monkeypatch.setattr(network_door, 'measure_network_baseline', lambda device_id: dict(DEPART_EN_LIGNE))
    monkeypatch.setattr(network_door, 'start_network_watch',
                        lambda device_id, baseline: demarrees.append((device_id, baseline)))
    return demarrees


def test_la_porte_demarre_la_veille_au_depart_de_la_session(veilles_demarrees):
    network_door.open_network_door('SERIE')

    assert veilles_demarrees == [('SERIE', DEPART_EN_LIGNE)]


def test_jamais_avant_une_rotation_d_ip(veilles_demarrees):
    """A rotation cuts the network on purpose, right after this measure."""
    network_door.open_network_door('SERIE', moment=network_door.BEFORE_IP_ROTATION)

    assert veilles_demarrees == []


def test_ni_sur_une_mesure_illisible(veilles_demarrees, monkeypatch):
    """A phone whose shell has no ping would be measured for nothing, all run long."""
    monkeypatch.setattr(network_door, 'measure_network_baseline', lambda device_id: None)

    network_door.open_network_door('SERIE')

    assert veilles_demarrees == []


# --- the thread -------------------------------------------------------------------------------

@pytest.fixture
def horloge_rapide(monkeypatch):
    monkeypatch.setattr(network_watch, 'MEASURE_INTERVAL_S', 0.01)
    monkeypatch.setattr(network_watch, 'CONFIRMATION_DELAY_S', 0.01)


def _fils_de_veille():
    return [fil for fil in threading.enumerate() if fil.name == network_watch.THREAD_NAME]


def test_le_fil_pose_le_verrou_puis_s_arrete(telephone, horloge_rapide):
    telephone(PING_INJOIGNABLE)

    veille = network_watch.start_network_watch('SERIE', DEPART_EN_LIGNE)
    veille.join(timeout=5)

    assert not veille.is_alive()
    assert run_halt.arret_demande()['code'] == run_halt.NETWORK_LOST
    network_watch.stop_network_watch()
    assert _fils_de_veille() == []


def test_une_nouvelle_veille_remplace_la_precedente(telephone, horloge_rapide):
    telephone(PING_COMPLET)

    premiere = network_watch.start_network_watch('SERIE', DEPART_EN_LIGNE)
    seconde = network_watch.start_network_watch('SERIE', DEPART_EN_LIGNE)

    assert not premiere.is_alive()
    assert seconde.is_alive()
    network_watch.stop_network_watch()
    assert not seconde.is_alive()
    assert _fils_de_veille() == []


def test_une_veille_arretee_pendant_sa_mesure_ne_pose_rien(telephone, horloge_rapide, monkeypatch):
    """The Lab stops the watch of the previous action before it lifts the latch for the next one: a
    measure still running when the watch is stopped must not stop the next action."""
    mesure_en_cours = threading.Event()
    reprendre = threading.Event()
    lecture = network_probe._shell

    def _ping_lent(device_id, command, timeout=15):
        mesure_en_cours.set()
        reprendre.wait(timeout=5)
        return lecture(device_id, command, timeout)

    telephone(PING_INJOIGNABLE)
    veille = network_watch.NetworkWatch('SERIE', DEPART_EN_LIGNE)
    veille.suspected = 'no route to the Internet (ping: network is unreachable)'
    monkeypatch.setattr(network_probe, '_shell', _ping_lent)
    veille.start()
    assert mesure_en_cours.wait(timeout=5)

    arret = threading.Thread(target=veille.stop)
    arret.start()
    for _ in range(500):
        if veille.stop_requested:
            break
        threading.Event().wait(0.01)
    reprendre.set()
    arret.join(timeout=5)

    assert not veille.is_alive()
    assert run_halt.arret_demande() is None


def test_a_phone_that_locks_during_the_run_stops_it_with_its_motive(monkeypatch):
    """Nothing keeps the screen on during a run: a long wait or the power button lock the phone, and
    the run would go on tapping on the lock screen. Lifted when it can be, the latch when it stays."""
    monkeypatch.setattr(network_watch, "phone_locked_after_lift", lambda device_id: True)
    monkeypatch.setattr(network_watch, "measure_network_baseline", lambda device_id: dict(DEPART_EN_LIGNE))

    assert network_watch.NetworkWatch("SERIAL", DEPART_EN_LIGNE).tick() is True

    halt = run_halt.arret_demande()
    assert halt["code"] == run_halt.PHONE_LOCKED and halt["device_id"] == "SERIAL"


def test_a_lock_lifted_during_the_run_does_not_stop_it(monkeypatch):
    monkeypatch.setattr(network_watch, "phone_locked_after_lift", lambda device_id: False)
    monkeypatch.setattr(network_watch, "measure_network_baseline", lambda device_id: dict(DEPART_EN_LIGNE))

    assert network_watch.NetworkWatch("SERIAL", DEPART_EN_LIGNE).tick() is False
    assert run_halt.arret_demande() is None
