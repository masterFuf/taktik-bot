"""The scan's rule comes from what the account recorded: its last scan, and the identities seen."""

from datetime import datetime, timedelta, timezone

from taktik.core.social_media.instagram.workflows.notifications import persistence

NOW = datetime(2000, 1, 10, tzinfo=timezone.utc)


def _account(monkeypatch, last_scan):
    monkeypatch.setattr(persistence, "resolve_account_id", lambda username: 7)
    monkeypatch.setattr(persistence.NotificationService, "known_content_hashes", staticmethod(lambda p, a: set()))
    monkeypatch.setattr(persistence.NotificationService, "last_scan_at", staticmethod(last_scan))


def test_the_horizon_is_the_last_scan(monkeypatch):
    _account(monkeypatch, lambda platform, account_id: NOW - timedelta(hours=3))

    rule = persistence.build_unread_rule("bot_account", now=NOW)

    assert rule.first_scan is False
    assert rule.horizon_s == 3 * 3600
    assert rule.reached_reason == "already_read"


def test_nothing_recorded_is_a_first_scan(monkeypatch):
    _account(monkeypatch, lambda platform, account_id: None)

    rule = persistence.build_unread_rule("bot_account", now=NOW)

    assert rule.first_scan is True
    assert rule.horizon_s == 7 * 24 * 3600


def test_an_unreadable_record_reads_as_a_first_scan_and_says_so(monkeypatch):
    def broken(platform, account_id):
        raise RuntimeError("database is locked")

    _account(monkeypatch, broken)
    warnings = []
    monkeypatch.setattr(persistence.logger, "warning", warnings.append)

    rule = persistence.build_unread_rule("bot_account", now=NOW)

    assert rule.first_scan is True
    assert any("database is locked" in message for message in warnings)
