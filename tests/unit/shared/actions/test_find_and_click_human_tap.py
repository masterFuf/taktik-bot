"""`_find_and_click` taps a *varied* point inside the element (via `human_tap`) instead
of its exact centre, and falls back to a plain centre click when the element bounds
can't be read. This locks the P1-taps prod wiring
(`taktik-docs/bot/security/humanization-master-plan.md`).
"""

import types

from taktik.core.shared.actions.base_action import SharedBaseAction
from taktik.core.shared.device.facade import BaseDeviceFacade


class _StubFacade(BaseDeviceFacade):
    """A facade whose human_tap just records its bounds (no real device)."""

    def __init__(self):
        self._device = None
        self.logger = types.SimpleNamespace(
            debug=lambda *a, **k: None, error=lambda *a, **k: None, warning=lambda *a, **k: None
        )
        self.taps = []

    def human_tap(self, bounds, *, rng=None):
        self.taps.append(tuple(bounds))
        return (bounds[0] + 1, bounds[1] + 1)


class _Element:
    """Minimal stand-in for a uiautomator2 XPath element."""

    def __init__(self, bounds=None, raise_get=False):
        self._bounds = bounds
        self._raise = raise_get

    def get(self, timeout=0.5):
        if self._raise:
            raise RuntimeError("not found")
        return types.SimpleNamespace(bounds=self._bounds)


def _action():
    return SharedBaseAction(_StubFacade())


def test_taps_a_point_within_the_element_bounds():
    a = _action()
    assert a._human_tap_element(_Element(bounds=(10, 20, 110, 220))) is True
    assert a.device.taps == [(10, 20, 110, 220)]


def test_falls_back_when_bounds_unreadable():
    a = _action()
    assert a._human_tap_element(_Element(raise_get=True)) is False  # lookup failed
    assert a._human_tap_element(_Element(bounds=None)) is False     # no bounds
    assert a._human_tap_element(_Element(bounds=(1, 2, 3))) is False  # malformed
    assert a.device.taps == []  # never tapped → caller will element.click()
