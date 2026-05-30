from taktik.core.social_media.tiktok.workflows.publish import upload_workflow as upload_module


class _FakeNotifier:
    def __init__(self):
        self.calls = []

    def log(self, *args, **kwargs):
        self.calls.append(("log", args, kwargs))

    def status(self, *args, **kwargs):
        self.calls.append(("status", args, kwargs))


def test_tiktok_upload_workflow_uses_injected_notifier(monkeypatch, tmp_path):
    local_file = tmp_path / "video.mp4"
    local_file.write_bytes(b"video")

    monkeypatch.setattr(upload_module, "push_media", lambda device_id, local_path: None)

    notifier = _FakeNotifier()
    workflow = upload_module.TikTokUploadWorkflow(device=object(), device_id="device-1", notifier=notifier)

    result = workflow.execute(
        local_path=str(local_file),
        caption="caption",
        hashtags=["a", "b", "c", "d", "e", "f"],
    )

    assert result["error_type"] == "push_failed"
    assert any(call[0] == "log" for call in notifier.calls)
