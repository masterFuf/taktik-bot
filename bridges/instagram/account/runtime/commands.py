"""CLI/config handling for the Instagram account bridge."""

from __future__ import annotations

import json
import sys

from bridges.instagram.runtime.ipc import send_error


def load_account_config(argv: list[str]) -> dict | None:
    if len(argv) < 2:
        print(json.dumps({"type": "error", "message": "Usage: account_bridge.py <config_path>"}))
        return None

    config_path = argv[1]
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        send_error(f"Failed to load config: {e}")
        return None


def run_account_bridge(bridge_cls, argv: list[str] | None = None) -> int:
    config = load_account_config(argv or sys.argv)
    if config is None:
        return 1

    bridge = bridge_cls(config)
    return bridge.run()
