"""The rows of a follow list, read on ONE photo of the screen.

List-level relationship read: each follower ROW carries an action button whose caption reveals our
relationship (Suivre / Suivi(e) / Suivre en retour), so an already-related follower is skipped
WITHOUT opening the profile. `get_row_follow_state` pairs a username to its row button by vertical
position and classifies the caption through the shared locale labels. Fail-open ('unknown') when a
row is unreadable or partially scrolled, so a valid target is never lost.

Each read of the list (its rows, a row's state, the tap on a row) asks all its questions of one
photo (`device.snapshot()`): one dump where `d.xpath()` took one per question. The phone here is
the facade production mounts (`CloneAwareDeviceProxy`) over uiautomator2's own xpath engine.

The screens are real follow lists of Instagram 410.0.0.53.71, anonymized:
- French, our followers (Pixel 4a): "Suivi(e)" and "Suivre en retour" rows, the top row scrolled
  half away, its button clipped and its name gone;
- French, another account's followers (Pixel 3a): "Suivre" rows;
- French, our followers while the buttons are still drawing (Pixel 3): most captions empty;
- English, our followers (Pixel 3a): "Follow back" and "Following" rows, the last one cut by the
  bottom edge;
- English, another account's followers (Pixel 3): "Follow" rows.
The expected state of a row is its OWN button, found in its row container
(`follow_list_container`), not by the position pairing under test.

Three screens are derived from the French list, said where they are: a row repeated, a name with
no size, and the list of a clone app (the same dump under the clone's package).
"""

import copy
from pathlib import Path

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.ui_dump import parse_bounds
from taktik.core.social_media.instagram.actions.atomic.detection.list_detection import (
    ListDetectionMixin,
)
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.actions.base.utils import ActionUtils
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS

PKG = "com.instagram.android"
CLONE = "com.taktik.ig1"
FIXTURES = Path(__file__).parent / "fixtures"


