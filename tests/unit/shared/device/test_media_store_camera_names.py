"""Pushed media look like camera shots, and the cleanup deletes only what we pushed.

A name like `TAKTIK_20260726_011540.png` in the camera folder names the tool. Pushed files now take
the stock camera's naming (`IMG_…`, `VID_…`), which the user's own shots share, so the cleanup can
no longer trust a name: it deletes only the exact paths recorded when we pushed them.

The failure that matters is deleting or overwriting a user's photo, so every test here pins what
is NOT touched as much as what is.
"""
import json
import os
import time

import pytest

from taktik.core.shared.device import media_store, pushed_media_registry
from taktik.core.shared.device.media_store import (
    camera_file_name,
    purge_pushed_media,
    push_media,
)

CAMERA = "/sdcard/DCIM/Camera"
STAMP = "20260925_031512"


class FakePhone:
    """A phone reduced to what media_store asks of it: a folder listing, a clock, file sizes."""

    def __init__(self, files=None, clock=STAMP, answers=True):
        self.files = dict(files or {})  # remote path -> size in bytes
        self.clock = clock
        self.answers = answers
        self.removed = []
        self.deleted_rows = []

    def shell(self, device_id, *args, timeout=15):
        if not self.answers:
            return 1, "", "error: device offline"
        command = args[0] if args else ""
        if command == "date":
            return (0, self.clock, "") if self.clock else (1, "", "date: bad format")
        if command == "ls":
            folder = args[-1].rstrip("/") + "/"
            names = [path[len(folder):] for path in self.files if path.startswith(folder)]
            return 0, "\n".join(names), ""
        if command == "stat":
            path = args[-1]
            if path in self.files:
                return 0, str(self.files[path]), ""
            return 1, "", f"stat: '{path}': No such file or directory"
        if command == "rm":
            self.removed.append(args[-1])
            self.files.pop(args[-1], None)
            return 0, "", ""
        if command == "content":
            self.deleted_rows.append(args[-1])
            return 0, "", ""
        return 0, "", ""

    def push(self, device_id, local_path, remote_path, timeout=60):
        self.files[remote_path] = os.path.getsize(local_path)
        return True


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    folder = tmp_path / "data"
    monkeypatch.setenv("TAKTIK_DATA_DIR", str(folder))
    return folder


@pytest.fixture
def phone(monkeypatch):
    def _install(**kwargs):
        fake = FakePhone(**kwargs)
        monkeypatch.setattr(media_store, "_adb_shell", fake.shell)
        monkeypatch.setattr(media_store, "_adb_push", fake.push)
        return fake
    return _install


@pytest.fixture
def media(tmp_path):
    def _make(name, size=10):
        path = tmp_path / name
        path.write_bytes(b"x" * size)
        return str(path)
    return _make


def _age_registry(device_id, hours):
    entries = pushed_media_registry.load(device_id)
    for entry in entries:
        entry["pushed_at"] -= hours * 3600
    pushed_media_registry.save(device_id, entries)


# --- naming -----------------------------------------------------------------------------------

def test_a_picture_is_named_like_a_camera_shot(phone, media):
    phone()
    remote = push_media("dev", media("post.jpg"))
    assert remote == f"{CAMERA}/IMG_{STAMP}.jpg"
    assert "TAKTIK" not in remote


def test_a_video_is_named_like_a_camera_recording(phone, media):
    phone()
    assert push_media("dev", media("reel.mp4")) == f"{CAMERA}/VID_{STAMP}.mp4"


def test_the_name_uses_the_phone_clock(phone, media):
    phone(clock="20251231_235959")
    assert push_media("dev", media("post.jpg")).endswith("/IMG_20251231_235959.jpg")


def test_an_unreadable_phone_clock_still_gives_a_camera_name(phone, media):
    phone(clock=None)
    name = os.path.basename(push_media("dev", media("post.jpg")))
    stamp = name[len("IMG_"):-len(".jpg")]
    assert name.startswith("IMG_") and name.endswith(".jpg")
    assert len(stamp) == 15 and stamp[8] == "_" and (stamp[:8] + stamp[9:]).isdigit()


def test_extensions_are_the_ones_a_camera_writes():
    assert camera_file_name("a.JPEG", STAMP) == f"IMG_{STAMP}.jpg"
    assert camera_file_name("a.PNG", STAMP) == f"IMG_{STAMP}.png"
    assert camera_file_name("a.MP4", STAMP) == f"VID_{STAMP}.mp4"
    assert camera_file_name("no_extension", STAMP) == f"VID_{STAMP}.mp4"


# --- no collision -----------------------------------------------------------------------------

def test_two_pushes_in_the_same_second_do_not_collide(phone, media):
    fake = phone()
    first = push_media("dev", media("one.jpg", size=11))
    second = push_media("dev", media("two.jpg", size=22))
    assert first == f"{CAMERA}/IMG_{STAMP}.jpg"
    assert second == f"{CAMERA}/IMG_{STAMP}_1.jpg"
    assert fake.files[first] == 11 and fake.files[second] == 22


def test_a_user_shot_of_the_same_second_is_never_overwritten(phone, media):
    user_shot = f"{CAMERA}/IMG_{STAMP}.JPG"  # the shared storage ignores case
    fake = phone(files={user_shot: 999})
    remote = push_media("dev", media("post.jpg"))
    assert remote == f"{CAMERA}/IMG_{STAMP}_1.jpg"
    assert fake.files[user_shot] == 999


