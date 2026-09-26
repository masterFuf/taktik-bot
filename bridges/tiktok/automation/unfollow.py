#!/usr/bin/env python3
"""TikTok Unfollow bridge entrypoint: the config file, the run, the exit code."""

from __future__ import annotations

import os
import sys


_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.common.runtime.entrypoint import report_error_event, run_bridge_main
from bridges.tiktok.automation.runtime.unfollow import TikTokUnfollowBridge


def main():
    """Main entry point - read the config file and run the workflow."""
    run_bridge_main(TikTokUnfollowBridge, usage="tiktok_unfollow_bridge <config_path>",
                    report_error=report_error_event)


if __name__ == "__main__":
    main()
