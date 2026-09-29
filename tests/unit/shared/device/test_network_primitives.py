"""What the phone sees of the network, and the strategies that reset its radio.

The probes read (the public IP, whether the Internet is back, a setting); the strategies only change
a radio state and say whether their commands took effect: deciding whether the IP rotated is the
orchestrator's job (`bridges/common/network.py`, `test_network_reset_verdicts.py`). The parsing of
the latency probe is pinned by `tests/unit/shared/device/test_network_baseline.py`. Doubles of the
phone's shell here, no device.
"""

import pytest

from taktik.core.shared.device import network_probe, network_reset


# ------------------------------------------------------------------------------ the public IP

@pytest.mark.parametrize("answer, ip", [
    ("fl=1\nip=81.2.3.4\nts=1", "81.2.3.4"),
    ("HTTP/1.1 200 OK\r\n\r\n81.2.3.4\n", "81.2.3.4"),
    ("ip=10.0.0.2\nvia 37.167.1.9", "37.167.1.9"),
    ("192.168.1.1 172.16.0.1 127.0.0.1 1.1.1.1 0.0.0.0 255.255.255.255", None),
    ("", None),
])
def test_the_public_ip_is_the_first_address_that_can_be_one(answer, ip):
    assert network_probe._extract_public_ip(answer) == ip


class _Shell:
    """`_shell`: the answer of the phone to each command, recorded."""

    def __init__(self, answers):
        self.answers = answers
        self.commands = []

    def __call__(self, device_id, command, timeout=15):
        self.commands.append(command)
        return self.answers(command) if callable(self.answers) else self.answers.get(command, "")


def test_the_first_probe_that_answers_gives_the_ip(monkeypatch):
    second = network_probe._IP_PROBE_COMMANDS[1]
    shell = _Shell({second: "37.167.1.9"})
    monkeypatch.setattr(network_probe, "_shell", shell)

    assert network_probe.read_public_ip("SERIAL") == "37.167.1.9"
    assert shell.commands == list(network_probe._IP_PROBE_COMMANDS[:2])


def test_no_probe_answering_twice_is_an_unreadable_ip(monkeypatch):
    shell = _Shell({})
    monkeypatch.setattr(network_probe, "_shell", shell)

    assert network_probe.read_public_ip("SERIAL") is None
    assert shell.commands == list(network_probe._IP_PROBE_COMMANDS) * 2


def test_at_least_one_pass_of_the_probes(monkeypatch):
    shell = _Shell({})
    monkeypatch.setattr(network_probe, "_shell", shell)

    assert network_probe.read_public_ip("SERIAL", attempts=0) is None
    assert len(shell.commands) == len(network_probe._IP_PROBE_COMMANDS)


def test_the_legacy_reader_says_unknown(monkeypatch):
    monkeypatch.setattr(network_probe, "read_public_ip", lambda device_id: None)
    assert network_probe.get_device_external_ip("SERIAL") == "unknown"

    monkeypatch.setattr(network_probe, "read_public_ip", lambda device_id: "81.2.3.4")
    assert network_probe.get_device_external_ip("SERIAL") == "81.2.3.4"


# ------------------------------------------------------------------- the Internet, back or not

ROUTE = "1.1.1.1 via 10.0.0.1 dev rmnet_data0 src 10.0.0.2 uid 0"
PING = "64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=23.4 ms"


@pytest.fixture
def clock(monkeypatch):
    """A clock that moves only when the probe waits between two rounds."""
    now = {"t": 0.0}
    waits = []
    monkeypatch.setattr(network_probe.time, "monotonic", lambda: now["t"])

    def sleep(seconds):
        waits.append(seconds)
        now["t"] += seconds

    monkeypatch.setattr(network_probe.time, "sleep", sleep)
    return waits


def test_a_route_and_a_reply_is_the_internet_back(monkeypatch, clock):
    shell = _Shell({"ip route get 1.1.1.1": ROUTE, "ping -c 1 -W 2 1.1.1.1": PING})
    monkeypatch.setattr(network_probe, "_shell", shell)

    assert network_probe.wait_for_internet("SERIAL") is True
    assert clock == []


def test_one_received_packet_counts_as_a_reply(monkeypatch, clock):
    monkeypatch.setattr(network_probe, "_shell", _Shell({
        "ip route get 1.1.1.1": ROUTE, "ping -c 1 -W 2 1.1.1.1": "1 packets transmitted, 1 received"}))

    assert network_probe.wait_for_internet("SERIAL") is True


def test_a_route_without_reply_keeps_waiting_until_the_deadline(monkeypatch, clock):
    shell = _Shell({"ip route get 1.1.1.1": ROUTE, "ping -c 1 -W 2 1.1.1.1": "100% packet loss"})
    monkeypatch.setattr(network_probe, "_shell", shell)

    assert network_probe.wait_for_internet("SERIAL", timeout_seconds=7) is False
    assert clock == [3, 3, 3]
    assert shell.commands.count("ping -c 1 -W 2 1.1.1.1") == 4


def test_no_route_is_not_pinged(monkeypatch, clock):
    shell = _Shell({"ip route get 1.1.1.1": "RTNETLINK answers: Network is unreachable"})
    monkeypatch.setattr(network_probe, "_shell", shell)

    assert network_probe.wait_for_internet("SERIAL", timeout_seconds=0) is False
    assert shell.commands == ["ip route get 1.1.1.1"]


def test_the_internet_coming_back_after_a_wait(monkeypatch, clock):
    rounds = {"n": 0}

    def answers(command):
        if command == "ip route get 1.1.1.1":
            rounds["n"] += 1
            return ROUTE if rounds["n"] >= 3 else ""
        return PING

    monkeypatch.setattr(network_probe, "_shell", _Shell(answers))

    assert network_probe.wait_for_internet("SERIAL", timeout_seconds=30) is True
    assert clock == [3, 3]


