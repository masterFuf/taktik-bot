"""What the TikTok upload workflow does around its screen steps.

The screen steps are proven on real screens elsewhere (`test_tiktok_publish_camera_to_post_screen`,
`test_tiktok_publish_sound_removal`); here they answer from a script, to pin what the workflow does
with their answers.
"""

import pytest

from taktik.core.social_media.tiktok.workflows.publish import upload_workflow as module


class _Quiet:
    def log(self, *args, **kwargs):
        pass

    def status(self, *args, **kwargs):
        pass


@pytest.fixture
def publish(monkeypatch, tmp_path):
    """Every screen step succeeds unless the test says otherwise; the Post taps are counted."""
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    seen = {"post_taps": 0}
    answers = {"advance": module.POST_SCREEN_REACHED}

    ok = lambda *a, **k: True  # noqa: E731
    for name in ("trigger_media_scan", "restart_tiktok_package", "wait_for_tiktok_home",
                 "tap_create_button", "tap_upload_button", "ensure_gallery_picker_open",
                 "select_first_gallery_item"):
        monkeypatch.setattr(module, name, ok)
    monkeypatch.setattr(module, "advance_to_post_screen", lambda *a, **k: answers["advance"])
    monkeypatch.setattr(module, "purge_pushed_media", lambda *a, **k: 0)
    monkeypatch.setattr(module, "push_media", lambda *a, **k: "/sdcard/DCIM/Camera/VID_20260928_010000.mp4")
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

    def _run():
        workflow = module.TikTokUploadWorkflow(device=object(), device_id="device-1", notifier=_Quiet())
        return workflow.execute(local_path=str(video), caption="")

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
