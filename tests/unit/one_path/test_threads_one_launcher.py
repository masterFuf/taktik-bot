"""Threads: the bridge and the CLI handler reach the engine through the same launcher.

The bridge used to read its own config and call `run_search_and_interact` /
`run_feed_and_interact` itself, next to a handler that read the payload again its own way.
Both now call `run_threads_search` / `run_threads_feed`, which read the payload once.
"""
from __future__ import annotations

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowRegistry
from taktik.core.social_media.threads.workflows import agent_handler
from taktik.core.social_media.threads.workflows.search_and_interact import InteractStats

DEVICE_ID = "emulator-5554"
PAGE = {
    "deviceId": DEVICE_ID,
    "targets": ["@creator_one"],
    "maxFollows": 4,
    "actionProbabilities": {"follow": 90, "like": 10},
    "filters": {"minFollowers": 100, "bioKeywordsInclude": ["ai"]},
}


def _recording_runner(calls, stats):
    def runner(config, **kwargs):
        calls.append((config, kwargs["startup"]))
        return stats

    return runner


def _silence_bridge(monkeypatch, *modules):
    events: list[tuple] = []
    for module in modules:
        for name in ("send_status", "send_error", "send_log", "send_threads_stats"):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, lambda *a, _n=name, **k: events.append((_n, a, k)))
    return events


def _cli(workflow_id, params, **runners):
    registry = WorkflowRegistry()
    agent_handler.register_threads_automation_handlers(registry, **runners)
    invocation = WorkflowInvocation(platform="threads", workflow_id=workflow_id, params=params)
    return registry.resolve(workflow_id)(invocation, {})


def test_threads_target_is_the_same_config_from_the_bridge_and_the_cli(monkeypatch):
    from bridges.threads.workflows.runtime import events as bridge_events
    from bridges.threads.workflows.runtime import search as bridge_search

    bridge_calls, cli_calls = [], []
    stats = InteractStats(profiles_visited=2, follows=1)
    monkeypatch.setitem(agent_handler.run_threads_search.__kwdefaults__, "search_runner",
                        _recording_runner(bridge_calls, stats))
    emitted = _silence_bridge(monkeypatch, bridge_events, bridge_search)

    assert bridge_search.run_follow(dict(PAGE)) is True
    result = _cli(agent_handler.THREADS_TARGET_WORKFLOW_ID, dict(PAGE),
                  search_runner=_recording_runner(cli_calls, stats))

    assert result["success"] is True
    assert bridge_calls == cli_calls
    config, startup = bridge_calls[0]
    assert (config.device_id, config.search_query, config.max_profiles) == (DEVICE_ID, "creator_one", 4)
    assert (config.actions.follow, config.filters.min_followers) == (90, 100)
    assert startup is None
    assert [name for name, *_ in emitted] == ["send_log", "send_status", "send_threads_stats", "send_status"]


def test_threads_feed_is_the_same_config_from_the_bridge_and_the_cli(monkeypatch):
    from bridges.threads.workflows.runtime import events as bridge_events
    from bridges.threads.workflows.runtime import feed as bridge_feed

    bridge_calls, cli_calls = [], []
    stats = InteractStats(errors=1)
    monkeypatch.setitem(agent_handler.run_threads_feed.__kwdefaults__, "feed_runner",
                        _recording_runner(bridge_calls, stats))
    _silence_bridge(monkeypatch, bridge_events, bridge_feed)

    assert bridge_feed.run_feed(dict(PAGE)) is False
    result = _cli(agent_handler.THREADS_FEED_WORKFLOW_ID, dict(PAGE),
                  feed_runner=_recording_runner(cli_calls, stats))

    assert result["success"] is False
    assert bridge_calls == cli_calls
    assert bridge_calls[0][0].max_profiles == 4


def test_threads_bridge_reports_a_missing_query_with_its_code(monkeypatch):
    from bridges.threads.workflows.runtime import events as bridge_events
    from bridges.threads.workflows.runtime import search as bridge_search

    emitted = _silence_bridge(monkeypatch, bridge_events, bridge_search)

    assert bridge_search.run_follow({"deviceId": DEVICE_ID, "targets": []}) is False
    assert emitted == [("send_error", ("No search query provided",), {"error_code": "threads.no_query"})]
