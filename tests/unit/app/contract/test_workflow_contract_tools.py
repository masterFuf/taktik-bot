"""The diagnostic tools print the lines `contract/diagnostics.py` declares, by their real paths.

Each tool runs from its entry to its stdout; only the phone (connection, app restart, screen), the
catalogue patcher, the base and, for the workflow bench, the production run's screen work are
replaced. What is held, per tool:
- every line printed under a declared `type` has its declared fields and types;
- every declared `type` is printed by a real path of the tool;
- nothing else is printed (the workflow bench: nothing but the lines of the run it drives).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from loguru import logger

from taktik.core.app.contract import TOOL_CONTRACTS
from taktik.core.app.contract.diagnostics import ACTION_SESSION, INSTAGRAM_DEBUG, SELECTOR_TEST, WORKFLOW_TEST
from taktik.core.app.contract.instagram_automation import INSTAGRAM_AUTOMATION
from taktik.core.app.contract.schema import ToolContract
from test_workflow_contract_bridges import problems_of

DEVICE = "emulator-5554"


def check(tool: ToolContract, printed: List[Dict[str, Any]], *, besides=frozenset()) -> None:
    declared = {event.type: event for event in tool.events}
    for line in printed:
        json.dumps(line)
        if line["type"] in declared:
            assert not problems_of(declared[line["type"]].fields, line), (line, problems_of(declared[line["type"]].fields, line))
        else:
            assert line["type"] in besides, f"undeclared line {line}"


def types_of(printed) -> set:
    return {line["type"] for line in printed}


@pytest.fixture
def lines(monkeypatch):
    """Every line printed through the real IPC helpers."""
    from bridges.common.runtime.ipc import IPC

    printed: List[Dict[str, Any]] = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **kwargs: printed.append({"type": msg_type, **kwargs}))
    return printed


@pytest.fixture
def no_telemetry_left():
    from taktik.core.shared.telemetry import sink

    yield
    sink.clear_telemetry_sink()


def test_every_tool_names_a_bridge_of_the_manifest():
    manifest = json.loads((Path(__file__).resolve().parents[4] / "bridges" / "bridges.manifest.json")
                          .read_text(encoding="utf-8-sig"))
    bridges = {name for platform in manifest.values() for name in platform}
    assert {tool.bridge for tool in TOOL_CONTRACTS} <= bridges


# ------------------------------------------------------------------------------ workflow bench


class _Screen:
    """The phone's screen: every selector finds something."""

    def xpath(self, selector):
        return SimpleNamespace(exists=True)


@pytest.fixture
def bench(monkeypatch, no_telemetry_left):
    """The bench's session with the phone, the catalogue patcher and the base replaced; the
    global hooks it installs (log sink, `IPCEmitter`, `BaseStatsManager`) are undone after."""
    import taktik.core.compat.selectors.setup as selector_setup
    import taktik.core.database as database
    import taktik.core.social_media.instagram.ui.language as language
    from bridges.compat.diagnostics.runtime.workflow_test import observability
    from bridges.compat.diagnostics.runtime.workflow_test.execution import session
    from taktik.core.social_media.instagram.actions.core.ipc.emitter import IPCEmitter
    from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager
    from taktik.core.social_media.instagram.ui.watchdog import WorkflowWatchdog

    for name in ("emit_follow", "emit_like", "emit_profile_visit", "emit_action", "emit_profile_captured"):
        monkeypatch.setattr(IPCEmitter, name, getattr(IPCEmitter, name))
    monkeypatch.setattr(BaseStatsManager, "__init__", BaseStatsManager.__init__)
    monkeypatch.setattr(BaseStatsManager, "_send_stats_update", BaseStatsManager._send_stats_update)

    class Connection:
        def __init__(self, device_id):
            self.device_manager = SimpleNamespace(device=_Screen())

        def connect(self):
            return True

        def disconnect(self):
            pass

    class App:
        def __init__(self, conn, platform):
            pass

        def is_installed(self):
            return True

        def restart(self):
            return True

    monkeypatch.setattr(session, "ConnectionService", Connection)
    monkeypatch.setattr(session, "AppService", App)
    monkeypatch.setattr(database, "configure_db_service", lambda *a, **k: None)
    monkeypatch.setattr(selector_setup, "apply_version_overrides", lambda app, version: 2)
    monkeypatch.setattr(language, "detect_and_optimize", lambda device: "fr")

    original_watchdog = WorkflowWatchdog.__init__

    def quick_watchdog(self, *args, **kwargs):
        original_watchdog(self, *args, **{**kwargs, "check_interval": 0.01})

    monkeypatch.setattr(WorkflowWatchdog, "__init__", quick_watchdog)
    sinks = set(logger._core.handlers)
    yield
    for handler_id in set(logger._core.handlers) - sinks:
        logger.remove(handler_id)
    observability.set_active_tracer(None)
    observability.clear_active_watchdog()


