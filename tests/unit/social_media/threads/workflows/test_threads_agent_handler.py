import pytest

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowRegistry
from taktik.core.social_media.threads.workflows.agent_handler import (
    THREADS_AUTOMATION_WORKFLOW_IDS,
    build_threads_automation_handler,
    register_threads_automation_handlers,
)


class FakeStats:
    def __init__(self, marker):
        self.marker = marker

    def as_dict(self):
        return {"marker": self.marker}


def test_threads_target_handler_runs_search_runner_with_injected_startup():
    calls = []
    startup = ("manager", "device", "anchor")

    def search_runner(config, **kwargs):
        calls.append(("search", config, kwargs))
        return FakeStats("search")

    handler = build_threads_automation_handler(
        startup_provider=lambda invocation, payload: startup,
        search_runner=search_runner,
        feed_runner=lambda config, **kwargs: FakeStats("feed"),
    )

    result = handler(
        WorkflowInvocation(
            platform="threads",
            workflow_id="threads.automation.target",
            params={
                "searchQuery": "creators",
                "maxProfiles": 4,
                "actionProbabilities": {"follow": 90, "like": 10},
                "filters": {"minFollowers": 100, "bioKeywordsInclude": ["ai"]},
            },
        ),
        {},
    )

    assert result == {"success": True, "stats": {"marker": "search"}}
    assert calls[0][0] == "search"
    assert calls[0][1].search_query == "creators"
    assert calls[0][1].max_profiles == 4
    assert calls[0][1].actions.follow == 90
    assert calls[0][1].filters.min_followers == 100
    assert calls[0][2]["startup"] is startup


def test_threads_feed_handler_runs_feed_runner():
    calls = []
    startup = ("manager", "device", "anchor")

    def feed_runner(config, **kwargs):
        calls.append((config, kwargs))
        return FakeStats("feed")

    handler = build_threads_automation_handler(
        startup_provider=lambda invocation, payload: startup,
        search_runner=lambda config, **kwargs: FakeStats("search"),
        feed_runner=feed_runner,
    )

    result = handler(
        WorkflowInvocation(
            platform="threads",
            workflow_id="threads.automation.feed",
            params={"maxFollows": 3},
        ),
        {},
    )

    assert result == {"success": True, "stats": {"marker": "feed"}}
    assert calls[0][0].max_profiles == 3
    assert calls[0][1]["startup"] is startup


def test_threads_handler_requires_startup_and_target():
    no_startup_handler = build_threads_automation_handler(
        startup_provider=lambda invocation, payload: None,
    )

    with pytest.raises(ValueError, match="requires injected startup"):
        no_startup_handler(
            WorkflowInvocation(
                platform="threads",
                workflow_id="threads.automation.feed",
                params={},
            ),
            {},
        )

    handler = build_threads_automation_handler(
        startup_provider=lambda invocation, payload: ("manager", "device", "anchor"),
    )

    with pytest.raises(ValueError, match="requires searchQuery"):
        handler(
            WorkflowInvocation(
                platform="threads",
                workflow_id="threads.automation.follow",
                params={},
            ),
            {},
        )


def test_register_threads_handlers_registers_manifest_ids():
    registry = WorkflowRegistry()

    register_threads_automation_handlers(
        registry,
        startup_provider=lambda invocation, payload: ("manager", "device", "anchor"),
    )

    assert set(registry.workflow_ids()) >= set(THREADS_AUTOMATION_WORKFLOW_IDS)
