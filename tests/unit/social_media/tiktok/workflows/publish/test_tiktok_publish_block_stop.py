"""A TikTok publication that TikTok refuses is reported as a refusal, not as a timeout nor a success.

Before, nothing looked for the refusal after the Post tap: the popups were dismissed, the commit
wait ran two minutes and the run ended on `publish_not_committed` (or on success on the retry
path). Now the one look (`look_for_action_block` on `DetectionActions.is_action_blocked`) runs
right after the tap, before any popup is dismissed, and the run's latch is set.
"""

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.tiktok.workflows.publish import upload_workflow as module


class _Refusing:
    def __init__(self, *_args):
        pass

    def is_action_blocked(self):
        run_halt.demander_arret(run_halt.ACTION_BLOCKED, "tiktok (Too many requests)")
        return True


class _Quiet:
    def log(self, *args, **kwargs):
        pass

    def status(self, *args, **kwargs):
        pass


@pytest.fixture
def publish(monkeypatch, tmp_path):
    """Every step before the Post tap succeeds; the Post button is tapped."""
    from taktik.core.social_media.tiktok.actions.atomic.detection import detection_actions

    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    seen = {"dismissed_after_post": 0, "commit_waits": 0, "posted": False}

    ok = lambda *a, **k: True  # noqa: E731
    for name in ("trigger_media_scan", "restart_tiktok_package", "wait_for_tiktok_home",
                 "tap_create_button", "tap_upload_button", "ensure_gallery_picker_open",
                 "select_first_gallery_item", "advance_to_post_screen"):
        monkeypatch.setattr(module, name, ok)
    monkeypatch.setattr(module, "push_media", lambda *a, **k: "/sdcard/DCIM/video.mp4")
    monkeypatch.setattr(module, "scan_wait_for", lambda path: 0)
    monkeypatch.setattr(module, "resolve_tiktok_package", lambda device_id: "com.zhiliaoapp.musically")
    monkeypatch.setattr(module, "handle_permission_dialog", lambda *a, **k: False)
    monkeypatch.setattr(module, "handle_publish_confirmation_dialog", lambda *a, **k: False)
    monkeypatch.setattr(module, "force_stop_app_package", lambda *a, **k: None)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    def _dismiss(*a, **k):
        if seen["posted"]:
            seen["dismissed_after_post"] += 1

    def _tap(device, selectors, timeout=0):
        seen["posted"] = True
        return True

    def _commit(self, timeout=120.0):
        seen["commit_waits"] += 1
        return False

    monkeypatch.setattr(module, "dismiss_post_popups", _dismiss)
    monkeypatch.setattr(module, "tap_element", _tap)
    monkeypatch.setattr(module.TikTokUploadWorkflow, "_recover_from_video_edit_screen", lambda self: False)
    monkeypatch.setattr(module.TikTokUploadWorkflow, "_wait_for_publish_commit", _commit)

    def _run(refusing):
        if refusing:
            monkeypatch.setattr(detection_actions, "DetectionActions", _Refusing)
        workflow = module.TikTokUploadWorkflow(device=object(), device_id="device-1", notifier=_Quiet())
        return workflow.execute(local_path=str(video), caption="")

    _run.seen = seen
    return _run


def test_a_refused_publication_is_reported_as_a_refusal(publish):
    result = publish(refusing=True)

    assert result["error_type"] == "action_blocked"
    assert publish.seen["dismissed_after_post"] == 0, "a popup dismissed over the refusal"
    assert publish.seen["commit_waits"] == 0
    assert run_halt.arret_demande()["code"] == "action_blocked"


def test_without_a_refusal_the_publication_runs_as_before(publish):
    result = publish(refusing=False)

    assert result["error_type"] == "publish_not_committed"
    assert publish.seen["commit_waits"] == 1