def _scripted_run(payload, *, device_manager, step_hook, **_kwargs):
    """The production launcher's place: one step, whose screen work answers from a script."""
    from taktik.core.social_media.instagram.actions.core.ipc.emitter import IPCEmitter
    from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager
    from taktik.core.shared.telemetry import emit_step

    def follow_alice(action):
        emit_step("tap", action="follow", target="alice")
        device_manager.device.xpath('//*[@resource-id="com.instagram.android:id/profile_header_follow_button"]')
        IPCEmitter.emit_follow("alice", profile_data={"followers_count": 12})
        BaseStatsManager("target_followers").increment("follows")
        logger.info("Followed @alice")
        return True

    step_hook({"type": "target_followers", "id": "target_followers"}, follow_alice)
    return {"success": True}


def _bench_config(**overrides) -> Dict[str, Any]:
    return {"device_id": DEVICE, "app": "instagram", "version": "410.0.0.53.71", "workflow": "target_followers",
            "target": "alice", "session_duration": 30, "delays": {"min": 2, "max": 5}, **overrides}


def test_the_workflow_bench_prints_its_declared_lines(monkeypatch, lines, bench):
    import taktik.core.social_media.instagram.workflows.core.agent_handler as launcher
    from bridges.common.runtime.ipc import IPC
    from bridges.compat.diagnostics.entrypoints import workflow_test

    monkeypatch.setattr(launcher, "run_instagram_automation", _scripted_run)

    workflow_test.run_workflow_test(IPC(), _bench_config())
    # A workflow the bench cannot run yet, and one it does not know.
    workflow_test.run_workflow_test(IPC(), _bench_config(workflow="dm_response", target=""))
    workflow_test.run_workflow_test(IPC(), _bench_config(workflow="not_a_workflow", target=""))
    with pytest.raises(SystemExit):
        workflow_test.run_workflow_test(IPC(), {"app": "instagram"})

    # The run it drives prints its own lines too; the bench reads only its declared ones.
    check(WORKFLOW_TEST, lines, besides={event.type for event in INSTAGRAM_AUTOMATION.events})
    assert {event.type for event in WORKFLOW_TEST.events} <= types_of(lines)
    report = next(line for line in lines if line["type"] == "test_report")
    assert report["actual_results"]["follows"] == 1


# ------------------------------------------------------------------------------ selector bench


#: A real Instagram 410 dump (the explore grid), the one screen the bench tests against.
_SCREEN = (Path(__file__).resolve().parents[2] / "social_media" / "instagram" / "fixtures"
           / "ig410_en_explore_grid.xml").read_text(encoding="utf-8")


def test_the_selector_bench_prints_its_declared_lines(monkeypatch, lines):
    from bridges.common.runtime.ipc import IPC
    from bridges.compat.diagnostics.entrypoints import selector_test
    from bridges.compat.diagnostics.runtime.selector_test import production
    from taktik.core.compat.selectors.registry import SelectorEntry

    class Connection:
        def __init__(self, device_id):
            self.device = SimpleNamespace(dump_hierarchy=lambda compressed=False: _SCREEN)

        def connect(self):
            return True

        def disconnect(self):
            pass

    found = '//*[@resource-id="com.instagram.android:id/action_bar_search_edit_text"]'
    missing = '//*[@resource-id="com.instagram.android:id/profile_header_follow_button"]'
    entries = {
        f"explore.field_{index}": SelectorEntry(xpaths=[found if index % 2 else missing], source="python")
        for index in range(6)
    }

    def plan(app, version, device_id, device):
        return production.SelectorTestPlan(
            device=device, rewrite=None, xml=_SCREEN, dump_error=None,
            selectors=production.ProductionSelectors(
                entries=entries, version=version, baseline_version="410.0.0.53.71", overrides_applied=0,
                language="fr", skipped_not_xpath=1, skipped_empty=0))

    monkeypatch.setattr(selector_test, "ConnectionService", Connection)
    monkeypatch.setattr(production, "prepare_selector_test", plan)

    selector_test.run_selector_test(IPC(), {"device_id": DEVICE, "app": "instagram", "version": "410.0.0.53.71"})
    with pytest.raises(SystemExit):
        selector_test.run_selector_test(IPC(), {"app": "instagram"})

    check(SELECTOR_TEST, lines)
    assert types_of(lines) == {event.type for event in SELECTOR_TEST.events}


