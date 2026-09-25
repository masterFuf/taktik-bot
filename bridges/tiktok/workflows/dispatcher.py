#!/usr/bin/env python3
"""TikTok workflow dispatcher entrypoint."""

import os
import sys


_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.common.runtime.entrypoint import run_bridge_main
from bridges.tiktok.workflows.runtime.dispatcher import TikTokDispatcherBridge


def main():
    """Main entry point - dispatch to the configured TikTok workflow bridge."""
    run_bridge_main(TikTokDispatcherBridge, usage="tiktok_bridge <config_path>")


if __name__ == "__main__":
    main()
