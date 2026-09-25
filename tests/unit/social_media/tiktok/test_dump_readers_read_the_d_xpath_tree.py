"""The TikTok dump readers evaluate the catalogue on the tree `d.xpath()` sees.

They used to parse the raw dump and translate each selector with a regex (`//X` into
`//node[@class="X"]`), which left axis steps such as `following-sibling::X` untranslated, so those
never matched. They now read `parse_ui_dump`'s tree and pass the selector unchanged. Dumps below
are invented.
"""

from types import SimpleNamespace

import pytest

from taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler import (
    PopupHandler,
)
from taktik.core.social_media.tiktok.services.publish.progress import get_publish_progress_percent
from taktik.core.social_media.tiktok.services.publish.upload_picker import tap_upload_button_from_dump
from taktik.core.social_media.tiktok.workflows.management.signup.signup_workflow import (
    TikTokSignupWorkflow,
)

TT = "com.zhiliaoapp.musically:id"


class _Device:
    def __init__(self, xml):
        self.xml = xml
        self.clicks = []

    def dump_hierarchy(self, compressed=False):
        return self.xml

    def click(self, x, y):
        self.clicks.append((x, y))


class _Log:
    def __getattr__(self, _name):
        return lambda *a, **k: None


def _screen(body):
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><hierarchy rotation=\"0\">"
        '<node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">'
        + body
        + "</node></hierarchy>"
    )


@pytest.fixture(autouse=True)
def _no_screen_ring(monkeypatch):
    import taktik.core.shared.diagnostics.screen_ring as ring

    monkeypatch.setattr(ring, "noter", lambda *a, **k: None)


def test_popup_scan_matches_class_steps_and_resource_ids():
    xml = _screen(
        '<node class="android.widget.Button" text="Ne pas autoriser" clickable="true"'
        ' resource-id="com.android.permissioncontroller:id/permission_deny_button"'
        ' bounds="[100,1500][980,1620]"/>'
        '<node class="android.widget.ImageView" content-desc="Close" clickable="true"'
        ' bounds="[980,100][1060,180]"/>'
    )
    handler = PopupHandler(None, SimpleNamespace(device=_Device(xml)))

    assert handler._fast_detect() == {"system_deny", "generic_popup"}


def test_popup_scan_on_a_clean_screen_finds_nothing():
    handler = PopupHandler(None, SimpleNamespace(device=_Device(_screen(
        '<node class="android.widget.TextView" text="Pour toi" bounds="[400,100][680,180]"/>'
    ))))

    assert handler._fast_detect() == set()


def test_popup_scan_falls_back_when_the_dump_does_not_parse():
    handler = PopupHandler(None, SimpleNamespace(device=_Device("<not xml")))

    assert handler._fast_detect() == {"_fallback"}


def _signup(xml):
    workflow = object.__new__(TikTokSignupWorkflow)
    workflow.device = _Device(xml)
    workflow.logger = _Log()
    workflow._detect_screen_slow = lambda: "slow_path"
    return workflow


def test_signup_detects_the_phone_screen_by_its_edit_text_hint():
    xml = _screen(
        '<node class="android.widget.EditText" hint="Numéro de téléphone" bounds="[40,600][1040,720]"/>'
    )

    assert _signup(xml)._detect_screen() == "phone_email"


def test_signup_takes_the_slow_path_when_the_dump_does_not_parse():
    assert _signup("<not xml")._detect_screen() == "slow_path"


def test_progress_badge_is_read_by_its_resource_id():
    xml = _screen(
        f'<node class="android.widget.TextView" resource-id="{TT}/x44" text="81%"'
        ' bounds="[20,80][120,140]"/>'
    )

    assert get_publish_progress_percent(_Device(xml)) == 81


def test_upload_button_is_tapped_from_its_bounds():
    device = _Device(_screen(
        f'<node class="android.widget.ImageView" resource-id="{TT}/ymg" clickable="true"'
        ' bounds="[800,2100][1000,2300]"/>'
    ))

    assert tap_upload_button_from_dump(device) is True
    assert device.clicks == [(900, 2200)]
