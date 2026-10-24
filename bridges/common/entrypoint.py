"""The one entry of every bridge: the JSON config file named by the first argument.

`bridges/launcher.py` calls the bridge module's `main()`, which hands its bridge to
`run_bridge_main`. Nothing else reads the command line or a config (`audit_bridge_entrypoints.py`).
Stdin stays for what a run exchanges while it runs (decision replies, stop orders, Lab commands).

The entry reads the file, not the payload: each launcher reads and validates its payload before it
calls the `connect` its bridge hands it, so the order (read, validate, then touch the phone) lives
in the launcher, the same for the bridge and for the CLI.
"""

from __future__ import annotations

import json
import signal
import sys
from typing import Any, Callable, Optional

import bridges.common.signal_handler as _sig_mod
from bridges.common.crash_hooks import exception_event
from bridges.common.ipc import IPC
from loguru import logger


_ipc: IPC = IPC()

#: Why the entry could not hand the run to its bridge, as passed to `report_error`.
MISSING_CONFIG = "MISSING_CONFIG"
CONFIG_ERROR = "CONFIG_ERROR"
NOT_AN_OBJECT = "NOT_AN_OBJECT"
INIT_ERROR = "INIT_ERROR"
CRASH = "CRASH"

#: The code of each entry failure on the `error` line (`taktik/core/contract/error_codes.py`). A config
#: that is no JSON object does not read as a config either; an exception that ends the bridge, at its
#: creation or in its run, is the one the launcher's crash hooks would say (`UNHANDLED_EXCEPTION`).
ENTRY_ERROR_CODES = {
    MISSING_CONFIG: "MISSING_CONFIG",
    CONFIG_ERROR: "CONFIG_ERROR",
    NOT_AN_OBJECT: "CONFIG_ERROR",
    INIT_ERROR: "UNHANDLED_EXCEPTION",
    CRASH: "UNHANDLED_EXCEPTION",
}

#: The words of each entry failure; a bridge may keep its own (`messages`), with `{usage}` and
#: `{error}` filled in.
DEFAULT_MESSAGES = {
    MISSING_CONFIG: "Usage: {usage}",
    CONFIG_ERROR: "Failed to load config: {error}",
    NOT_AN_OBJECT: "Failed to load config: the config must be a JSON object",
    INIT_ERROR: "Failed to initialize bridge: {error}",
    CRASH: "Bridge crashed: {error}",
}

ErrorReporter = Callable[[str, str], None]

_config_path: Optional[str] = None


def load_bridge_config(config_path: str) -> dict:
    """Read a JSON config file the way every bridge does it.

    Falls back to `utf-8-sig` so configs written by Electron's `fs.writeFileSync`
    on Windows can still parse correctly when they include a BOM.
    """
    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except UnicodeError:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)


def loaded_config_path() -> Optional[str]:
    """The config file of this process, once `run_bridge_main` has read it."""
    return _config_path


def send_import_error(exc: ImportError) -> None:
    """A module the run needs did not import: the `error` line with the bot's code and the traceback.

    For an import nothing worded: one that reaches the entry (`run_bridge_main`), or the Instagram
    automation's catch-all (`send_instagram_workflow_error`): `PYTHON_IMPORT_ERROR`, the exception's
    words and its traceback, as the crash hook says an import of the bridge's own module
    (`crash_hooks.exception_event`). The traceback goes to stderr too, the run's log. A run that
    catches the import with words of its own says it by `send_run_error`, which keeps them.
    """
    logger.opt(exception=exc).error(f"A module the run needs did not import: {exc}")
    _ipc.send("error", **exception_event(type(exc), exc, exc.__traceback__))


def send_run_error(message: str, exc: BaseException, **extra: Any) -> None:
    """A run that an exception ended, in its bridge's words: the `error` line with the traceback.

    For a run that catches its own failure and returns (the TikTok workflow runners, the Lab benches,
    the opening of the base): the bridge keeps its words (`message`) and the code it passes in
    `extra`, the line carries the traceback the crash report needs (`crash_hooks.exception_event`),
    and the traceback goes to stderr too. A run that names no code gets the one the bot reads in the
    exception when it has one: `PYTHON_IMPORT_ERROR` for an import that failed.
    """
    event = exception_event(type(exc), exc, exc.__traceback__)
    if isinstance(exc, ImportError):
        extra.setdefault("error_code", event["error_code"])
    logger.opt(exception=exc).error(message)
    _ipc.error(message, traceback=event["traceback"], **extra)


