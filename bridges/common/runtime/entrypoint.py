"""Shared JSON-config bridge entrypoint helpers."""

from __future__ import annotations

import json
import signal
import sys
from typing import Any, Callable

import bridges.common.runtime.signal_handler as _sig_mod
from bridges.common.runtime.ipc import IPC
from loguru import logger


_ipc: IPC = IPC()


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


def _send_error(error: str) -> None:
    """Emit a machine-readable entrypoint error without importing bridge_base."""
    _ipc.error(error)


def _read_stdin_config() -> dict:
    """One JSON line on stdin, the way the stdin bridges receive their payload."""
    line = sys.stdin.readline()
    if not line:
        _send_error("No config received from stdin")
        logger.error("No config received from stdin")
        sys.exit(1)
    try:
        return json.loads(line)
    except json.JSONDecodeError as exc:
        _send_error(f"Invalid JSON config: {exc}")
        logger.error(f"Invalid JSON config on stdin: {exc}")
        sys.exit(1)


def run_bridge_main(
    bridge_factory: Callable[[dict], Any],
    *,
    usage: str = "bridge <config_path>",
    install_signal_handlers: bool = False,
    config_source: str = "argv",
) -> None:
    """
    Universal `main()` for bridges that expose a `.run() -> int` method.

    `config_source="argv"` reads the JSON file named by `sys.argv[1]`; `"stdin"` reads one JSON
    line from stdin.
    """
    if config_source not in ("argv", "stdin"):
        raise ValueError(f"Unknown config_source: {config_source}")

    if install_signal_handlers:
        signal.signal(signal.SIGINT, _sig_mod._handle_signal)
        signal.signal(signal.SIGTERM, _sig_mod._handle_signal)

    if config_source == "argv" and len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": f"Usage: {usage}"}))
        sys.exit(1)

    # Le point de depart commun aux deux plateformes, cote Python. Les compteurs partages de
    # diagnostic (plafond de captures, serie de blocage, horodatage du controle de premier plan)
    # sont des etats de MODULE : sans remise a zero, ils entreraient dans le run suivant avec le
    # compte du precedent. `miss_capture.reinitialiser()` etait ecrit pour ce moment et n'etait
    # appele nulle part -- la note en tete de `foreground_guard` disait que ce point n'existait
    # pas ; il existe, c'est ici, et un processus de pont sert exactement un run.
    for module in ('miss_capture', 'foreground_guard', 'screen_ring', 'run_halt'):
        try:
            __import__(f'taktik.core.shared.diagnostics.{module}', fromlist=['reinitialiser'])
            sys.modules[f'taktik.core.shared.diagnostics.{module}'].reinitialiser()
        except Exception:
            # Un diagnostic qui empeche un pont de demarrer serait pire que pas de diagnostic.
            pass

    if config_source == "stdin":
        config = _read_stdin_config()
    else:
        config_path = sys.argv[1]
        try:
            config = load_bridge_config(config_path)
        except Exception as exc:
            _send_error(f"Failed to load config: {exc}")
            logger.error(f"Failed to load config from {config_path}: {exc}")
            sys.exit(1)

    try:
        bridge = bridge_factory(config)
    except Exception as exc:
        _send_error(f"Failed to initialize bridge: {exc}")
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
        _send_error(f"Bridge crashed: {exc}")
        logger.exception("Bridge crashed")
        sys.exit(1)
