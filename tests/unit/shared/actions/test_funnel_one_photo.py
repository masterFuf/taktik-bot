"""The shared funnel asks all its selectors of ONE photo of the screen.

`_is_element_present`, `_get_text_from_element` and `_get_element_attribute` take one photo per
call, `_wait_for_element` one per turn, where `d.xpath()` took one dump per selector (and two for
a text or an attribute: `.exists`, then `.get()`). Unchanged: the order of the selectors, "the
first that answers", the timeout and the pause between turns, a rejected selector skipped, a
failed dump finding nothing.

The phone is uiautomator2's own xpath engine behind the real facades; the dumps are invented
(public repository).
"""

import time

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.actions.base_action import SharedBaseAction
from taktik.core.shared.device.facade import BaseDeviceFacade

PKG = "com.example.app"


def _node(rid, text, package=PKG, desc=""):
    return (f'<node index="0" text="{text}" resource-id="{package}:id/{rid}" class="android.widget.TextView" '
            f'package="{package}" content-desc="{desc}" clickable="false" enabled="true" bounds="[0,0][100,50]" />')


def _screen(*nodes, package=PKG):
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            f'<node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="{package}" '
            'bounds="[0,0][1080,2400]">' + "".join(nodes) + "</node></hierarchy>")


SCREEN = _screen(_node("title", "  Hello  ", desc="greeting"), _node("empty", ""), _node("count", "12"))


class _Phone:
    """Serves its screens in turn (the last one stays), counts its dumps."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2400}

    def __init__(self, *screens):
        self.screens = list(screens)
        self.dumps = 0
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        screen = self.screens[min(self.dumps, len(self.screens) - 1)]
        self.dumps += 1
        if isinstance(screen, Exception):
            raise screen
        return screen


def _action(*screens, clone_package=None):
    phone = _Phone(*screens)
    device = CloneAwareDeviceProxy(phone, clone_package) if clone_package else phone
    return SharedBaseAction(BaseDeviceFacade(device)), phone


def _id(rid, package=PKG):
    return f'//*[@resource-id="{package}:id/{rid}"]'


@pytest.fixture
def clock(monkeypatch):
    """A clock that only moves when the code sleeps."""
    now = [100.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


def test_presence_is_one_dump_whatever_the_number_of_selectors():
    action, phone = _action(SCREEN)
    assert action._is_element_present([_id("a"), _id("b"), _id("c"), _id("count")]) is True
    assert action._is_element_present([_id("a"), _id("b"), _id("c")]) is False
    assert phone.dumps == 2


def test_nothing_to_look_for_takes_no_photo():
    action, phone = _action(SCREEN)
    assert action._is_element_present([]) is False
    assert action._get_text_from_element([]) is None
    assert phone.dumps == 0


def test_text_is_the_first_non_empty_one_stripped_on_one_dump():
    action, phone = _action(SCREEN)
    assert action._get_text_from_element([_id("missing"), _id("empty"), _id("title")]) == "Hello"
    assert action._get_text_from_element(_id("count")) == "12"
    assert action._get_text_from_element([_id("missing"), _id("empty")]) is None
    assert phone.dumps == 3


def test_an_attribute_is_read_from_the_first_match_on_one_dump():
    action, phone = _action(SCREEN)
    assert action._get_element_attribute([_id("missing"), _id("title")], "content-desc") == "greeting"
    assert phone.dumps == 1


def test_a_rejected_selector_is_skipped():
    action, _phone = _action(SCREEN)
    assert action._is_element_present(["//*[", _id("count")]) is True
    assert action._get_text_from_element(["//*[", _id("count")]) == "12"


def test_a_failed_dump_finds_nothing():
    action, _phone = _action(RuntimeError("uiautomator2 server gone"))
    assert action._is_element_present([_id("count")]) is False
    assert action._get_text_from_element([_id("count")]) is None
    assert action._get_element_attribute([_id("count")], "text") is None


def test_a_wait_takes_one_photo_per_turn_until_the_element_appears(clock):
    action, phone = _action(_screen(), _screen(), SCREEN)
    assert action._wait_for_element([_id("a"), _id("b"), _id("count")], timeout=5.0, check_interval=0.5) is True
    assert phone.dumps == 3
    assert clock[0] == 101.0  # two pauses, as before


def test_a_wait_that_times_out_keeps_its_turns(clock):
    action, phone = _action(_screen())
    assert action._wait_for_element([_id("a"), _id("b")], timeout=2.0, check_interval=0.5) is False
    assert phone.dumps == 4  # one photo per turn: 0, 0.5, 1.0, 1.5
    action._wait_for_element([_id("a")], timeout=0.0)
    assert phone.dumps == 4  # a zero timeout does not look


def test_a_clone_screen_is_read_through_the_proxy_rewrite():
    """The catalogue names the official package; a clone shows its own prefix. The photo applies
    the proxy's rewrite, as `d.xpath()` does through the proxy."""
    clone = "com.example.clone1"
    action, phone = _action(_screen(_node("count", "12", package=clone), package=clone), clone_package=clone)
    assert action._is_element_present([_id("count")]) is True
    assert action._get_text_from_element([_id("count")]) == "12"
    assert phone.dumps == 2
