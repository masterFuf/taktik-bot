"""The Instagram language switch ends with a restart of the app, in production and in the Lab.

Without it, screens drawn before the switch keep the old language until the next start: the feed
header did. The restart is the clean start a run makes (force-stop, then launch the active
package), and the Lab action `settings.change_language` goes through the same workflow. After the
restart Instagram shows a real 410 feed in English, so the read back says the change took.
"""

import types

import pytest

import taktik.core.social_media.instagram.workflows.account.change_language_workflow as module
from taktik.core.social_media.instagram.ui.language import reset_detected_language
from taktik.core.social_media.instagram.workflows.account.change_language_workflow import (
    ChangeLanguageWorkflow,
)
from unit.paths import CORE

PACKAGE = "com.instagram.android"
ENGLISH_FEED = CORE / "tests/unit/social_media/instagram/fixtures/ig410_en_feed_post_hours_ago.xml"


class _Phone:
    """What the restart asks of a phone: stop, start, and which app is in front."""

    def __init__(self, comes_back=True):
        self.calls = []
        self.front = PACKAGE
        self.comes_back = comes_back
        self.serial = "serial-of-the-lab-phone"

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
        return ENGLISH_FEED.read_text(encoding="utf-8")


@pytest.fixture
def screens(monkeypatch):
    """Every settings screen answers; taps are recorded in order with the phone's calls."""
    monkeypatch.setattr(module, "time", types.SimpleNamespace(sleep=lambda seconds: None))
    monkeypatch.setattr(module, "detect_and_optimize", lambda device: None)
    monkeypatch.setattr(module, "get_active_package", lambda: PACKAGE, raising=False)
    monkeypatch.setattr(module, "set_app_locale", lambda device_id, package, tag: True)
    reset_detected_language()

    def _install(workflow, phone):
        workflow._click_first_match = lambda selectors, name: phone.calls.append(("tap", name)) or True
        workflow._element_exists = lambda selectors: True
        workflow._scroll_until_present = lambda selectors, max_scrolls: True
        return workflow

    yield _install
    reset_detected_language()


def test_the_switch_ends_with_a_restart_of_instagram(screens):
    phone = _Phone()
    steps = []
    workflow = screens(ChangeLanguageWorkflow(phone, "dev", notifier=lambda **event: steps.append(
        (event["step"], event["status"]))), phone)

    result = workflow.execute(language="en")

    assert phone.calls[-3:] == [("tap", "Language English"), ("stop", PACKAGE), ("start", PACKAGE)]
    assert result["success"] is True
    assert result["app_restarted"] is True
    assert ("restart_app", "done") in steps
    assert steps[-1] == ("done", "done")


def test_a_failed_switch_does_not_restart_the_app(screens):
    phone = _Phone()
    workflow = screens(ChangeLanguageWorkflow(phone, "dev"), phone)
    workflow._element_exists = lambda selectors: False

    result = workflow.execute(language="en")

    assert result["success"] is False
    assert ("stop", PACKAGE) not in phone.calls


def test_the_lab_action_runs_the_same_restart_on_the_session_phone(screens, monkeypatch):
    from bridges.tools.lab.actions.instagram import ACTION_REGISTRY, register_actions

    register_actions()
    phone = _Phone()
    built = []
    real_init = ChangeLanguageWorkflow.__init__

    def _init(self, device, device_id, notifier=None):
        real_init(self, device, device_id, notifier)
        built.append(device_id)
        screens(self, phone)

    monkeypatch.setattr(ChangeLanguageWorkflow, "__init__", _init)

    result = ACTION_REGISTRY["settings.change_language"](
        types.SimpleNamespace(device=phone), {"language": "en"})

    assert phone.calls[-2:] == [("stop", PACKAGE), ("start", PACKAGE)]
    assert built == ["serial-of-the-lab-phone"]
    assert result["success"] is True
    assert result["details"]["app_restarted"] is True
