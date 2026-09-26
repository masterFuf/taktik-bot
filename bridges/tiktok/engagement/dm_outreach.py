#!/usr/bin/env python3
"""TikTok DM Outreach bridge entrypoint: the config file, the run, the exit code."""

from __future__ import annotations

import os
import sys


_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.common.runtime.entrypoint import report_error_event, run_bridge_main
from bridges.tiktok.engagement.runtime.dm_outreach import TikTokDMOutreachBridge


def main():
    """Main entry point - reads the config file."""
    run_bridge_main(TikTokDMOutreachBridge, usage="dm_outreach_bridge <config_path>",
                    report_error=report_error_event)


if __name__ == "__main__":
    main()