# ------------------------------------------------------------------------------ Lab action session


def _printed(capsys) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]


def test_the_action_session_prints_its_declared_lines(monkeypatch, capsys, no_telemetry_left):
    import taktik.core.shared.device.manager as manager
    from bridges.compat.diagnostics.runtime import events
    from bridges.compat.diagnostics.runtime.action_test import session
    from taktik.core.shared.telemetry import emit_step

    connected = {"ok": True}

    class Manager:
        def __init__(self, device_id):
            self.device = SimpleNamespace(xpath=lambda expr, *a, **k: SimpleNamespace(exists=True),
                                          app_current=lambda: {"package": "com.instagram.android"})

        def connect(self, verify_atx=False):
            return connected["ok"]

    def open_profile(bundle, params):
        bundle.device._device.xpath('//*[@resource-id="com.instagram.android:id/row_profile_header"]')
        emit_step("tap", action="open_profile", target=params.get("username"))
        return {"success": True, "details": {"username": params.get("username")}}

    def runtime(platform):
        facade = lambda raw: SimpleNamespace(_device=raw)  # noqa: E731
        bundle = lambda device: SimpleNamespace(device=device, detection=None)  # noqa: E731
        return {"lab.open_profile": open_profile}, facade, bundle

    monkeypatch.setattr(manager, "DeviceManager", Manager)
    monkeypatch.setattr(session, "_load_platform_runtime", runtime)
    commands = [
        {"type": "run_action", "action_id": "lab.open_profile", "request_id": "r1", "params": {"username": "alice"},
         "capture_artifacts": False},
        {"type": "run_action", "action_id": "lab.unknown", "request_id": "r2"},
        {"type": "reboot", "request_id": "r3"},
        {"type": "shutdown"},
    ]
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json\n" + "\n".join(json.dumps(c) for c in commands) + "\n"))

    session.run_action_session_bridge({"device_id": DEVICE, "platform": "instagram", "capture_artifacts": False})
    # The session's log line, as `configure_logger` routes loguru to it.
    events.log("info", "Session closed")
    connected["ok"] = False
    with pytest.raises(SystemExit):
        session.run_action_session_bridge({"device_id": DEVICE, "platform": "instagram"})

    printed = _printed(capsys)
    check(ACTION_SESSION, printed)
    assert types_of(printed) == {event.type for event in ACTION_SESSION.events}


# ------------------------------------------------------------------------------ debug tooling


def test_the_debug_tooling_prints_its_declared_lines(monkeypatch, lines, tmp_path):
    import taktik.core.shared.device.manager as manager
    import taktik.core.social_media.instagram.ui.detectors.problematic_page as problematic_page
    import taktik.core.shared.diagnostics.ui_dump_files as ui_dump
    from bridges.instagram.automation import desktop

    connected = {"ok": True}
    foreground = {"package": "com.instagram.android"}

    class Manager:
        def __init__(self, device_id):
            self.device = SimpleNamespace(app_current=lambda: dict(foreground))

        def connect(self, verify_atx=False):
            return connected["ok"]

    class Detector:
        def __init__(self, device, debug_mode=False):
            pass

        def detect_and_handle_problematic_pages(self):
            return {"detected": True, "closed": True}

    monkeypatch.setattr(manager, "DeviceManager", Manager)
    monkeypatch.setattr(ui_dump, "capture_screenshot", lambda device, output_dir: str(tmp_path / "screen.png"))
    monkeypatch.setattr(ui_dump, "dump_ui_hierarchy", lambda device, output_dir: str(tmp_path / "screen.xml"))
    monkeypatch.setattr(problematic_page, "ProblematicPageDetector", Detector)

    def run(**config):
        return desktop._desktop_bridge({"debugMode": True, "deviceId": DEVICE, **config}).run()

    assert run(mode="analyze") == 0
    assert run(mode="detect") == 0
    foreground["package"] = "com.zhiliaoapp.musically"
    assert run(mode="detect") == 0
    connected["ok"] = False
    assert run(mode="analyze") == 2

    check(INSTAGRAM_DEBUG, lines)
    assert types_of(lines) == {event.type for event in INSTAGRAM_DEBUG.events}
