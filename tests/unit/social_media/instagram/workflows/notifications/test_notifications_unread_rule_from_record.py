"""The scan's rule comes from what the account recorded: its last scan, and the identities seen.

The last scan is the moment it began reading its feed, not the moment it wrote what it read: a
notification that comes in while a scan reads lands above what it has read, and the next scan must
find it unread. The rows a scan writes keep their write time in `last_seen_at`, the column the
Turso sync follows.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from taktik.core.social_media.instagram.workflows.notifications import persistence
from taktik.core.social_media.instagram.workflows.notifications.unread_rule import BEYOND, UNREAD

NOW = datetime(2000, 1, 10, tzinfo=timezone.utc)


def _account(monkeypatch, last_scan):
    monkeypatch.setattr(persistence, "resolve_account_id", lambda username: 7)
    monkeypatch.setattr(persistence.NotificationService, "known_content_hashes", staticmethod(lambda p, a: set()))
    monkeypatch.setattr(persistence.NotificationService, "last_scan_at", staticmethod(last_scan))


@pytest.fixture
def recorded(monkeypatch, conn, tmp_db_path):
    """The real service and repositories on a throwaway base, for account 7."""
    def open_base():
        connection = sqlite3.connect(tmp_db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(persistence.NotificationService, "_open", staticmethod(open_base))
    monkeypatch.setattr(persistence, "resolve_account_id", lambda username: 7)
    return conn


def _follow(actor, age):
    return {"type": "new_follower", "username": actor, "time": age,
            "text": f"{actor} a commencé à vous suivre. {age}"}


def _now_to_the_second():
    return datetime.now(timezone.utc).replace(microsecond=0)


def test_the_horizon_is_the_last_scan(monkeypatch):
    _account(monkeypatch, lambda platform, account_id: NOW - timedelta(hours=3))

    rule = persistence.build_unread_rule("bot_account", clock=lambda: NOW)

    assert rule.first_scan is False
    assert rule.horizon_s == 3 * 3600
    assert rule.reached_reason == "already_read"


def test_nothing_recorded_is_a_first_scan(monkeypatch):
    _account(monkeypatch, lambda platform, account_id: None)

    rule = persistence.build_unread_rule("bot_account", clock=lambda: NOW)

    assert rule.first_scan is True
    assert rule.horizon_s == 7 * 24 * 3600


def test_an_unreadable_record_reads_as_a_first_scan_and_says_so(monkeypatch):
    def broken(platform, account_id):
        raise RuntimeError("database is locked")

    _account(monkeypatch, broken)
    warnings = []
    monkeypatch.setattr(persistence.logger, "warning", warnings.append)

    rule = persistence.build_unread_rule("bot_account", clock=lambda: NOW)

    assert rule.first_scan is True
    assert any("database is locked" in message for message in warnings)


def test_a_notification_that_came_in_while_the_last_scan_read_is_unread(recorded):
    """The last scan began reading at 0, wrote what it read at 3 min; a follow came in at 1 min,
    above what it had read. The next scan, at 33 min, shows it « 32 min » old: unread. Measured from
    the write, the horizon was 30 min and the row was beyond it, never read."""
    began = _now_to_the_second() - timedelta(minutes=3)
    persistence.record_scan_notifications("bot_account", [_follow("old_fan", "2 h")], read_started_at=began)

    rule = persistence.build_unread_rule("bot_account", clock=lambda: began + timedelta(minutes=33))

    assert rule.horizon_s == 33 * 60
    assert rule.verdict(_follow("new_fan", "32 min")) == UNREAD


def test_the_rows_keep_their_write_time_for_the_sync(recorded):
    """`last_seen_at` is the column the Turso sync pushes and pulls from: a row back-dated to the
    start of the scan would fall behind its cursors. The start lives in the scan's own row."""
    began = _now_to_the_second() - timedelta(minutes=3)
    persistence.record_scan_notifications("bot_account", [_follow("old_fan", "2 h")], read_started_at=began)

    last_seen = recorded.execute("SELECT last_seen_at FROM notifications").fetchone()["last_seen_at"]
    scans = recorded.execute(
        "SELECT created_at FROM notification_actions WHERE action = 'scan' AND account_id = 7").fetchall()

    assert last_seen >= (began + timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S")
    assert [row["created_at"] for row in scans] == [began.strftime("%Y-%m-%d %H:%M:%S")]


def test_a_base_written_before_the_scan_row_reads_from_the_last_write(recorded):
    """Scans of an older engine left no row of their own: the horizon is their last write."""
    persistence.NotificationService.record_notifications(
        platform="instagram", account_id=7, items=[_follow("old_fan", "2 h")])
    recorded.execute("UPDATE notifications SET last_seen_at = '2000-01-09 21:00:00'")
    recorded.commit()

    assert persistence.NotificationService.last_scan_at("instagram", 7) == NOW - timedelta(hours=3)


def test_the_horizon_is_measured_when_the_row_is_judged(monkeypatch):
    """The rule is built before the scan reaches the feed; the row is judged 40 s later. A follow
    that came in 20 s after the last scan began reads « 30 min » then: unknown, it is unread. A
    horizon fixed when the rule was built (30 min) would put it beyond."""
    began = NOW - timedelta(minutes=30)
    _account(monkeypatch, lambda platform, account_id: began)
    clock = {"now": NOW}

    rule = persistence.build_unread_rule("bot_account", clock=lambda: clock["now"])
    clock["now"] = NOW + timedelta(seconds=40)

    assert rule.verdict(_follow("new_fan", "30 min")) == UNREAD
    assert rule.verdict(_follow("old_fan", "31 min")) == BEYOND
