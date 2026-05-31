from taktik.core.social_media.instagram.workflows.core import runtime_setup
from taktik.core.social_media.instagram.workflows.core.runtime_setup import (
    prepare_instagram_automation_runtime,
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
    monkeypatch.setattr(
        runtime_setup,
        "apply_version_overrides",
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
