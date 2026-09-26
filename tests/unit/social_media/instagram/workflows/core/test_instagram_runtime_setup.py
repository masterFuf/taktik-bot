from taktik.core.social_media.instagram.workflows.core import runtime_setup
from taktik.core.social_media.instagram.workflows.core.runtime_setup import (
    prepare_instagram_automation_runtime,
    prepare_instagram_selectors,
)


class FakeAutomation:
    def __init__(self):
        self.config = None
        self.package_name = None
        self.device = object()


def test_prepare_runtime_applies_config_package_version_clone_and_language(monkeypatch):
    calls = []
    logs = []

    monkeypatch.setattr(runtime_setup, "set_active_package", lambda package: calls.append(("active", package)))
    # apply_version_overrides is imported lazily inside prepare_*_runtime (to break a
    # circular import), so it resolves from its owner module at call time — patch there.
    monkeypatch.setattr(
        "taktik.core.compat.selectors.setup.apply_version_overrides",
        lambda platform, version: calls.append(("version", platform, version)) or 2,
    )
    monkeypatch.setattr(
        runtime_setup,
        "patch_selectors_for_package",
        lambda platform, package: calls.append(("clone", platform, package)) or 1,
    )
    monkeypatch.setattr(
        runtime_setup,
        "detect_and_optimize",
        lambda device: calls.append(("language", device)) or "fr",
    )

    automation = FakeAutomation()
    workflow_config = {"actions": []}

    prepare_instagram_automation_runtime(
        automation=automation,
        workflow_config=workflow_config,
        package_name="com.instagram.android.c1",
        installed_version_provider=lambda: "321.0.0",
        log=lambda level, message: logs.append((level, message)),
    )

    assert automation.config is workflow_config
    assert automation.package_name == "com.instagram.android.c1"
    assert calls == [
        ("active", "com.instagram.android.c1"),
        ("version", "instagram", "321.0.0"),
        ("clone", "instagram", "com.instagram.android.c1"),
        ("language", automation.device),
    ]
    assert ("info", "Dynamic config applied") in logs
    assert ("info", "Applied 2 selector override(s) for Instagram v321.0.0") in logs
    assert ("info", "Patched 1 selector(s) for clone: com.instagram.android.c1") in logs
    assert ("info", "App language detected: FR") in logs


def test_prepare_runtime_uses_official_package_without_clone(monkeypatch):
    calls = []

    monkeypatch.setattr(runtime_setup, "set_active_package", lambda package: calls.append(("active", package)))
    monkeypatch.setattr(
        runtime_setup,
        "patch_selectors_for_package",
        lambda platform, package: calls.append(("clone", platform, package)) or 1,
    )
    monkeypatch.setattr(runtime_setup, "detect_and_optimize", lambda device: "en")

    automation = FakeAutomation()

    prepare_instagram_automation_runtime(
        automation=automation,
        workflow_config={},
    )

    assert automation.package_name == "com.instagram.android"
    assert calls == [("active", "com.instagram.android")]


def _record_setup(monkeypatch, calls):
    monkeypatch.setattr(runtime_setup, "set_active_package", lambda package: calls.append(("active", package)))
    monkeypatch.setattr(
        "taktik.core.compat.selectors.setup.apply_version_overrides",
        lambda platform, version: calls.append(("version", platform, version)) or 3,
    )
    monkeypatch.setattr(
        runtime_setup,
        "patch_selectors_for_package",
        lambda platform, package: calls.append(("clone", platform, package)) or 0,
    )
    monkeypatch.setattr(runtime_setup, "detect_and_optimize", lambda device: calls.append(("language", device)) or "en")


def test_the_shared_setup_is_version_then_clone_then_language(monkeypatch):
    """The part every Instagram launcher shares: no automation object, no active package."""
    calls = []
    logs = []
    _record_setup(monkeypatch, calls)
    device = object()

    prepare_instagram_selectors(
        device=device,
        package_name="com.instagram.android.c1",
        installed_version_provider=lambda: "447.0.0.55.81",
        log=lambda level, message: logs.append((level, message)),
    )

    assert calls == [
        ("version", "instagram", "447.0.0.55.81"),
        ("clone", "instagram", "com.instagram.android.c1"),
        ("language", device),
    ]
    assert ("info", "App language detected: EN") in logs


def test_the_shared_setup_without_version_reader_or_package_reads_the_language_only(monkeypatch):
    calls = []
    _record_setup(monkeypatch, calls)
    device = object()

    prepare_instagram_selectors(device=device)

    assert calls == [("language", device)]


def test_a_failed_detection_never_stops_the_run(monkeypatch):
    logs = []

    def broken(device):
        raise RuntimeError("no dump")

    monkeypatch.setattr(runtime_setup, "detect_and_optimize", broken)

    prepare_instagram_selectors(device=object(), log=lambda level, message: logs.append((level, message)))

    assert ("warning", "Language detection failed (non-fatal): no dump") in logs
