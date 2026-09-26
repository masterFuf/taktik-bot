"""The one entry of every bridge: the JSON config file named by the first argument.

`bridges/launcher.py` calls the bridge module's `main()`, which hands its bridge to
`run_bridge_main`. Nothing else reads the command line or a config (`audit_bridge_entrypoints.py`).
Stdin stays for what a run exchanges while it runs (decision replies, stop orders, Lab commands).
"""

from __future__ import annotations

import json
import signal
import sys
from typing import Any, Callable, Optional

import bridges.common.runtime.signal_handler as _sig_mod
from bridges.common.runtime.ipc import IPC
from loguru import logger


_ipc: IPC = IPC()

#: Why the entry could not hand the run to its bridge, as passed to `report_error`.
MISSING_CONFIG = "MISSING_CONFIG"
CONFIG_ERROR = "CONFIG_ERROR"
NOT_AN_OBJECT = "NOT_AN_OBJECT"
INIT_ERROR = "INIT_ERROR"
CRASH = "CRASH"

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


def _default_report() -> ErrorReporter:
    def report(message: str, reason: str) -> None:
        if reason == MISSING_CONFIG:
            report_error_message(message, reason)
        else:
            _send_error(message)

    return report


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

    `report_error(message, reason)` emits an entry failure in the bridge's own event shape
    (reasons: MISSING_CONFIG, CONFIG_ERROR, NOT_AN_OBJECT, INIT_ERROR, CRASH), worded by
    `messages` over `DEFAULT_MESSAGES`. `catch_crashes=False` leaves an
    exception of the factory or of `.run()` to the launcher's crash hooks (UNHANDLED_EXCEPTION
    with its traceback).
    """
    global _config_path
    reporter = report_error or _default_report()
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
            code = bridge_factory(config).run()
        except KeyboardInterrupt:
            logger.info("Bridge interrupted by user")
            sys.exit(0)
        sys.exit(int(code or 0))

    try:
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
