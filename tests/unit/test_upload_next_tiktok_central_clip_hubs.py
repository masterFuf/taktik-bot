from pathlib import Path

import upload_next_tiktok as shared_uploader
import upload_next_tiktok_central_clip_hubs as central_uploader


def test_main_configures_central_clip_hubs_before_running_shared_uploader(monkeypatch):
    captured = {}

    def fake_main():
        captured.update(
            target=shared_uploader.TARGET_ACCOUNT,
            video_dir=shared_uploader.VIDEO_DIR,
            posted_file=shared_uploader.POSTED_FILE,
            lock_file=shared_uploader.LOCK_FILE,
            caption_builder=shared_uploader.make_caption,
            upload_handler=shared_uploader.upload,
        )
        return 17

    monkeypatch.setattr(shared_uploader, "main", fake_main)

    result = central_uploader.main()

    expected_dir = Path("/home/tospak/Downloads/central.clip.hub")
    assert result == 17
    assert captured == {
        "target": "central.clips.hub",
        "video_dir": expected_dir,
        "posted_file": expected_dir / ".tiktok_posted_central.clips.hub.txt",
        "lock_file": expected_dir / ".tiktok_upload.lock",
        "caption_builder": central_uploader.make_caption,
        "upload_handler": central_uploader.upload_exact,
    }


def test_caption_removes_download_id_and_uses_central_clip_branding():
    caption, tags = central_uploader.make_caption(
        Path("Rick and Morty - Pickle Rick [ijbBV7GvCFA].mp4")
    )

    assert caption == "Rick and Morty - Pickle Rick"
    assert tags == [
        "cartoon",
        "animation",
        "clips",
        "centralclipshub",
    ]


def test_find_exact_media_uri_requires_one_matching_row(monkeypatch):
    class Result:
        returncode = 0
        stdout = "Row: 0 _id=76, _display_name=TAKTIK_20260909_130317.mp4"
        stderr = ""

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(shared_uploader, "run", fake_run)

    uri = central_uploader.find_exact_media_uri(
        "phone-1",
        "/sdcard/DCIM/Camera/TAKTIK_20260909_130317.mp4",
    )

    assert uri == "content://media/external/video/media/76"
    assert captured["command"][-2:] == [
        "--where",
        "_data='/storage/emulated/0/DCIM/Camera/TAKTIK_20260909_130317.mp4'",
    ]
    assert captured["kwargs"] == {"capture_output": True, "timeout": 15}


def test_find_exact_media_uri_rejects_ambiguous_rows(monkeypatch):
    class Result:
        returncode = 0
        stdout = "Row: 0 _id=76\nRow: 1 _id=77"
        stderr = ""

    monkeypatch.setattr(shared_uploader, "run", lambda *args, **kwargs: Result())

    assert (
        central_uploader.find_exact_media_uri(
            "phone-1",
            "/sdcard/DCIM/Camera/TAKTIK_20260909_130317.mp4",
        )
        is None
    )


def test_open_exact_media_uses_targeted_tiktok_share_intent(monkeypatch):
    class Result:
        returncode = 0
        stdout = "Starting: Intent"
        stderr = ""

    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return Result()

    monkeypatch.setattr(shared_uploader, "run", fake_run)

    opened = central_uploader.open_exact_media(
        "phone-1",
        "com.zhiliaoapp.musically",
        "content://media/external/video/media/76",
    )

    assert opened is True
    assert commands == [
        (
            [
                "adb",
                "-s",
                "phone-1",
                "shell",
                "am",
                "force-stop",
                "com.zhiliaoapp.musically",
            ],
            {"capture_output": True, "timeout": 15},
        ),
        (
            [
                "adb",
                "-s",
                "phone-1",
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.SEND",
                "-t",
                "video/mp4",
                "--eu",
                "android.intent.extra.STREAM",
                "content://media/external/video/media/76",
                "-p",
                "com.zhiliaoapp.musically",
                "--grant-read-uri-permission",
            ],
            {"capture_output": True, "timeout": 30},
        ),
    ]


def test_remote_copy_matches_local_sha256(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"the exact queued video")
    expected = central_uploader.file_sha256(video)

    class Result:
        returncode = 0
        stdout = f"{expected}  /sdcard/DCIM/Camera/TAKTIK_test.mp4\n"
        stderr = ""

    monkeypatch.setattr(shared_uploader, "run", lambda *args, **kwargs: Result())

    assert central_uploader.remote_copy_matches(
        "phone-1",
        video,
        "/sdcard/DCIM/Camera/TAKTIK_test.mp4",
    )


def test_remote_copy_rejects_checksum_mismatch(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"the exact queued video")

    class Result:
        returncode = 0
        stdout = f"{'0' * 64}  /sdcard/DCIM/Camera/TAKTIK_test.mp4\n"
        stderr = ""

    monkeypatch.setattr(shared_uploader, "run", lambda *args, **kwargs: Result())

    assert not central_uploader.remote_copy_matches(
        "phone-1",
        video,
        "/sdcard/DCIM/Camera/TAKTIK_test.mp4",
    )
