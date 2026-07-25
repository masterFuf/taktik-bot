"""The purge must reclaim our own media and nothing else.

Publishing copies a file into the device gallery and never removes it, so a phone automated for
months fills up. The purge runs at the START of a publish and only removes media this bot pushed
more than a few hours ago — never a wildcard sweep of the camera folder, which holds the user's
own photos.

The risky failure here is not "it forgot a file", it is "it deleted a holiday picture", so the
selection rule is what gets pinned.
"""
import time

import pytest

from taktik.core.shared.device import media_store
from taktik.core.shared.device.media_store import parse_pushed_timestamp, purge_pushed_media


def _name(hours_ago: float, prefix="TAKTIK", ext=".png"):
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(time.time() - hours_ago * 3600))
    return f"{prefix}_{stamp}{ext}"


class FakeAdb:
    """Records shell calls and answers `ls` with a fixed listing."""

    def __init__(self, listing):
        self.listing = listing
        self.removed = []
        self.deleted_rows = []

    def __call__(self, device_id, *args, timeout=15):
        if args and args[0] == "ls":
            return 0, "\n".join(self.listing), ""
        if args and args[0] == "rm":
            self.removed.append(args[-1])
            return 0, "", ""
        if args and args[0] == "content":
            self.deleted_rows.append(args[-1])
            return 0, "", ""
        return 0, "", ""


@pytest.fixture
def adb(monkeypatch):
    def _install(listing):
        fake = FakeAdb(listing)
        monkeypatch.setattr(media_store, "_adb_shell", fake)
        return fake
    return _install


def test_only_our_prefix_is_ever_removed(adb):
    fake = adb([_name(24), "IMG_20240101_120000.jpg", "holiday.png", "VID_20240101.mp4", ""])
    assert purge_pushed_media("dev") == 1
    assert len(fake.removed) == 1
    assert "TAKTIK_" in fake.removed[0]


def test_recent_media_is_left_alone(adb):
    """A publish still uploading in the background must not lose its file."""
    fake = adb([_name(0.1), _name(1)])
    assert purge_pushed_media("dev", max_age_hours=6) == 0
    assert fake.removed == []


def test_old_media_is_removed_with_its_mediastore_row(adb):
    fake = adb([_name(48)])
    assert purge_pushed_media("dev") == 1
    # Both image and video tables are cleared, else a ghost thumbnail stays in the gallery.
    assert len(fake.deleted_rows) == 2
    assert all("/storage/emulated/0/" in row for row in fake.deleted_rows)


def test_a_prefixed_name_without_a_valid_timestamp_is_not_touched(adb):
    """Age is unknown, so it could belong to a run in flight — leaving it is the safe answer."""
    fake = adb(["TAKTIK_not_a_date.png", "TAKTIK_.png", "TAKTIK_20261345_999999.png"])
    assert purge_pushed_media("dev") == 0
    assert fake.removed == []


def test_an_unreadable_folder_is_not_an_error(adb, monkeypatch):
    monkeypatch.setattr(media_store, "_adb_shell", lambda *a, **k: (1, "", "no such directory"))
    assert purge_pushed_media("dev") == 0


def test_parse_rejects_foreign_names():
    assert parse_pushed_timestamp("IMG_20240101_120000.jpg") is None
    assert parse_pushed_timestamp("holiday.png") is None
    assert parse_pushed_timestamp(_name(1)) is not None
