"""The device proxy of every Instagram bridge rewrites Instagram's own ids, never another app's.

`CloneAwareDeviceProxy` makes an id equality match a clone's prefix and the bare ids of the
Compose screens. It did so for EVERY id, whatever its package: the indicator of Google's autofill
popup, `com.google.android.gms:id/title`, became "any node whose id ends in `title`" and found
Instagram's own titles (165 captures of the corpus, a list of followers among them) and the ADB
keyboard's (55 captures). The login flow then believed the popup was up and went looking for a
button to close it. Only an id of Instagram's package (the official one or the clone driven) and
a bare id are rewritten now; another app's id means what it says.

The screens are real dumps of Instagram 410.0.0.53.71, anonymized (`fixtures/`), read through the
production path: uiautomator2's own xpath engine behind the proxy, and the screen photo that
applies the proxy's rewrite. No capture of the Google popup itself exists in the corpus: that it
is still found rests on its selector reaching uiautomator2 unchanged (last tests).
"""

from pathlib import Path

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.social_media.instagram.actions.account.login import InstagramLogin
from taktik.core.social_media.instagram.ui.selectors.shell.auth import AUTH_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.notifications import (
    NOTIFICATION_SELECTORS,
)

FIXTURES = Path(__file__).parent / "fixtures"
IG = "com.instagram.android"
CLONE = "com.taktik.ig1"

# Instagram's own `title` ids (the list's section headers).
FOLLOWERS_LIST = "ig410_fr_followers_list.xml"
# The ADB keyboard's `com.alexal1.adbkeyboard:id/title` under a comment sheet.
COMMENT_SHEET = "ig410_fr_comment_sheet.xml"
# The Compose rows of the activity screen, with bare ids (`activity_feed_list`).
NOTIFICATIONS = "ig410_en_notifications.xml"


def _screen(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class _U2Phone:
    """uiautomator2 as far as `d.xpath()` needs it: a dump and a wait timeout."""

    wait_timeout = 1.0

    def __init__(self, xml: str):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml


def _login_on(xml: str, package: str = IG) -> InstagramLogin:
    """The login flow's popup checks on the device production mounts. The constructor is skipped:
    it opens the session directory, which these checks never touch."""
    login = InstagramLogin.__new__(InstagramLogin)
    login.device = CloneAwareDeviceProxy(_U2Phone(xml), package)
    login.auth_selectors = AUTH_SELECTORS
    login.logger = logger
    return login


def _photo_of(xml: str, package: str = IG) -> ScreenSnapshot:
    return ScreenSnapshot(xml, rewrite=CloneAwareDeviceProxy(object(), package).rewrite_xpath)


# ── Another app's id is not rewritten ───────────────────────────────────────────────────────

@pytest.mark.parametrize("fixture", [FOLLOWERS_LIST, COMMENT_SHEET])
@pytest.mark.parametrize("package", [IG, CLONE])
def test_the_google_autofill_popup_is_not_seen_on_a_screen_without_it(fixture, package):
    login = _login_on(_screen(fixture), package)
    assert not login._element_exists(AUTH_SELECTORS.google_autofill_popup_indicators)


@pytest.mark.parametrize("fixture", [FOLLOWERS_LIST, COMMENT_SHEET])
def test_the_screen_photo_does_not_see_it_either(fixture):
    photo = _photo_of(_screen(fixture))
    assert not photo.exists(AUTH_SELECTORS.google_autofill_popup_indicators)


# ── Instagram's ids are still rewritten ─────────────────────────────────────────────────────

def test_an_instagram_id_still_finds_its_nodes():
    titles = _login_on(_screen(FOLLOWERS_LIST)).device.xpath(f'//*[@resource-id="{IG}:id/title"]').all()
    assert titles and {el.attrib["resource-id"] for el in titles} == {f"{IG}:id/title"}


def test_an_instagram_id_still_reaches_the_bare_ids_of_a_compose_screen():
    xml = _screen(NOTIFICATIONS)
    device = CloneAwareDeviceProxy(_U2Phone(xml), IG)
    indicators = NOTIFICATION_SELECTORS.notifications_screen_indicators
    assert any(device.xpath(selector).exists for selector in indicators)
    assert _photo_of(xml).exists(indicators)


# ── What reaches uiautomator2 ───────────────────────────────────────────────────────────────

_FOREIGN_IDS = [
    "com.google.android.gms:id/title",
    "com.google.android.gms:id/cancel",
    "android:id/autofill_dialog_picker",
    "com.android.packageinstaller:id/permission_allow_button",
    "com.alexal1.adbkeyboard:id/title",
]


@pytest.mark.parametrize("rid", _FOREIGN_IDS)
@pytest.mark.parametrize("package", [IG, CLONE])
def test_another_apps_id_reaches_uiautomator2_as_written(rid, package):
    xpath = f'//*[@resource-id="{rid}"]'
    assert CloneAwareDeviceProxy(object(), package).rewrite_xpath(xpath) == xpath


@pytest.mark.parametrize("rid", [f"{IG}:id/title", f"{CLONE}:id/title", "title"])
def test_an_instagram_or_bare_id_is_made_to_match_every_form_of_it(rid):
    rewritten = CloneAwareDeviceProxy(object(), CLONE).rewrite_xpath(f'//*[@resource-id="{rid}"]')
    assert rewritten == '//*[(substring-after(@resource-id,":id/")="title" or @resource-id="title")]'


class _Recorder:
    """A device that keeps the selector kwargs it is called with."""

    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return object()


@pytest.mark.parametrize("rid", _FOREIGN_IDS)
def test_another_apps_resource_id_kwarg_is_left_exact(rid):
    phone = _Recorder()
    CloneAwareDeviceProxy(phone, CLONE)(resourceId=rid)
    assert phone.calls == [{"resourceId": rid}]


@pytest.mark.parametrize("rid", [f"{IG}:id/title", f"{CLONE}:id/title", "title"])
def test_an_instagram_or_bare_resource_id_kwarg_is_made_agnostic(rid):
    phone = _Recorder()
    CloneAwareDeviceProxy(phone, CLONE)(resourceId=rid)
    assert phone.calls == [{"resourceIdMatches": "^(.*:id/)?title$"}]
