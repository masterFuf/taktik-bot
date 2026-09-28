"""What a publish leaves in the camera folder, found without guessing and removed intact.

TikTok saves a copy of the video it publishes in `DCIM/Camera`. MediaStore names the package that
wrote each file: TikTok's copies carry `com.zhiliaoapp.musically`, a file pushed over adb carries
`com.android.shell` (Pixel 6a, 2026-09-28, `content query` on the phone). The outputs below are
that phone's, as `content` printed them; the paths hold only TikTok's own names (a date and time).

`adb shell` joins its arguments with spaces and the device's shell splits the line again, so what
matters is what the device RECEIVES: the tests replay that split (`shlex.split` of the joined line).
"""

import shlex
import subprocess

import pytest

from taktik.core.shared.device import media_store, pushed_media_registry

TIKTOK = "com.zhiliaoapp.musically"
CAMERA = "/storage/emulated/0/DCIM/Camera"

# `content query --projection _size:_data --where "owner_package_name=... AND relative_path=..."`
ROWS = (
    f"Row: 0 _size=8172575, _data={CAMERA}/2026-06-11-010830653.mp4\n"
    f"Row: 1 _size=2142271, _data={CAMERA}/2026-06-11-100718487.mp4\n"
    f"Row: 2 _size=8172575, _data={CAMERA}/2026-06-11-010830653 (1).mp4\n"
)
NO_ROW = "No result found.\n"
PROVIDER_ERROR = (
    "Error while accessing provider:media\n"
    "java.lang.IllegalArgumentException: Invalid token owner_package_nam\n"
    "\tat android.database.DatabaseUtils.readExceptionFromParcel(DatabaseUtils.java:207)\n"
)


@pytest.fixture(autouse=True)
def _own_registry(tmp_path, monkeypatch):
    """Never read the pushed-media registry of the machine running the tests."""
    monkeypatch.setenv("TAKTIK_DATA_DIR", str(tmp_path / "data"))


class DeviceShell:
    """Stands for `subprocess.run` of `adb -s <serial> shell ...`: keeps the words the device's
    shell reads, and answers from a script keyed by the first word."""

    def __init__(self, answers=None):
        self.received = []
        self.answers = answers or {}

    def __call__(self, cmd, capture_output=True, text=True, timeout=15):
        assert cmd[:2] == ["adb", "-s"] and cmd[3] == "shell"
        words = shlex.split(" ".join(cmd[4:]))
        self.received.append(words)
        out, err = self.answers.get(words[0], ("", ""))
        return subprocess.CompletedProcess(cmd, 0, out, err)

    def where_clauses(self):
        return [words[words.index("--where") + 1] for words in self.received if "--where" in words]


@pytest.fixture
def shell(monkeypatch):
    def _install(answers=None):
        fake = DeviceShell(answers)
        monkeypatch.setattr(media_store.subprocess, "run", fake)
        return fake
    return _install


# --- every argument reaches the device whole ---------------------------------------------------


def test_the_mediastore_row_is_deleted_with_its_where_clause_intact(shell):
    """Unquoted, the provider received `_data=/storage/...` and answered "Invalid token"."""
    fake = shell()

    assert media_store._delete_remote_media("dev", "/sdcard/DCIM/Camera/VID_20260928_010000.mp4")
    assert fake.where_clauses() == [f"_data='{CAMERA}/VID_20260928_010000.mp4'"] * 2


def test_a_file_name_with_a_space_stays_one_path(shell):
    fake = shell()
    path = f"{CAMERA}/2026-06-11-010830653 (1).mp4"

    media_store._delete_remote_media("dev", path)

    assert fake.received[0] == ["rm", "-f", path]
    assert fake.where_clauses()[0] == f"_data='{path}'"


# --- what an app saved, as MediaStore lists it -------------------------------------------------


def test_the_media_an_app_saved_are_read_from_mediastore(shell):
    fake = shell({"content": (ROWS, "")})

    rows = media_store.list_media_saved_by("dev", TIKTOK)

    assert rows == [
        {"path": f"{CAMERA}/2026-06-11-010830653.mp4", "size": 8172575},
        {"path": f"{CAMERA}/2026-06-11-100718487.mp4", "size": 2142271},
        {"path": f"{CAMERA}/2026-06-11-010830653 (1).mp4", "size": 8172575},
    ]
    assert fake.where_clauses() == [f"owner_package_name='{TIKTOK}' AND relative_path='DCIM/Camera/'"]


def test_an_app_that_saved_nothing_there_has_no_rows(shell):
    shell({"content": (NO_ROW, "")})

    assert media_store.list_media_saved_by("dev", TIKTOK) == []


def test_an_error_of_the_media_provider_is_no_empty_folder(shell):
    """`content` exits 0 on a provider error: the text says it, and nothing is taken for a list."""
    shell({"content": ("", PROVIDER_ERROR)})

    assert media_store.list_media_saved_by("dev", TIKTOK) is None


def test_a_row_without_a_size_is_left_out(shell):
    shell({"content": (f"Row: 0 _size=NULL, _data={CAMERA}/2026-09-28-010203456.mp4\n" + ROWS, "")})

    assert [row["path"] for row in media_store.list_media_saved_by("dev", TIKTOK)] == [
        f"{CAMERA}/2026-06-11-010830653.mp4",
        f"{CAMERA}/2026-06-11-100718487.mp4",
        f"{CAMERA}/2026-06-11-010830653 (1).mp4",
    ]


# --- the copy of this publish: recorded, then deleted like a pushed file -----------------------


def test_only_the_media_new_since_the_publish_began_are_recorded(shell):
    shell({"content": (ROWS, "")})
    known = [f"{CAMERA}/2026-06-11-010830653.mp4", f"{CAMERA}/2026-06-11-100718487.mp4"]

    recorded = media_store.record_new_media_saved_by("dev", TIKTOK, known)

    assert recorded == [f"{CAMERA}/2026-06-11-010830653 (1).mp4"]
    assert [(entry["path"], entry["size"]) for entry in pushed_media_registry.load("dev")] == [
        (f"{CAMERA}/2026-06-11-010830653 (1).mp4", 8172575)]


def test_nothing_is_recorded_when_mediastore_does_not_answer(shell):
    shell({"content": ("", PROVIDER_ERROR)})

    assert media_store.record_new_media_saved_by("dev", TIKTOK, []) is None
    assert pushed_media_registry.load("dev") == []


def test_a_recorded_copy_is_deleted_once_the_publish_is_confirmed(shell):
    copy = f"{CAMERA}/2026-06-11-010830653 (1).mp4"
    fake = shell({"content": (ROWS, ""), "stat": ("8172575", "")})
    media_store.record_new_media_saved_by("dev", TIKTOK, [f"{CAMERA}/2026-06-11-010830653.mp4",
                                                         f"{CAMERA}/2026-06-11-100718487.mp4"])

    assert media_store.delete_pushed_media("dev", [copy]) == 1
    assert ["rm", "-f", copy] in fake.received
    assert pushed_media_registry.load("dev") == []
