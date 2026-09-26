"""Every publish reclaims the media earlier runs pushed, before it pushes its own.

`purge_pushed_media` was called by the Instagram post only: a phone that published on TikTok or
YouTube alone kept every medium it was sent, legacy `TAKTIK_` / `YT_` names included. Each publish
now runs the same purge, at the same moment (before the push, never after: the app may still be
reading the file it was handed).
"""

import types

import pytest


def _recorder(monkeypatch, module, push_name):
    calls = []

    def purge(device_id, **_kwargs):
        calls.append(("purge", device_id))
        return 0

    def push(*args, **kwargs):
        calls.append(("push", kwargs.get("device_id", args[0] if args else None)))
        return None                                   # a failed push ends the run right there

    monkeypatch.setattr(module, "purge_pushed_media", purge, raising=False)
    monkeypatch.setattr(module, push_name, push)
    return calls


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"\0" * 16)
    return str(path)


def test_the_instagram_post_purges_before_it_pushes(monkeypatch, clip):
    from taktik.core.social_media.instagram.workflows.publish import post_workflow as module

    calls = _recorder(monkeypatch, module, "push_media")
    wf = object.__new__(module.InstagramPostWorkflow)
    wf.device_id = "dev"
    wf._log = lambda *_a: None
    wf._status = lambda *_a: None

    assert wf._push_all([clip]) is False
    assert calls == [("purge", "dev"), ("push", "dev")]


def test_the_tiktok_upload_purges_before_it_pushes(monkeypatch, clip):
    from taktik.core.social_media.tiktok.workflows.publish import upload_workflow as module

    calls = _recorder(monkeypatch, module, "push_media")
    result = module.TikTokUploadWorkflow(types.SimpleNamespace(), "dev").execute(clip)

    assert result["success"] is False and result["error_type"] == "push_failed"
    assert calls == [("purge", "dev"), ("push", "dev")]


def test_the_youtube_upload_purges_before_it_pushes(monkeypatch, clip):
    from taktik.core.social_media.youtube.workflows.publish import upload_workflow as module

    calls = _recorder(monkeypatch, module, "push_and_scan")
    result = module.YouTubeUploadWorkflow(types.SimpleNamespace(), "dev").execute(clip)

    assert result["success"] is False
    assert calls == [("purge", "dev"), ("push", "dev")]


@pytest.mark.parametrize("module_path, push_name, cls", [
    ("taktik.core.social_media.tiktok.workflows.publish.upload_workflow", "push_media",
     "TikTokUploadWorkflow"),
    ("taktik.core.social_media.youtube.workflows.publish.upload_workflow", "push_and_scan",
     "YouTubeUploadWorkflow"),
])
def test_a_purge_that_fails_does_not_stop_the_publish(monkeypatch, clip, module_path, push_name, cls):
    import importlib

    module = importlib.import_module(module_path)
    calls = _recorder(monkeypatch, module, push_name)

    def broken_purge(*_a, **_k):
        calls.append(("purge", "raised"))
        raise OSError("registry unreadable")

    monkeypatch.setattr(module, "purge_pushed_media", broken_purge)
    getattr(module, cls)(types.SimpleNamespace(), "dev").execute(clip)

    assert calls == [("purge", "raised"), ("push", "dev")]
