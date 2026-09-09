from taktik.core.social_media.tiktok.workflows.publish import upload_workflow as upload_module


def test_temp_cleanup_policy_covers_safe_failure_success_and_inflight_post():
    policy = upload_module._should_delete_temp_media
    assert policy(post_started=False, publish_confirmed=False)
    assert policy(post_started=True, publish_confirmed=True)
    assert not policy(post_started=True, publish_confirmed=False)


def test_safe_pre_post_failure_deletes_only_the_pushed_copy(monkeypatch, tmp_path):
    local_path = tmp_path / "source.mp4"
    local_path.write_bytes(b"video")
    remote_path = "/sdcard/DCIM/Camera/TAKTIK_20260905_120000.mp4"
    calls = []

    monkeypatch.setattr(upload_module, "purge_pushed_media", lambda *a, **k: calls.append("purge") or 0)
    monkeypatch.setattr(upload_module, "push_media", lambda *a, **k: remote_path)
    monkeypatch.setattr(upload_module, "trigger_media_scan", lambda *a, **k: None)
    monkeypatch.setattr(upload_module, "scan_wait_for", lambda _path: 0)
    monkeypatch.setattr(upload_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(upload_module, "restart_tiktok_package", lambda *a, **k: None)
    monkeypatch.setattr(upload_module, "wait_for_tiktok_home", lambda *a, **k: True)
    monkeypatch.setattr(upload_module, "dismiss_post_popups", lambda *a, **k: None)
    monkeypatch.setattr(upload_module, "tap_create_button", lambda *a, **k: False)
    monkeypatch.setattr(
        upload_module,
        "delete_pushed_media",
        lambda device_id, path, **kwargs: calls.append((device_id, path)) or True,
    )

    result = upload_module.TikTokUploadWorkflow(object(), "device-1").execute(
        str(local_path), package_name="com.zhiliaoapp.musically"
    )

    assert result["error_type"] == "create_btn_not_found"
    assert calls == ["purge", ("device-1", remote_path)]
    assert local_path.exists()
