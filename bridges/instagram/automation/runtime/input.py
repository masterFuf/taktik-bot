"""Command-line parsing for the debug mode of the Instagram desktop bridge."""

from __future__ import annotations

import argparse


def load_debug_config() -> dict:
    """`desktop_bridge --debug --mode <analyze|detect> --device <serial>` as a debug config."""
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
