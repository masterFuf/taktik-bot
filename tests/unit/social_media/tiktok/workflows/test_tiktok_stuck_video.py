"""A swipe that leaves the same video on screen: not watched or counted again, swiped once more.

On a Pixel 6a (TikTok 46.9.3) a flick sometimes left the video in place, and the run watched and
counted it again up to three times (6 counted for 4 seen).
"""

from types import SimpleNamespace

from taktik.core.social_media.tiktok.actions.business.workflows._internal.base_video_workflow import (
    BaseVideoWorkflow,
)
from taktik.core.social_media.tiktok.actions.business.workflows._internal.models import VideoWorkflowStats


class _Scroll:
    def __init__(self):
        self.swipes = 0

    def scroll_to_next_video(self):
        self.swipes += 1
        return True


def _workflow():
    wf = BaseVideoWorkflow.__new__(BaseVideoWorkflow)
    wf.logger = SimpleNamespace(warning=lambda *_: None, error=lambda *_: None, info=lambda *_: None)
    wf.scroll = _Scroll()
    wf.click = SimpleNamespace(close_system_popup=lambda: False)
    wf.device = SimpleNamespace(press=lambda *_: None)
    wf._handle_popups = lambda: False
    wf.stats = VideoWorkflowStats()
    wf._running = True
    wf.stop = lambda: setattr(wf, "_running", False)
    wf._last_video_signature = None
    wf._same_video_count = 0
    wf._stuck_recoveries = 0
    return wf


VIDEO = {"author": "someone", "like_count": "20,2 K", "description": "a caption"}


def test_the_same_video_again_is_swiped_not_processed(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    wf = _workflow()
    assert wf._handle_stuck_video(VIDEO) is False
    assert wf._handle_stuck_video(dict(VIDEO)) is True
    assert wf.scroll.swipes == 1


def test_another_video_by_the_same_author_is_a_new_video():
    wf = _workflow()
    assert wf._handle_stuck_video(VIDEO) is False
    assert wf._handle_stuck_video({**VIDEO, "description": "another caption"}) is False


def test_a_feed_that_no_longer_moves_stops_the_run(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    wf = _workflow()
    wf._handle_stuck_video(VIDEO)
    calls = 0
    while wf._running and calls < 50:
        wf._handle_stuck_video(dict(VIDEO))
        calls += 1
    assert not wf._running
    assert calls == 9


def test_a_live_preview_the_swipe_does_not_leave_ends_the_run(monkeypatch):
    """A LIVE has no author: the guard used to ignore it, and the run skipped it forever."""
    monkeypatch.setattr("time.sleep", lambda *_: None)
    wf = _workflow()
    live = {"author": None, "like_count": None, "description": None, "is_live": True}
    wf._handle_stuck_video(live)
    for _ in range(20):
        if not wf._running:
            break
        wf._handle_stuck_video(dict(live))
    assert not wf._running