def report_entry_error(message: str, reason: str, exc: Optional[BaseException] = None) -> None:
    """An entry failure on the contract's `error` line: the words, the code of the reason
    (`ENTRY_ERROR_CODES`) and, for an exception that ended the bridge, its traceback (`send_run_error`,
    which writes it on stderr too)."""
    code = ENTRY_ERROR_CODES[reason]
    if reason in (INIT_ERROR, CRASH) and exc is not None:
        send_run_error(message, exc, error_code=code)
    else:
        _ipc.error(message, error_code=code)


def _reset_run_diagnostics() -> None:
    # Module-level diagnostic counters would otherwise carry the previous run's counts.
    for module in ('miss_capture', 'foreground_guard', 'screen_ring', 'run_halt'):
        try:
            __import__(f'taktik.core.shared.diagnostics.{module}', fromlist=['reinitialiser'])
            sys.modules[f'taktik.core.shared.diagnostics.{module}'].reinitialiser()
        except Exception:
            # A diagnostic must never keep a bridge from starting.
            pass


def run_bridge_main(
    bridge_factory: Callable[[dict], Any],
    *,
    usage: str = "bridge <config_path>",
    install_signal_handlers: bool = False,
    report_error: Optional[ErrorReporter] = None,
    messages: Optional[dict] = None,
    catch_crashes: bool = True,
) -> None:
    """Universal `main()`: read the config file, build the bridge, exit with its `.run()` code.

    An entry failure (reasons: MISSING_CONFIG, CONFIG_ERROR, NOT_AN_OBJECT, INIT_ERROR, CRASH), worded
    by `messages` over `DEFAULT_MESSAGES`, goes on the contract's `error` line (`report_entry_error`);
    a bridge whose entry failures end in a shape of its own (a final JSON result, a Lab event) passes
    `report_error(message, reason)`. An import that fails under it is no entry failure:
    `send_import_error` says it with its code, whatever the bridge's reporter. `catch_crashes=False`
    leaves an exception of the factory or of `.run()` to the launcher's crash hooks
    (UNHANDLED_EXCEPTION, or PYTHON_IMPORT_ERROR, with its traceback).
    """
    global _config_path
    words = {**DEFAULT_MESSAGES, **(messages or {})}

    def report(reason: str, exc: Optional[BaseException] = None) -> None:
        message = words[reason].format(usage=usage, error="" if exc is None else exc)
        if report_error is None:
            report_entry_error(message, reason, exc)
            return
        report_error(message, reason)
        if exc is not None and reason in (INIT_ERROR, CRASH):
            logger.opt(exception=exc).error(message)

    if install_signal_handlers:
        signal.signal(signal.SIGINT, _sig_mod._handle_signal)
        signal.signal(signal.SIGTERM, _sig_mod._handle_signal)

    if len(sys.argv) < 2:
        report(MISSING_CONFIG)
        logger.error(f"No config file given. Usage: {usage}")
        sys.exit(1)

    _reset_run_diagnostics()

    config_path = sys.argv[1]
    try:
        config = load_bridge_config(config_path)
    except Exception as exc:
        report(CONFIG_ERROR, exc)
        logger.error(f"Failed to load config from {config_path}: {exc}")
        sys.exit(1)
    if not isinstance(config, dict):
        report(NOT_AN_OBJECT)
        logger.error(f"Config in {config_path} is not a JSON object")
        sys.exit(1)
    _config_path = config_path

    if not catch_crashes:
        try:
            code = bridge_factory(config).run()
        except KeyboardInterrupt:
            logger.info("Bridge interrupted by user")
            sys.exit(0)
        sys.exit(int(code or 0))

    try:
        bridge = bridge_factory(config)
    except ImportError as exc:
        send_import_error(exc)
        sys.exit(1)
    except Exception as exc:
        report(INIT_ERROR, exc)
        sys.exit(1)

    try:
        sys.exit(int(bridge.run()))
    except SystemExit:
        raise
    except KeyboardInterrupt:
        logger.info("Bridge interrupted by user")
        sys.exit(0)
    except ImportError as exc:
        send_import_error(exc)
        sys.exit(1)
    except Exception as exc:
        report(CRASH, exc)
        sys.exit(1)
