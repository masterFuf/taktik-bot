"""The notifications pass files its two gestures under a handle, and sends no event nobody reads.

A suggested follow used to be filed nowhere: not in `interactions`, not in the day's totals, so it
escaped the daily follow quota and the unfollow never knew the bot had made it. The suggestion row
shows a display name only, so the handle is read on the suggestion's profile BEFORE the follow,
and a suggestion whose handle cannot be read is not followed. A wave is filed as the "already
written to" marker, under the handle read on the thread's profile card.

The per-row `activity_row`, `hello_sent` and `suggested_followed` events had no reader: their totals
already travel in `notifications_result`, which the page reads. They are gone.
"""

from types import SimpleNamespace

import pytest

from taktik.core.social_media.tiktok.actions.business.workflows.notifications.payload import (
    NotificationsSettings,
)
from taktik.core.social_media.tiktok.actions.business.workflows.notifications.workflow import (
    run_notifications_pass,
)


class _Notifier:
    def __init__(self):
        self.sent = []
        self.logs = []

    def status(self, *_args, **_kwargs):
        pass

    def log(self, level, message):
        self.logs.append((level, message))

    def send(self, msg_type, **payload):
        self.sent.append((msg_type, payload))


class _Phone:
    """The inbox and the Activity summary, and what each display name's profile/thread shows."""

    def __init__(self):
        self.calls = []
        self.suggestions = [{"name": "Suggested A"}, {"name": "Suggested B"}]
        self.hello_candidates = ["Ana", "Bob"]
        #: Display name -> the handle its profile (or its thread's card) shows; absent: unreadable.
        self.handles = {"Suggested A": "suggested_a", "Suggested B": "suggested_b", "Ana": "ana.handle"}
        self.activity_rows = [SimpleNamespace(kind="like", usernames=["Nico"], others_count=1,
                                              age_label="2 j", post_count=1)]
        self.follows = []
        self.hellos = []
        self.recorded_follows = []
        self.recorded_hellos = []


@pytest.fixture
def phone(monkeypatch):
    phone = _Phone()

    class FakeDMActions:
        def __init__(self, device):
            pass

        def navigate_to_inbox(self):
            phone.calls.append("open_inbox")
            return True

        def is_on_inbox_page(self):
            return True

        def say_hello_candidates(self):
            return list(phone.hello_candidates)

        def say_hello(self, name):
            phone.calls.append(f"say_hello {name}")
            phone.hellos.append(name)
            return True

        def resolve_conversation_handle(self, name):
            phone.calls.append(f"read_thread_handle {name}")
            return phone.handles.get(name)

    class FakeActivityActions:
        def __init__(self, device):
            pass

        def open_activity(self, expand=False):
            return True

        def is_on_activity_page(self):
            return True

        def read_activity(self, max_rows=30):
            return list(phone.activity_rows)

        def read_suggested_accounts(self):
            return list(phone.suggestions)

        def _scroll_down(self, scale=1.0):
            pass

        def resolve_suggested_account_handle(self, name):
            phone.calls.append(f"read_profile_handle {name}")
            return phone.handles.get(name)

        def follow_suggested_account(self, name):
            phone.calls.append(f"follow {name}")
            phone.follows.append(name)
            return True

    monkeypatch.setattr(
        "taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions.DMActions", FakeDMActions)
    monkeypatch.setattr(
        "taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions.ActivityActions",
        FakeActivityActions)

    from taktik.core.database import tiktok_account_identity, tiktok_dm
    from taktik.core.database.tiktok_follow_graph import TikTokFollowGraphService

    monkeypatch.setattr(tiktok_account_identity, "resolve_tiktok_account_id",
                        lambda username, logger=None: 7 if username else None)

    def record_follow(username, account_id, session_id=None):
        phone.recorded_follows.append((username, account_id))
        return True

    def record_say_hello(account_id, handle):
        phone.recorded_hellos.append((handle, account_id))
        return True

    monkeypatch.setattr(TikTokFollowGraphService, "record_follow", staticmethod(record_follow), raising=False)
    monkeypatch.setattr(tiktok_dm, "record_say_hello", record_say_hello, raising=False)
    return phone


def _run(phone, *, account="acting_account", **settings):
    notifier = _Notifier()
    values = dict(scan_new_followers=False, read_activity=False, max_hellos=0, max_suggested_follows=0)
    values.update(settings)
    result = run_notifications_pass(None, NotificationsSettings(**values), bot_username=account,
                                    notifier=notifier)
    return result, notifier


def test_a_suggested_follow_is_filed_under_the_handle_its_profile_shows(phone):
    result, _ = _run(phone, max_suggested_follows=1)

    assert phone.calls[-2:] == ["read_profile_handle Suggested A", "follow Suggested A"]
    assert phone.recorded_follows == [("suggested_a", 7)]
    assert result["stats"]["suggested_followed"] == 1


def test_a_suggestion_whose_handle_cannot_be_read_is_not_followed(phone):
    del phone.handles["Suggested A"]

    result, notifier = _run(phone, max_suggested_follows=1)

    assert phone.follows == ["Suggested B"]
    assert phone.recorded_follows == [("suggested_b", 7)]
    assert result["stats"]["suggested_followed"] == 1
    assert ("warning", "1 suggested account(s) not followed (handle unreadable)") in notifier.logs


def test_no_suggestion_is_followed_when_no_handle_can_be_read(phone):
    phone.handles = {}

    result, _ = _run(phone, max_suggested_follows=2)

    assert phone.follows == []
    assert phone.recorded_follows == []
    assert result["stats"]["suggested_followed"] == 0


def test_a_wave_is_filed_under_the_handle_of_its_thread(phone):
    result, notifier = _run(phone, max_hellos=2)

    assert phone.hellos == ["Ana", "Bob"]
    assert phone.calls.index("say_hello Ana") < phone.calls.index("read_thread_handle Ana")
    assert phone.recorded_hellos == [("ana.handle", 7)]
    assert result["stats"]["hello_sent"] == 2
    assert ("warning", "1 hello(s) sent but not recorded (handle unreadable)") in notifier.logs


def test_without_a_readable_account_neither_gesture_is_made(phone):
    result, notifier = _run(phone, account=None, max_hellos=2, max_suggested_follows=2)

    assert phone.follows == [] and phone.hellos == []
    assert result["stats"]["hello_sent"] == 0 and result["stats"]["suggested_followed"] == 0
    assert [level for level, _ in notifier.logs] == ["warning", "warning"]


def test_the_only_event_sent_is_the_result_the_page_reads(phone):
    result, notifier = _run(phone, read_activity=True, max_hellos=2, max_suggested_follows=1)

    assert result["success"] is True
    assert [kind for kind, _ in notifier.sent] == ["notifications_result"]
    assert notifier.sent[0][1]["stats"] == result["stats"]
    assert result["stats"]["activity_read"] == 1
