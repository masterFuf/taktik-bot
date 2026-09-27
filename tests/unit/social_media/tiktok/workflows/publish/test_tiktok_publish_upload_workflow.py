"""What the TikTok upload workflow does around its screen steps.

The screen steps are proven on real screens elsewhere (`test_tiktok_publish_camera_to_post_screen`,
`test_tiktok_publish_sound_removal`); here they answer from a script, to pin what the workflow does
with their answers.
"""

import pytest

from taktik.core.social_media.tiktok.workflows.publish import upload_workflow as module

PUSHED = "/sdcard/DCIM/Camera/VID_20260928_010000.mp4"
SAVED_IN_JUNE = {"path": "/storage/emulated/0/DCIM/Camera/2026-06-11-010830653.mp4", "size": 8172575}
COPY = "/storage/emulated/0/DCIM/Camera/2026-09-28-010203456.mp4"


class _Notes:
    def __init__(self):
        self.logs = []

    def log(self, level, message, *args, **kwargs):
        self.logs.append((level, message))

    def status(self, *args, **kwargs):
        pass


@pytest.fixture
def publish(monkeypatch, tmp_path):
    """Every screen step succeeds unless the test says otherwise; the Post taps are counted."""
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    seen = {"post_taps": 0, "listed": [], "recorded": [], "deleted": []}
    answers = {"advance": module.POST_SCREEN_REACHED, "saved_before": [SAVED_IN_JUNE], "saved_copies": [COPY]}

    ok = lambda *a, **k: True  # noqa: E731
    for name in ("trigger_media_scan", "restart_tiktok_package", "wait_for_tiktok_home",
                 "tap_create_button", "tap_upload_button", "ensure_gallery_picker_open",
                 "select_first_gallery_item"):
        monkeypatch.setattr(module, name, ok)
    monkeypatch.setattr(module, "advance_to_post_screen", lambda *a, **k: answers["advance"])
    monkeypatch.setattr(module, "purge_pushed_media", lambda *a, **k: 0)
    monkeypatch.setattr(module, "push_media", lambda *a, **k: PUSHED)

    def _list(device_id, package):
        seen["listed"].append(package)
        return answers["saved_before"]

    def _record(device_id, package, known_paths):
        seen["recorded"].append((package, list(known_paths)))
        return answers["saved_copies"]

    def _delete(device_id, paths, log=None):
        seen["deleted"].append(list(paths))
        return len(paths)

    monkeypatch.setattr(module, "list_media_saved_by", _list)
    monkeypatch.setattr(module, "record_new_media_saved_by", _record)
    monkeypatch.setattr(module, "delete_pushed_media", _delete)
    monkeypatch.setattr(module, "scan_wait_for", lambda path: 0)
    monkeypatch.setattr(module, "resolve_tiktok_package", lambda device_id: "com.zhiliaoapp.musically")
    monkeypatch.setattr(module, "handle_permission_dialog", lambda *a, **k: False)
    monkeypatch.setattr(module, "handle_publish_confirmation_dialog", lambda *a, **k: False)
    monkeypatch.setattr(module, "dismiss_post_popups", lambda *a, **k: False)
    monkeypatch.setattr(module, "force_stop_app_package", lambda *a, **k: None)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)
    monkeypatch.setattr(module.TikTokUploadWorkflow, "_recover_from_video_edit_screen", lambda self: False)
    monkeypatch.setattr(module.TikTokUploadWorkflow, "_refused", lambda self: False)
    monkeypatch.setattr(module.TikTokUploadWorkflow, "_wait_for_publish_commit", lambda self, timeout=120.0: True)

    def _tap(device, selectors, timeout=0):
        seen["post_taps"] += 1
        return True

    monkeypatch.setattr(module, "tap_element", _tap)

    notes = _Notes()

    def _run():
        workflow = module.TikTokUploadWorkflow(device=object(), device_id="device-1", notifier=notes)
        return workflow.execute(local_path=str(video), caption="")

    _run.notes = notes

    _run.seen = seen
    _run.answers = answers
    return _run


def test_a_publication_that_reaches_the_post_screen_is_posted(publish):
    result = publish()

    assert result["success"] is True
    assert publish.seen["post_taps"] == 1


def test_a_sound_that_stays_on_the_video_publishes_nothing(publish):
    publish.answers["advance"] = module.SOUND_NOT_REMOVED

    result = publish()

    assert result["success"] is False
    assert result["error_type"] == "sound_not_removed"
    assert publish.seen["post_taps"] == 0


def test_a_post_screen_never_reached_publishes_nothing(publish):
    publish.answers["advance"] = "post_screen_not_reached"

    result = publish()

    assert result["error_type"] == "post_screen_not_reached"
    assert publish.seen["post_taps"] == 0


# --- what the publication leaves in the camera folder --------------------------------------------


def test_a_confirmed_publication_deletes_the_video_pushed_and_tiktok_s_copy(publish):
    result = publish()

    assert result["success"] is True
    assert publish.seen["listed"] == ["com.zhiliaoapp.musically"]
    # The copy is what TikTok saved after the first reading: the June copy is known, never touched.
    assert publish.seen["recorded"] == [("com.zhiliaoapp.musically", [SAVED_IN_JUNE["path"]])]
    assert publish.seen["deleted"] == [[PUSHED, COPY]]
    assert ("info", "[gallery] saved by TikTok during this publication: 2026-09-28-010203456.mp4") in publish.notes.logs


def test_a_failed_publication_records_tiktok_s_copy_and_deletes_nothing(publish):
    publish.answers["advance"] = "post_screen_not_reached"

    publish()

    assert publish.seen["recorded"] == [("com.zhiliaoapp.musically", [SAVED_IN_JUNE["path"]])]
    assert publish.seen["deleted"] == []


def test_a_crash_midway_still_records_tiktok_s_copy(publish, monkeypatch):
    def _crash(*a, **k):
        raise RuntimeError("uiautomator server gone")

    monkeypatch.setattr(module, "advance_to_post_screen", _crash)

    with pytest.raises(RuntimeError):
        publish()
    assert len(publish.seen["recorded"]) == 1
    assert publish.seen["deleted"] == []


def test_without_a_first_reading_no_copy_is_guessed(publish):
    """MediaStore did not answer before the push: nothing tells TikTok's copy from older files, so
    only the video pushed is deleted."""
    publish.answers["saved_before"] = None

    assert publish()["success"] is True
    assert publish.seen["recorded"] == []
    assert publish.seen["deleted"] == [[PUSHED]]
