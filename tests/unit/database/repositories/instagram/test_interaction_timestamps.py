"""Anti-regression: batched interaction recording must keep each gesture's REAL time.

Bug found on real data (2026-07): the bot counted likes during profile processing and
wrote them in one burst at the end (record_individual_actions(count=N) -> N INSERTs all
stamped datetime('now') at write time). 2230 of 3022 production interactions shared
their second with another row, so per-action timing stats were meaningless. The chain
now threads an optional interaction_time from the capture site down to the INSERT.

Also locks the sibling fix: the likers workflows double-recorded every FOLLOW (once at
the gesture in _do_follow, once again in _update_stats_from_interaction_result).
"""

from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.database.repositories.instagram.interaction.interaction_repository import InteractionRepository


class _FakeDbService:
    def __init__(self):
        self.interaction_calls = []

    def record_interaction(self, **kwargs):
        self.interaction_calls.append(kwargs)
        return True


def test_repository_record_honors_explicit_interaction_time(conn):
    conn.execute(
        "INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 1, 'bot', 1)"
    )
    repo = InteractionRepository(conn)

    row_id = repo.record(
        account_id=1, profile_id=10, interaction_type='LIKE',
        interaction_time='2026-07-01 10:00:00',
    )
    assert row_id is not None
    stored = conn.execute(
        "SELECT interaction_time FROM interactions WHERE id=?", (row_id,)
    ).fetchone()
    assert stored['interaction_time'] == '2026-07-01 10:00:00'


def test_repository_record_defaults_to_insert_time_when_no_timestamp(conn):
    conn.execute(
        "INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 1, 'bot', 1)"
    )
    repo = InteractionRepository(conn)

    row_id = repo.record(account_id=1, profile_id=10, interaction_type='LIKE')
    stored = conn.execute(
        "SELECT interaction_time FROM interactions WHERE id=?", (row_id,)
    ).fetchone()
    assert stored['interaction_time'] is not None


def test_record_individual_actions_passes_one_timestamp_per_row(monkeypatch):
    fake_db = _FakeDbService()
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    times = ['2026-07-01 10:00:05', '2026-07-01 10:01:12', '2026-07-01 10:02:47']
    ok = InstagramWorkflowStateService.record_individual_actions(
        username="target", action_type="LIKE", count=3,
        account_id=7, session_id=12, timestamps=times,
    )

    assert ok is True
    assert [c["interaction_time"] for c in fake_db.interaction_calls] == times


def test_record_individual_actions_without_timestamps_keeps_legacy_behaviour(monkeypatch):
    fake_db = _FakeDbService()
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    ok = InstagramWorkflowStateService.record_individual_actions(
        username="target", action_type="LIKE", count=2, account_id=7,
    )

    assert ok is True
    assert len(fake_db.interaction_calls) == 2
    assert all(c["interaction_time"] is None for c in fake_db.interaction_calls)


def test_record_individual_actions_pads_missing_timestamps_with_none(monkeypatch):
    # Defensive: a capture site that lost a timestamp must not drop the row itself.
    fake_db = _FakeDbService()
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    ok = InstagramWorkflowStateService.record_individual_actions(
        username="target", action_type="LIKE", count=3,
        account_id=7, timestamps=['2026-07-01 10:00:05'],
    )

    assert ok is True
    assert [c["interaction_time"] for c in fake_db.interaction_calls] == [
        '2026-07-01 10:00:05', None, None,
    ]


def test_utc_timestamp_matches_sqlite_datetime_format():
    ts = InstagramWorkflowStateService.utc_timestamp()
    # 'YYYY-MM-DD HH:MM:SS' — same shape/zone as SQLite datetime('now'), so mixed rows sort correctly.
    import re
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", ts)


def test_service_record_interaction_threads_interaction_time(db):
    account_id, _ = db.get_or_create_account(username='bot', is_bot=True)
    ok = db.record_interaction(
        account_id=account_id, target_username='someone',
        interaction_type='LIKE', interaction_time='2026-07-01 09:30:00',
    )
    assert ok is True

    rows = db.get_interactions(account_id, limit=1)
    assert rows and rows[0]['interaction_time'] == '2026-07-01 09:30:00'


def test_update_stats_from_interaction_result_records_neither_db_nor_action_counters(monkeypatch):
    """The likers path only sets the per-PROFILE counters.

    Two things it must NOT do: re-record the FOLLOW in DB (_do_follow already did it at the
    gesture), and re-add the profile's action totals to the stats manager. The interaction
    engine moves likes/follows/comments/stories as each gesture lands so the desktop live
    panel ticks in real time; adding the totals back here would double every counter.
    """
    from taktik.core.social_media.instagram.actions.base.base_business.stats_recording import StatsRecordingMixin

    calls = []
    monkeypatch.setattr(
        InstagramWorkflowStateService, "record_individual_actions",
        staticmethod(lambda *a, **k: calls.append((a, k)) or True),
    )

    class _Stats:
        def __init__(self):
            self.increments = []

        def increment(self, key, value=1):
            self.increments.append((key, value))

    class _Host(StatsRecordingMixin):
        def __init__(self):
            self.stats_manager = _Stats()

    host = _Host()
    host._update_stats_from_interaction_result(
        'target', {'likes': 2, 'follows': 1, 'stories': 1, 'stories_liked': 0},
        account_id=7, session_id=12,
    )

    assert calls == []  # no direct DB write anymore — the engine already recorded it
    assert host.stats_manager.increments == [('profiles_visited', 1), ('profiles_interacted', 1)]
