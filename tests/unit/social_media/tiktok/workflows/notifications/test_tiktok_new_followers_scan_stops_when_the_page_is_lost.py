"""The new-followers scan stops, and says why, when it cannot get back to the page.

The page shows display names; each one is resolved by opening its row, which leaves the phone on a
profile, and the scan reopens the page before the next row. It used to ignore what that reopening
answered: when it failed, the next row was looked for on whatever screen was left, and nothing said
so. A scan that resolved one follower of three then read like an account that gained one.

The phone here is a stand-in for `DMActions` (no screen is read: what is tested is what the scan
does with the answers); the page reading and its reopening have their own tests on real captures.
"""

import pytest

from taktik.core.social_media.tiktok.workflows.notifications import scan as scan_module
from taktik.core.social_media.tiktok.workflows.notifications.payload import NotificationsSettings
from taktik.core.social_media.tiktok.workflows.notifications.scan import scan_new_followers
from taktik.core.social_media.tiktok.workflows.notifications.workflow import run_notifications_pass

ROWS = [{"username": name, "activity": "1d", "can_follow_back": False} for name in ("Ana", "Bob Ross", "Cléo")]
HANDLES = {"Ana": "ana.handle", "Bob Ross": "bob_ross", "Cléo": "cleo.c"}


class _Notifier:
    def __init__(self):
        self.logs = []

    def status(self, *_args, **_kwargs):
        pass

    def log(self, level, message):
        self.logs.append((level, message))

    def send(self, *_args, **_kwargs):
        pass


@pytest.fixture
def phone(monkeypatch):
    """The page opens once; `reopenings` says what each later opening answers."""
    phone = {"calls": [], "reopenings": [], "recorded": []}

    class FakeDMActions:
        def __init__(self, device):
            self._opened = False

        def open_new_followers_page(self):
            phone["calls"].append("open_page")
            if not self._opened:
                self._opened = True
                return True
            return phone["reopenings"].pop(0)

        def get_new_followers(self, max_items=50):
            return [dict(row) for row in ROWS]

        def open_new_follower_profile(self, shown):
            phone["calls"].append(f"open_profile {shown}")
            return HANDLES[shown]

    monkeypatch.setattr(
        "taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions.DMActions", FakeDMActions)
    monkeypatch.setattr(scan_module, "record_scan_notifications",
                        lambda account, items: phone["recorded"].extend(items) or [True] * len(items))
    return phone


def test_a_page_that_cannot_be_reopened_stops_the_scan_and_says_so(phone):
    phone["reopenings"] = [False]

    result = scan_new_followers(None, account_username="acting_account")

    assert phone["calls"] == ["open_page", "open_profile Ana", "open_page"]
    assert result["stop_reason"] == "list_unreachable"
    assert result["left_unread"] == 2
    assert result["resolved"] == 1
    assert [item["username"] for item in phone["recorded"]] == ["ana.handle"]


def test_a_page_reopened_each_time_reads_every_row(phone):
    phone["reopenings"] = [True, True, True]

    result = scan_new_followers(None, account_username="acting_account")

    assert result["stop_reason"] is None
    assert result["left_unread"] == 0
    assert result["resolved"] == 3


def test_a_page_lost_after_the_last_row_loses_nothing(phone):
    phone["reopenings"] = [True, True, False]

    result = scan_new_followers(None, account_username="acting_account")

    assert result["stop_reason"] is None
    assert result["resolved"] == 3


def test_the_pass_says_how_many_followers_were_left_unread(phone):
    phone["reopenings"] = [False]
    notifier = _Notifier()
    settings = NotificationsSettings(scan_new_followers=True, read_activity=False, max_hellos=0,
                                     max_suggested_follows=0)

    run_notifications_pass(None, settings, bot_username="acting_account", notifier=notifier)

    assert ("warning", "The new-followers page could not be reopened after a profile: "
                       "2 follower(s) left unread") in notifier.logs
