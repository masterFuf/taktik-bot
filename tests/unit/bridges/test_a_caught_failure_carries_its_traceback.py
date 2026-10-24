"""A bridge that catches a failure says it in its words, with the traceback on its `error` line.

The real bridge, run by the launcher as the app runs it, with one call that raises
(`tests/unit/bridge_with_fault.py`; `phone` lets the run past its connection on a stand-in device) or
a base that cannot open. Each `except Exception` here wrote its own line: the words with no
traceback (the TikTok cold DM, the Instagram connection, Threads, the database of the Gmail and
YouTube bridges), or the words and the traceback in a `log` line beside it (the account flows, the
YouTube upload, the tasks, the debug tooling), which the crash report does not read. They say it by
`entrypoint.send_run_error`: the same words, code and exit, the traceback on the line and on stderr,
and no `log` line that repeats it.
"""

from __future__ import annotations

import pytest

INJECTED = "fault injected by the test"
DEVICE = "gate-phone"
#: One payload every account flow reads: each takes the fields it needs.
ACCOUNT = {"deviceId": DEVICE, "username": "gate_user", "password": "gate-pass", "email": "gate@example.com",
           "method": "email", "language": "fr", "targetUsername": "gate_other"}
#: An Instagram automation run.
AUTOMATION = {"deviceId": DEVICE, "workflowType": "target_followers", "target": "gate-target"}

_IG_ACCOUNT = "bridges.instagram.account.launch:AccountLaunchMixin._launch_account"
_TIKTOK_ACCOUNT = "bridges.tiktok.account.account_launch:TikTokAccountLaunchMixin._launch_account"
_GMAIL_ACCOUNT = "taktik.core.social_media.gmail.workflows.agent_handler:run_gmail_account"


def _account(bridge: str, workflow: str, fault: str, words: str):
    return pytest.param(bridge, {**ACCOUNT, "workflowType": workflow}, fault, True,
                        f"{words}: {INJECTED}", f"RuntimeError: {INJECTED}", None, 1, id=f"{bridge}-{workflow}")


def _assert_said_with_its_traceback(proc, errors, said: str, cause: str, code, exit_code: int) -> None:
    stderr = proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == exit_code, stderr[-3000:]
    assert [error["error"] for error in errors] == [said], stderr[-3000:]
    [error] = errors
    assert error.get("error_code") == code
    assert error.get("traceback", "").rstrip().endswith(cause), error
    assert cause in stderr


