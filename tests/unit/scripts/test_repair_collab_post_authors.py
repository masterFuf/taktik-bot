"""The repair script: a dry run writes nothing, --apply backs the base up first, then repairs.

Every handle here is invented; the base is a temporary file built from the real schema.
"""

import hashlib
import sqlite3
import sys
from collections import namedtuple
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import repair_collab_post_authors as script  # noqa: E402

COLLAB = "lina.photo et marc_studio"


@pytest.fixture
def base(conn, tmp_db_path):
    conn.execute(
        "INSERT INTO processed_hashtag_posts (account_id, hashtag, post_author, post_caption_hash) "
        "VALUES (1, 'velo', ?, 'h1')",
        (COLLAB,),
    )
    conn.commit()
    return tmp_db_path


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _authors(path):
    check = sqlite3.connect(path)
    try:
        return [row[0] for row in check.execute("SELECT post_author FROM processed_hashtag_posts")]
    finally:
        check.close()


def _backups(path):
    return sorted(Path(path).parent.glob(f"*.backup-*-{script.BACKUP_LABEL}.db"))


def test_the_dry_run_writes_nothing(base, capsys):
    before = _digest(base)

    assert script.main(["--db", base]) == 0

    assert _digest(base) == before
    assert _backups(base) == []
    out = capsys.readouterr().out
    assert "1 ligne(s) a reprendre" in out
    assert "@lina.photo" in out


def test_apply_backs_up_then_repairs(base, capsys):
    assert script.main(["--db", base, "--apply"]) == 0

    backups = _backups(base)
    assert len(backups) == 1
    assert _authors(str(backups[0])) == [COLLAB]
    assert _authors(base) == ["lina.photo"]
    assert "Sauvegarde :" in capsys.readouterr().out


def test_no_room_for_the_backup_means_nothing_written(base, monkeypatch, capsys):
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(script.shutil, "disk_usage", lambda _path: usage(10, 10, 0))

    assert script.main(["--db", base, "--apply"]) == 1

    assert _authors(base) == [COLLAB]
    assert _backups(base) == []
    assert "Place insuffisante" in capsys.readouterr().out


def test_nothing_to_repair_means_no_backup(conn, tmp_db_path):
    assert script.main(["--db", tmp_db_path, "--apply"]) == 0
    assert _backups(tmp_db_path) == []
