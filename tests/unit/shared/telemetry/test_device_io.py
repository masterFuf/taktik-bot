"""M1: what an action costs on the phone is counted, and counting changes nothing."""

import pytest

from taktik.core.shared.telemetry import clear_telemetry_sink, configure_telemetry_sink
from taktik.core.shared.telemetry.device_io import (
    DeviceIoMeasure,
    DeviceIoMeter,
    instrument_device_io,
    measure_device_io,
)


class FakeU2Device:
    """The two entry points of a uiautomator2 device the meter wraps."""

    def __init__(self):
        self.calls = []

    def jsonrpc_call(self, method, params=None, timeout=10):
        self.calls.append((method, params, timeout))
        if method == "boom":
            raise RuntimeError("server error")
        return f"{method}-result"

    def shell(self, cmd, timeout=60):
        self.calls.append(("shell", cmd, timeout))
        return "shell-output"


@pytest.fixture
def steps():
    received = []
    configure_telemetry_sink(received.append)
    yield received
    clear_telemetry_sink()


def test_calls_are_passed_through_unchanged():
    device, meter = FakeU2Device(), DeviceIoMeter()
    assert instrument_device_io(device, meter) is True

    assert device.jsonrpc_call("dumpWindowHierarchy", (False, 50), 7) == "dumpWindowHierarchy-result"
    assert device.shell("getprop ro.build.version.sdk", timeout=5) == "shell-output"
    assert device.calls == [("dumpWindowHierarchy", (False, 50), 7),
                            ("shell", "getprop ro.build.version.sdk", 5)]


def test_dumps_waits_and_round_trips_are_counted_apart():
    device, meter = FakeU2Device(), DeviceIoMeter()
    instrument_device_io(device, meter)
    device.jsonrpc_call("dumpWindowHierarchy", (False, 50))
    device.jsonrpc_call("dumpWindowHierarchy", (False, 50))
    device.jsonrpc_call("waitForExists", ({}, 2000))
    device.jsonrpc_call("click", (10, 20))
    device.shell("input keyevent 4")

    totals = meter.snapshot()
    assert (totals["rpc"], totals["dumps"], totals["waits"], totals["shells"]) == (4, 2, 1, 1)


def test_an_error_is_raised_as_before_and_counted():
    device, meter = FakeU2Device(), DeviceIoMeter()
    instrument_device_io(device, meter)
    with pytest.raises(RuntimeError):
        device.jsonrpc_call("boom")
    assert meter.snapshot()["errors"] == 1 and meter.snapshot()["rpc"] == 1


def test_instrumenting_twice_counts_once():
    device, meter = FakeU2Device(), DeviceIoMeter()
    instrument_device_io(device, meter)
    instrument_device_io(device, meter)
    device.jsonrpc_call("click")
    assert meter.snapshot()["rpc"] == 1


def test_a_device_without_the_entry_point_is_left_alone():
    class Other:
        pass
    assert instrument_device_io(Other(), DeviceIoMeter()) is False


def test_an_action_emits_its_own_costs(steps):
    device, meter = FakeU2Device(), DeviceIoMeter()
    instrument_device_io(device, meter)
    device.jsonrpc_call("dumpWindowHierarchy")  # before the action: not its cost

    with measure_device_io("profile.get_biography", meter, source="lab"):
        device.jsonrpc_call("dumpWindowHierarchy")
        device.jsonrpc_call("objInfo")

    assert len(steps) == 1
    step = steps[0]
    assert step.category == "device_io" and step.action == "profile.get_biography"
    assert step.detail["dumps"] == 1 and step.detail["rpc"] == 2 and step.detail["source"] == "lab"
    assert step.detail["total_ms"] >= step.detail["other_ms"] >= 0


def test_an_action_that_raises_is_still_measured(steps):
    meter = DeviceIoMeter()
    with pytest.raises(ValueError):
        with measure_device_io("navigation.open_profile", meter):
            raise ValueError("action failed")
    assert [s.action for s in steps] == ["navigation.open_profile"]


