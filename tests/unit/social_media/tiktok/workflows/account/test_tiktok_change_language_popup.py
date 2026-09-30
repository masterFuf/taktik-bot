"""The language change closes a modal in its way through the shared popup actions.

`_scroll_to` asks `_dismiss_blocking_popup` before spending another scroll under a modal. Its lazy
import aimed at `actions/atomic/popup_actions`, which does not exist (the popup actions live under
`actions/atomic/interaction/`): the ImportError went to a debug line and nothing was ever closed.

The screen is a real capture holding a modal `close_popup` knows: TikTok's invite banner over the
Messages inbox, 43.1.4 in French (Pixel 3a), anonymized, read by uiautomator2's own `XPathEntry`.
"""

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_action_module
import taktik.core.social_media.tiktok.workflows.account.change_language_workflow as language_module
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.workflows.account.change_language_workflow import TikTokChangeLanguageWorkflow
from unit.paths import CORE

PKG = "com.zhiliaoapp.musically:id/"
INBOX_WITH_BANNER = (CORE / "tests/unit/social_media/tiktok/fixtures/tt4314_fr_inbox.xml").read_text(encoding="utf-8")


DUMP_S = 0.25


class _Clock:
    """Time moves only when the code sleeps or dumps the screen."""

    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(float(seconds), 0.0)


class _Phone:
    """Shows the capture, records the taps; the xpath queries are uiautomator2's."""

    wait_timeout = 1.0

    def __init__(self, clock, xml):
        self.clock, self.xml = clock, xml
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.clock.now += DUMP_S
        return self.xml

    def click(self, x, y):
        self.taps.append((x, y))

    def window_size(self):
        return 1080, 2400


def _bounds(xml, rid):
    """The bounds of a node of the capture, read without the production readers."""
    node = etree.fromstring(xml.encode("utf-8")).xpath(f'//node[@resource-id="{PKG}{rid}"]')[0]
    left_top, right_bottom = node.get("bounds").strip("[]").split("][")
    return tuple(int(v) for v in left_top.split(",")) + tuple(int(v) for v in right_bottom.split(","))


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    for module in (shared_action_module, language_module):
        monkeypatch.setattr(module, "time", fake)
    return fake


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def test_a_modal_in_the_way_is_closed_before_the_next_scroll(clock):
    phone = _Phone(clock, INBOX_WITH_BANNER)

    assert TikTokChangeLanguageWorkflow(phone)._dismiss_blocking_popup() is True

    # One tap, on the banner's close button (the X, `fac`, inside its clickable frame `fad`).
    left, top, right, bottom = _bounds(INBOX_WITH_BANNER, "fad")
    assert len(phone.taps) == 1
    x, y = phone.taps[0]
    assert left <= x <= right and top <= y <= bottom