@pytest.mark.parametrize("bridge, config, fault, phone, said, cause, code, exit_code", [
    # The bridges the app's crash capture reads.
    pytest.param("dm_outreach_bridge", {"device_id": DEVICE}, None, False,
                 "TikTok DM outreach requires at least one recipient",
                 "ValueError: TikTok DM outreach requires at least one recipient", None, 1,
                 id="tiktok-cold-dm-refused"),
    pytest.param("dm_outreach_bridge", {"device_id": DEVICE, "recipients": ["gate_user"], "messages": ["hi"]},
                 "taktik.core.social_media.tiktok.workflows.dm.agent_handler:run_tiktok_dm_outreach", False,
                 INJECTED, f"RuntimeError: {INJECTED}", None, 1, id="tiktok-cold-dm"),
    pytest.param("desktop_bridge", AUTOMATION, "bridges.instagram.automation.session:AppService", True,
                 f"Failed to connect to device: {INJECTED}", f"RuntimeError: {INJECTED}",
                 "DEVICE_CONNECTION_FAILED", 3, id="instagram-automation-connection"),
    pytest.param("youtube_upload_bridge", {"deviceId": DEVICE, "localPath": __file__},
                 "taktik.core.social_media.youtube.workflows.publish.agent_handler:run_youtube_upload", True,
                 f"Upload workflow error: {INJECTED}", f"RuntimeError: {INJECTED}", None, 1, id="youtube-upload"),
    # The others: Threads, the tasks, the debug tooling, the account flows.
    pytest.param("threads_bridge", {"deviceId": DEVICE, "workflowType": "follow"},
                 "bridges.threads.automation.threads_bridge:run_follow", False,
                 f"Workflow error: {INJECTED}", f"RuntimeError: {INJECTED}", None, 1, id="threads-dispatch"),
    pytest.param("task_bridge", {"deviceId": DEVICE, "taskId": "story_relay"},
                 "taktik.core.kernel.registry:WorkflowRegistry.resolve", True,
                 f"Task error: {INJECTED}", f"RuntimeError: {INJECTED}", None, 1, id="instagram-task"),
    pytest.param("desktop_bridge", {"deviceId": DEVICE, "debugMode": True, "mode": "analyze"},
                 "bridges.instagram.automation.debug:connect_debug_device", False,
                 f"Debug error: {INJECTED}", f"RuntimeError: {INJECTED}", None, 1, id="instagram-debug"),
    pytest.param("desktop_bridge", {"deviceId": DEVICE, "debugMode": True, "mode": "analyze"},
                 "taktik.core.shared.diagnostics.ui_dump_files:capture_screenshot", True,
                 f"Analyze error: {INJECTED}", f"RuntimeError: {INJECTED}", None, 1, id="instagram-debug-analyze"),
    _account("account_bridge", "login", _IG_ACCOUNT, "Login error"),
    _account("account_bridge", "register", _IG_ACCOUNT, "Register error"),
    _account("account_bridge", "logout", _IG_ACCOUNT, "Logout error"),
    _account("account_bridge", "change_language", _IG_ACCOUNT, "Change language error"),
    _account("account_bridge", "switch_account", _IG_ACCOUNT, "Switch error"),
    _account("account_bridge", "list_accounts", _IG_ACCOUNT, "List-accounts error"),
    _account("account_bridge", "list_saved_accounts", _IG_ACCOUNT, "List-saved-accounts error"),
    _account("tiktok_account_bridge", "login", _TIKTOK_ACCOUNT, "Login error"),
    _account("tiktok_account_bridge", "register", _TIKTOK_ACCOUNT, "Register error"),
    _account("tiktok_account_bridge", "logout", _TIKTOK_ACCOUNT, "Logout error"),
    _account("tiktok_account_bridge", "change_language", _TIKTOK_ACCOUNT, "Change language error"),
    _account("gmail_account_bridge", "login", _GMAIL_ACCOUNT, "Gmail login error"),
    _account("gmail_account_bridge", "logout", _GMAIL_ACCOUNT, "Gmail logout error"),
    _account("gmail_account_bridge", "read_otp", _GMAIL_ACCOUNT, "Gmail OTP error"),
    _account("gmail_account_bridge", "scan_accounts", _GMAIL_ACCOUNT, "Gmail scan_accounts error"),
])
def test_a_bridge_says_a_caught_failure_in_its_words_with_the_traceback(
        run_bridge_process, bridge, config, fault, phone, said, cause, code, exit_code):
    proc, errors = run_bridge_process(bridge, config, fault=fault, phone=phone)

    _assert_said_with_its_traceback(proc, errors, said, cause, code, exit_code)
    # Once on stdout: in the `error` line, not again in a `log` line beside it.
    assert proc.stdout.decode("utf-8", "replace").count("Traceback (most recent call last)") == 1


@pytest.mark.parametrize("bridge, config, code", [
    pytest.param("gmail_account_bridge", {**ACCOUNT, "workflowType": "login"}, None, id="gmail-account"),
    pytest.param("youtube_account_bridge", {**ACCOUNT, "workflowType": "login"}, None, id="youtube-account"),
    pytest.param("youtube_upload_bridge", {"deviceId": DEVICE, "localPath": __file__}, None, id="youtube-upload"),
    pytest.param("account_bridge", {**ACCOUNT, "workflowType": "login"}, None, id="instagram-account"),
    pytest.param("tiktok_account_bridge", {**ACCOUNT, "workflowType": "login"}, None, id="tiktok-account"),
    pytest.param("task_bridge", {"deviceId": DEVICE, "taskId": "story_relay"}, None, id="instagram-task"),
    pytest.param("desktop_bridge", AUTOMATION, "DATABASE_SETUP_FAILED", id="instagram-automation"),
])
def test_a_base_that_does_not_open_is_said_with_its_traceback(tmp_path, run_bridge_process, bridge, config, code):
    """A base whose folder is a file: the schema runner cannot create it, before any phone."""
    (tmp_path / "a-file").write_text("not a folder", encoding="utf-8")

    proc, errors = run_bridge_process(bridge, config, db_path=tmp_path / "a-file" / "taktik-data.db")

    stderr = proc.stderr.decode("utf-8", "replace")
    assert proc.returncode != 0, stderr[-3000:]
    [error] = errors
    assert error["error"].startswith("Database setup failed: "), (error, stderr[-3000:])
    assert error.get("error_code") == code
    assert "FileExistsError" in error.get("traceback", ""), error
    assert "Traceback (most recent call last)" in stderr


