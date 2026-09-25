#!/usr/bin/env python3
"""TikTok Unfollow bridge entrypoint: one JSON line on stdin, the run, the exit code."""

from __future__ import annotations

import os
import sys


_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.common.runtime.entrypoint import run_bridge_main
from bridges.tiktok.automation.runtime.unfollow import TikTokUnfollowBridge


def main():
    """Main entry point - read config from stdin and run workflow."""
    run_bridge_main(TikTokUnfollowBridge, usage="tiktok_unfollow_bridge", config_source="stdin")


if __name__ == "__main__":
    main()
