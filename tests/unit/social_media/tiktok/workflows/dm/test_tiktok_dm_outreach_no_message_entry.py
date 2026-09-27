"""Cold DM, TikTok 47.0.3: a profile that offers no message entry is skipped, not failed.

The screen is a real dump (Pixel 6a, TikTok 47.0.3 in French) of an account that follows us
without being followed back: « Suivre en retour » and the suggested-accounts icon, no Message
button, and no message item in its « ... » menu either. Anonymized: structure, ids and bounds
kept, display name, handle and counters invented
(`fixtures/tt47_fr_profile_follows_us_no_message_entry.xml`).

The run counted that recipient as a failure (`dms_failed: 1`, « Message button not found »).
The workflow here is the production one, its taps and probes the real `BaseAction` answered by
uiautomator2's own `d.xpath()` on that screen. Stand-ins: the TikTok manager, the search that
opened the profile (`navigate_to_user_profile`, which verifies the handle, tested elsewhere) and
the composer. The Lab action `tt.profile.click_message` runs the same step.
"""

import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.social_media.tiktok.actions.core.base_action as tiktok_base_action
from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.tiktok.actions.business.workflows.dm import outreach
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
FOLLOWER_PROFILE = (FIXTURES / "tt47_fr_profile_follows_us_no_message_entry.xml").read_text(encoding="utf-8")
# Neither a profile nor a Message entry: what the run would face after a stray navigation, here
# the For You feed of the same phone and version (its tab bar says « Messages »).
NOT_A_PROFILE = (FIXTURES / "tt4703_fr_home.xml").read_text(encoding="utf-8")


class _Clock:
    """The probes wait on `time.time()`: a clock that runs on every read, and sleeps that do not."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        self.now += 0.7
        return self.now

    def sleep(self, _seconds):
        pass

    def __getattr__(self, name):
        return getattr(time, name)


class _Phone:
    """uiautomator2's xpath engine on one screen; records every tap."""

    wait_timeout = 0.0

    def __init__(self, xml):
        self._xml = xml
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self._xml

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration=None):
        self.taps.append((x, y))

    def __call__(self, **kwargs):
        # `click_message_button`'s last resort: the kwargs selector `text=`.
        ((key, value),) = kwargs.items()
        assert key == "text"
        found = self.xpath(f'//*[@text="{value}"]').exists
        return SimpleNamespace(exists=found, click=lambda: self.taps.append(value))


class _OpenedProfile:
    """The search already opened and verified the recipient's profile."""

    def __init__(self, device):
        pass

    def navigate_to_user_profile(self, username):
        return True

    def navigate_to_home(self):
        pass


class _Composer:
    def __init__(self, device):
        self.sent = []

    def is_in_conversation(self):
        return True

    def send_text_message(self, message):
        self.sent.append(message)
        return True


class _Notifier:
    def __init__(self):
        self.events = []

    def send(self, event_type, **payload):
        self.events.append((event_type, payload))

    def of(self, event_type):
        return [payload for kind, payload in self.events if kind == event_type]


@pytest.fixture(autouse=True)
def _french_47_0_3_phone_without_waits(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(shared_base_action, "time", clock)
    monkeypatch.setattr(tiktok_base_action, "time", clock)
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    monkeypatch.setattr(miss_capture, "blocage_a_signaler", lambda: False)
    previous = active_locale()
    set_active_locale("fr")
    apply_version_overrides("tiktok", "47.0.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")
    set_active_locale(previous)


def _run(xml):
    phone = _Phone(xml)
    manager = SimpleNamespace(
        device_manager=SimpleNamespace(connect=lambda: True, device=phone),
        stop=lambda: None,
        launch=lambda: None,
    )
    notifier = _Notifier()
    records = []
    workflow = outreach.TikTokDMOutreachWorkflow(
        "device-1",
        notifier=notifier,
        sent_dm_recorder=lambda *args: records.append(args),
        manager_factory=lambda device_id=None: manager,
        navigation_factory=_OpenedProfile,
        dm_actions_factory=_Composer,
        rng=SimpleNamespace(choice=lambda values: values[0], uniform=lambda low, high: low),
        sleeper=lambda _seconds: None,
    )
    assert workflow.connect()
    result = workflow.run(["demo_follower"], ["Salut !"], account_id=7, session_id="session-1")
    return result, notifier, records, phone, workflow


def test_the_profile_step_answers_no_message_entry_on_the_real_screen():
    _, _, _, _, workflow = _run(FOLLOWER_PROFILE)
    assert workflow.open_conversation_from_profile() == outreach.NO_MESSAGE_ENTRY


def test_a_follower_we_do_not_follow_back_is_skipped_not_failed():
    result, notifier, records, phone, workflow = _run(FOLLOWER_PROFILE)

    assert (result["dms_sent"], result["dms_failed"], result.get("no_message_entry")) == (0, 0, 1)
    assert notifier.of("dm_result") == [{
        "username": "demo_follower",
        "success": False,
        "error": "No message entry on profile",
        "skipped": True,
        "reason": "no_message_entry",
    }]
    assert notifier.of("stats")[-1]["stats"]["no_message_entry"] == 1
    assert notifier.of("stats")[-1]["stats"]["failed"] == 0
    # Not marked in `sent_dms`, nothing typed, and nothing tapped: « Suivre en retour » is the
    # widest button on that screen.
    assert records == []
    assert workflow.dm_actions.sent == []
    assert phone.taps == []


def test_the_lab_action_runs_the_same_step_on_the_session_device():
    from bridges.compat.diagnostics.actions.tiktok import ACTION_REGISTRY, register_actions

    register_actions()
    phone = _Phone(FOLLOWER_PROFILE)
    result = ACTION_REGISTRY["tt.profile.click_message"](
        SimpleNamespace(device=phone, device_id="device-1"), {})

    assert result["success"] is False
    assert result["details"] == {"outcome": "no_message_entry"}
    assert phone.taps == []


def test_the_same_miss_on_a_screen_that_is_not_a_profile_stays_a_failure():
    result, notifier, records, _, workflow = _run(NOT_A_PROFILE)

    assert (result["dms_failed"], result.get("no_message_entry", 0)) == (1, 0)
    assert notifier.of("dm_result") == [
        {"username": "demo_follower", "success": False, "error": "Message button not found"}
    ]
    assert records == []
    assert workflow.open_conversation_from_profile() == outreach.UNEXPECTED_SCREEN
