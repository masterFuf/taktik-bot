"""Le garde de premier plan : il distingue « je suis ailleurs » de tout le reste.

Le risque du contrôle n'est pas de rater une sortie, c'est d'en inventer une : conclure « ce run
est sorti de l'application » quand l'appareil est simplement illisible arrêterait un run qui va
bien. Chaque cas où la réponse doit être `None` est donc testé une fois.
"""

import time

import pytest

from taktik.core.clone.packages.package_map import belongs_to_platform
from taktik.core.shared.diagnostics import foreground_guard as fg


class _Device:
    def __init__(self, package):
        self._package = package

    def app_current(self):
        return {"package": self._package}


class _DeviceQuiLeve:
    def app_current(self):
        raise RuntimeError("adb down")


@pytest.fixture(autouse=True)
def _reset():
    fg.reinitialiser()
    yield
    fg.reinitialiser()


# ── belongs_to_platform : la définition unique ────────────────────────────────

@pytest.mark.parametrize("package,platform,attendu", [
    ("com.instagram.android", "instagram", True),
    ("com.zhiliaoapp.musically", "tiktok", True),
    # Les trois autres paquets TikTok qui circulent : comparer à UNE constante les rejetait.
    ("com.ss.android.ugc.trill", "tiktok", True),
    ("com.ss.android.ugc.aweme", "tiktok", True),
    ("com.bytedance.trill", "tiktok", True),
    # Les clones Taktik portent un paquet suffixé : aucun ne figure dans les variantes.
    ("com.instagram.android.clone3", "instagram", True),
    ("com.zhiliaoapp.musically.clone2", "tiktok", True),
    # Une vraie sortie d'application.
    ("com.android.chrome", "instagram", False),
    ("com.google.android.apps.nexuslauncher", "tiktok", False),
    ("com.android.vending", "instagram", False),
    # Chacune est l'app de l'AUTRE plateforme : appartenir quelque part ne suffit pas.
    ("com.instagram.android", "tiktok", False),
    ("com.zhiliaoapp.musically", "instagram", False),
    # Rien à décider.
    (None, "instagram", False),
    ("", "tiktok", False),
    ("com.instagram.android", "threads", False),
])
def test_appartenance_paquet(package, platform, attendu):
    assert belongs_to_platform(package, platform) is attendu


# ── Le garde ──────────────────────────────────────────────────────────────────

def test_signale_le_paquet_etranger():
    assert fg.paquet_etranger(_Device("com.android.chrome"), "instagram") == "com.android.chrome"


def test_se_tait_quand_on_est_dans_l_application():
    assert fg.paquet_etranger(_Device("com.instagram.android"), "instagram") is None


def test_se_tait_dans_un_clone():
    # Un clone EST l'application. Le signaler arrêterait des runs parfaitement sains.
    assert fg.paquet_etranger(_Device("com.instagram.android.clone7"), "instagram") is None


def test_un_appareil_illisible_ne_prouve_rien():
    # Ni `None`, ni une exception ne veulent dire « une autre application ».
    assert fg.paquet_etranger(_DeviceQuiLeve(), "instagram") is None
    fg.reinitialiser()
    assert fg.paquet_etranger(_Device(None), "instagram") is None
    fg.reinitialiser()
    assert fg.paquet_etranger(None, "instagram") is None


def test_sans_plateforme_le_garde_est_inactif():
    # Une classe qui ne déclare pas sa plateforme se comporte exactement comme avant.
    assert fg.paquet_etranger(_Device("com.android.chrome"), None) is None


def test_l_intervalle_borne_le_cout():
    device = _Device("com.android.chrome")
    assert fg.paquet_etranger(device, "instagram") == "com.android.chrome"
    # Le deuxième échec dans la foulée ne repaie pas la lecture (~440 ms sur un Pixel).
    assert fg.paquet_etranger(device, "instagram") is None
    # `force` sert aux appelants qui ont une raison de savoir tout de suite.
    assert fg.paquet_etranger(device, "instagram", force=True) == "com.android.chrome"


def test_l_intervalle_se_rouvre(monkeypatch):
    device = _Device("com.android.chrome")
    assert fg.paquet_etranger(device, "instagram") == "com.android.chrome"
    depart = time.monotonic()
    monkeypatch.setattr(fg.time, "monotonic", lambda: depart + fg.INTERVALLE_MINIMUM_S + 0.1)
    assert fg.paquet_etranger(device, "instagram") == "com.android.chrome"


def test_un_ctrl_c_traverse_le_garde():
    # Le `except Exception` avale les pannes ADB, pas un arrêt demandé par l'opérateur : un
    # KeyboardInterrupt doit continuer à remonter, sinon Ctrl+C ne rendrait plus la main.
    class Interrompu:
        def app_current(self):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        fg.paquet_etranger(Interrompu(), "instagram")
