"""A publication reads its selectors at the version of the Instagram it publishes on, as the automation
and the scraping do.

The automation and the scraping match the selectors to the installed version twice: at the
connection (`DeviceManager.connect`), at the version of the official Instagram whatever the run
drives, then in the launcher, at the version of the run's own Instagram, read on the package the
payload names (`InstagramRunPhone.installed_version`, then `prepare_instagram_selectors`). The
publication had the first only: its host handed the launcher a bare device, and its start step
matched the selectors to the clone's package and to the app language, never to the clone's version.
A clone in 447 on a phone whose official Instagram is at the baseline published with the baseline's
selectors.

The publication now asks its host for the phone as the automation and the scraping do
(`connect(package_name) -> InstagramRunPhone`), and its start step reads that phone's version. Each
host runs its real path down to the connection (`ConnectionService`, `DeviceManager.connect`); only
uiautomator2, the versions adb would read and the screen are replaced. The stock phone in 447 was
already right, by the connection: its case stays as a guard.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from taktik.core.clone import set_active_package
from taktik.core.compat.selectors.setup import apply_version_overrides, baseline_version
from taktik.core.shared.device import app_inspection, app_manager
from taktik.core.shared.device import manager as manager_module
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.workflows.common import runtime_setup
from taktik.core.social_media.instagram.workflows.publish.post_workflow import InstagramPostWorkflow

DEVICE_ID = "emulator-5554"
INSTAGRAM = "com.instagram.android"
CLONE = "com.taktik.ig1"
BASELINE = baseline_version("instagram")
V447 = "447.0.0.55.81"


def _keep_out_at(version: str) -> list:
    """A selector the 447 entries of `instagram.yaml` change, as the catalogue holds it at `version`."""
    apply_version_overrides("instagram", version)
    try:
        return list(NAVIGATION_SELECTORS.search_result_tap_keep_out)
    finally:
        apply_version_overrides("instagram", BASELINE)


class _FakeDevice:
    """The uiautomator2 device `u2.connect` would hand out: the screen is the workflow's doubles'."""

    serial = DEVICE_ID


class _WayHome:
    """The publication's first selector read (the way home), recorded with the catalogue it meets."""

    def __init__(self, seen: dict):
        self.seen = seen

    def navigate_to_home(self) -> bool:
        self.seen["keep_out"] = list(NAVIGATION_SELECTORS.search_result_tap_keep_out)
        return True


@pytest.fixture
def phone(monkeypatch, tmp_path):
    """The phone, down to what adb would read: the installed versions per package (`versions`)."""
    versions = {INSTAGRAM: BASELINE, CLONE: V447}
    seen: dict = {"versions_read": []}

    def installed_version(_device_id, package, _platform):
        seen["versions_read"].append(package)
        return versions.get(package)

    monkeypatch.setattr(app_inspection, "get_installed_app_version", installed_version)
    monkeypatch.setattr(app_manager, "get_installed_app_version", installed_version)
    monkeypatch.setattr(manager_module.u2, "connect", lambda _serial: _FakeDevice())
    monkeypatch.setattr(manager_module.DeviceManager, "_verify_and_repair_atx", lambda self, max_retries=2: True)
    monkeypatch.setattr(manager_module.DeviceManager, "list_devices",
                        classmethod(lambda cls: [{"id": DEVICE_ID, "status": "device"}]))

    # The clone's ids and the app language, recorded: what this test reads is the version's step.
    monkeypatch.setattr(runtime_setup, "patch_selectors_for_package", lambda _platform, _package: 0)
    monkeypatch.setattr(runtime_setup, "detect_and_optimize", lambda _device: "fr")

    # The production workflow, its orchestration and its start step real; the screen is recorded.
    monkeypatch.setattr(InstagramPostWorkflow, "_push_all", lambda self, media_paths: True)
    monkeypatch.setattr(InstagramPostWorkflow, "_launch_app", lambda self: None)
    monkeypatch.setattr(InstagramPostWorkflow, "_build_actions", staticmethod(lambda device: {"nav": _WayHome(seen)}))
    monkeypatch.setattr(InstagramPostWorkflow, "_open_creation_and_gallery",
                        lambda self: self._error("test_stop", "stop before the creation screen"))

    media = tmp_path / "a.png"
    media.write_bytes(b"x")
    seen["media"] = str(media)
    seen["installed"] = versions
    yield seen
    apply_version_overrides("instagram", BASELINE)
    set_active_package(INSTAGRAM)


def _bridge(seen: dict, package_name):
    import bridges.instagram.publish.bridge as bridge

    config = {"deviceId": DEVICE_ID, "postType": "post", "mediaPaths": [seen["media"]], "caption": "hello"}
    if package_name:
        config["packageName"] = package_name
    bridge.InstagramPublishBridge(config).run()


def _cli_publish(seen: dict, _package_name):
    """`taktik publish post`, which names no clone: the official Instagram."""
    from taktik.cli.commands.instagram import publish as publish_cmds

    CliRunner().invoke(publish_cmds.publish, ["post", seen["media"], "--device", DEVICE_ID])


def _cli_workflows_run(seen: dict, package_name):
    from taktik.cli.commands import workflows as workflow_cmds

    payload = {"postType": "post", "mediaPaths": [seen["media"]], "caption": "hello"}
    if package_name:
        payload["packageName"] = package_name
    CliRunner().invoke(workflow_cmds.workflows, ["run", "instagram.content.publish", "-d", DEVICE_ID,
                                                 "--json", json.dumps(payload), "--yes"])


HOSTS = {"bridge": _bridge, "taktik workflows run": _cli_workflows_run}


@pytest.mark.parametrize("host", HOSTS)
def test_a_clone_in_447_publishes_with_the_447_selectors(phone, host):
    expected = _keep_out_at(V447)
    assert expected != _keep_out_at(BASELINE)

    HOSTS[host](phone, CLONE)

    assert phone.get("keep_out") == expected, phone
    assert CLONE in phone["versions_read"], phone["versions_read"]


@pytest.mark.parametrize("host", [*HOSTS, "taktik publish"])
def test_the_official_instagram_in_447_publishes_with_the_447_selectors(phone, host):
    """The stock phone in 447: right by the connection already, kept right by the launcher."""
    phone["installed"][INSTAGRAM] = V447
    expected = _keep_out_at(V447)

    {**HOSTS, "taktik publish": _cli_publish}[host](phone, None)

    assert phone.get("keep_out") == expected, phone


def test_the_official_instagram_at_the_baseline_keeps_the_baseline(phone):
    """A clone in 447 next to it changes nothing for a publication on the official app."""
    _bridge(phone, None)

    assert phone.get("keep_out") == _keep_out_at(BASELINE), phone