def test_without_a_sink_measuring_is_silent():
    clear_telemetry_sink()
    with measure_device_io("detection.dump_xml", DeviceIoMeter()):
        pass


def test_what_the_action_found_is_emitted_with_its_costs(steps):
    device, meter = FakeU2Device(), DeviceIoMeter()
    instrument_device_io(device, meter)
    with measure_device_io("tiktok.feed.decision", meter, source="for_you") as outcome:
        device.jsonrpc_call("dumpWindowHierarchy")
        outcome["kind"] = "ad"
    detail = steps[0].detail
    assert (detail["kind"], detail["source"], detail["dumps"]) == ("ad", "for_you", 1)


def test_an_action_with_several_exits_is_emitted_once_by_the_exit_it_took(steps):
    device, meter = FakeU2Device(), DeviceIoMeter()
    instrument_device_io(device, meter)
    decision = DeviceIoMeasure("tiktok.feed.decision", meter, source="search")
    device.jsonrpc_call("dumpWindowHierarchy")
    device.jsonrpc_call("dumpWindowHierarchy")
    decision.finish(kind="comments")
    decision.finish(kind="video")
    assert [(s.action, s.detail["kind"], s.detail["dumps"]) for s in steps] == [
        ("tiktok.feed.decision", "comments", 2)]


def test_an_action_that_never_finishes_emits_nothing(steps):
    DeviceIoMeasure("tiktok.feed.decision", DeviceIoMeter())
    assert steps == []


def test_an_outcome_that_cannot_be_emitted_does_not_break_the_action(steps):
    DeviceIoMeasure("tiktok.feed.decision", DeviceIoMeter()).finish(action="clash")
    assert steps == []


# ── Where it is wired ─────────────────────────────────────────────────────────

def test_the_connection_instruments_the_device(monkeypatch):
    from taktik.core.shared.device import manager as device_manager

    device = FakeU2Device()
    monkeypatch.setattr(device_manager.u2, "connect", lambda _serial: device)
    monkeypatch.setattr(device_manager.DeviceManager, "_apply_selector_overrides", staticmethod(lambda _s: None))

    assert device_manager.DeviceManager("serial-x").connect(verify_atx=False) is True
    assert getattr(device, "_taktik_device_io_instrumented", False) is True


def test_every_workflow_step_emits_what_it_cost(steps):
    from types import SimpleNamespace
    from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner

    runner = WorkflowRunner(SimpleNamespace())
    assert runner.run_workflow_step({"type": "initialize"}) is True
    assert [(s.category, s.action, s.detail["source"]) for s in steps] == [
        ("device_io", "workflow.initialize", "workflow")]


class FakeAdbDevice:
    """The adbutils device under a uiautomator2 device: shell2 falls back on shell (shell v1)."""

    def __init__(self):
        self.commands = []

    def shell(self, cmd, **_kwargs):
        self.commands.append(cmd)
        return "dumpsys output"

    def shell2(self, cmd, **_kwargs):
        return self.shell(cmd)

    def app_current(self):
        return [self.shell(["dumpsys", "window", "windows"]), self.shell(["dumpsys", "activity", "top"])]


def test_the_adb_round_trips_of_uiautomator2_itself_are_counted_once():
    device, meter = FakeU2Device(), DeviceIoMeter()
    device._dev = FakeAdbDevice()
    instrument_device_io(device, meter)

    device._dev.app_current()              # two dumpsys, outside Device.shell
    device._dev.shell2("getprop x")        # shell v1: shell2 then shell, one round trip

    assert meter.snapshot()["shells"] == 3


def test_the_bot_s_own_adb_shell_is_counted(monkeypatch):
    from taktik.core.shared.device import adb as adb_module
    from taktik.core.shared.telemetry import device_io

    meter = DeviceIoMeter()
    monkeypatch.setattr(device_io, "METER", meter)
    monkeypatch.setattr(adb_module, "_run_adb_shell", lambda _d, _c: "ok")

    assert adb_module.run_adb_shell("phone", "settings get secure default_input_method") == "ok"
    assert meter.snapshot()["shells"] == 1
