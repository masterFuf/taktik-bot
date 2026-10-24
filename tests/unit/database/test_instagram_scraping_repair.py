"""The repair of the Instagram scraping runs: post sessions typed 'followers', stats snapshots saved twice.

Every base here is a temporary file built by the numbered schema (the schema of an operator's base);
every pseudo is invented. The session types are read back by the workflow's own rule,
`saved_post_session_type`, as the repair script wires it.
"""

import dataclasses
import json
import sqlite3
import uuid

import pytest

from taktik.core.database.instagram_scraping_repair import ScrapingRunRepair
from taktik.core.database.local.versions.runner import migrate_database
from taktik.core.social_media.instagram.workflows.scraping.persistence import (
    POST_SOURCE_TYPES,
    saved_post_session_type,
)

NO_CONFIG = object()
LIKERS_ONLY = {'type': 'hashtag', 'hashtag': 'metz', 'scrape_likers': True, 'scrape_commenters': False}


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "taktik-data.db"
    assert migrate_database(path, backup_dir=tmp_path / "backups").success
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    yield con
    con.close()


def _repair(conn):
    return ScrapingRunRepair(conn, tuple(POST_SOURCE_TYPES.values()), saved_post_session_type)


def _session(conn, source_type='HASHTAG', scraping_type='followers', config=NO_CONFIG, status='COMPLETED',
             start='2026-09-01 20:00:00', end='2026-09-01 21:00:00', platform='instagram'):
    if config is NO_CONFIG:
        raw = None
    elif isinstance(config, str):
        raw = config
    else:
        raw = json.dumps(config)
    cursor = conn.execute(
        "INSERT INTO scraping_sessions (scraping_type, source_type, source_name, config_used, status, "
        "start_time, end_time, platform, updated_at) VALUES (?, ?, 'source', ?, ?, ?, ?, ?, '2026-09-01 21:00:00')",
        (scraping_type, source_type, raw, status, start, end, platform),
    )
    conn.commit()
    return cursor.lastrowid


def _profile(conn, profile_id, username, *runs):
    conn.execute("INSERT INTO social_profiles (platform, legacy_profile_id, username) VALUES ('instagram', ?, ?)",
                 (profile_id, username))
    for run in runs:
        conn.execute("INSERT INTO scraped_profiles (platform, scraping_id, profile_id) VALUES ('instagram', ?, ?)",
                     (run, profile_id))
    conn.commit()


def _snapshot(conn, profile_id, at, followers=1200, following=300, posts=40, biography=None):
    cursor = conn.execute(
        "INSERT INTO profile_stats_history (profile_id, followers_count, following_count, posts_count, "
        "biography, recorded_at, sync_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (profile_id, followers, following, posts, biography, at, uuid.uuid4().hex),
    )
    conn.commit()
    return cursor.lastrowid


def _types(conn):
    return {row[0]: row[1] for row in conn.execute("SELECT scraping_id, scraping_type FROM scraping_sessions")}


def _snapshot_ids(conn):
    return sorted(row[0] for row in conn.execute("SELECT id FROM profile_stats_history"))


class TestPostSessionTypes:
    def test_a_hashtag_session_that_read_likers_becomes_likers(self, conn):
        run = _session(conn, config=LIKERS_ONLY)

        _repair(conn).apply()

        assert _types(conn) == {run: 'likers'}

    def test_a_post_url_session_takes_the_lists_its_config_names(self, conn):
        commenters = _session(conn, 'POST_URL', config={'type': 'post_url', 'scrape_likers': False,
                                                         'scrape_commenters': True})
        both = _session(conn, 'POST_URL', config={'type': 'post_url', 'scrape_likers': True,
                                                   'scrape_commenters': True})

        _repair(conn).apply()

        assert _types(conn) == {commenters: 'commenters', both: 'likers+commenters'}

    def test_the_new_type_travels_with_the_sync(self, conn):
        run = _session(conn, config=LIKERS_ONLY)

        _repair(conn).apply()

        updated_at = conn.execute("SELECT updated_at FROM scraping_sessions WHERE scraping_id = ?", (run,)).fetchone()[0]
        assert updated_at != '2026-09-01 21:00:00'

    @pytest.mark.parametrize("config, reason", [
        (NO_CONFIG, "aucune config"),
        ("{not json", "illisible"),
        ([1, 2], "pas un objet"),
        ({'type': 'hashtag', 'scrape_likers': True}, "sans scrape_commenters"),
        ({'type': 'hashtag'}, "sans scrape_likers, scrape_commenters"),
        ({'type': 'target', 'scrape_likers': True, 'scrape_commenters': False}, "autre run"),
        ({'scrape_likers': True, 'scrape_commenters': False}, "autre run"),
    ])
    def test_a_session_the_config_cannot_decide_is_listed_and_left(self, conn, config, reason):
        run = _session(conn, config=config)

        plan = _repair(conn).apply()

        assert _types(conn) == {run: 'followers'}
        assert [session.scraping_id for session in plan.session_types.undecided] == [run]
        assert reason in plan.session_types.undecided[0].reason

    def test_clean_sessions_and_other_sources_are_not_touched(self, conn):
        already = _session(conn, scraping_type='likers', config=LIKERS_ONLY)
        target = _session(conn, 'TARGET', config={'type': 'target', 'scrape_type': 'followers'})
        tiktok = _session(conn, platform='tiktok', config=LIKERS_ONLY)

        plan = _repair(conn).plan()

        assert not plan.has_work
        assert plan.session_types.undecided == []
        assert _types(conn) == {already: 'likers', target: 'followers', tiktok: 'followers'}


