"""The repair script: a dry run writes nothing, --apply backs the base up first, then marks.

Every pseudo here is invented; the base is a temporary file built from the real schema.
"""

import hashlib
import sqlite3
import sys
from collections import namedtuple
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import repair_invalid_profile_handles as script  # noqa: E402

LABEL = "Envoyer un message"


@pytest.fixture
def base(conn, tmp_db_path):
    conn.execute(
        "INSERT INTO social_profiles (platform, legacy_profile_id, username) VALUES ('instagram', 1, ?)",
        (LABEL,),
    )
    conn.execute(
        "INSERT INTO social_profiles (platform, legacy_profile_id, username) VALUES ('instagram', 2, 'lina.photo')"
    )
    conn.commit()
    return tmp_db_path


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _marked(path):
    check = sqlite3.connect(path)
    try:
        return {row[0]: row[1] is not None for row in check.execute(
            "SELECT username, unreachable_at FROM social_profiles")}
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
    assert "1 a marquer" in out
    assert repr(LABEL) in out


def test_apply_backs_up_then_marks(base, capsys):
    assert script.main(["--db", base, "--apply"]) == 0

    backups = _backups(base)
    assert len(backups) == 1
    assert _marked(str(backups[0])) == {LABEL: False, "lina.photo": False}
    assert _marked(base) == {LABEL: True, "lina.photo": False}
    assert "Sauvegarde :" in capsys.readouterr().out


def test_no_room_for_the_backup_means_nothing_written(base, monkeypatch, capsys):
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(script.backup_database.__globals__["shutil"], "disk_usage",
                        lambda _path: usage(10, 10, 0))

    assert script.main(["--db", base, "--apply"]) == 1

    assert _marked(base) == {LABEL: False, "lina.photo": False}
    assert _backups(base) == []
    assert "Place insuffisante" in capsys.readouterr().out


def test_nothing_to_mark_means_no_backup(conn, tmp_db_path):
    assert script.main(["--db", tmp_db_path, "--apply"]) == 0
    assert _backups(tmp_db_path) == []
