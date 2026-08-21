"""CLI/config handling for the Instagram task bridge.

Same contract as every bridge entrypoint: one JSON config file as argv[1]; anything else
is an error emitted as a JSON event, never a traceback on stdout.
"""

from __future__ import annotations

import json
import sys

from bridges.instagram.runtime.ipc import send_error


def load_task_config(argv: list[str]) -> dict | None:
    if len(argv) < 2:
        print(json.dumps({"type": "error", "message": "Usage: tasks.py <config_path>"}))
        return None

    config_path = argv[1]
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        send_error(f"Failed to load config: {e}")
        return None


def run_task_bridge(bridge_cls, argv: list[str] | None = None) -> int:
    config = load_task_config(argv or sys.argv)
    if config is None:
        return 1

    bridge = bridge_cls(config)
    return bridge.run()
