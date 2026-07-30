"""The rotation verdict decides whether a run is allowed to start, so it is pinned here.

The distinction that matters: an IP proven to be the SAME blocks the run, an IP that could not be
READ does not. Collapsing the two either lets accounts share an IP (the whole point of the option)
or grounds every phone whose shell has no HTTP tool.
"""

import bridges.common.device.network as network_module
from bridges.common.device.network import MAX_ROTATION_ATTEMPTS, perform_network_reset


class _FakeStrategy:
    """Stands in for a reset strategy, recording how many times it was asked to rotate."""

    def __init__(self, commands_ok: bool = True):
        self.commands_ok = commands_ok
        self.calls = 0

    def __call__(self, device_id: str) -> bool:
        self.calls += 1
        return self.commands_ok


def _install(monkeypatch, method: str, strategy, ips):
    """Wire a fake strategy and a scripted sequence of public-IP reads."""
    monkeypatch.setitem(network_module._STRATEGIES, method, strategy)
    reads = iter(ips)
    monkeypatch.setattr(network_module, "read_public_ip", lambda device_id, **kw: next(reads))
    monkeypatch.setattr(network_module.time, "sleep", lambda seconds: None)


def test_a_changed_ip_is_verified_and_lets_the_run_start(monkeypatch):
    strategy = _FakeStrategy()
    _install(monkeypatch, "data", strategy, ["81.2.3.4", "37.167.1.9"])

    outcome = perform_network_reset("DEVICE1", method="data")

    assert outcome.verdict == "verified"
    assert outcome.ip_changed is True
    assert outcome.should_block_run is False
    assert strategy.calls == 1


def test_the_same_ip_is_proof_of_failure_and_blocks_the_run(monkeypatch):
    strategy = _FakeStrategy()
    # Same IP every read: the carrier keeps handing the sticky one back.
    _install(monkeypatch, "data", strategy, ["81.2.3.4"] * (1 + 2 * MAX_ROTATION_ATTEMPTS))

    outcome = perform_network_reset("DEVICE1", method="data")

    assert outcome.verdict == "unchanged"
    assert outcome.should_block_run is True
    # It retried before giving up rather than failing on the first attempt.
    assert strategy.calls == MAX_ROTATION_ATTEMPTS
    assert "cell-airplane" in outcome.describe()


def test_an_unreadable_ip_does_not_block_the_run(monkeypatch):
    strategy = _FakeStrategy()
    _install(monkeypatch, "airplane_cell", strategy, [None, None])

    outcome = perform_network_reset("DEVICE1", method="airplane_cell")

    assert outcome.verdict == "unverifiable"
    assert outcome.ip_changed is False
    assert outcome.should_block_run is False


def test_a_readable_new_ip_counts_as_rotated_even_if_the_old_one_was_unreadable(monkeypatch):
    strategy = _FakeStrategy()
    _install(monkeypatch, "airplane_cell", strategy, [None, "37.167.1.9"])

    outcome = perform_network_reset("DEVICE1", method="airplane_cell")

    assert outcome.verdict == "verified"


def test_commands_that_never_took_effect_block_the_run_without_retrying(monkeypatch):
    strategy = _FakeStrategy(commands_ok=False)
    _install(monkeypatch, "data", strategy, ["81.2.3.4", None])

    outcome = perform_network_reset("DEVICE1", method="data")

    assert outcome.commands_ok is False
    assert outcome.should_block_run is True
    # Repeating a command the device refused is pointless — one attempt, then report.
    assert strategy.calls == 1


def test_an_unknown_method_degrades_to_mobile_data_instead_of_crashing(monkeypatch):
    strategy = _FakeStrategy()
    _install(monkeypatch, "data", strategy, ["81.2.3.4", "37.167.1.9"])

    outcome = perform_network_reset("DEVICE1", method="vpn")

    assert outcome.method == "data"
    assert outcome.verdict == "verified"
