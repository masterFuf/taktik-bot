"""The Lab recognises a TikTok screen as the feed loop does: on one photo.

`tt.detection.read_screen` calls the production `DetectionActions.read_screen`, and the runner
names the screen before and after every action from the same reading instead of waiting out
`is_on_inbox_page` then `is_on_for_you_page` selector by selector. The screens are invented and
read by uiautomator2's own `XPathEntry`.
"""

from types import SimpleNamespace

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.compat.diagnostics.actions.tiktok import ACTION_REGISTRY, register_actions
from bridges.compat.diagnostics.runtime.action_test import runner
from bridges.compat.diagnostics.runtime.action_test.bundles.tiktok import (
    build_tiktok_action_bundle,
    create_tiktok_device_facade,
)
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale

PKG = "com.zhiliaoapp.musically:id/"


def _n(text="", desc="", rid="", selected="false"):
    rid = f"{PKG}{rid}" if rid else ""
    return (f'<node class="android.widget.TextView" text="{text}" content-desc="{desc}" resource-id="{rid}" '
            f'package="com.zhiliaoapp.musically" selected="{selected}" bounds="[0,0][10,10]" />')


FOR_YOU = ('<hierarchy rotation="0">' + _n(desc="Pour toi") + _n(desc="Accueil", selected="true")
           + _n(text="demo_author", rid="title") + _n(desc="Attribuer un « J'aime » à la vidéo. 12", rid="f57")
           + _n(desc="Partager une vidéo. 3 partages") + "</hierarchy>")
INBOX = ('<hierarchy rotation="0">' + _n(text="Messages", rid="title")
         + _n(desc="Messages", selected="true") + "</hierarchy>")


class _Phone:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml, self.dumps = xml, 0
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.dumps += 1
        return self.xml

    def app_current(self):
        return {"package": "com.zhiliaoapp.musically", "activity": "demo.Activity"}


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _bundle(xml):
    phone = _Phone(xml)
    return build_tiktok_action_bundle(create_tiktok_device_facade(phone)), phone


def test_the_lab_action_is_the_production_reading():
    register_actions()
    bundle, phone = _bundle(FOR_YOU)
    result = ACTION_REGISTRY["tt.detection.read_screen"](bundle, {})
    assert result["success"] is True and result["message"] == "video"
    details = result["details"]
    assert (details["kind"], details["for_you"], details["video"], details["popups"]) == ("video", True, True, [])
    assert isinstance(details["photoAgeMs"], int) and phone.dumps == 1


@pytest.mark.parametrize("xml, name", [(FOR_YOU, "tiktok.feed.for_you"), (INBOX, "tiktok.inbox")])
def test_the_runner_names_a_tiktok_screen_from_one_photo(xml, name):
    bundle, phone = _bundle(xml)
    assert runner._detect_screen(bundle) == name
    assert phone.dumps == 1


def test_a_detection_that_only_forwards_attributes_is_not_taken_for_a_reader():
    class Forwarding:
        def __getattr__(self, _name):
            return lambda *_a, **_k: False

    bundle = SimpleNamespace(detection=Forwarding(), device=SimpleNamespace(_device=_Phone(INBOX)))
    assert runner._detect_screen(bundle) == "android.com.zhiliaoapp.musically:demo.Activity"