def _screen(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


FR_OURS = _screen("ig410_fr_followers_list.xml")
FR_THEIRS = _screen("ig410_fr_followers_list_of_another_account.xml")
FR_DRAWING = _screen("ig410_fr_followers_list_buttons_unlabelled.xml")
EN_OURS = _screen("ig410_en_followers_list.xml")
EN_THEIRS = _screen("ig410_en_followers_list_of_another_account.xml")
NO_LIST = _screen("ig410_fr_own_profile.xml")

LISTS = {"fr": [FR_OURS, FR_THEIRS], "en": [EN_OURS, EN_THEIRS], None: [FR_OURS, FR_THEIRS, EN_OURS, EN_THEIRS]}
STATES = {"Suivi(e)": "following", "Suivre en retour": "follow_back", "Suivre": "follow",
          "Following": "following", "Follow back": "follow_back", "Follow": "follow"}


@pytest.fixture(autouse=True)
def _reset_locale():
    set_active_locale(None)
    yield
    set_active_locale(None)


def _short(node) -> str:
    return node.get("resource-id", "").rsplit("/", 1)[-1]


def _rows(xml: str) -> list:
    """(username, username bounds, caption of the row's own button or None), top to bottom."""
    rows = []
    for row in etree.fromstring(xml.encode("utf-8")).iter("node"):
        if _short(row) != "follow_list_container":
            continue
        names = [n for n in row.iter("node") if _short(n) == "follow_list_username"]
        buttons = [n for n in row.iter("node") if _short(n) == "follow_list_row_large_follow_button"]
        if names:
            caption = buttons[0].get("text") if buttons else None
            rows.append((names[0].get("text"), parse_bounds(names[0].get("bounds")), caption))
    return rows


def _derived(xml: str, change) -> str:
    root = etree.fromstring(xml.encode("utf-8"))
    change(root)
    return etree.tostring(root, encoding="unicode")


def _first_row(root):
    return next(n for n in root.iter("node") if _short(n) == "follow_list_container"
                and any(_short(c) == "follow_list_username" for c in n.iter("node")))


def _row_repeated(root):
    row = _first_row(root)
    row.getparent().append(copy.deepcopy(row))


def _name_without_size(root):
    name = next(n for n in _first_row(root).iter("node") if _short(n) == "follow_list_username")
    name.set("bounds", "[0,0][0,0]")


class _Phone:
    """What uiautomator2's `d.xpath()` and a tap need; its screen is a real dump."""

    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.dumps = 0
        self.taps = []
        self.xpath = XPathEntry(self)
        width, height = 1080, 2400
        if isinstance(xml, str):
            first = etree.fromstring(xml.encode("utf-8")).find("node")
            _, _, width, height = parse_bounds(first.get("bounds"))
        self.info = {"displayWidth": width, "displayHeight": height}

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
        return self.info["displayWidth"], self.info["displayHeight"]


def _host(xml, package=PKG):
    """The list reader on the facade every Instagram bridge mounts."""
    phone = _Phone(xml)
    host = object.__new__(ListDetectionMixin)
    host.device = DeviceFacade(CloneAwareDeviceProxy(phone, package))
    host.detection_selectors = DETECTION_SELECTORS
    host.utils = ActionUtils()
    host.logger = host.device.logger
    return host, phone


@pytest.mark.parametrize("locale", ["fr", "en", None])
def test_reads_each_relationship_from_the_row(locale):
    set_active_locale(locale)
    seen = set()
    for xml in LISTS[locale]:
        host, _phone = _host(xml)
        for username, _bounds, caption in _rows(xml):
            assert host.get_row_follow_state(username) == STATES[caption], (username, caption)
            seen.add(STATES[caption])
    assert seen == {"following", "follow_back", "follow"}


def test_the_clipped_button_of_a_row_scrolled_away_is_paired_with_no_name():
    """The top row of the French list lost its name under the tabs; its clipped button sits just
    above the first whole row, which keeps its own button."""
    set_active_locale("fr")
    root = etree.fromstring(FR_OURS.encode("utf-8"))
    headless = [row for row in root.iter("node") if _short(row) == "follow_list_container"
                and not any(_short(c) == "follow_list_username" for c in row.iter("node"))]
    assert headless and headless[0].xpath('.//node[@text="Suivi(e)"]')
    username, _bounds, caption = _rows(FR_OURS)[0]
    assert caption == "Suivre en retour"

    host, _phone = _host(FR_OURS)
    assert host.get_row_follow_state(username) == "follow_back"


@pytest.mark.parametrize("locale", ["fr", None])
def test_fail_open_when_row_button_says_nothing(locale):
    """While the list draws, a row's button can be on screen with no caption yet."""
    set_active_locale(locale)
    host, _phone = _host(FR_DRAWING)
    unlabelled = [username for username, _b, caption in _rows(FR_DRAWING) if caption == ""]
    assert unlabelled
    for username in unlabelled:
        assert host.get_row_follow_state(username) == "unknown"


def test_fail_open_for_unknown_username():
    set_active_locale("fr")
    host, _phone = _host(FR_OURS)
    assert host.get_row_follow_state("nobody") == "unknown"


def test_no_rows_is_unknown():
    host, _phone = _host(NO_LIST)
    username = _rows(FR_OURS)[0][0]
    assert host.get_row_follow_state(username) == "unknown"


def test_each_read_of_the_list_is_one_dump():
    """Before the photo, a row's state cost at least four dumps (usernames `.exists` and `.all()`,
    buttons the same), the rows two, the tap on a row two."""
    set_active_locale("fr")
    host, phone = _host(FR_OURS)
    first, second = _rows(FR_OURS)[0][0], _rows(FR_OURS)[1][0]
    for read in (lambda: host.get_row_follow_state(second),
                 host.get_visible_followers_with_elements,
                 host.extract_usernames_from_follow_list,
                 lambda: host.click_follower_in_list(first)):
        before = phone.dumps
        read()
        assert phone.dumps - before == 1


@pytest.mark.parametrize("xml", [FR_OURS, EN_OURS], ids=["fr", "en"])
def test_the_rows_carry_their_username_and_bounds(xml):
    host, _phone = _host(xml)
    rows = host.get_visible_followers_with_elements()
    assert [(row["username"], tuple(row["element"].bounds)) for row in rows] == [
        (username, bounds) for username, bounds, _caption in _rows(xml)]


def test_extracted_usernames_are_the_rows_without_repeats():
    """Derived: the French list with its first row repeated right under itself."""
    xml = _derived(FR_OURS, _row_repeated)
    names = [username for username, _b, _c in _rows(FR_OURS)]
    host, _phone = _host(xml)
    assert host.extract_usernames_from_follow_list() == names
    assert [row["username"] for row in host.get_visible_followers_with_elements()] == names[:1] + names


def test_a_row_is_tapped_inside_its_username():
    username, (left, top, right, bottom), _caption = _rows(FR_OURS)[1]
    host, phone = _host(FR_OURS)
    assert host.click_follower_in_list(username) is True
    assert len(phone.taps) == 1
    x, y = phone.taps[0]
    assert left <= x <= right and top <= y <= bottom


def test_a_username_not_on_screen_is_not_tapped():
    host, phone = _host(FR_OURS)
    assert host.click_follower_in_list("nobody") is False
    assert phone.taps == []


def test_an_element_without_bounds_is_not_tapped():
    """A photo's element carries no device: without usable bounds there is nothing to aim at (the
    old centre click of such an element landed on a corner of the screen). Derived: the French
    list with its first name given no size."""
    host, phone = _host(_derived(FR_OURS, _name_without_size))
    assert host.click_follower_in_list(_rows(FR_OURS)[0][0]) is False
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
    applies the proxy's rewrite, as `d.xpath()` does through the proxy. Derived: the French list
    under the clone's package."""
    set_active_locale("fr")
    xml = FR_OURS.replace(PKG, CLONE)
    rows = _rows(FR_OURS)
    host, phone = _host(xml, package=CLONE)
    assert [row["username"] for row in host.get_visible_followers_with_elements()] == [r[0] for r in rows]
    assert host.get_row_follow_state(rows[0][0]) == "follow_back"
    assert host.click_follower_in_list(rows[1][0]) is True and len(phone.taps) == 1
