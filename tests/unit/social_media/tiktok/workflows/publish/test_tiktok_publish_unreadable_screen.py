"""While TikTok commits a publication, an unreadable screen is not a badge that went away
(decision D11 of 2026-09-27).

The progress reader answered None both when no badge was on screen and when the screen could not
be dumped; the wait loop took both for "the badge disappeared", settled, and declared the
publication committed. An unreadable screen proves nothing: the loop now waits it out, and a
publication whose screen stays unreadable ends on the timeout, not as a success.
"""

from __future__ import annotations

from taktik.core.social_media.tiktok.services.publish.commit import (
    PublishCommitCallbacks,
    wait_for_publish_commit,
)
from taktik.core.social_media.tiktok.services.publish.progress import (
    PublishProgress,
    read_publish_progress,
)


class _Clock:
    def __init__(self):
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class _UnreadableDevice:
    def dump_hierarchy(self, compressed=False):
        raise RuntimeError("uiautomator2 server gone")


def _wait(readings, *, on_post_screen=False, success=False, timeout=30.0):
    clock = _Clock()
    logs = []
    sequence = list(readings)

    def read():
        return sequence.pop(0) if len(sequence) > 1 else sequence[0]

    callbacks = PublishCommitCallbacks(
        handle_publish_confirmation=lambda: False,
        dismiss_popups=lambda: None,
        read_progress=read,
        is_on_post_screen=lambda: on_post_screen,
        has_success_indicator=lambda: success,
    )
    committed = wait_for_publish_commit(
        callbacks, timeout=timeout, min_grace=2.0, settle_after_progress_gone=1.0,
        clock=clock.time, sleep=clock.sleep, log=lambda level, message: logs.append((level, message)),
    )
    return committed, logs


def test_the_reader_tells_an_unreadable_screen_from_no_badge():
    reading = read_publish_progress(_UnreadableDevice(), log=lambda *_: None)

    assert reading == PublishProgress(percent=None, readable=False)
    assert PublishProgress() == PublishProgress(percent=None, readable=True)


def test_an_unreadable_screen_after_the_badge_is_no_commit():
    committed, logs = _wait([PublishProgress(60), PublishProgress(readable=False)])

    assert committed is False
    assert not any("badge disappeared" in message for _, message in logs)
    assert any("unreadable" in message for level, message in logs if level == "warning")


def test_the_badge_that_goes_away_still_settles_into_a_commit():
    committed, logs = _wait([PublishProgress(60), PublishProgress(90), PublishProgress()])

    assert committed is True
    assert any("badge disappeared" in message for _, message in logs)


def test_a_screen_readable_again_resumes_the_wait():
    readings = [PublishProgress(60), PublishProgress(readable=False), PublishProgress(readable=False),
                PublishProgress()]

    committed, _ = _wait(readings)

    assert committed is True


def test_the_lab_reads_the_badge_with_the_same_reader():
    from types import SimpleNamespace

    from bridges.tools.lab.actions.tiktok import ACTION_REGISTRY, register_actions

    register_actions()
    result = ACTION_REGISTRY["tt.publish.read_progress"](SimpleNamespace(device=SimpleNamespace(device=_UnreadableDevice())), {})

    assert result["success"] is False
    assert result["details"] == {"readable": False, "percent": None}
