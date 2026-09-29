"""Une capture d'échec dit sur quelle version, dans quelle langue et sur quel téléphone elle a été prise.

`miss_capture` appelait `capture_surface` sans version, sans langue ni appareil : les 1 833 fiches
`selector_miss` du bot (`captures.jsonl`) ont `appVersion`, `language` et `deviceModel` vides, et le
corpus des captures (rapport du 28/09) les laisse « version inconnue » (530 des 658 captures
Instagram sans version). Ses appelants (`_find_and_click`, la grille de profil introuvable) ne les
tiennent pas non plus ; le processus, lui, les a lus : la version par `get_installed_app_version`
à la connexion, la langue par la détection de la plateforme, l'appareil par sa série.

Le téléphone ci-dessous montre un vrai écran d'Instagram 410 en français (le fil,
`ig410_fr_home_feed.xml`, Pixel 3, anonymisé) ; la version et la langue sont lues par les fonctions
de production, sur les réponses que ce téléphone donne à adb.
"""

import json

import pytest
from PIL import Image

from taktik.core.shared.device import app_inspection
from taktik.core.shared.diagnostics import miss_capture, surface_capture
from taktik.core.social_media.instagram.ui import language as instagram_language
from unit.paths import CORE

SERIAL = "phone-4a"
PACKAGE = "com.instagram.android"
FEED = (CORE / "tests/unit/social_media/instagram/fixtures/ig410_fr_home_feed.xml"
        ).read_text(encoding="utf-8")


class _Phone:
    """Ce que la capture demande au téléphone : l'écran, l'application au premier plan, l'image."""

    serial = SERIAL

    def dump_hierarchy(self, *_a, **_k):
        return FEED

    def app_current(self):
        return {"package": PACKAGE}

    def screenshot(self, *_a, **_k):
        return Image.new("RGB", (108, 222))


class _Answer:
    def __init__(self, stdout):
        self.stdout = stdout
        self.returncode = 0


def _adb_process(device_id, command_args, **_kwargs):
    """`pm list packages` et `dumpsys package` d'un téléphone qui a Instagram 410."""
    assert device_id == SERIAL
    if command_args[:2] == ["pm", "list"]:
        return _Answer(f"package:{PACKAGE}\n")
    if command_args[:2] == ["dumpsys", "package"]:
        return _Answer("    versionCode=374109040 minSdk=28 targetSdk=34\n    versionName=410.0.0.53.71\n")
    raise AssertionError(command_args)


def _adb_shell(device_id, command):
    assert device_id == SERIAL
    if command == "getprop ro.product.model":
        return "Pixel 4a\n"
    raise AssertionError(command)


@pytest.fixture
def phone(monkeypatch, tmp_path):
    miss_capture.reinitialiser()
    monkeypatch.setattr(surface_capture, "captures_dir", lambda platform, surface: str(tmp_path / platform / surface))
    monkeypatch.setattr(app_inspection, "run_adb_shell_process", _adb_process)
    monkeypatch.setattr(miss_capture, "run_adb_shell", _adb_shell, raising=False)
    monkeypatch.setattr(instagram_language._DETECTION, "_detected_lang", None)
    yield _Phone(), tmp_path
    miss_capture.reinitialiser()


def test_une_capture_d_echec_dit_version_langue_et_appareil(phone):
    device, tmp_path = phone
    # Ce que le processus a lu en se connectant, par les fonctions de production.
    assert app_inspection.get_installed_app_version(SERIAL, PACKAGE, "instagram") == "410.0.0.53.71"
    assert instagram_language.detect_language(device) == "fr"

    record = miss_capture.capturer_echec(device, selectors=["//introuvable"], platform="instagram")

    assert (record["appVersion"], record["language"], record["deviceModel"], record["deviceSerial"]) == (
        "410.0.0.53.71", "fr", "Pixel 4a", SERIAL)
    line = json.loads((tmp_path / "instagram" / miss_capture.SURFACE / "captures.jsonl")
                      .read_text(encoding="utf-8").splitlines()[-1])
    assert (line["appVersion"], line["language"], line["deviceModel"], line["deviceSerial"]) == (
        "410.0.0.53.71", "fr", "Pixel 4a", SERIAL)


def test_ce_que_l_appelant_sait_passe_avant(phone):
    device, _ = phone
    app_inspection.get_installed_app_version(SERIAL, PACKAGE, "instagram")

    record = miss_capture.capturer_echec(device, selectors=["//introuvable"], platform="instagram",
                                         app_version="447.0.0.55.81", language="en")

    assert (record["appVersion"], record["language"]) == ("447.0.0.55.81", "en")


def test_sans_rien_de_lu_les_champs_restent_vides_et_rien_ne_casse(phone):
    """Une plateforme dont ce processus n'a lu ni la version ni la langue : vide (inconnu), pas une
    valeur devinée."""
    device, _ = phone

    record = miss_capture.capturer_echec(device, selectors=["//introuvable"], platform="youtube")

    assert (record["appVersion"], record["language"]) == ("", "")
    assert record["deviceSerial"] == SERIAL
