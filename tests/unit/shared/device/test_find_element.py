"""The two element lookups differ in ONE thing, and it has to stay explicit.

Eight files carried their own copy of this loop, and the copies had drifted into two
behaviours under the same name: four tested `.exists` (instant), two awaited
`.wait(timeout=5)`. Same call, same name — one gave up on an element that appears in 200ms,
the other blocked five seconds on a screen where absence was the expected answer. That kind
of divergence surfaces as a flaky workflow, never as an error.

They are now two named functions, and these tests pin what each one promises — including
the per-selector deadline of `wait_for_element`, which is a real cost worth keeping visible.
"""

import time

import pytest

from taktik.core.shared.device.wait import find_element, wait_for_element


class _Element:
    def __init__(self, exists=False, appears_after=None):
        self._exists = exists
        self._appears_after = appears_after
        self.waited_for = None

    @property
    def exists(self):
        return self._exists

    def wait(self, timeout=0.0):
        self.waited_for = timeout
        return self._appears_after is not None and self._appears_after <= timeout


class _Device:
    """Maps a selector to an element; an unmapped selector raises, like a bad xpath."""

    def __init__(self, mapping):
        self.mapping = mapping
        self.queried = []

    def xpath(self, selector):
        self.queried.append(selector)
        if selector not in self.mapping:
            raise ValueError(f"bad selector: {selector}")
        return self.mapping[selector]


def test_find_element_returns_the_first_match_and_stops_there():
    hit = _Element(exists=True)
    device = _Device({"//a": _Element(exists=False), "//b": hit, "//c": _Element(exists=True)})

    assert find_element(device, ["//a", "//b", "//c"]) is hit
    assert device.queried == ["//a", "//b"]  # never looked past the winner


def test_find_element_returns_none_when_nothing_is_on_screen():
    device = _Device({"//a": _Element(exists=False)})
    assert find_element(device, ["//a"]) is None


def test_a_broken_selector_does_not_abort_the_lookup():
    """One malformed xpath must not cost the selectors that follow it."""
    hit = _Element(exists=True)
    device = _Device({"//good": hit})
    assert find_element(device, ["//unmapped", "//good"]) is hit


def test_find_element_never_waits():
    """`exists` only — the caller uses this one where absence is a normal outcome."""
    element = _Element(exists=False)
    device = _Device({"//a": element})

    started = time.monotonic()
    assert find_element(device, ["//a"]) is None
    assert time.monotonic() - started < 0.2
    assert element.waited_for is None


def test_wait_for_element_returns_the_one_that_appears():
    late = _Element(appears_after=2.0)
    device = _Device({"//a": _Element(appears_after=None), "//b": late})

    assert wait_for_element(device, ["//a", "//b"], timeout=3.0) is late


def test_the_deadline_is_per_selector_not_total():
    """Documented cost: a miss on N selectors spends N * timeout, not timeout.

    Kept deliberately — it is what every historical copy did, and changing it here would
    silently retime the auth and signup flows. `wait_for_any` is the bounded-total variant.
    """
    elements = {f"//{i}": _Element(appears_after=None) for i in range(3)}
    device = _Device(elements)

    assert wait_for_element(device, list(elements), timeout=1.5) is None
    assert [e.waited_for for e in elements.values()] == [1.5, 1.5, 1.5]


@pytest.mark.parametrize("empty", [[], None])
def test_no_selectors_is_not_a_crash(empty):
    device = _Device({})
    assert find_element(device, empty) is None
    assert wait_for_element(device, empty) is None
