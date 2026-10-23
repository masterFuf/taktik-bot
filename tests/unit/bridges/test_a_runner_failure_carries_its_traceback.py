"""A workflow runner that an exception ends says it with its words and the traceback.

The TikTok runners catch their run's failure and return False (exit 1). They wrote "<Workflow>
error: ..." with `logger.error`: no traceback in the line nor on stderr, so a TikTok crash report
had none. The Threads runners sent their code and logged the traceback, but not on the line. They
now say it by `entrypoint.send_run_error`: the same words, the same code (none for TikTok), the
traceback on the line and on stderr.
"""

from __future__ import annotations

import importlib

import pytest

from bridges.common.ipc import IPC

_WORKFLOWS = "taktik.core.social_media.tiktok.workflows"


_THREADS = "taktik.core.social_media.threads.workflows.agent_handler"


@pytest.mark.parametrize("runner, launcher, words, code", [
    pytest.param("bridges.tiktok.automation.for_you:run_for_you_workflow",
                 f"{_WORKFLOWS}.automation.for_you.agent_handler:run_tiktok_for_you",
                 "Workflow error", None, id="for-you"),
    pytest.param("bridges.tiktok.automation.inbox.dm_read:run_dm_read_workflow",
                 f"{_WORKFLOWS}.dm.agent_handler:run_tiktok_dm_read", "DM workflow error", None,
                 id="dm-read"),
    pytest.param("bridges.tiktok.scraping.workflow:run_scraping_workflow",
                 f"{_WORKFLOWS}.scraping.agent_handler:run_tiktok_scraping", "Scraping workflow error", None,
                 id="scraping"),
    pytest.param("bridges.tiktok.unfollow.unfollow:run_unfollow_workflow",
                 f"{_WORKFLOWS}.automation.unfollow.agent_handler:run_tiktok_unfollow",
                 "Unfollow workflow error", None, id="unfollow"),
    pytest.param("bridges.threads.automation.feed:run_feed", f"{_THREADS}:run_threads_feed",
                 "Threads feed workflow crashed", "threads.workflow_crash", id="threads-feed"),
    pytest.param("bridges.threads.automation.search:run_follow", f"{_THREADS}:run_threads_search",
                 "Threads search workflow crashed", "threads.workflow_crash", id="threads-search"),
])
def test_a_runner_that_fails_says_its_words_with_the_traceback(monkeypatch, runner, launcher, words, code):
    lines = []
    # On the class: every IPC of the process (the entry's, the bridge's) prints through it.
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **data: lines.append({"type": msg_type, **data}))

    def the_list_did_not_open(*args, **kwargs):
        raise RuntimeError("the list did not open")

    launcher_module, launcher_name = launcher.split(":")
    monkeypatch.setattr(importlib.import_module(launcher_module), launcher_name, the_list_did_not_open)
    runner_module, runner_name = runner.split(":")
    run = getattr(importlib.import_module(runner_module), runner_name)

    assert run({"deviceId": "gate-phone"}) is False

    [error] = [line for line in lines if line["type"] == "error"]
    assert error["error"] == f"{words}: the list did not open"
    assert error.get("error_code") == code
    assert error["traceback"].rstrip().endswith("RuntimeError: the list did not open")
