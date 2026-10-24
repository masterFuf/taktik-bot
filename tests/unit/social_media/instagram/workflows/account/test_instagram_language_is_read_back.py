"""The Instagram language change is a success only when Instagram SHOWS the language after the restart.

Measured on a Pixel 6 Pro (Android 17, Instagram 410): « English » picked, « App language set to
English », restart, success; Instagram stayed in French on every screen. The picker had taken the
choice (English was ticked) and Android ignored it. `adb shell cmd locale get-app-locales` answered
`[]`; once Android was given a per-app language (`cmd locale set-app-locales`), Instagram showed
English after a relaunch.

So the flow now gives Android the same per-app language as the picker, restarts, and reads the
language back with the detection every run uses. The screens are real captures: the French one is
the conversation Instagram showed right after that "successful" switch to English
(`fixtures/ig410_fr_dm_thread_after_switch_to_english.xml`), the English one a 410 feed.
"""

import types
from pathlib import Path

import pytest

import taktik.core.social_media.instagram.workflows.account.change_language_workflow as module
from taktik.core.social_media.instagram.ui.language import reset_detected_language
from taktik.core.social_media.instagram.workflows.account.change_language_workflow import (
    ChangeLanguageWorkflow,
)
from unit.paths import CORE

PACKAGE = "com.instagram.android"
SERIAL = "serial-of-the-pixel"
STILL_FRENCH = Path(__file__).parent / "fixtures" / "ig410_fr_dm_thread_after_switch_to_english.xml"
ENGLISH_FEED = CORE / "tests/unit/social_media/instagram/fixtures/ig410_en_feed_post_hours_ago.xml"


class _Phone:
    """Stops and starts Instagram, and shows `after` once it started again."""

    def __init__(self, after: Path, comes_back: bool = True):
        self.calls = []
        self.front = PACKAGE
        self.comes_back = comes_back
        self.after = after.read_text(encoding="utf-8")

    def app_stop(self, package):
        self.calls.append(("stop", package))
        self.front = "com.android.launcher"

    def app_start(self, package, activity=None):
        self.calls.append(("start", package))
        if self.comes_back:
            self.front = package

    def app_current(self):
        return {"package": self.front}

    def dump_hierarchy(self):
        self.calls.append(("read",))
        return self.after


class _Android:
    """`set_app_locale`: what Android was asked, and whether it took it."""

    def __init__(self, phone, takes_it=True):
        self.phone = phone
        self.takes_it = takes_it

    def __call__(self, device_id, package, language_tag):
        self.phone.calls.append(("android_locale", device_id, package, language_tag))
        return self.takes_it


@pytest.fixture
def flow(monkeypatch):
    """The settings screens answer; the start-of-run detection is left out (it filters the
    catalogues in place); the read after the restart is the real one."""
    monkeypatch.setattr(module, "time", types.SimpleNamespace(sleep=lambda seconds: None))
    monkeypatch.setattr(module, "detect_and_optimize", lambda device: "fr")
    monkeypatch.setattr(module, "get_active_package", lambda: PACKAGE, raising=False)
    reset_detected_language()

    def _build(phone, android_takes_it=True):
        monkeypatch.setattr(module, "set_app_locale", _Android(phone, android_takes_it), raising=False)
        steps = []
        workflow = ChangeLanguageWorkflow(phone, SERIAL, notifier=lambda **event: steps.append(
            (event["step"], event["status"])))
        workflow._click_first_match = lambda selectors, name: phone.calls.append(("tap", name)) or True
        workflow._element_exists = lambda selectors: True
        workflow._scroll_until_present = lambda selectors, max_scrolls: True
        return workflow, steps

    yield _build
    reset_detected_language()


def test_instagram_still_in_french_after_the_switch_is_a_failure_said_as_such(flow):
    phone = _Phone(STILL_FRENCH)
    workflow, steps = flow(phone)

    result = workflow.execute(language="en")

    assert result["success"] is False
    assert result["error_type"] == "language_not_applied"
    assert result["language_before"] == "fr"
    assert result["language_after"] == "fr"
    assert "English" in result["message"] and "'fr'" in result["message"]
    assert ("verify", "failed") in steps
    assert ("done", "done") not in steps


def test_the_switch_is_a_success_once_instagram_reads_in_english(flow):
    phone = _Phone(ENGLISH_FEED)
    workflow, steps = flow(phone)

    result = workflow.execute(language="en")

    assert result["success"] is True
    assert result["error_type"] is None
    assert result["language_after"] == "en"
    assert result["android_app_locale"] == "en"
    assert ("verify", "done") in steps
    assert steps[-1] == ("done", "done")


def test_android_gets_the_per_app_language_of_the_active_package_before_the_restart(flow):
    phone = _Phone(ENGLISH_FEED)
    workflow, _ = flow(phone)

    workflow.execute(language="fr-CA")

    assert phone.calls[-5:-1] == [
        ("tap", "Language Français (Canada)"),
        ("android_locale", SERIAL, PACKAGE, "fr-CA"),
        ("stop", PACKAGE),
        ("start", PACKAGE),
    ]
    assert phone.calls[-1] == ("read",)


def test_without_a_per_app_language_the_read_back_alone_decides(flow):
    """Before Android 13 there is no per-app language: the picker alone sets it, and the read says."""
    phone = _Phone(ENGLISH_FEED)
    workflow, steps = flow(phone, android_takes_it=False)

    result = workflow.execute(language="en")

    assert result["success"] is True
    assert result["android_app_locale"] is None
    assert ("set_android_locale", "failed") in steps


def test_an_instagram_that_does_not_come_back_is_not_read_and_is_a_failure(flow):
    phone = _Phone(ENGLISH_FEED, comes_back=False)
    workflow, _ = flow(phone)

    result = workflow.execute(language="en")

    assert result["success"] is False
    assert result["error_type"] == "app_not_restarted"
    assert result["app_restarted"] is False
    assert ("read",) not in phone.calls
