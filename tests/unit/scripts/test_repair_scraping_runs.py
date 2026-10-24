"""The repair script of the scraping runs: a dry run writes nothing and shows five examples, --apply
backs the base up, writes in one transaction and keeps a journal of every changed row.

The base is a temporary file built by the numbered schema; every pseudo is invented.
"""

import hashlib
import json
import sqlite3
import sys
from collections import namedtuple
from pathlib import Path

import pytest
from unit.paths import CORE

from taktik.core.database.local.versions.runner import migrate_database

sys.path.insert(0, str(CORE / "scripts/repairs"))

import repair_scraping_runs as script  # noqa: E402

LIKERS_ONLY = {'type': 'hashtag', 'hashtag': 'metz', 'scrape_likers': True, 'scrape_commenters': False}


@pytest.fixture
def base(tmp_path):
    path = tmp_path / "taktik-data.db"
    assert migrate_database(path, backup_dir=tmp_path / "schema-backups").success
    conn = sqlite3.connect(str(path))
    for _ in range(7):
        conn.execute(
            "INSERT INTO scraping_sessions (scraping_type, source_type, source_name, config_used, status, "
            "start_time, end_time) VALUES ('followers', 'HASHTAG', '#metz', ?, 'COMPLETED', "
            "'2026-09-01 20:00:00', '2026-09-01 21:00:00')",
            (json.dumps(LIKERS_ONLY),),
        )
    conn.execute(
        "INSERT INTO scraping_sessions (scraping_type, source_type, source_name, config_used, status) "
        "VALUES ('followers', 'POST_URL', 'https://example.org/p/1', NULL, 'COMPLETED')"
    )
    conn.execute("INSERT INTO social_profiles (platform, legacy_profile_id, username) VALUES ('instagram', 7, 'lina.photo')")
    conn.execute("INSERT INTO scraped_profiles (platform, scraping_id, profile_id) VALUES ('instagram', 1, 7)")
    for at, sync_id in (('2026-09-01 20:05:00', 'a1'), ('2026-09-01 20:59:30', 'b2')):
        conn.execute(
            "INSERT INTO profile_stats_history (profile_id, followers_count, following_count, posts_count, "
            "recorded_at, sync_id) VALUES (7, 1200, 300, 40, ?, ?)",
            (at, sync_id),
        )
    conn.commit()
    conn.close()
    return str(path)


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _state(path):
    conn = sqlite3.connect(path)
    try:
        types = [row[0] for row in conn.execute("SELECT scraping_type FROM scraping_sessions ORDER BY scraping_id")]
        snapshots = [row[0] for row in conn.execute("SELECT sync_id FROM profile_stats_history ORDER BY id")]
        return types, snapshots
    finally:
        conn.close()


def _backups(path):
    return sorted(Path(path).parent.glob(f"*.backup-*-{script.BACKUP_LABEL}.db"))


BEFORE = (['followers'] * 8, ['a1', 'b2'])
AFTER = (['likers'] * 7 + ['followers'], ['a1'])


def test_the_dry_run_writes_nothing_and_shows_five_examples(base, capsys):
    before = _digest(base)

    assert script.main(["--db", base]) == 0

    assert _digest(base) == before
    assert _backups(base) == []
    out = capsys.readouterr().out
    assert "7 session(s) a retyper, 1 non tranchee(s)" in out
    assert out.count(": followers -> likers") == 5
    assert "... et 2 autre(s)" in out
    assert "aucune config enregistree" in out
    assert "1 releve(s) en double a retirer" in out


def test_apply_backs_up_then_repairs_and_journals_every_row(base, capsys):
    assert script.main(["--db", base, "--apply"]) == 0

    backups = _backups(base)
    assert len(backups) == 1
    assert _state(str(backups[0])) == BEFORE
    assert _state(base) == AFTER

    journal = backups[0].with_suffix(".journal.txt").read_text(encoding="utf-8")
    assert journal.count(": followers -> likers") == 7
    assert '"sync_id": "b2"' in journal
    out = capsys.readouterr().out
    assert "Sauvegarde :" in out and "Journal :" in out


def test_a_second_apply_finds_nothing_and_backs_nothing_up(base):
    assert script.main(["--db", base, "--apply"]) == 0
    assert script.main(["--db", base, "--apply"]) == 0

    assert len(_backups(base)) == 1


def test_no_room_for_the_backup_means_nothing_written(base, monkeypatch, capsys):
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(script.backup_database.__globals__["shutil"], "disk_usage",
                        lambda _path: usage(10, 10, 0))

    assert script.main(["--db", base, "--apply"]) == 1

    assert _state(base) == BEFORE
    assert _backups(base) == []
    assert "Place insuffisante" in capsys.readouterr().out


def test_a_missing_base_is_said(tmp_path, capsys):
    assert script.main(["--db", str(tmp_path / "absent.db")]) == 1
    assert "Base introuvable" in capsys.readouterr().out
