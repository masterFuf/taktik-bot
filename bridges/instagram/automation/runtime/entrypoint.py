"""Entrypoint dispatch for the Instagram desktop automation bridge."""

from __future__ import annotations

from bridges.instagram.diagnostics.debug import DebugBridge


def run_desktop_config(config: dict, bridge_cls) -> int:
    if config.get('debugMode'):
        bridge = DebugBridge(config)
        return bridge.run()

    bridge = bridge_cls(config)
    return bridge.run()
