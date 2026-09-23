"""M1: what an action costs on the phone is counted, and counting changes nothing."""

import pytest

from taktik.core.shared.telemetry import clear_telemetry_sink, configure_telemetry_sink
from taktik.core.shared.telemetry.device_io import (
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
