"""After a stop, the hashtag's walk of a post's likers or commenters leaves their sheet on screen.

Kevin's rule of 2026-11-16: once the run is asked to stop, no gesture. The walk closed its sheet in
its `finally` whatever happened; the plan's loop reads the latch right after the walk, before any other
gesture, so nothing lands on the wrong screen when the sheet stays open.

The phone is played by doubles that write down the gestures asked of it: no screen is read here.
"""

import types

import pytest

import taktik.core.social_media.instagram.workflows.automation.hashtag.workflow as hashtag_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.base.stats import create_workflow_stats
from taktik.core.social_media.instagram.workflows.automation.hashtag.workflow import HashtagBusiness

_QUIET = types.SimpleNamespace(**{level: (lambda *a, **k: None)
                                   for level in ("debug", "info", "success", "warning", "error")})


def _hashtag(gestures, *, stop_in_the_walk):
    workflow = object.__new__(HashtagBusiness)
    workflow.logger = _QUIET
    workflow._open_likers_popup = lambda is_reel: gestures.append("open:likers") or True
    workflow._open_comments_view = lambda: gestures.append("open:commenters") or True
    workflow._close_likers_popup = lambda: gestures.append("close:likers")
    workflow._close_comments_view = lambda: gestures.append("close:commenters")

    def walk(stats, **_kw):
        if stop_in_the_walk:
            run_halt.demander_arret(run_halt.NETWORK_LOST, "the network watch lost the phone")

    workflow._interact_with_likers_list = walk
    return workflow


@pytest.mark.parametrize("mode", ["likers", "commenters"])
def test_a_stop_during_the_walk_leaves_the_sheet_on_screen(mode, monkeypatch):
    monkeypatch.setattr(hashtag_module, "resolve_list_source", lambda workflow, mode: None)
    gestures = []
    workflow = _hashtag(gestures, stop_in_the_walk=True)

    workflow._walk_post_people("travel", mode, 5, {}, create_workflow_stats("hashtag"), False)

    assert gestures == [f"open:{mode}"]


@pytest.mark.parametrize("mode", ["likers", "commenters"])
def test_without_a_stop_the_walk_closes_its_sheet(mode, monkeypatch):
    monkeypatch.setattr(hashtag_module, "resolve_list_source", lambda workflow, mode: None)
    gestures = []
    workflow = _hashtag(gestures, stop_in_the_walk=False)

    workflow._walk_post_people("travel", mode, 5, {}, create_workflow_stats("hashtag"), False)

    assert gestures == [f"open:{mode}", f"close:{mode}"]


def test_a_stop_during_the_likers_walk_opens_no_commenters_sheet(monkeypatch):
    """The plan walks the likers then the commenters of the post: after a stop in the first walk,
    the second sheet would be opened over the first one, which stays on screen."""
    monkeypatch.setattr(hashtag_module, "resolve_list_source", lambda workflow, mode: None)
    gestures = []
    workflow = _hashtag(gestures, stop_in_the_walk=True)
    plan = types.SimpleNamespace(engage_posts=False, walk_likers=True, max_likers_per_post=5,
                                 walk_commenters=True, max_commenters_per_post=2)

    workflow._engage_one_post("travel", plan, {}, create_workflow_stats("hashtag"), False, "post_author")

    assert gestures == ["open:likers"]
