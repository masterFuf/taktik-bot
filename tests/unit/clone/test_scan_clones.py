"""scan_clones lists every instance of a platform a phone carries, the Cloner of TAKTIK's included.

The packages of the phone come from a double of `pm list packages` (the ADB door of the detector).
"""

import subprocess

import pytest

from taktik.core.clone.detection import detector

PHONE_PACKAGES = "\n".join(
    f"package:{name}"
    for name in [
        "com.android.chrome",
        "com.instagram.android",
        "com.instagram.androie",
        "com.taktik.ig1",
        "com.taktik.ig2",
        "com.taktik.tt1",
        "com.zhiliaoapp.musically",
    ]
)


@pytest.fixture
def phone(monkeypatch):
    def pm_list(device_id, args, adb_command="adb", timeout=15):
        assert args == ["pm", "list", "packages"]
        return subprocess.CompletedProcess(args, 0, stdout=PHONE_PACKAGES, stderr="")

    monkeypatch.setattr(detector, "run_adb_shell_process", pm_list)


def test_instagram_instances_include_the_taktik_clones(phone):
    found = detector.scan_clones("emulator-5554", platform="instagram")
    assert [clone.package for clone in found] == [
        "com.instagram.android",
        "com.instagram.androie",
        "com.taktik.ig1",
        "com.taktik.ig2",
    ]
    assert [clone.is_original for clone in found] == [True, False, False, False]
    assert found[2].label == "Instagram (clone 1)"


def test_tiktok_instances_include_the_taktik_clones_and_no_instagram_one(phone):
    found = detector.scan_clones("emulator-5554", platform="tiktok")
    assert [clone.package for clone in found] == ["com.taktik.tt1", "com.zhiliaoapp.musically"]
    assert [clone.is_original for clone in found] == [False, True]
