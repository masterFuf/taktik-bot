"""The problematic-page detector reads the screen whatever device object it is handed.

On 2026-10-25 (Pixel 6a, Instagram 447, `instagram.engagement.coldDm`), on the way back home, the
detector logged `'DeviceManager' object has no attribute 'dump_hierarchy'`: the cold DM builds its
navigation on the `DeviceManager`, `NavigationActions` handed that object to its detector as it was,
and the detector called `dump_hierarchy()` on it. The read failed, and the failure answered "no
account check" (and "no block"): the check was never seen on that path, nor on any other that builds
its navigation on a `DeviceManager` (the agent's autopilot, the DM persistence, the persona bridge).

Now the detector reads through the device facade, whatever it receives (the facade itself, the
shared one a bridge mounts, the bare uiautomator2 device, the clone proxy, a `DeviceManager`), and
a screen it could not read is an error said as such (`SnapshotUnavailable`), never a "no".

The screens are real captures, anonymized: the account check (410, French) and the contacts request
(447, French), an Instagram alert that is not a block.
"""

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.shared.device.manager import DeviceManager
from taktik.core.shared.device.snapshot import SnapshotUnavailable
from taktik.core.shared.diagnostics import run_halt
from taktik.core.shared.diagnostics.action_block import look_for_action_block
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.selectors import locales
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
CHALLENGE = (FIXTURES / "ig410_fr_account_challenge.xml").read_text(encoding="utf-8")
CONTACTS_PROMPT = (FIXTURES / "ig447_fr_discover_people_contacts_prompt.xml").read_text(encoding="utf-8")
OPTIONS_SHEET = (FIXTURES / "ig410_en_profile_options_sheet.xml").read_text(encoding="utf-8")
CHALLENGE_ACTIVITY = "com.instagram.challenge.activity.ChallengeActivity"


