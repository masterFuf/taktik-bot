"""A bridge that cannot import a module says so with the bot's code, `PYTHON_IMPORT_ERROR`.

The cause is the same wherever the import ran: the bridge's own module (the launcher's crash hook),
a run's lazy import that the bridge catches (the TikTok and Threads runners, the debug bridge), one
that reaches the entry (`run_bridge_main`), or one that lands in a run's catch-all `except Exception`
(the Instagram automation, the TikTok unfollow). The bridges used to write "Import error: ..." with
no code and no traceback, which nothing classified: the operator read a generic crash. Now one
reading of the exception (`crash_hooks.exception_event`) gives the code, the words and the traceback,
and one function sends it (`entrypoint.send_import_error`).
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bridges.common import crash_hooks, entrypoint
from unit.paths import CORE

#: Runs the real launcher with one module made unimportable, as a broken install would leave it.
RUNNER = CORE / "tests" / "unit" / "bridge_without_module.py"


def _run_bridge_without(tmp_path: Path, bridge: str, config: dict, blocked: str):
    """The bridge as the app runs it (the launcher, its config file), with `blocked` missing."""
    config_path = tmp_path / f"{bridge}.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP", "USERPROFILE", "APPDATA",
                                            "PYTHONUSERBASE") if key in os.environ}
    env.update({"PYTHONIOENCODING": "utf-8", "TAKTIK_DB_PATH": str(tmp_path / "taktik-data.db")})
    proc = subprocess.run(
        [sys.executable, str(RUNNER), blocked, bridge, str(config_path)],
        cwd=str(CORE), env=env, capture_output=True, timeout=180,
    )
    lines = [json.loads(line) for line in proc.stdout.decode("utf-8").splitlines() if line.startswith("{")]
    return proc, [line for line in lines if line.get("type") == "error"]


def _assert_said_with_the_code(proc, errors, blocked: str, exit_code: int = 1) -> None:
    stderr = proc.stderr.decode("utf-8", "replace")[-3000:]
    assert proc.returncode == exit_code, stderr
    assert errors, f"no error line; stderr: {stderr}"
    last = errors[-1]
    assert last.get("error_code") == "PYTHON_IMPORT_ERROR", (errors, stderr)
    assert blocked in last["error"]
    assert last["traceback"].rstrip().endswith(f"ModuleNotFoundError: No module named '{blocked}'")


def test_a_run_whose_lazy_import_fails_says_it_with_the_bots_code(tmp_path):
    """The TikTok scraping runner imports its workflow when the run starts and catches the failure."""
    blocked = "taktik.core.social_media.tiktok.workflows.scraping.agent_handler"
    proc, errors = _run_bridge_without(tmp_path, "tiktok_scraping_bridge", {"deviceId": "gate-phone"}, blocked)

    _assert_said_with_the_code(proc, errors, blocked)
    assert not (tmp_path / "taktik-data.db").exists()


def test_a_bridge_whose_own_module_does_not_import_says_it_with_the_bots_code(tmp_path):
    """The launcher imports the bridge after its crash hook: the hook names the cause."""
    blocked = "bridges.tiktok.scraping.workflow"
    proc, errors = _run_bridge_without(tmp_path, "tiktok_scraping_bridge", {"deviceId": "gate-phone"}, blocked)

    _assert_said_with_the_code(proc, errors, blocked)
    assert errors[-1]["bridge"] == "tiktok_scraping_bridge"


@pytest.mark.parametrize("bridge, config, blocked, exit_code", [
    pytest.param("desktop_bridge", {"deviceId": "gate-phone", "workflowType": "target", "target": "gate-target"},
                 "taktik.core.social_media.instagram.workflows.automation.agent_handler", 5,
                 id="instagram-automation"),
    pytest.param("tiktok_unfollow_bridge", {"device_id": "gate-phone", "config": {}},
                 "taktik.core.social_media.tiktok.workflows.automation.unfollow.payload", 1,
                 id="tiktok-unfollow"),
])
def test_a_run_that_catches_every_exception_still_says_an_import_with_the_bots_code(
        tmp_path, bridge, config, blocked, exit_code):
    """The Instagram automation said "Workflow error: ..." under `WORKFLOW_ERROR`, the TikTok unfollow
    "Startup error: ..." with no code: their `except Exception` took the import for a workflow failure."""
    proc, errors = _run_bridge_without(tmp_path, bridge, config, blocked)

    _assert_said_with_the_code(proc, errors, blocked, exit_code)
    assert not (tmp_path / "taktik-data.db").exists()


class _Bridge:
    def __init__(self, config, *, fail_in: str):
        if fail_in == "init":
            raise ModuleNotFoundError("No module named 'uiautomator2'", name="uiautomator2")
        self.fail_in = fail_in

    def run(self) -> int:
        raise ImportError("cannot import name 'run_workflow' from 'taktik.core.social_media'")


@pytest.mark.parametrize("fail_in, words", [
    pytest.param("init", "ModuleNotFoundError: No module named 'uiautomator2'", id="building-the-bridge"),
    pytest.param("run", "ImportError: cannot import name 'run_workflow'", id="its-run"),
])
def test_the_entry_says_an_import_that_reaches_it_with_the_bots_code(tmp_path, monkeypatch, fail_in, words):
    """`run_bridge_main` reported it as "Bridge crashed: ..." in the bridge's own shape, with no code."""
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["bridge", str(config_path)])
    sent = []
    monkeypatch.setattr(entrypoint._ipc, "send", lambda msg_type, **data: sent.append({"type": msg_type, **data}))
    reported = []

    with pytest.raises(SystemExit) as exit_:
        entrypoint.run_bridge_main(lambda config: _Bridge(config, fail_in=fail_in),
                                   report_error=lambda message, reason: reported.append(reason))

    assert exit_.value.code == 1
    assert reported == []
    [event] = sent
    assert event["type"] == "error" and event["error_code"] == "PYTHON_IMPORT_ERROR"
    assert event["error"].startswith(words) and words in event["traceback"]


def test_the_crash_hook_names_an_import_and_nothing_else_by_it():
    def raised(exc):
        try:
            raise exc
        except BaseException:
            return sys.exc_info()

    assert crash_hooks.exception_event(*raised(ModuleNotFoundError("No module named 'x'")))["error_code"] \
        == "PYTHON_IMPORT_ERROR"
    assert crash_hooks.exception_event(*raised(RuntimeError("boom")))["error_code"] == "UNHANDLED_EXCEPTION"


def _handlers_that_word_an_import_error(path: Path):
    """The `except ImportError` blocks of `path` that send an error line of their own."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or node.type is None:
            continue
        caught = [node.type] if not isinstance(node.type, ast.Tuple) else list(node.type.elts)
        if not any(isinstance(item, ast.Name) and item.id in ("ImportError", "ModuleNotFoundError")
                   for item in caught):
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name == "send_error" or (name == "error" and "ipc" in ast.unparse(func).lower()):
                yield f"{path.relative_to(CORE).as_posix()}:{node.lineno}"


def test_no_bridge_words_an_import_error_of_its_own():
    """One way to say it: a bridge that catches an import says it by `send_import_error`, so its line
    carries the code and the traceback. A copied "Import error: ..." block is red."""
    offenders = [where for path in sorted((CORE / "bridges").rglob("*.py"))
                 for where in _handlers_that_word_an_import_error(path)]

    assert offenders == []
