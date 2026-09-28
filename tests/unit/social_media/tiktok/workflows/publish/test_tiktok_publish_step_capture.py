"""A failed step capture of the TikTok publication is said, and does not stop the publication
(decision D10 of 2026-09-27).

`_capture` hands each phase to the host's hook (the bridge saves a screenshot and a dump for the
Lab). A hook that failed was dropped without a word (`except Exception: pass`): a publication
with no capture left no trace of why. It is logged now, and the publication goes on.
"""

from __future__ import annotations

from taktik.core.social_media.tiktok.workflows.publish import upload_workflow
from taktik.core.social_media.tiktok.workflows.publish.upload_workflow import TikTokUploadWorkflow


class _Notifier:
    def __init__(self):
        self.logs = []

    def log(self, level, message):
        self.logs.append((level, message))

    def status(self, *args, **kwargs):
        pass


def _capture_with(hook):
    notifier = _Notifier()
    workflow = TikTokUploadWorkflow(device=None, device_id="emulator-5554", notifier=notifier, step_hook=hook)
    token = upload_workflow._CURRENT_NOTIFIER.set(notifier)
    try:
        workflow._capture("03_gallery")
    finally:
        upload_workflow._CURRENT_NOTIFIER.reset(token)
    return notifier.logs


def test_a_failed_capture_is_logged_and_the_publication_goes_on():
    def broken(phase):
        raise OSError("disk full")

    logs = _capture_with(broken)

    assert logs == [("warning", "Step capture 03_gallery failed: disk full")]


def test_a_capture_that_works_says_nothing():
    phases = []

    assert _capture_with(phases.append) == []
    assert phases == ["03_gallery"]