_APP = "taktik.core.shared.device.app_manager:AppService"


@pytest.mark.parametrize("bridge, config, fault, passes, said, code", [
    pytest.param("selector_test_bridge", {"device_id": DEVICE, "app": "instagram"},
                 "bridges.tools.lab.selector_test.production:prepare_selector_test", (),
                 f"Failed to load selectors: {INJECTED}", "REGISTRY_INIT_ERROR", id="lab-selector-test"),
    pytest.param("workflow_test_bridge", {"device_id": DEVICE, "app": "instagram", "workflow": "feed"},
                 "taktik.core.database:configure_db_service", (f"{_APP}.is_installed", f"{_APP}.restart"),
                 f"Automation init failed: {INJECTED}", "AUTOMATION_INIT_ERROR", id="lab-workflow-test"),
])
def test_a_lab_bench_says_a_caught_failure_with_its_code_and_the_traceback(
        run_bridge_process, bridge, config, fault, passes, said, code):
    """The Lab benches the app reads by `error` and `error_code` (`handlers/compat/compat.ts`). The
    workflow bench also relays its log on stdout, the traceback of `send_run_error` with it."""
    proc, errors = run_bridge_process(bridge, config, fault=fault, phone=True, passes=passes)

    _assert_said_with_its_traceback(proc, errors, said, f"RuntimeError: {INJECTED}", code, 1)


_IMPORT = "ModuleNotFoundError: No module named 'gate_missing_module'"


@pytest.mark.parametrize("bridge, config, fault, phone, passes, said, code, exit_code", [
    pytest.param("selector_test_bridge", {"device_id": DEVICE, "app": "instagram"},
                 "bridges.tools.lab.selector_test.production:prepare_selector_test", True, (),
                 "Failed to load selectors: No module named 'gate_missing_module'", "REGISTRY_INIT_ERROR", 1,
                 id="lab-selector-test"),
    pytest.param("workflow_test_bridge", {"device_id": DEVICE, "app": "instagram", "workflow": "feed"},
                 "taktik.core.database:configure_db_service", True, (f"{_APP}.is_installed", f"{_APP}.restart"),
                 "Automation init failed: No module named 'gate_missing_module'", "AUTOMATION_INIT_ERROR", 1,
                 id="lab-workflow-test"),
    pytest.param("desktop_bridge", AUTOMATION, "taktik.core.database:configure_db_service", False, (),
                 "Database setup failed: No module named 'gate_missing_module'", "DATABASE_SETUP_FAILED", None,
                 id="instagram-automation-database"),
    # A run that names no code of its own: the import is the code the bot knows.
    pytest.param("threads_bridge", {"deviceId": DEVICE, "workflowType": "follow"},
                 "bridges.threads.automation.threads_bridge:run_follow", False, (),
                 "Workflow error: No module named 'gate_missing_module'", "PYTHON_IMPORT_ERROR", 1,
                 id="threads-dispatch"),
])
def test_an_import_a_run_catches_keeps_its_words_and_code(
        run_bridge_process, bridge, config, fault, phone, passes, said, code, exit_code):
    """`send_run_error` answered an `ImportError` by `send_import_error`: « A module the run needs did
    not import » under `PYTHON_IMPORT_ERROR`, the caller's words and code dropped (the Lab showed an
    engine failure, not « Failed to load selectors », and `compat.ts` relayed another code). The words
    and the code are the caller's, the traceback names the import."""
    proc, errors = run_bridge_process(bridge, config, fault=fault, phone=phone, passes=passes, import_error=True)

    stderr = proc.stderr.decode("utf-8", "replace")
    if exit_code is None:
        assert proc.returncode != 0, stderr[-3000:]
        exit_code = proc.returncode
    _assert_said_with_its_traceback(proc, errors, said, _IMPORT, code, exit_code)