class _Phone:
    """uiautomator2 as the detector reads it: one screen, its activity, every gesture recorded."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}

    def __init__(self, screen, activity=CHALLENGE_ACTIVITY):
        self.screen = screen
        self.activity = activity
        self.gestures = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        if isinstance(self.screen, Exception):
            raise self.screen
        return self.screen

    def app_current(self):
        return {"package": "com.instagram.android", "activity": self.activity}

    def press(self, key):
        self.gestures.append(f"press {key}")

    def click(self, x, y):
        self.gestures.append(f"click {x},{y}")

    def window_size(self):
        return 1080, 2160

    def swipe(self, *_a, **_k):
        self.gestures.append("swipe")


def _manager(device):
    """A `DeviceManager` once connected: its `device` is the phone (behind the clone proxy, as
    `InstagramDeviceBase` leaves it)."""
    manager = DeviceManager("demo-serial")
    manager.device = device
    return manager


#: Every object a detector is built on today, by the path that hands it.
FORMS = {
    "bare uiautomator2 device (InstagramAutomation, autopilot's look after a gesture)": lambda p: p,
    "clone proxy (autopilot's `device_manager.device`)": lambda p: CloneAwareDeviceProxy(p, "com.instagram.android"),
    "DeviceManager (NavigationActions of the cold DM, the autopilot, the DM persistence)":
        lambda p: _manager(CloneAwareDeviceProxy(p, "com.instagram.android")),
    "shared facade (InstagramDeviceBase.device: DM, cold DM, notifications)": lambda p: BaseDeviceFacade(p),
    "Instagram facade (an action's own device)": lambda p: DeviceFacade(p),
}


@pytest.fixture
def warnings_logged():
    """The warnings (and worse) the code under test logs, one message per entry."""
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="WARNING")
    yield lines
    logger.remove(sink)


@pytest.fixture(autouse=True)
def fresh_latch():
    run_halt.reinitialiser()
    before = locales.active_locale()
    locales.set_active_locale("fr")
    yield
    locales.set_active_locale(before)
    run_halt.reinitialiser()


@pytest.mark.parametrize("form", FORMS.values(), ids=FORMS.keys())
def test_the_account_check_is_seen_whatever_device_the_detector_is_handed(form):
    phone = _Phone(CHALLENGE)

    assert ProblematicPageDetector(form(phone)).is_account_challenged() is True
    assert (run_halt.arret_demande() or {}).get("code") == "account_challenge"
    assert phone.gestures == []


@pytest.mark.parametrize("form", FORMS.values(), ids=FORMS.keys())
def test_the_look_after_a_gesture_sees_the_check_whatever_device_it_is_handed(form):
    phone = _Phone(CHALLENGE)

    assert look_for_action_block(ProblematicPageDetector(form(phone)), after="dm", target="demo") is True
    assert phone.gestures == []


@pytest.mark.parametrize("form", FORMS.values(), ids=FORMS.keys())
def test_the_check_of_pages_names_the_check_whatever_device_it_is_handed(form):
    phone = _Phone(CHALLENGE)

    result = ProblematicPageDetector(form(phone)).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": False, "soft_ban": True, "page_type": "account_challenge"}
    assert phone.gestures == []


@pytest.mark.parametrize("form", FORMS.values(), ids=FORMS.keys())
def test_an_alert_that_is_no_block_is_a_no_read_on_the_screen(form):
    # The contacts request is an Instagram alert, not a block: a "no" read on a real screen.
    assert ProblematicPageDetector(form(_Phone(CONTACTS_PROMPT))).is_action_blocked() is False
    assert run_halt.arret_demande() is None


@pytest.mark.parametrize("form", FORMS.values(), ids=FORMS.keys())
def test_the_tap_outside_a_sheet_lands_whatever_device_it_is_handed(form, monkeypatch):
    # The Instagram facade's `click` takes an xpath: the tap, written for the bare device, was an
    # error there (the actions' facade, the Lab's) and never reached the screen.
    from taktik.core.social_media.instagram.ui.detectors import problematic_page

    monkeypatch.setattr(problematic_page.time, "sleep", lambda *_a, **_k: None)
    phone = _Phone(OPTIONS_SHEET)

    assert ProblematicPageDetector(form(phone))._close_via_tap_outside() is True
    assert phone.gestures == ["click 540,453"]


def test_the_cold_dm_way_home_presses_no_back_on_the_check():
    # The path of the finding: the navigation built on the DeviceManager, its tab bar gone.
    phone = _Phone(CHALLENGE)
    navigation = NavigationActions(_manager(CloneAwareDeviceProxy(phone, "com.instagram.android")))
    backs = []
    navigation._back_one_screen = lambda: backs.append("back")

    assert navigation._back_out_until(lambda: False) is False
    assert backs == []
    assert phone.gestures == []
    assert (run_halt.arret_demande() or {}).get("code") == "account_challenge"


@pytest.mark.parametrize("screen", [RuntimeError("uiautomator2 server gone"), ""],
                         ids=["the dump fails", "the dump is empty"])
def test_a_screen_that_cannot_be_read_is_never_a_no(screen):
    detector = ProblematicPageDetector(_manager(_Phone(screen)))

    with pytest.raises(SnapshotUnavailable):
        detector.is_account_challenged()
    with pytest.raises(SnapshotUnavailable):
        detector.is_action_blocked()
    with pytest.raises(SnapshotUnavailable):
        detector.detect_and_handle_problematic_pages()
    assert run_halt.arret_demande() is None


def test_the_look_after_a_gesture_says_an_unread_screen_and_proves_no_block(warnings_logged):
    detector = ProblematicPageDetector(_Phone(RuntimeError("uiautomator2 server gone")))

    # Nothing is proven, so nothing is stopped; the log says the block could not be ruled out.
    assert look_for_action_block(detector, after="dm", target="demo") is False
    assert run_halt.arret_demande() is None
    assert any("cannot be ruled out" in line for line in warnings_logged)


def test_no_back_is_pressed_on_a_screen_that_could_not_be_read():
    navigation = NavigationActions(_Phone(RuntimeError("uiautomator2 server gone")))
    backs = []
    navigation._back_one_screen = lambda: backs.append("back")

    assert navigation._back_out_until(lambda: False) is False
    assert backs == []


def test_a_device_manager_never_connected_is_an_unread_screen_not_a_no():
    # It holds no phone: the facade keeps the manager itself, and every read fails, said as such.
    with pytest.raises(SnapshotUnavailable):
        ProblematicPageDetector(DeviceManager("demo-serial")).is_action_blocked()


def test_the_watchdog_says_an_unread_screen_and_sees_the_check_through_a_device_manager(warnings_logged):
    from taktik.core.social_media.instagram.ui.watchdog import WorkflowWatchdog

    assert WorkflowWatchdog(_Phone(RuntimeError("uiautomator2 server gone")))._block_on_screen() is False
    assert run_halt.arret_demande() is None
    assert any("cannot be ruled out" in line for line in warnings_logged)

    phone = _Phone(CHALLENGE)
    assert WorkflowWatchdog(_manager(phone))._block_on_screen() is True
    assert (run_halt.arret_demande() or {}).get("code") == "account_challenge"
    assert phone.gestures == []
