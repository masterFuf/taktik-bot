"""The selector catalog must be matched to the phone as soon as we connect to it.

Bridges have always done this in their own connect(). The standalone CLI has no such base
class, and an audit found the patch reached only two of its entry points -- so an open-source
user whose phone had auto-updated ran the baseline catalog nearly everywhere. The funnel every
caller shares is DeviceManager.connect(), so that is where it belongs now.
"""

import pytest

from taktik.core.compat.selectors import setup as compat_setup
from taktik.core.shared.device import manager as manager_module
from taktik.core.social_media.tiktok.ui.selectors.shell.auth.account_switch import (
    ACCOUNT_SWITCH_SELECTORS,
)
from taktik.core.social_media.tiktok.ui.selectors.flows.publish import (
    PUBLISH_COMPOSER_SELECTORS,
    PUBLISH_MEDIA_PICKER_SELECTORS,
)


@pytest.fixture(autouse=True)
def restore_tiktok_selector_catalogs(monkeypatch):
    """Keep process-global selector overrides from leaking into later tests."""
    for singleton in compat_setup.TIKTOK_SELECTOR_DOMAINS.values():
        for field_name, value in vars(singleton).items():
            if isinstance(value, list):
                monkeypatch.setattr(singleton, field_name, list(value))


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


def test_tiktok_4673_patches_the_native_account_switcher_catalog(monkeypatch):
    for field_name, selectors in vars(ACCOUNT_SWITCH_SELECTORS).items():
        monkeypatch.setattr(ACCOUNT_SWITCH_SELECTORS, field_name, list(selectors))

    patched = compat_setup.apply_version_overrides("tiktok", "46.7.3")

    assert patched >= 2
    assert ":id/su7" in ACCOUNT_SWITCH_SELECTORS.profile_switcher_button[0]
    assert ":id/lkp" in ACCOUNT_SWITCH_SELECTORS.account_rows[0]


def test_tiktok_4673_patches_the_publish_media_picker_catalog(monkeypatch):
    for field_name, selectors in vars(PUBLISH_MEDIA_PICKER_SELECTORS).items():
        monkeypatch.setattr(PUBLISH_MEDIA_PICKER_SELECTORS, field_name, list(selectors))

    patched = compat_setup.apply_version_overrides("tiktok", "46.7.3")

    assert patched >= 6
    assert ":id/upload_hot_area" in PUBLISH_MEDIA_PICKER_SELECTORS.upload_btn[0]
    assert ":id/jfy" in PUBLISH_MEDIA_PICKER_SELECTORS.gallery_first_item[0]
    assert ":id/viewpager_choose_media" in PUBLISH_MEDIA_PICKER_SELECTORS._gallery_picker_xml_markers
    assert ":id/xip" in PUBLISH_MEDIA_PICKER_SELECTORS.next_btn[0]


def test_tiktok_4673_patches_the_real_caption_and_hashtag_catalog(monkeypatch):
    for field_name, selectors in vars(PUBLISH_COMPOSER_SELECTORS).items():
        monkeypatch.setattr(PUBLISH_COMPOSER_SELECTORS, field_name, list(selectors))

    patched = compat_setup.apply_version_overrides("tiktok", "46.7.3")

    assert patched >= 10
    assert ":id/h3a" in PUBLISH_COMPOSER_SELECTORS.caption_input[0]
    assert any(":id/t66" in selector for selector in PUBLISH_COMPOSER_SELECTORS.post_btn)
    assert any(":id/t6b" in selector for selector in PUBLISH_COMPOSER_SELECTORS.post_btn)
    assert ":id/h3a" in PUBLISH_COMPOSER_SELECTORS._post_screen_xml_markers_base
    assert ":id/jt_" in PUBLISH_COMPOSER_SELECTORS.hashtag_suggestion_nodes[0]
    assert ":id/f15" in PUBLISH_COMPOSER_SELECTORS.hashtag_suggestion_rows[0]


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
