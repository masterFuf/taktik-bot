"""The Lab's Instagram automation run goes through the production launcher.

The bench used to build `InstagramAutomation` itself and patch its step runner to trace each
step. It now hands a step hook to `run_instagram_automation`, the launcher the desktop bridge
and the CLI call, so the engine a bench run exercises is built in one place.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from taktik.core.social_media.instagram.workflows.core import agent_handler
from taktik.core.social_media.instagram.workflows.core import automation as automation_module
from taktik.core.social_media.instagram.workflows.core import runtime_setup as runtime_setup_module


class FakeRunner:
    def __init__(self, calls):
        self.calls = calls

    def run_workflow_step(self, action):
        self.calls.append(("engine_step", action["type"]))
        return action["type"] != "unfollow"


class FakeAutomation:
    built: list = []

    def __init__(self, device_manager):
        self.device_manager = device_manager
        self.calls: list = []
        self.workflow_runner = FakeRunner(self.calls)
        self.config = {}
        FakeAutomation.built.append(self)

    def run_workflow(self):
        for step in self.config["actions"]:
            self.workflow_runner.run_workflow_step(step)

    def final_stats(self):
        return {"likes": 0}


class Recorder:
    def __init__(self):
        self.events: list[tuple] = []

    def send(self, kind, **data):
        self.events.append((kind, data))

    def begin_step(self, name):
        self.events.append(("begin", name))

    def end_step(self, success, error=None):
        self.events.append(("end", success))


@pytest.fixture
def engine(monkeypatch):
    FakeAutomation.built = []
    monkeypatch.setattr(automation_module, "InstagramAutomation", FakeAutomation)

    def fake_setup(*, automation, workflow_config, **_kwargs):
        automation.config = workflow_config

    monkeypatch.setattr(runtime_setup_module, "prepare_instagram_automation_runtime", fake_setup)
    return FakeAutomation


def test_step_hook_wraps_every_workflow_step(engine):
    seen = []

    def hook(step, run_step):
        seen.append(step["type"])
        return run_step(step)

    agent_handler.run_instagram_automation(
        {"workflowType": "feed", "target": "feed"}, device_manager=object(), step_hook=hook,
    )

    run = engine.built[0]
    assert seen == ["feed"]
    assert run.calls == [("engine_step", "feed")]


def test_lab_automation_run_builds_the_engine_through_the_launcher(engine, monkeypatch):
    from bridges.compat.diagnostics.runtime.workflow_test.platforms.instagram.dispatcher import (
        dispatch_instagram_workflow,
    )
    from taktik.core.social_media.instagram.ui import watchdog as watchdog_module

    monkeypatch.setattr(watchdog_module, "WorkflowWatchdog", lambda *a, **k: SimpleNamespace(start=lambda: None))
    device_manager = SimpleNamespace(device=object())
    lab = Recorder()

    result = dispatch_instagram_workflow(
        workflow_type="feed", target="feed", limits={"maxProfiles": 2}, probabilities={"like": 50},
        session_duration=5, delays=None, conn=SimpleNamespace(device_manager=device_manager),
        device=device_manager.device, tracer=lab, ipc=lab,
    )

    assert result.success is True
    run = engine.built[0]
    assert run.device_manager is device_manager
    assert run.calls == [("engine_step", "feed")]
    steps = [event for event in lab.events if event[0] in ("begin", "end", "workflow_step")]
    assert steps == [
        ("begin", "feed"),
        ("workflow_step", {"step": "feed", "status": "running"}),
        ("end", True),
        ("workflow_step", {"step": "feed", "status": "done"}),
    ]
