"""CLI/config handling for the TikTok account bridge."""

import json
import sys
from typing import Sequence

from bridges.tiktok.account.account import TikTokAccountBridge
from bridges.tiktok.runtime.ipc import send_error


def run_account_bridge_cli(argv: Sequence[str]) -> int:
    """Run the TikTok account bridge from launcher-provided arguments."""
    if len(argv) < 1:
        print(json.dumps({"type": "error", "message": "Usage: tiktok_account_bridge.py <config_path>"}))
        return 1

    config_path = argv[0]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        send_error(f"Failed to load config: {e}")
        return 1

    bridge = TikTokAccountBridge(config)
    return bridge.run()


def main() -> None:
    sys.exit(run_account_bridge_cli(sys.argv[1:]))
