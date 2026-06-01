"""CLI/config handling for the TikTok publish bridge."""

from __future__ import annotations

import json
import sys
from typing import Sequence

from bridges.tiktok.publish.runtime.bridge import TikTokPublishBridge


def run_publish_bridge_cli(argv: Sequence[str]) -> int:
    """Run the TikTok publish bridge from launcher-provided arguments."""
    if len(argv) < 1:
        print(json.dumps({"type": "error", "message": "Usage: tiktok_publish_bridge.py <config.json>"}))
        return 1

    config_path = argv[0]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Failed to read config: {e}"}))
        return 1

    bridge = TikTokPublishBridge(config)
    return bridge.run()


def main() -> None:
    sys.exit(run_publish_bridge_cli(sys.argv[1:]))
