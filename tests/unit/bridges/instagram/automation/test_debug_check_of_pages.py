"""The debug bridge's check of pages says a page left open, not "detected and handled".

`detect_problematic_pages` (the desktop's debug command) logged "Problematic page detected and
handled" for every page detected, closed or not: Instagram checking the account, which the detector
never touches, read as handled. The line now says what the detector did; `handled` was already
right in the result.

The screen is a real dump, anonymized: Instagram checking the account (410, French).
"""

from uiautomator2.xpath import XPathEntry

from bridges.instagram.automation import debug_actions
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.ui.detectors import problematic_page
from taktik.core.social_media.instagram.ui.selectors import locales
from unit.paths import CORE

CHALLENGE = (CORE / "tests/unit/social_media/instagram/fixtures/ig410_fr_account_challenge.xml").read_text(encoding="utf-8")


class _Phone:
    wait_timeout = 1.0

    def __init__(self):
        self.gestures = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return CHALLENGE

    def app_current(self):
        return {"package": "com.instagram.android",
                "activity": "com.instagram.challenge.activity.ChallengeActivity"}

    def press(self, key):
        self.gestures.append(key)

    def click(self, *args):
        self.gestures.append(args)


def test_a_page_left_open_is_said_left_open(monkeypatch, tmp_path):
    logs, messages = [], []
    monkeypatch.setattr(debug_actions, "send_log", lambda level, text: logs.append((level, text)))
    monkeypatch.setattr(debug_actions, "send_message", lambda kind, **data: messages.append((kind, data)))

    def dump_into_tmp(device, _folder):
        path = tmp_path / "dump.xml"
        path.write_text(device.dump_hierarchy(), encoding="utf-8")
        return str(path)

    # The bridge runs the detector in debug mode, which files its dumps: here, in a temporary folder.
    monkeypatch.setattr(problematic_page, "dump_ui_hierarchy", dump_into_tmp)
    before = locales.active_locale()
    locales.set_active_locale("fr")
    run_halt.reinitialiser()
    phone = _Phone()
    try:
        assert debug_actions.detect_problematic_pages(phone) == 0
    finally:
        locales.set_active_locale(before)
        run_halt.reinitialiser()

    assert messages == [("debug_result", {"success": True, "detected": True, "handled": False})]
    assert ("info", "Problematic page detected and left open") in logs
    assert phone.gestures == []
