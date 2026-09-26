"""Cold DM: no decision off a profile, and the tab bar's Direct tab is no Message button.

Measured on a Pixel 3 (Instagram 410, in French): the Lab's `dm.cold_dm_check_profile`, run on
the home feed, answered "DM would be attempted" with a Message button found. The evaluation read
the screen without asking whether it was a profile, and took the tab bar's Direct tab, whose
content-desc is the button's own label ("Envoyer un message", "Message" in English), for the
profile's Message button. In a run, a search that opened no profile would tap the inbox tab and
type the message there.

The screens are real dumps, anonymized (every text and content-desc emptied except the app's
interface labels, the Android system bars removed):
- `ig410_fr_home_feed.xml`: the Pixel 3's home feed, in French;
- `ig410_en_own_profile.xml`: the account's own profile with its tab bar, in English;
- `ig410_en_profile_with_message_button.xml`: another account's profile and its Message button.

The phone answers `xpath` through uiautomator2's own engine and the `d(text=...)` calls from the
same dump, behind the clone proxy and the facade the bridges mount; its clock jumps when the code
sleeps.
"""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.actions.atomic.detection.screen_detection as screen_detection
import taktik.core.social_media.instagram.workflows.cold_dm.navigation as cold_dm_navigation
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.cold_dm.navigation import NOT_ON_PROFILE
from taktik.core.social_media.instagram.workflows.cold_dm.recipient_policy import ColdDmRecipientPolicy
from taktik.core.social_media.instagram.workflows.cold_dm.workflow import ColdDMWorkflow

PKG = "com.instagram.android"
FIXTURES = Path(__file__).parent / "fixtures"
HOME_FR = (FIXTURES / "ig410_fr_home_feed.xml").read_text(encoding="utf-8")
OWN_PROFILE_EN = (FIXTURES / "ig410_en_own_profile.xml").read_text(encoding="utf-8")
PROFILE_EN = (FIXTURES / "ig410_en_profile_with_message_button.xml").read_text(encoding="utf-8")
MESSAGE_BUTTON = (496, 877, 943, 965)


class _Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(0.0, seconds)


def _bounds(node):
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


_UI_SELECTOR = {
    "text": lambda node, value: node.get("text") == value,
    "description": lambda node, value: node.get("content-desc") == value,
    "resourceId": lambda node, value: node.get("resource-id") == value,
    # uiautomator's regex: the whole id must match (the clone proxy asks every id this way).
    "resourceIdMatches": lambda node, value: re.fullmatch(value, node.get("resource-id") or "") is not None,
    "className": lambda node, value: node.get("class") == value,
    "textContains": lambda node, value: value in (node.get("text") or ""),
    "descriptionContains": lambda node, value: value in (node.get("content-desc") or ""),
}


class _Selection:
    """What a uiautomator2 `d(**selector)` finds, read off the dump: document order."""

    def __init__(self, phone, nodes):
        self._phone = phone
        self._nodes = nodes

    @property
    def exists(self):
        return bool(self._nodes)

    @property
    def count(self):
        return len(self._nodes)

    def __getitem__(self, index):
        return _Selection(self._phone, [self._nodes[index]])

    @property
    def info(self):
        return {"resourceName": self._nodes[0].get("resource-id")}

    def click(self):
        left, top, right, bottom = _bounds(self._nodes[0])
        self._phone.taps.append(((left + right) // 2, (top + bottom) // 2))


class _Phone:
    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}

    def __init__(self, xml):
        self.xml = xml
        self.nodes = list(etree.fromstring(xml.encode("utf-8")).iter("node"))
        self.xpath = XPathEntry(self)
        self.queries = []
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return 1080, 2160

    def __call__(self, **selector):
        self.queries.append(selector)
        return _Selection(self, [n for n in self.nodes
                                 if all(_UI_SELECTOR[k](n, v) for k, v in selector.items())])

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration=0.0):
        self.taps.append((x, y))


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(screen_detection, "time", clock)
    monkeypatch.setattr(cold_dm_navigation.time, "sleep", lambda *_: None)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    yield
    set_active_locale(None)


def _workflow(phone):
    """The production workflow, on the device a bridge hands it."""
    proxy = CloneAwareDeviceProxy(phone, PKG)
    return ColdDMWorkflow(DeviceFacade(proxy), SimpleNamespace(device=proxy),
                          keyboard=SimpleNamespace(device_id="demo-phone"))


def _lab_bundle(phone):
    facade = DeviceFacade(CloneAwareDeviceProxy(phone, PKG))
    return SimpleNamespace(device=facade, detection=DetectionActions(facade))


# ── off a profile: nothing read, nothing tapped ──────────────────────────────────────────────

def test_the_lab_check_refuses_the_home_feed_and_reads_nothing():
    from bridges.compat.diagnostics.actions.instagram.dm import cold_dm_check_profile

    set_active_locale("fr")
    phone = _Phone(HOME_FR)

    result = cold_dm_check_profile(_lab_bundle(phone), {"skipVerified": "true"})

    assert result["success"] is False
    assert "not on a profile" in result["message"]
    assert result["details"]["on_profile"] is False
    assert result["details"]["has_message_button"] is None
    assert phone.queries == [] and phone.taps == []


def test_a_search_that_opened_no_profile_taps_nothing_and_composes_nothing(monkeypatch):
    set_active_locale("fr")
    phone = _Phone(HOME_FR)
    composed, sent = [], []
    monkeypatch.setattr(ColdDMWorkflow, "navigate_to_search", lambda self: True)
    monkeypatch.setattr(ColdDMWorkflow, "search_user", lambda self, username: True)
    monkeypatch.setattr(ColdDMWorkflow, "send_message", lambda self, message: sent.append(message) or True)

    reached = _workflow(phone).reach_and_send("demo_recipient", lambda: composed.append(1) or "Bonjour",
                                              ColdDmRecipientPolicy())

    assert reached == {"outcome": NOT_ON_PROFILE}
    assert phone.taps == [] and composed == [] and sent == []


# ── on a profile: the Direct tab is never the Message button ─────────────────────────────────

def test_the_direct_tab_is_not_the_message_button_of_a_profile_without_one():
    set_active_locale("en")
    phone = _Phone(OWN_PROFILE_EN)
    workflow = _workflow(phone)

    opened = workflow.open_dm_from_profile(ColdDmRecipientPolicy(skip_private=False))
    verdict = workflow.evaluate_cold_dm_profile(ColdDmRecipientPolicy(skip_private=False))

    assert opened is False
    assert phone.taps == []
    assert verdict["has_message_button"] is False
    assert verdict["on_profile"] is True


def test_the_message_button_of_a_profile_is_still_found_and_tapped():
    set_active_locale("en")
    phone = _Phone(PROFILE_EN)

    opened = _workflow(phone).open_dm_from_profile(ColdDmRecipientPolicy())

    assert opened is True
    assert len(phone.taps) == 1
    x, y = phone.taps[0]
    left, top, right, bottom = MESSAGE_BUTTON
    assert left <= x <= right and top <= y <= bottom


def test_the_lab_check_on_a_profile_without_message_button_says_the_dm_would_fail():
    from bridges.compat.diagnostics.actions.instagram.dm import cold_dm_check_profile

    set_active_locale("en")
    phone = _Phone(OWN_PROFILE_EN)

    result = cold_dm_check_profile(_lab_bundle(phone), {"skipPrivate": "false"})

    assert result["success"] is True
    assert result["details"]["has_message_button"] is False
    assert "would fail" in result["message"]
    assert phone.taps == []
