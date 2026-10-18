"""The one entry of every bridge: the JSON config file named by the first argument.

`bridges/launcher.py` calls the bridge module's `main()`, which hands its bridge to
`run_bridge_main`. Nothing else reads the command line or a config (`audit_bridge_entrypoints.py`).
Stdin stays for what a run exchanges while it runs (decision replies, stop orders, Lab commands).

A bridge whose launcher is handed a phone the bridge already prepared (connected, on a fresh IP)
names the launcher's payload reader here (`read_payload`): the payload is read and validated before
the bridge is built, so what the reader refuses never reaches the phone.
"""

from __future__ import annotations

import json
import signal
import sys
from typing import Any, Callable, Optional

import bridges.common.signal_handler as _sig_mod
from bridges.common.ipc import IPC
from loguru import logger


_ipc: IPC = IPC()

#: Why the entry could not hand the run to its bridge, as passed to `report_error`.
MISSING_CONFIG = "MISSING_CONFIG"
CONFIG_ERROR = "CONFIG_ERROR"
NOT_AN_OBJECT = "NOT_AN_OBJECT"
INIT_ERROR = "INIT_ERROR"
CRASH = "CRASH"
#: The workflow's reader refused the payload (`read_payload`): the bridge was not built.
REFUSED = "REFUSED"

#: The words of each entry failure; a bridge may keep its own (`messages`), with `{usage}` and
#: `{error}` filled in.
DEFAULT_MESSAGES = {
    MISSING_CONFIG: "Usage: {usage}",
    CONFIG_ERROR: "Failed to load config: {error}",
    NOT_AN_OBJECT: "Failed to load config: the config must be a JSON object",
    INIT_ERROR: "Failed to initialize bridge: {error}",
    CRASH: "Bridge crashed: {error}",
    REFUSED: "{error}",
}

ErrorReporter = Callable[[str, str], None]
#: The launcher's payload reader: returns what it read, raises `ValueError` to refuse.
PayloadReader = Callable[[dict], Any]

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


def _send_error(error: str) -> None:
    """Emit a machine-readable entrypoint error without importing bridge_base."""
    _ipc.error(error)


def report_error_message(message: str, _reason: str = CONFIG_ERROR) -> None:
    """`{"type": "error", "message": ...}`: the shape of the usage error, and of the publish and
    upload bridges' entry errors."""
    print(json.dumps({"type": "error", "message": message}))


def report_error_event(message: str, _reason: str = CONFIG_ERROR) -> None:
    """Every entry failure as an `error` event, a missing file included."""
    _send_error(message)


def report_entry_error(message: str, reason: str) -> None:
    """The default shape: the usage line for a missing file, an `error` event for the rest."""
    if reason == MISSING_CONFIG:
        report_error_message(message, reason)
    else:
        _send_error(message)


def _refuse_what_the_reader_refuses(
    read_payload: Optional[PayloadReader], config: dict, report: Callable[[str, object], None]
) -> None:
    """Read the payload with the workflow's reader; on its refusal, report it and exit.

    A reader refuses with a `ValueError` (its own subclass included: `DmCommandError`...). Any other
    exception is a bug of the reader, not a refusal: it goes where the bridge's crashes go.
    """
    if read_payload is None:
        return
    try:
        read_payload(config)
    except ValueError as refused:
        report(REFUSED, refused)
        logger.warning(f"Payload refused before the bridge was built: {refused}")
        sys.exit(1)


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
    read_payload: Optional[PayloadReader] = None,
) -> None:
    """Universal `main()`: read the config file, build the bridge, exit with its `.run()` code.

    `report_error(message, reason)` emits an entry failure in the bridge's own event shape
    (reasons: MISSING_CONFIG, CONFIG_ERROR, NOT_AN_OBJECT, INIT_ERROR, CRASH, REFUSED), worded by
    `messages` over `DEFAULT_MESSAGES`. `catch_crashes=False` leaves an
    exception of the factory or of `.run()` to the launcher's crash hooks (UNHANDLED_EXCEPTION
    with its traceback).

    `read_payload(config)`: the launcher's payload reader. Called before the bridge is built: a
    payload it refuses is reported (REFUSED, the reader's sentence) and the process exits 1 with
    nothing built, so nothing connects to the phone, rotates its IP or stops its app. The order is
    read, validate, then connect, for every bridge that names its reader.
    """
    global _config_path
    reporter = report_error or report_entry_error
    words = {**DEFAULT_MESSAGES, **(messages or {})}

    def report(reason: str, error: object = "") -> None:
        reporter(words[reason].format(usage=usage, error=error), reason)

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
            _refuse_what_the_reader_refuses(read_payload, config, report)
            code = bridge_factory(config).run()
        except KeyboardInterrupt:
            logger.info("Bridge interrupted by user")
            sys.exit(0)
        sys.exit(int(code or 0))

    try:
        _refuse_what_the_reader_refuses(read_payload, config, report)
        bridge = bridge_factory(config)
    except Exception as exc:
        report(INIT_ERROR, exc)
        logger.exception("Bridge initialization failed")
        sys.exit(1)

    try:
        sys.exit(int(bridge.run()))
    except SystemExit:
        raise
    except KeyboardInterrupt:
        logger.info("Bridge interrupted by user")
        sys.exit(0)
    except Exception as exc:
        report(CRASH, exc)
        logger.exception("Bridge crashed")
        sys.exit(1)
