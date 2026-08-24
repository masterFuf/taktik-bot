"""A selector that stops matching must say its name.

A missed selector is how an app update announces itself, and it used to produce a loguru warning
and nothing else: no name on the wire, so neither the run log nor a crash report could tell which
one gave up. These tests pin the `selector_miss` metric that carries it.
"""

import pytest

from taktik.core.shared.device import wait as wait_module
from taktik.core.shared.telemetry import clear_telemetry_sink, configure_telemetry_sink


class FakeXPath:
    def __init__(self, matches: bool):
        self._matches = matches

    @property
    def exists(self) -> bool:
        return self._matches

    def wait(self, timeout: float = 0) -> bool:
        return self._matches


class FakeDevice:
    """A screen where the given selectors match and nothing else does."""

    def __init__(self, matching: set[str] | None = None):
        self.matching = matching or set()

    def xpath(self, selector: str) -> FakeXPath:
        return FakeXPath(selector in self.matching)


@pytest.fixture
def metrics():
    captured = []
    configure_telemetry_sink(captured.append)
    yield captured
    clear_telemetry_sink()


def test_wait_for_any_reports_the_miss(metrics, monkeypatch):
    monkeypatch.setattr(wait_module.time, "sleep", lambda _s: None)

    found = wait_module.wait_for_any(FakeDevice(), ["//a", "//b", "//c"], timeout=0.01)

    assert found is None
    misses = [m for m in metrics if m.category == "selector_miss"]
    assert len(misses) == 1
    assert misses[0].action == "wait_for_any"
    assert misses[0].target == "//a"
    assert misses[0].detail["selector_count"] == 3
    assert misses[0].detail["timeout_s"] == 0.01
    assert misses[0].detail["elapsed_ms"] >= 0


def test_a_hit_reports_nothing(metrics, monkeypatch):
    monkeypatch.setattr(wait_module.time, "sleep", lambda _s: None)

    found = wait_module.wait_for_any(FakeDevice({"//b"}), ["//a", "//b"], timeout=0.5)

    assert found == "//b"
    assert [m for m in metrics if m.category == "selector_miss"] == []


def test_wait_for_element_reports_the_miss(metrics):
    element = wait_module.wait_for_element(FakeDevice(), ["//a", "//b"], timeout=0)

    assert element is None
    misses = [m for m in metrics if m.category == "selector_miss"]
    assert len(misses) == 1
    assert misses[0].action == "wait_for_element"
    assert misses[0].detail["selector_count"] == 2


def test_find_element_stays_silent(metrics):
    """`find_element` answers "is it on screen already?" — absence is a normal outcome there.

    Reporting it would drown the real signal under every popup check that legitimately finds
    nothing.
    """
    assert wait_module.find_element(FakeDevice(), ["//a"]) is None
    assert [m for m in metrics if m.category == "selector_miss"] == []


def test_telemetry_stays_silent_without_a_sink(monkeypatch):
    """Standalone runs and unit tests must not pay for telemetry they never wired."""
    clear_telemetry_sink()
    monkeypatch.setattr(wait_module.time, "sleep", lambda _s: None)

    assert wait_module.wait_for_any(FakeDevice(), ["//a"], timeout=0.01) is None
