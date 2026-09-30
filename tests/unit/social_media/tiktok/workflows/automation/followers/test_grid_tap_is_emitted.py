"""The tap that opens a video from a TikTok profile's grid is emitted like every other tap.

On a run of target profiles (Pixel 6a, TikTok 47.0.3), the three taps on a grid thumbnail were
written nowhere: 20 humanized taps came out as `step_metric` `tap` / `press`, not these. The
workflow holds the raw uiautomator2 device (`TikTokStartup.device`); `tap_element_human` tapped
it by `long_click` itself, a copy of the facade's `human_tap` without its log line nor its step
metric. Its taps could only be inferred from `grid_entry_choice` and the viewing that followed.

The grid is a real 47.0.3 profile (`tt4703_fr_profile_followed.xml`, anonymized), read by the
`d.xpath()` engine of uiautomator2; the tap is the production `_click_profile_post`.
"""

import types

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.shared.telemetry import sink
from taktik.core.social_media.tiktok.workflows.automation.followers import interaction
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from unit.paths import CORE

PROFILE = CORE / "tests/unit/social_media/tiktok/fixtures/tt4703_fr_profile_followed.xml"


class _RawPhone:
    """The raw uiautomator2 device the workflow holds: the dump, and the fingers it moves."""

    wait_timeout = 0.0

    def __init__(self, xml):
        self._xml = xml
        self.xpath = XPathEntry(self)
        self.presses = []

    def dump_hierarchy(self, *_a, **_k):
        return self._xml

    def long_click(self, x, y, duration):
        self.presses.append((x, y, duration))

    def click(self, x, y):
        self.presses.append((x, y, None))


class _Visit(interaction.VideoInteractionMixin):
    """A profile visit: the real `_click_profile_post`, on the raw phone."""

    def __init__(self, phone):
        self.device = phone
        self.followers_selectors = FOLLOWERS_SELECTORS
        self.logger = types.SimpleNamespace(debug=lambda *_: None, info=lambda *_: None)
        self.click = None  # the first-post fallback is not reached: the grid has its cells


@pytest.fixture
def metrics(monkeypatch):
    """The metrics emitted during the test; the sink a bridge installed before is put back after."""
    sent = []
    monkeypatch.setattr(sink, "_sink", sent.append)
    return sent


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    monkeypatch.setattr(interaction.time, "sleep", lambda *_: None)


def _cells(phone):
    for selector in FOLLOWERS_SELECTORS.profile_post_item:
        cells = phone.xpath(selector).all()
        if cells:
            return cells
    return []


@pytest.mark.parametrize("index", [0, 4, 8])
def test_the_grid_tap_is_a_tap_step_metric(metrics, index):
    phone = _RawPhone(PROFILE.read_text(encoding="utf-8"))
    cell = tuple(_cells(phone)[index].bounds)

    assert _Visit(phone)._click_profile_post(index) is True

    assert len(phone.presses) == 1
    x, y, duration = phone.presses[0]
    taps = [m for m in metrics if m.category == "tap"]
    assert len(taps) == 1
    assert taps[0].action == "press"
    assert (taps[0].detail["x"], taps[0].detail["y"]) == (x, y)
    assert tuple(taps[0].detail["bounds"]) == cell
    assert taps[0].detail["down_ms"] == round(duration * 1000)


def test_a_tap_through_the_facade_is_emitted_once(metrics):
    """The facade and the raw device go through the same tap: one metric, never two."""
    phone = _RawPhone(PROFILE.read_text(encoding="utf-8"))
    cell = _cells(phone)[0]

    assert tap_element_human(BaseDeviceFacade(phone), cell) is True

    assert len(phone.presses) == 1
    assert [m.category for m in metrics] == ["tap"]