# ------------------------------------------------------------------------------ radio settings

@pytest.mark.parametrize("raw, state", [("1", True), ("0", False), (" 1\n", True), ("null", None), ("", None)])
def test_a_setting_is_read_as_on_off_or_unknown(monkeypatch, raw, state):
    commands = []
    monkeypatch.setattr(network_probe, "run_adb_shell", lambda device_id, command: commands.append(command) or raw)

    assert network_probe.is_mobile_data_enabled("SERIAL") is state
    assert network_probe.is_airplane_mode_enabled("SERIAL") is state
    assert commands == ["settings get global mobile_data", "settings get global airplane_mode_on"]


# ------------------------------------------------------------------------- the reset strategies

class _Radio:
    """The phone's shell for the strategies: the commands, the state read after them, the Internet."""

    def __init__(self, *, data_after_disable=False, airplane_after_enable=True, internet=True,
                 radios="cell,bluetooth,wifi,nfc,wimax", raises_on=None):
        self.data_after_disable = data_after_disable
        self.airplane_after_enable = airplane_after_enable
        self.internet = internet
        self.radios = radios
        self.raises_on = raises_on
        self.commands = []
        self.waited = []

    def adb(self, device_id, command):
        self.commands.append(command)
        if command == self.raises_on:
            raise OSError("adb gone")
        if command == "settings get global airplane_mode_radios":
            return self.radios
        return ""

    def install(self, monkeypatch):
        monkeypatch.setattr(network_reset, "run_adb_shell", self.adb)
        monkeypatch.setattr(network_reset, "is_mobile_data_enabled", lambda device_id: self.data_after_disable)
        monkeypatch.setattr(network_reset, "is_airplane_mode_enabled", lambda device_id: self.airplane_after_enable)
        monkeypatch.setattr(network_reset, "wait_for_internet",
                            lambda device_id, timeout_seconds: self.waited.append(timeout_seconds) or self.internet)
        monkeypatch.setattr(network_reset.time, "sleep", lambda seconds: self.commands.append(f"settle {seconds}"))
        return self


def test_a_data_toggle_disables_then_enables_and_waits_for_the_internet(monkeypatch):
    radio = _Radio().install(monkeypatch)

    assert network_reset.reset_mobile_data("SERIAL", wait_seconds=2) is True
    assert radio.commands == ["svc data disable", "settle 2", "svc data enable"]
    assert radio.waited == [30.0]


def test_data_still_on_after_the_disable_stops_the_toggle(monkeypatch):
    radio = _Radio(data_after_disable=True).install(monkeypatch)

    assert network_reset.reset_mobile_data("SERIAL", wait_seconds=2) is False
    assert "svc data enable" not in radio.commands


def test_no_internet_after_the_toggle_is_a_failure(monkeypatch):
    _Radio(internet=False).install(monkeypatch)

    assert network_reset.reset_mobile_data("SERIAL") is False


def test_a_shell_that_fails_fails_the_toggle(monkeypatch):
    _Radio(raises_on="svc data disable").install(monkeypatch)

    assert network_reset.reset_mobile_data("SERIAL") is False


def test_an_airplane_cycle_enables_then_disables_and_waits(monkeypatch):
    radio = _Radio().install(monkeypatch)

    assert network_reset.reset_airplane_mode("SERIAL", wait_seconds=1) is True
    assert radio.commands == ["cmd connectivity airplane-mode enable", "settle 1",
                              "cmd connectivity airplane-mode disable"]
    assert radio.waited == [40.0]


def test_airplane_mode_that_did_not_turn_on_stops_the_cycle(monkeypatch):
    radio = _Radio(airplane_after_enable=False).install(monkeypatch)

    assert network_reset.reset_airplane_mode("SERIAL") is False
    assert "cmd connectivity airplane-mode disable" not in radio.commands


def test_a_cell_only_cycle_restores_the_radios_of_the_phone(monkeypatch):
    radio = _Radio(radios="cell,wifi\n").install(monkeypatch)

    assert network_reset.reset_airplane_cell("SERIAL", wait_seconds=1) is True
    assert radio.commands == [
        "settings get global airplane_mode_radios",
        "settings put global airplane_mode_radios cell",
        "cmd connectivity airplane-mode enable",
        "settle 1",
        "cmd connectivity airplane-mode disable",
        "settings put global airplane_mode_radios cell,wifi",
    ]
    assert radio.waited == [40.0]


@pytest.mark.parametrize("unreadable", ["null", ""])
def test_unreadable_radios_are_restored_to_the_default_list(monkeypatch, unreadable):
    radio = _Radio(radios=unreadable).install(monkeypatch)

    network_reset.reset_airplane_cell("SERIAL")

    assert radio.commands[-1] == "settings put global airplane_mode_radios cell,bluetooth,wifi,nfc,wimax"


def test_the_radios_are_restored_even_when_the_cycle_fails(monkeypatch):
    radio = _Radio(internet=False, radios="cell,wifi").install(monkeypatch)

    assert network_reset.reset_airplane_cell("SERIAL") is False
    assert radio.commands[-1] == "settings put global airplane_mode_radios cell,wifi"


def test_a_shell_that_fails_mid_cycle_still_restores_the_radios(monkeypatch):
    radio = _Radio(radios="cell,wifi", raises_on="cmd connectivity airplane-mode enable").install(monkeypatch)

    assert network_reset.reset_airplane_cell("SERIAL") is False
    assert radio.commands[-1] == "settings put global airplane_mode_radios cell,wifi"
