"""CLI/config handling for the Instagram publish bridge."""

from __future__ import annotations

import json
import sys
from typing import Sequence

from bridges.instagram.publish.runtime.bridge import InstagramPublishBridge


def run_publish_bridge_cli(argv: Sequence[str]) -> int:
    """Run the Instagram publish bridge from launcher-provided arguments."""
    if len(argv) < 1:
        print(json.dumps({"type": "error", "message": "Usage: instagram_publish_bridge.py <config.json>"}))
        return 1

    config_path = argv[0]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Failed to read config: {e}"}))
        return 1

    bridge = InstagramPublishBridge(config)
    return bridge.run()


def main() -> None:
    sys.exit(run_publish_bridge_cli(sys.argv[1:]))