class TestStatsDoubles:
    def test_the_exact_double_of_one_run_is_removed_and_the_first_kept(self, conn):
        run = _session(conn, config=LIKERS_ONLY)
        _profile(conn, 7, 'lina.photo', run)
        first = _snapshot(conn, 7, '2026-09-01 20:05:00')
        second = _snapshot(conn, 7, '2026-09-01 20:59:30')

        plan = _repair(conn).apply()

        assert _snapshot_ids(conn) == [first]
        assert [(pair.first_id, pair.second_id) for pair in plan.stats_doubles.doubles] == [(first, second)]

    def test_two_different_readings_in_one_run_are_both_kept(self, conn):
        run = _session(conn, config=LIKERS_ONLY)
        _profile(conn, 7, 'lina.photo', run)
        first = _snapshot(conn, 7, '2026-09-01 20:05:00', followers=1200)
        second = _snapshot(conn, 7, '2026-09-01 20:59:30', followers=1201)

        plan = _repair(conn).apply()

        assert _snapshot_ids(conn) == [first, second]
        assert [(pair.first_id, pair.second_id) for pair in plan.stats_doubles.different] == [(first, second)]

    def test_a_difference_outside_the_counters_is_a_difference(self, conn):
        run = _session(conn, config=LIKERS_ONLY)
        _profile(conn, 7, 'lina.photo', run)
        first = _snapshot(conn, 7, '2026-09-01 20:05:00', biography='ceramique')
        second = _snapshot(conn, 7, '2026-09-01 20:59:30', biography='ceramique, Metz')

        _repair(conn).apply()

        assert _snapshot_ids(conn) == [first, second]

    def test_a_double_outside_any_run_is_not_touched(self, conn):
        run = _session(conn, config=LIKERS_ONLY)
        _profile(conn, 7, 'lina.photo', run)
        before = _snapshot(conn, 7, '2026-09-01 19:00:00')
        after = _snapshot(conn, 7, '2026-09-01 22:00:00')
        _profile(conn, 8, 'marc.atelier')
        unlinked = [_snapshot(conn, 8, '2026-09-01 20:05:00'), _snapshot(conn, 8, '2026-09-01 20:59:30')]

        plan = _repair(conn).apply()

        assert not plan.stats_doubles.has_work
        assert _snapshot_ids(conn) == sorted([before, after, *unlinked])

    def test_a_run_that_did_not_complete_is_not_touched(self, conn):
        run = _session(conn, config=LIKERS_ONLY, status='INTERRUPTED')
        _profile(conn, 7, 'lina.photo', run)
        kept = [_snapshot(conn, 7, '2026-09-01 20:05:00'), _snapshot(conn, 7, '2026-09-01 20:59:30')]

        _repair(conn).apply()

        assert _snapshot_ids(conn) == kept

    def test_more_than_two_snapshots_in_a_run_are_listed_and_left(self, conn):
        run = _session(conn, config=LIKERS_ONLY)
        _profile(conn, 7, 'lina.photo', run)
        kept = [_snapshot(conn, 7, f'2026-09-01 20:{minute}:00') for minute in ('05', '30', '59')]

        plan = _repair(conn).apply()

        assert _snapshot_ids(conn) == kept
        assert [crowded.snapshot_ids for crowded in plan.stats_doubles.crowded] == [tuple(kept)]

    def test_a_pair_another_run_of_the_profile_also_covers_is_left(self, conn):
        run = _session(conn, config=LIKERS_ONLY)
        other = _session(conn, 'TARGET', scraping_type='followers', start='2026-09-01 20:30:00', end=None,
                         status='RUNNING')
        _profile(conn, 7, 'lina.photo', run, other)
        kept = [_snapshot(conn, 7, '2026-09-01 20:05:00'), _snapshot(conn, 7, '2026-09-01 20:59:30')]

        plan = _repair(conn).apply()

        assert _snapshot_ids(conn) == kept
        assert [pair.other_runs for pair in plan.stats_doubles.shared] == [(other,)]


class TestOneTransaction:
    def test_a_failure_in_the_second_repair_writes_nothing(self, conn, monkeypatch):
        run = _session(conn, config=LIKERS_ONLY)
        _profile(conn, 7, 'lina.photo', run)
        kept = [_snapshot(conn, 7, '2026-09-01 20:05:00'), _snapshot(conn, 7, '2026-09-01 20:59:30')]
        repair = _repair(conn)

        def broken(_plan):
            raise RuntimeError("disk gone")

        monkeypatch.setattr(repair._snapshots, "write", broken)

        with pytest.raises(RuntimeError, match="disk gone"):
            repair.apply()

        assert _types(conn) == {run: 'followers'}
        assert _snapshot_ids(conn) == kept

    def test_a_snapshot_gone_meanwhile_undoes_the_ones_already_removed(self, conn, monkeypatch):
        run = _session(conn, config=LIKERS_ONLY)
        _profile(conn, 7, 'lina.photo', run)
        kept = [_snapshot(conn, 7, '2026-09-01 20:05:00'), _snapshot(conn, 7, '2026-09-01 20:59:30')]
        repair = _repair(conn)
        found = repair._snapshots.plan()
        gone = dataclasses.replace(found.doubles[0], second_id=999_999)
        monkeypatch.setattr(repair._snapshots, "plan",
                            lambda: dataclasses.replace(found, doubles=[found.doubles[0], gone]))

        with pytest.raises(RuntimeError, match="999999"):
            repair.apply()

        assert _snapshot_ids(conn) == kept
        assert _types(conn) == {run: 'followers'}

    def test_a_clean_base_has_no_work(self, conn):
        assert not _repair(conn).plan().has_work
