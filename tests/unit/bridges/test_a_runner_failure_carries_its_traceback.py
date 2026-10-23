"""A workflow runner that an exception ends says it with its words and the traceback.

The TikTok runners catch their run's failure and return False (exit 1). They wrote "<Workflow>
error: ..." with `logger.error`: no traceback in the line nor on stderr, so a TikTok crash report
had none. The Threads runners sent their code and logged the traceback, but not on the line. They
now say it by `entrypoint.send_run_error`: the same words, the same code (none for TikTok), the
traceback on the line and on stderr.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

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


def _instagram_account(device_id):
    from bridges.instagram.account.session import AccountSessionLifecycleMixin

    return AccountSessionLifecycleMixin._prepare_runtime_session(SimpleNamespace(device_id=device_id))


def _instagram_task(device_id):
    from bridges.instagram.tasks.bridge import TaskBridge

    return TaskBridge._prepare_runtime_session(SimpleNamespace(device_id=device_id))


def _tiktok_account(device_id):
    from bridges.tiktok.account.account_session import TikTokAccountSessionMixin

    return TikTokAccountSessionMixin._setup_database(SimpleNamespace(device_id=device_id))


def _instagram_automation(device_id):
    from bridges.instagram.automation.session import InstagramDesktopRuntime

    return InstagramDesktopRuntime(device_id=None, package_name=None, network_reset={}).setup_database()


@pytest.mark.parametrize("prepare, failed, code", [
    pytest.param(_instagram_account, None, None, id="instagram-account"),
    pytest.param(_instagram_task, None, None, id="instagram-task"),
    pytest.param(_tiktok_account, False, None, id="tiktok-account"),
    pytest.param(_instagram_automation, False, "DATABASE_SETUP_FAILED", id="instagram-automation"),
])
def test_a_database_that_does_not_open_is_said_with_the_traceback(monkeypatch, prepare, failed, code):
    """The bridges said "Database setup failed: ..." with no traceback anywhere but the automation's log."""
    lines = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **data: lines.append({"type": msg_type, **data}))

    def locked():
        raise RuntimeError("the base is locked")

    monkeypatch.setattr("taktik.core.database.configure_db_service", locked)

    assert prepare("gate-phone") is failed

    [error] = [line for line in lines if line["type"] == "error"]
    assert error["error"] == "Database setup failed: the base is locked"
    assert error.get("error_code") == code
    assert error["traceback"].rstrip().endswith("RuntimeError: the base is locked")


@pytest.mark.parametrize("raised, said", [
    pytest.param(RuntimeError("the router broke"), {"error": "Workflow error: the router broke"}, id="crash"),
    pytest.param(ModuleNotFoundError("No module named 'gate'", name="gate"),
                 {"error": "ModuleNotFoundError: No module named 'gate'", "error_code": "PYTHON_IMPORT_ERROR"},
                 id="import"),
])
def test_the_tiktok_dispatcher_says_what_its_runner_did_not_catch_and_still_stops_tiktok(
        tmp_path, monkeypatch, raised, said):
    """A runner that does not catch its own failure (notifications) ends in the dispatcher: its words
    with the traceback, an import with the bot's code. Run in the process: its cleanup stops TikTok
    over adb, which a test does not reach."""
    import sys

    from bridges.common import entrypoint
    from bridges.tiktok.automation import dispatcher

    config_path = tmp_path / "config.json"
    config_path.write_text('{"workflowType": "followers", "deviceId": "gate-phone"}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["tiktok_bridge", str(config_path)])
    lines = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **data: lines.append({"type": msg_type, **data}))
    stopped = []
    monkeypatch.setattr(dispatcher, "reset_network_if_enabled", lambda config, device_id: True)
    monkeypatch.setattr(dispatcher, "force_stop_tiktok", stopped.append)

    def broken_router(config):
        raise raised

    monkeypatch.setattr(dispatcher, "dispatch_tiktok_workflow", broken_router)

    with pytest.raises(SystemExit) as exit_:
        entrypoint.run_bridge_main(dispatcher.TikTokDispatcherBridge, usage="tiktok_bridge <config_path>")

    assert exit_.value.code == 1
    [error] = [line for line in lines if line["type"] == "error"]
    assert {key: error[key] for key in said} == said
    assert error["traceback"].rstrip().endswith(f"{type(raised).__name__}: {raised}")
    assert stopped == ["gate-phone"]
