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


def test_a_feed_that_no_longer_moves_says_why_the_run_ended(monkeypatch):
    """The run used to end like a normal one: nothing told the operator the feed had frozen."""
    monkeypatch.setattr("time.sleep", lambda *_: None)
    wf = _workflow()
    wf._handle_stuck_video(VIDEO)
    while wf._running:
        wf._handle_stuck_video(dict(VIDEO))
    assert wf.stats.completion_reason == "feed_stuck"
    assert wf.stats.to_dict()["completion_reason"] == "feed_stuck"


def test_a_recovery_that_works_leaves_no_motive(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    wf = _workflow()
    wf._handle_stuck_video(VIDEO)
    for _ in range(3):
        wf._handle_stuck_video(dict(VIDEO))
    wf._handle_stuck_video({**VIDEO, "description": "the next video"})
    assert wf._running
    assert wf.stats.completion_reason == ""


def test_the_final_status_carries_the_motive_to_the_desktop(monkeypatch):
    from bridges.tiktok.runtime import video_callbacks

    sent = []
    monkeypatch.setattr(video_callbacks, "send_stats", lambda **_: None)
    monkeypatch.setattr(video_callbacks, "send_status", lambda status, message="": sent.append(
        {"type": "status", "status": status, "message": message}))
    monkeypatch.setattr(video_callbacks, "send_message", lambda msg_type, **kw: sent.append({"type": msg_type, **kw}))

    stuck = VideoWorkflowStats(completion_reason="feed_stuck")
    video_callbacks.send_final_video_stats(stuck, "For You workflow")
    assert sent[-1]["type"] == "status"
    assert sent[-1]["status"] == "completed"
    assert sent[-1]["completion_reason"] == "feed_stuck"

    video_callbacks.send_final_video_stats(VideoWorkflowStats(), "For You workflow")
    assert sent[-1] == {"type": "status", "status": "completed",
                        "message": "For You workflow completed: 0 videos, 0 likes, 0 follows"}


def test_a_search_run_reports_the_motive_of_its_last_query(monkeypatch):
    from taktik.core.social_media.tiktok.actions.business.workflows.search import agent_handler

    monkeypatch.setattr(agent_handler, "_return_home", lambda _device: None)

    def motive_of_a_run(motives):
        motives = iter(motives)

        class _Workflow:
            def __init__(self, *_args, **_kwargs):
                pass

            def run(self):
                return VideoWorkflowStats(videos_watched=1, completion_reason=next(motives))

        finished = []
        agent_handler.run_tiktok_search(
            {"hashtags": ["a", "b"], "maxVideos": 10},
            workflow_type="hashtag",
            device=object(),
            workflow_factory=_Workflow,
            query_hook=lambda *_: None,
            on_finished=finished.append,
        )
        return finished[0].completion_reason

    assert motive_of_a_run(["", "feed_stuck"]) == "feed_stuck"
    # The next query moved: the run did not end on a frozen feed.
    assert motive_of_a_run(["feed_stuck", ""]) == ""


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
