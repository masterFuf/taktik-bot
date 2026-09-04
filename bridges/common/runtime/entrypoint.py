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


def run_bridge_main(
    bridge_factory: Callable[[dict], Any],
    *,
    usage: str = "bridge <config_path>",
    install_signal_handlers: bool = False,
) -> None:
    """
    Universal `main()` for bridges that take a single JSON config path and
    expose a `.run() -> int` method.
    """
    if install_signal_handlers:
        signal.signal(signal.SIGINT, _sig_mod._handle_signal)
        signal.signal(signal.SIGTERM, _sig_mod._handle_signal)

    if len(sys.argv) < 2:
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