def test_a_folder_that_cannot_be_listed_is_not_pushed_into(phone, media, monkeypatch):
    fake = phone()
    monkeypatch.setattr(media_store, "_adb_shell", lambda *a, **k: (1, "", "ls: permission denied"))
    assert push_media("dev", media("post.jpg")) is None
    assert fake.files == {}
    assert pushed_media_registry.load("dev") == []


# --- registry ---------------------------------------------------------------------------------

def test_every_push_is_recorded_with_its_exact_path_and_size(phone, media):
    phone()
    remote = push_media("dev", media("post.jpg", size=42))
    [entry] = pushed_media_registry.load("dev")
    assert entry["path"] == remote and entry["size"] == 42


def test_a_network_serial_gets_its_own_registry_file(phone, media, data_dir):
    phone()
    push_media("10.0.0.2:5555", media("post.jpg"))
    assert pushed_media_registry.load("10.0.0.2:5555")
    assert all(":" not in name for name in os.listdir(data_dir / "pushed_media"))


# --- cleanup ----------------------------------------------------------------------------------

def test_the_cleanup_deletes_what_we_pushed_and_no_user_shot(phone, media):
    user_shots = {
        f"{CAMERA}/IMG_20240101_120000.jpg": 5000,
        f"{CAMERA}/VID_20240101_120000.mp4": 9000,
        f"{CAMERA}/IMG_{STAMP}_2.jpg": 10,  # same pattern, same size as ours, never pushed
    }
    fake = phone(files=user_shots)
    ours = push_media("dev", media("post.jpg", size=10))
    _age_registry("dev", 24)

    assert purge_pushed_media("dev") == 1
    assert fake.removed == [ours]
    assert all(path in fake.files for path in user_shots)
    assert pushed_media_registry.load("dev") == []


def test_camera_named_files_are_never_swept_without_a_record(phone):
    fake = phone(files={f"{CAMERA}/IMG_20200101_000000.jpg": 10, f"{CAMERA}/VID_20200101_000000.mp4": 10})
    assert purge_pushed_media("dev") == 0
    assert fake.removed == []


def test_a_push_still_in_flight_is_kept(phone, media):
    fake = phone()
    push_media("dev", media("post.jpg"))
    assert purge_pushed_media("dev", max_age_hours=6) == 0
    assert fake.removed == []
    assert len(pushed_media_registry.load("dev")) == 1


def test_a_recorded_path_now_holding_another_file_is_left_alone(phone, media):
    fake = phone()
    ours = push_media("dev", media("post.jpg", size=10))
    fake.files[ours] = 777  # our file went away and something else took the name
    _age_registry("dev", 24)

    assert purge_pushed_media("dev") == 0
    assert fake.removed == [] and fake.files[ours] == 777
    assert pushed_media_registry.load("dev") == []


def test_a_recorded_path_already_gone_is_forgotten(phone, media):
    fake = phone()
    ours = push_media("dev", media("post.jpg"))
    del fake.files[ours]
    _age_registry("dev", 24)

    assert purge_pushed_media("dev") == 0
    assert fake.removed == []
    assert pushed_media_registry.load("dev") == []


def test_a_phone_that_does_not_answer_keeps_the_record_for_next_time(phone, media):
    fake = phone()
    push_media("dev", media("post.jpg"))
    _age_registry("dev", 24)
    fake.answers = False

    assert purge_pushed_media("dev") == 0
    assert len(pushed_media_registry.load("dev")) == 1


def test_the_cleanup_forgets_the_mediastore_row_too(phone, media):
    fake = phone()
    push_media("dev", media("post.jpg"))
    _age_registry("dev", 24)

    purge_pushed_media("dev")
    assert len(fake.deleted_rows) == 2
    assert all(f"/storage/emulated/0/DCIM/Camera/IMG_{STAMP}.jpg" in row for row in fake.deleted_rows)


def test_legacy_taktik_files_are_still_cleaned_next_to_registered_ones(phone, media):
    old = time.strftime("%Y%m%d_%H%M%S", time.localtime(time.time() - 48 * 3600))
    legacy = f"{CAMERA}/TAKTIK_{old}.png"
    user_shot = f"{CAMERA}/IMG_{old}.jpg"
    fake = phone(files={legacy: 10, user_shot: 10})
    ours = push_media("dev", media("post.jpg"))
    _age_registry("dev", 24)

    assert purge_pushed_media("dev") == 2
    assert sorted(fake.removed) == sorted([ours, legacy])
    assert user_shot in fake.files


def test_a_record_from_another_phone_is_not_used(phone, media):
    fake = phone()
    ours = push_media("phone-a", media("post.jpg", size=10))
    _age_registry("phone-a", 24)
    fake.files = {ours: 10}  # phone B holds a same-named, same-sized file of its own

    assert purge_pushed_media("phone-b") == 0
    assert fake.removed == []


def test_a_corrupt_registry_deletes_nothing(phone, data_dir):
    fake = phone(files={f"{CAMERA}/IMG_{STAMP}.jpg": 10})
    (data_dir / "pushed_media").mkdir(parents=True)
    (data_dir / "pushed_media" / "dev.json").write_text("{not json", encoding="utf-8")

    assert purge_pushed_media("dev") == 0
    assert fake.removed == []


def test_a_malformed_record_is_ignored(phone, data_dir):
    fake = phone(files={f"{CAMERA}/IMG_{STAMP}.jpg": 10})
    (data_dir / "pushed_media").mkdir(parents=True)
    (data_dir / "pushed_media" / "dev.json").write_text(
        json.dumps({"pushed": [{"path": f"{CAMERA}/IMG_{STAMP}.jpg", "pushed_at": 0}]}),
        encoding="utf-8",
    )

    assert purge_pushed_media("dev") == 0
    assert fake.removed == []
