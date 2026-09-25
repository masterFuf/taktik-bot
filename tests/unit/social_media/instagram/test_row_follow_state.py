"""The rows of a follow list, read on ONE photo of the screen.

List-level relationship read: each follower ROW carries an action button whose caption reveals our
relationship (Suivre / Suivi(e) / Suivre en retour), so an already-related follower is skipped
WITHOUT opening the profile. `get_row_follow_state` pairs a username to its row button by vertical
position and classifies the caption through the shared locale labels. Fail-open ('unknown') when a
row is unreadable or partially scrolled, so a valid target is never lost.

Each read of the list (its rows, a row's state, the tap on a row) asks all its questions of one
photo (`device.snapshot()`): one dump where `d.xpath()` took one per question. The phone here is
the facade production mounts (`CloneAwareDeviceProxy`) over uiautomator2's own xpath engine; the
dumps are invented (public repository).
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.detection.list_detection import (
    ListDetectionMixin,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.actions.core.utils import ActionUtils
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS

PKG = "com.instagram.android"


@pytest.fixture(autouse=True)
def _reset_locale():
    set_active_locale(None)
    yield
    set_active_locale(None)


def _node(rid, text, bounds, package=PKG):
    left, top, right, bottom = bounds
    return (f'<node index="0" text="{text}" resource-id="{package}:id/{rid}" class="android.widget.TextView" '
            f'package="{package}" content-desc="" clickable="true" enabled="true" '
            f'bounds="[{left},{top}][{right},{bottom}]" />')


def _screen(*nodes):
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            f'<node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="{PKG}" '
            'bounds="[0,0][1080,2400]">' + "".join(nodes) + "</node></hierarchy>")


class _Phone:
    """What uiautomator2's `d.xpath()` and a tap need; its screen is an invented dump."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2400}

    def __init__(self, xml):
        self.xml = xml
        self.dumps = 0
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.dumps += 1
        if isinstance(self.xml, Exception):
            raise self.xml
        return self.xml

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration=0.0):
        self.taps.append((x, y))

    def window_size(self):
        return 1080, 2400


def _host(xml, package=PKG):
    """The list reader on the facade every Instagram bridge mounts."""
    phone = _Phone(xml)
    host = object.__new__(ListDetectionMixin)
    host.device = DeviceFacade(CloneAwareDeviceProxy(phone, package))
    host.detection_selectors = DETECTION_SELECTORS
    host.utils = ActionUtils()
    host.logger = host.device.logger
    return host, phone


def _rows(locale, package=PKG):
    """Three clean rows, and a fourth whose button is missing (partially scrolled): that last one
    must fail open to 'unknown'. The third username sits a few pixels above its button's top, as
    Instagram 410 lays out a row with a display name."""
    set_active_locale(locale)
    fr = locale != "en"
    return _screen(
        _node("follow_list_username", "alice", (200, 100, 700, 140), package),
        _node("follow_list_row_large_follow_button", "Suivi(e)" if fr else "Following", (760, 100, 1040, 150), package),
        _node("follow_list_username", "bob", (200, 200, 700, 240), package),
        _node("follow_list_row_large_follow_button", "Suivre en retour" if fr else "Follow back", (760, 200, 1040, 250), package),
        _node("follow_list_username", "carol", (200, 296, 700, 306), package),
        _node("follow_list_row_large_follow_button", "Suivre" if fr else "Follow", (760, 305, 1040, 355), package),
        _node("follow_list_username", "dave", (200, 400, 700, 440), package),
    )


@pytest.mark.parametrize("locale", ["fr", "en", None])
def test_reads_each_relationship_from_the_row(locale):
    host, _phone = _host(_rows(locale))
    assert host.get_row_follow_state("alice") == "following"
    assert host.get_row_follow_state("bob") == "follow_back"
    assert host.get_row_follow_state("carol") == "follow"


@pytest.mark.parametrize("locale", ["fr", "en", None])
def test_fail_open_when_row_button_missing(locale):
    host, _phone = _host(_rows(locale))
    assert host.get_row_follow_state("dave") == "unknown"


def test_fail_open_for_unknown_username():
    host, _phone = _host(_rows("fr"))
    assert host.get_row_follow_state("nobody") == "unknown"


def test_no_rows_is_unknown():
    host, _phone = _host(_screen())
    assert host.get_row_follow_state("alice") == "unknown"


def test_each_read_of_the_list_is_one_dump():
    """Before the photo, a row's state cost at least four dumps (usernames `.exists` and `.all()`,
    buttons the same), the rows two, the tap on a row two."""
    host, phone = _host(_rows("fr"))
    for read in (lambda: host.get_row_follow_state("carol"),
                 host.get_visible_followers_with_elements,
                 host.extract_usernames_from_follow_list,
                 lambda: host.click_follower_in_list("bob")):
        before = phone.dumps
        read()
        assert phone.dumps - before == 1


def test_the_rows_carry_their_username_and_bounds():
    host, _phone = _host(_rows("en"))
    rows = host.get_visible_followers_with_elements()
    assert [(row["username"], tuple(row["element"].bounds)) for row in rows] == [
        ("alice", (200, 100, 700, 140)), ("bob", (200, 200, 700, 240)),
        ("carol", (200, 296, 700, 306)), ("dave", (200, 400, 700, 440))]


def test_extracted_usernames_are_the_rows_without_repeats():
    xml = _screen(_node("follow_list_username", "alice", (200, 100, 700, 140)),
                  _node("follow_list_username", "alice", (200, 200, 700, 240)),
                  _node("follow_list_username", "bob", (200, 300, 700, 340)))
    host, _phone = _host(xml)
    assert host.extract_usernames_from_follow_list() == ["alice", "bob"]
    assert [row["username"] for row in host.get_visible_followers_with_elements()] == ["alice", "alice", "bob"]


def test_a_row_is_tapped_inside_its_username():
    host, phone = _host(_rows("fr"))
    assert host.click_follower_in_list("bob") is True
    assert len(phone.taps) == 1
    x, y = phone.taps[0]
    assert 200 <= x <= 700 and 200 <= y <= 240


def test_a_username_not_on_screen_is_not_tapped():
    host, phone = _host(_rows("fr"))
    assert host.click_follower_in_list("nobody") is False
    assert phone.taps == []


def test_an_element_without_bounds_is_not_tapped():
    """A photo's element carries no device: without usable bounds there is nothing to aim at (the
    old centre click of such an element landed on a corner of the screen)."""
    host, phone = _host(_screen(_node("follow_list_username", "bob", (0, 0, 0, 0))))
    assert host.click_follower_in_list("bob") is False
    assert phone.taps == []


def test_a_failed_dump_reads_nothing_and_taps_nothing():
    host, phone = _host(RuntimeError("uiautomator2 server gone"))
    assert host.get_visible_followers_with_elements() == []
    assert host.extract_usernames_from_follow_list() == []
    assert host.get_row_follow_state("alice") == "unknown"
    assert host.click_follower_in_list("alice") is False
    assert phone.taps == []


def test_a_clone_list_is_read_through_the_proxy_rewrite():
    """The catalogue names `com.instagram.android:id/...`; a clone shows its own prefix. The photo
    applies the proxy's rewrite, as `d.xpath()` does through the proxy."""
    host, phone = _host(_rows("fr", package="com.taktik.ig1"), package="com.taktik.ig1")
    assert [row["username"] for row in host.get_visible_followers_with_elements()] == ["alice", "bob", "carol", "dave"]
    assert host.get_row_follow_state("bob") == "follow_back"
    assert host.click_follower_in_list("carol") is True and len(phone.taps) == 1
