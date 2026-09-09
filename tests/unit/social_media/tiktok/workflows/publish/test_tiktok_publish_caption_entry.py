from taktik.core.social_media.tiktok.workflows.publish import upload_workflow as upload_module


class FakeField:
    def __init__(self, *, accepts_text=True):
        self.text = "Add description..."
        self.accepts_text = accepts_text
        self.set_calls = []

    @property
    def info(self):
        return {"text": self.text, "hint": "Add description...", "focused": True}

    def get_text(self):
        return self.text

    def set_text(self, text):
        self.set_calls.append(text)
        if self.accepts_text:
            self.text = text
        return self.accepts_text


def _patch_caption_dependencies(monkeypatch, field):
    monkeypatch.setattr(upload_module, "focus_caption_field", lambda *_a, **_k: field)
    monkeypatch.setattr(upload_module, "clear_caption_text", lambda *_a, **_k: True)
    # This deliberately recreates the defect: Android accepts the keyboard broadcast,
    # while the editable field remains unchanged.
    monkeypatch.setattr(upload_module, "type_caption_text", lambda *_a, **_k: True)
    monkeypatch.setattr(upload_module, "dismiss_keyboard", lambda *_a, **_k: True)
    monkeypatch.setattr(upload_module.time, "sleep", lambda _seconds: None)


def test_fill_caption_does_not_trust_false_positive_keyboard_ack(monkeypatch):
    field = FakeField()
    _patch_caption_dependencies(monkeypatch, field)
    monkeypatch.setattr(
        upload_module.TikTokUploadWorkflow,
        "_confirm_hashtag_suggestion",
        lambda *_a, **_k: False,
    )

    workflow = upload_module.TikTokUploadWorkflow(object(), "device-1")

    assert workflow._fill_caption("Unicode — caption", ["stickman", "animation"])
    assert field.text == "Unicode — caption\n#stickman #animation"
    assert field.set_calls[-1] == "Unicode — caption\n#stickman #animation"


def test_fill_caption_fails_when_keyboard_and_accessibility_input_are_not_visible(monkeypatch):
    field = FakeField(accepts_text=False)
    _patch_caption_dependencies(monkeypatch, field)
    monkeypatch.setattr(
        upload_module.TikTokUploadWorkflow,
        "_confirm_hashtag_suggestion",
        lambda *_a, **_k: False,
    )

    workflow = upload_module.TikTokUploadWorkflow(object(), "device-1")

    assert not workflow._fill_caption("Must be visible", ["verified"])


def test_caption_verification_failure_aborts_before_post(monkeypatch, tmp_path):
    local_path = tmp_path / "source.mp4"
    local_path.write_bytes(b"video")
    remote_path = "/sdcard/DCIM/Camera/TAKTIK_20260905_160000.mp4"
    post_taps = []

    monkeypatch.setattr(upload_module, "purge_pushed_media", lambda *_a, **_k: 0)
    monkeypatch.setattr(upload_module, "push_media", lambda *_a, **_k: remote_path)
    monkeypatch.setattr(upload_module, "trigger_media_scan", lambda *_a, **_k: None)
    monkeypatch.setattr(upload_module, "scan_wait_for", lambda _path: 0)
    monkeypatch.setattr(upload_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(upload_module, "restart_tiktok_package", lambda *_a, **_k: None)
    monkeypatch.setattr(upload_module, "wait_for_tiktok_home", lambda *_a, **_k: True)
    monkeypatch.setattr(upload_module, "dismiss_post_popups", lambda *_a, **_k: None)
    monkeypatch.setattr(upload_module, "handle_permission_dialog", lambda *_a, **_k: False)
    monkeypatch.setattr(upload_module, "tap_create_button", lambda *_a, **_k: True)
    monkeypatch.setattr(upload_module, "tap_upload_button", lambda *_a, **_k: True)
    monkeypatch.setattr(upload_module, "ensure_gallery_picker_open", lambda *_a, **_k: True)
    monkeypatch.setattr(upload_module, "select_first_gallery_item", lambda *_a, **_k: True)
    monkeypatch.setattr(upload_module, "advance_to_post_screen", lambda *_a, **_k: True)
    monkeypatch.setattr(upload_module.TikTokUploadWorkflow, "_fill_caption", lambda *_a: False)
    monkeypatch.setattr(upload_module, "tap_element", lambda *_a, **_k: post_taps.append(True) or True)
    monkeypatch.setattr(upload_module, "delete_pushed_media", lambda *_a, **_k: True)

    result = upload_module.TikTokUploadWorkflow(object(), "device-1").execute(
        str(local_path), caption="required", hashtags=["verified"],
        package_name="com.zhiliaoapp.musically",
    )

    assert result["error_type"] == "caption_fill_failed"
    assert post_taps == []
