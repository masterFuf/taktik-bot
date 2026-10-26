"""Le verrou d'arret : ce qu'il retient, et ce que la session en fait.

Ce module existe parce que DETECTER n'est pas ARRETER. Le lien ADB tombe etait deja constate,
emis, journalise -- et le run continuait jusqu'a son plafond, en avalant une exception par tour.
Les proprietes testees ici sont celles dont la perte ramenerait ce comportement sans qu'aucun test
existant ne bouge.
"""

import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE))

from taktik.core.shared.diagnostics import run_halt  # noqa: E402
from taktik.core.social_media.instagram.workflows.common.session import stop_reasons  # noqa: E402


@pytest.fixture(autouse=True)
def verrou_leve():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


def test_aucun_arret_par_defaut():
    """Un run qui demarre avec le verrou du precedent s'arreterait d'emblee."""
    assert run_halt.arret_demande() is None


def test_le_premier_constat_gagne():
    """Le premier a le contexte ; une fois le lien perdu, les suivants ne savent plus rien."""
    run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED, "le telephone ne repond plus")
    run_halt.demander_arret(run_halt.TARGET_APP_CRASHED, "arrive trop tard")

    constat = run_halt.arret_demande()
    assert constat["code"] == run_halt.DEVICE_DISCONNECTED
    assert constat["detail"] == "le telephone ne repond plus"


def test_le_contexte_voyage():
    run_halt.demander_arret(run_halt.TARGET_APP_CRASHED, "aerr_close", platform="tiktok")

    assert run_halt.arret_demande()["platform"] == "tiktok"


def test_arret_demande_rend_une_copie():
    run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED)
    run_halt.arret_demande()["code"] = "saccage"

    assert run_halt.arret_demande()["code"] == run_halt.DEVICE_DISCONNECTED


def test_la_remise_a_zero_leve_le_verrou():
    run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED)
    run_halt.reinitialiser()

    assert run_halt.arret_demande() is None


# --- ce que la session en fait ------------------------------------------------------------

def test_un_appareil_perdu_classe_le_run_en_interrompu():
    """C'est tout l'enjeu : un run sans telephone ne s'est pas TERMINE, il a echoue."""
    motif = stop_reasons.device_disconnected("le telephone ne repond plus")

    assert motif.code == "device_disconnected"
    assert motif.family == stop_reasons.FAMILY_FAILED
    assert stop_reasons.terminal_status(motif) == stop_reasons.STATUS_INTERRUPTED
    assert stop_reasons.ends_the_session(motif) is True


def test_une_application_plantee_classe_le_run_en_interrompu():
    motif = stop_reasons.target_app_crashed("android:id/aerr_close")

    assert motif.code == "target_app_crashed"
    assert stop_reasons.terminal_status(motif) == stop_reasons.STATUS_INTERRUPTED


def test_les_codes_passes_en_chaine_brute_sont_classes_aussi():
    """Un vieux client passe le code sans l'objet ; il ne doit pas retomber sur COMPLETED."""
    assert stop_reasons.terminal_status("device_disconnected") == stop_reasons.STATUS_INTERRUPTED
    assert stop_reasons.terminal_status("target_app_crashed") == stop_reasons.STATUS_INTERRUPTED


def test_le_motif_reste_la_phrase_anglaise_qu_il_a_toujours_ete():
    """Le contrat du catalogue : `str(reason)` est la phrase, `code` est la charge utile."""
    motif = stop_reasons.device_disconnected()

    assert str(motif) == "Device disconnected"
    assert motif.event_fields()["reason_code"] == "device_disconnected"


def test_le_detail_est_plafonne():
    motif = stop_reasons.device_disconnected("x" * 400)

    assert len(motif.params["detail"]) == 120


# --- deux fils qui constatent en meme temps ---------------------------------------------------

def test_deux_fils_qui_constatent_ensemble_n_ecrivent_qu_un_constat(monkeypatch):
    """Le chien de garde de l'app de bureau et la veille du reseau posent le verrou depuis leur fil.

    Le premier constat gagne, une seule fois : le temoin (l'historique de sante du compte) n'est
    prevenu qu'une fois. Le second fil arrive ici pendant que le premier ecrit son constat (entre
    la lecture « pas encore d'arret » et l'ecriture), la fenetre ou deux constats passaient.
    """
    import threading

    prevenus = []
    run_halt.configurer_temoin(prevenus.append)
    second = threading.Thread(target=run_halt.demander_arret, args=(run_halt.DESKTOP_GONE, "le second"))
    heure = run_halt.time.time

    def horloge_qui_laisse_passer_le_second():
        if not second.is_alive() and second.ident is None:
            second.start()
            second.join(timeout=0.5)
        return heure()

    monkeypatch.setattr(run_halt.time, "time", horloge_qui_laisse_passer_le_second)
    run_halt.demander_arret(run_halt.NETWORK_LOST, "le premier")
    monkeypatch.setattr(run_halt.time, "time", heure)
    second.join(timeout=5)

    assert not second.is_alive()
    assert run_halt.arret_demande()["code"] == run_halt.NETWORK_LOST
    assert [constat["code"] for constat in prevenus] == [run_halt.NETWORK_LOST]
