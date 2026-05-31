"""CLI/stdin payload loading for the Instagram desktop automation bridge."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Callable


def load_desktop_config(log: Callable[[str, str], None]) -> dict | None:
    """Load bridge config from debug flags, a JSON file/arg or stdin."""
    if len(sys.argv) >= 2 and sys.argv[1] == "--debug":
        parser = argparse.ArgumentParser()
        parser.add_argument("--debug", action="store_true")
        parser.add_argument("--mode", choices=["analyze", "detect"], default="analyze")
        parser.add_argument("--device", type=str, required=True)
        args = parser.parse_args()

        return {
            "debugMode": True,
            "mode": args.mode,
            "deviceId": args.device,
        }

    config = None
    if len(sys.argv) >= 2:
        arg = sys.argv[1]

        if os.path.isfile(arg):
            with open(arg, "r", encoding="utf-8-sig") as f:
                config = json.load(f)
            log("debug", f"Loaded config from file: {arg}")
        else:
            try:
                config = json.loads(arg)
                log("debug", "Parsed config from argument")
            except json.JSONDecodeError:
                pass

    if config is None:
        log("debug", "Reading config from stdin...")
        stdin_data = sys.stdin.read()
        if stdin_data.strip():
            config = json.loads(stdin_data)
            log("debug", "Parsed config from stdin")

    return config
