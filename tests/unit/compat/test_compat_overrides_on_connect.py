"""The selector catalog must be matched to the phone as soon as we connect to it.

Bridges have always done this in their own connect(). The standalone CLI has no such base
class, and an audit found the patch reached only two of its entry points -- so an open-source
user whose phone had auto-updated ran the baseline catalog nearly everywhere. The funnel every
caller shares is DeviceManager.connect(), so that is where it belongs now.
"""

import pytest

from taktik.core.compat.selectors import setup as compat_setup
from taktik.core.shared.device import manager as manager_module


@pytest.fixture
def fake_versions(monkeypatch):
    """Answer a version per package, and record what was asked and what was patched."""
    asked = []
    patched = []

    def _version(device_id, package_name, platform):
        asked.append(package_name)
        return {"com.instagram.android": "442.0.0.46.79", "com.ss.android.ugc.trill": "46.6.3"}.get(package_name)

    def _apply(platform, version):
        patched.append((platform, version))
        return 7

    monkeypatch.setattr(
        "taktik.core.shared.device.app_inspection.get_installed_app_version", _version
    )
    monkeypatch.setattr(compat_setup, "apply_version_overrides", _apply)
    return asked, patched


def test_both_platforms_are_patched_from_what_is_installed(fake_versions):
    asked, patched = fake_versions
    applied = compat_setup.apply_overrides_for_device("serial-1")
    assert applied == {"instagram": 7, "tiktok": 7}
    assert ("instagram", "442.0.0.46.79") in patched
    assert ("tiktok", "46.6.3") in patched


def test_tiktok_is_found_under_a_variant_package(fake_versions):
    # A phone carrying the `trill` build has TikTok installed even though the canonical
    # package answers nothing; stopping at the first package would report it absent.
    asked, _patched = fake_versions
    compat_setup.apply_overrides_for_device("serial-1")
    assert "com.zhiliaoapp.musically" in asked
    assert "com.ss.android.ugc.trill" in asked


def test_an_absent_app_is_simply_not_patched(monkeypatch):
    monkeypatch.setattr(
        "taktik.core.shared.device.app_inspection.get_installed_app_version",
        lambda *args, **kwargs: None,
    )
    assert compat_setup.apply_overrides_for_device("serial-1") == {}


def test_a_failure_to_read_never_stops_a_run(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("adb went away")

    monkeypatch.setattr(
        "taktik.core.shared.device.app_inspection.get_installed_app_version", _boom
    )
    assert compat_setup.apply_overrides_for_device("serial-1") == {}


def test_connect_patches_once_per_device(monkeypatch):
    calls = []
    monkeypatch.setattr(
        manager_module.DeviceManager,
        "_apply_selector_overrides",
        staticmethod(lambda device_id: calls.append(device_id)),
    )
    monkeypatch.setattr(manager_module.u2, "connect", lambda device_id: object())

    manager = manager_module.DeviceManager()
    assert manager.connect("serial-1", verify_atx=False)
    assert manager.connect("serial-1", verify_atx=False)
    assert calls == ["serial-1"]

    assert manager.connect("serial-2", verify_atx=False)
    assert calls == ["serial-1", "serial-2"]
