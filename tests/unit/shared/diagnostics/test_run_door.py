"""The door of a run (`taktik/core/shared/diagnostics/run_door.py`): a locked phone does not start
its run, and says so, instead of ending `target_never_reached` a minute later."""
import pytest

from taktik.core.shared.device import network_door
from taktik.core.shared.diagnostics import run_door, run_halt
from unit.paths import CORE


def test_a_phone_that_stays_locked_is_refused_before_the_network_is_measured(monkeypatch):
    monkeypatch.setattr(run_door, "phone_locked_after_lift", lambda device_id: True)

    def _never(device_id):
        raise AssertionError("no measure of a locked phone")

    monkeypatch.setattr(network_door, "measure_network_baseline", _never)

    with pytest.raises(run_door.PhoneLockedError) as refused:
        run_door.open_run_door("SERIAL")

    assert refused.value.error_code == "PHONE_LOCKED"
    assert refused.value.device_id == "SERIAL"
    # A host that prints the exception (the CLI) says the same motive.
    assert "PHONE_LOCKED" in str(refused.value)
    assert isinstance(refused.value, run_halt.RunRefused)


def test_the_two_refusals_of_the_door_are_caught_as_one(monkeypatch):
    monkeypatch.setattr(run_door, "phone_locked_after_lift", lambda device_id: False)
    monkeypatch.setattr(network_door, "measure_network_baseline",
                        lambda device_id: {"unreachable": True, "received": 0, "rtt_ms": None, "packet_loss_pct": None})

    with pytest.raises(run_halt.RunRefused) as refused:
        run_door.open_run_door("SERIAL")

    assert refused.value.error_code == "NETWORK_UNREACHABLE"


@pytest.mark.parametrize("state", [False, None])
def test_a_phone_lifted_or_unreadable_goes_on_to_the_network_door(monkeypatch, state):
    """Unreadable is not locked: a phone whose dump does not say it keeps its run."""
    monkeypatch.setattr(run_door, "phone_locked_after_lift", lambda device_id: state)
    measured = []
    monkeypatch.setattr(network_door, "measure_network_baseline", lambda device_id: measured.append(device_id))

    assert run_door.open_run_door("SERIAL") is None
    assert measured == ["SERIAL"]


def test_without_a_device_nothing_is_read(monkeypatch):
    def _never(device_id):
        raise AssertionError("nothing is read without a device")

    monkeypatch.setattr(run_door, "phone_locked_after_lift", _never)

    assert run_door.open_run_door("") is None


def test_every_launcher_opens_the_run_door_and_none_the_network_door_alone():
    """One door for a run: a launcher that opened the network door alone would start on a locked phone."""
    openers = {}
    for path in sorted((CORE / "taktik").rglob("*.py")):
        text = path.read_text(encoding="utf-8-sig")
        relative = path.relative_to(CORE).as_posix()
        if "open_run_door(" in text:
            openers[relative] = "run"
        if "open_network_door(" in text and relative not in ("taktik/core/shared/device/network_door.py",
                                                              "taktik/core/shared/diagnostics/run_door.py"):
            openers[relative] = "network"

    assert "network" not in openers.values(), openers
    assert len(openers) >= 8, openers
