"""A story relay reads its selectors for the Instagram it relays on: its version, its package (a clone).

The relay restarted the Instagram its payload names, then read the screen with the selectors of the
official app at the official app's version, the only ones the connection matches
(`DeviceManager.connect`): it never made a clone the active package, never patched the catalogues to
a clone's ids and never read a clone's version. A pass on a clone in 447 looked for the official
package's ids with the baseline's selectors.

The launcher now asks its host for the phone as the automation, the scraping and the publication
do (`connect(package_name) -> InstagramRunPhone`), restarts that Instagram through the phone's
`start`, then matches the selectors to it (`activate_instagram_package`, `prepare_instagram_selectors`
with the phone's installed version), before the relay's first selector. Each host runs its real path
down to the connection; only uiautomator2, the versions adb would read, the app's restart and the
relay's screen are replaced.
"""

from __future__ import annotations

import json
import time

import pytest
from click.testing import CliRunner

from taktik.core.clone import get_active_package, set_active_package
from taktik.core.compat.selectors.setup import apply_version_overrides, baseline_version
from taktik.core.shared.device import app_inspection, app_manager
from taktik.core.shared.device import manager as manager_module
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.workflows.common import runtime_setup
from taktik.core.social_media.instagram.workflows.tasks import agent_handler

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
    serial = DEVICE_ID


@pytest.fixture
def phone(monkeypatch):
    versions = {INSTAGRAM: BASELINE, CLONE: V447}
    seen: dict = {"calls": []}

    def installed_version(_device_id, package, _platform):
        return versions.get(package)

    monkeypatch.setattr(app_inspection, "get_installed_app_version", installed_version)
    monkeypatch.setattr(app_manager, "get_installed_app_version", installed_version)
    monkeypatch.setattr(manager_module.u2, "connect", lambda _serial: _FakeDevice())
    monkeypatch.setattr(manager_module.DeviceManager, "_verify_and_repair_atx", lambda self, max_retries=2: True)
    monkeypatch.setattr(manager_module.DeviceManager, "list_devices",
                        classmethod(lambda cls: [{"id": DEVICE_ID, "status": "device"}]))
    monkeypatch.setattr(manager_module.DeviceManager, "is_app_installed", lambda self, package: True)
    monkeypatch.setattr(manager_module.DeviceManager, "stop_app",
                        lambda self, package: seen["calls"].append(f"stop {package}") or True)
    monkeypatch.setattr(manager_module.DeviceManager, "launch_app",
                        lambda self, package, activity=None, stop_first=False:
                        seen["calls"].append(f"launch {package}") or True)
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("bridges.common.run_setup.configure_run_database", lambda **_extra: True)

    # The clone's ids and the app language, recorded instead of applied.
    monkeypatch.setattr(runtime_setup, "patch_selectors_for_package",
                        lambda _platform, package: seen["calls"].append(f"clone_patch {package}") or 0)
    monkeypatch.setattr(runtime_setup, "detect_and_optimize",
                        lambda _device: seen["calls"].append("detect_language") or "fr")

    def relay(*, device, source_username, account_id, max_stories):
        seen["calls"].append("relay")
        seen["keep_out"] = list(NAVIGATION_SELECTORS.search_result_tap_keep_out)
        seen["active_package"] = get_active_package()
        report = agent_handler.new_relay_report(source_username)
        report["success"] = True
        return report

    monkeypatch.setitem(agent_handler.run_instagram_story_relay.__kwdefaults__, "relay", relay)
    yield seen
    apply_version_overrides("instagram", BASELINE)
    set_active_package(INSTAGRAM)


def _task_bridge():
    import bridges.instagram.tasks.bridge as bridge

    bridge.TaskBridge({"deviceId": DEVICE_ID, "taskId": "story_relay",
                       "params": {"source_username": "source_account", "packageName": CLONE}}).run()


def _cli_workflows_run():
    from taktik.cli.commands import workflows as workflow_cmds

    payload = {"source_username": "source_account", "packageName": CLONE}
    CliRunner().invoke(workflow_cmds.workflows, ["run", "instagram.task.story_relay", "-d", DEVICE_ID,
                                                 "--json", json.dumps(payload), "--yes"])


HOSTS = {"task bridge": _task_bridge, "taktik workflows run": _cli_workflows_run}


@pytest.mark.parametrize("host", HOSTS)
def test_a_relay_on_a_clone_in_447_reads_the_447_selectors(phone, host):
    expected = _keep_out_at(V447)
    assert expected != _keep_out_at(BASELINE)

    HOSTS[host]()

    assert phone.get("keep_out") == expected, phone


@pytest.mark.parametrize("host", HOSTS)
def test_a_relay_on_a_clone_drives_the_clone_and_its_ids(phone, host):
    HOSTS[host]()

    assert phone.get("active_package") == CLONE, phone
    calls = phone["calls"]
    assert calls.index(f"launch {CLONE}") < calls.index(f"clone_patch {CLONE}") < calls.index("relay"), calls
