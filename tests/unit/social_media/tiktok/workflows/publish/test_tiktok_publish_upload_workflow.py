"""What the TikTok upload workflow does around its screen steps.

The screen steps are proven on real screens elsewhere (`test_tiktok_publish_camera_to_post_screen`,
`test_tiktok_publish_sound_removal`); here they answer from a script, to pin what the workflow does
with their answers.
"""

import pytest

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.services.navigation import reset
from taktik.core.social_media.tiktok.services.publish.navigation import POST_SCREEN_NOT_REACHED
from taktik.core.social_media.tiktok.ui import language
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.workflows.publish import upload_workflow as module
from screen_phone import ScreenPhone
from test_tiktok_publish_exit import BACKS, SCREENS

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
    answers = {"advance": module.POST_SCREEN_REACHED, "saved_before": [SAVED_IN_JUNE], "saved_copies": [COPY],
               "caption_filled": True, "post_tapped": True, "refused": False, "committed": True}

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
    monkeypatch.setattr(module.TikTokUploadWorkflow, "_refused", lambda self: answers["refused"])
    monkeypatch.setattr(module.TikTokUploadWorkflow, "_wait_for_publish_commit",
                        lambda self, timeout=120.0: answers["committed"])
    monkeypatch.setattr(module.TikTokUploadWorkflow, "_fill_caption",
                        lambda self, caption, hashtags: answers["caption_filled"])
    monkeypatch.setattr(language, "detect_and_optimize", lambda device: "fr")

    def _tap(device, selectors, timeout=0):
        seen["post_taps"] += 1
        return answers["post_tapped"]

    monkeypatch.setattr(module, "tap_element", _tap)

    notes = _Notes()

    def _run(device=None, caption=""):
        workflow = module.TikTokUploadWorkflow(device=device or object(), device_id="device-1", notifier=notes)
        return workflow.execute(local_path=str(video), caption=caption)

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


# --- a failure after the medium was chosen backs out to the feed ---------------------------------


@pytest.fixture
def phone_on_the_publication(monkeypatch):
    """A TikTok 47.0.3 in French on real screens (`test_tiktok_publish_exit`), each back as the
    phone answered it."""
    monkeypatch.setattr(reset.time, "sleep", lambda _seconds: None)
    apply_version_overrides("tiktok", "47.0.3")
    set_active_locale("fr")
    yield lambda screen: ScreenPhone(screen, SCREENS, BACKS)
    set_active_locale(None)
    apply_version_overrides("tiktok", "43.1.4")


#: Each failure after the medium was chosen: what makes it, the screen it leaves, the backs to the feed.
FAILURES = {
    "sound_not_removed": ({"advance": module.SOUND_NOT_REMOVED}, "editor", 3),
    "post_screen_not_reached": ({"advance": POST_SCREEN_NOT_REACHED}, "editor", 3),
    "caption_fill_failed": ({"caption_filled": False}, "post_screen", 4),
    "post_btn_not_found": ({"post_tapped": False}, "post_screen", 4),
    "publish_not_committed": ({"committed": False}, "post_screen", 4),
    "action_blocked": ({"refused": True}, "post_screen", 4),
}


@pytest.mark.parametrize("error_type", list(FAILURES))
def test_a_failure_after_the_medium_was_chosen_leaves_the_publication_for_the_feed(
        publish, phone_on_the_publication, error_type):
    answers, screen, backs = FAILURES[error_type]
    publish.answers.update(answers)
    phone = phone_on_the_publication(screen)

    result = publish(device=phone, caption="a caption")

    assert result["success"] is False
    assert result["error_type"] == error_type, "the way out replaced the motive of the failure"
    assert result["left_publish_flow"] is True
    assert phone.screen == "feed"
    assert phone.keys == ["back"] * backs
    assert ("info", "[exit] back on the feed: the publication is left") in publish.notes.logs


def test_a_failure_whose_way_out_cannot_read_the_feed_says_so(publish, phone_on_the_publication):
    publish.answers["committed"] = False
    phone = ScreenPhone("post_screen", SCREENS, BACKS, unreadable=("feed",))

    result = publish(device=phone)

    assert result["error_type"] == "publish_not_committed"
    assert result["left_publish_flow"] is False
    assert any(level == "error" and "TikTok may still be on the publication" in message
               for level, message in publish.notes.logs)


def test_a_published_video_presses_no_back(publish, phone_on_the_publication):
    phone = phone_on_the_publication("post_screen")

    result = publish(device=phone)

    assert result["success"] is True
    assert "left_publish_flow" not in result
    assert phone.keys == []


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
