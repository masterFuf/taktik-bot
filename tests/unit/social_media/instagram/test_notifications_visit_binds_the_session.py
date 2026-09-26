"""The suggestions visit binds its per-profile pipeline to the pass's account AND session.

The bridge used to build that pipeline through a method that took no `session_id`: every visit
raised a TypeError before the first profile, caught as `stop_reason: error`. The launcher now
calls the core constructor, which takes it; the sequence test's fake accepted any keyword, so it
could not see the difference.
"""
import inspect

from taktik.core.social_media.instagram.workflows.management.notifications import commands
from taktik.core.social_media.instagram.workflows.management.notifications.profile_pipeline import (
    build_notifications_profile_pipeline,
)


class _Workflow:
    profile_pipeline = None

    def visit_suggestions(self, *, max_profiles):
        return {"visited": 1, "processed": 1, "follows": 0, "filtered": 1, "errors": 0,
                "profiles": ["someone"], "stop_reason": "budget"}


def test_the_core_builder_takes_the_session_the_visit_passes():
    inspect.signature(build_notifications_profile_pipeline).bind(object(), account_id=7, session_id=3)


def test_the_visit_hands_the_account_and_the_session_to_the_pipeline(monkeypatch):
    built = []
    monkeypatch.setattr(commands, "build_notifications_profile_pipeline",
                        lambda device, **kwargs: built.append(kwargs) or "pipeline")
    host = commands.NotificationsHost(connect=lambda restart: None, emit=lambda payload: None)
    runtime = type("Runtime", (), {"device": object()})()
    workflow = _Workflow()
    result = {"visited": 0, "processed": 0, "follows": 0, "filtered": 0, "errors": 0, "profiles": []}

    commands._run_visit_with_session(host, runtime, workflow, result, account_id=7, session_id=3,
                                     max_profiles=1)

    assert built == [{"account_id": 7, "session_id": 3}]
    assert workflow.profile_pipeline == "pipeline"
    assert result["visited"] == 1
