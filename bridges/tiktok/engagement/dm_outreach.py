#!/usr/bin/env python3
"""TikTok DM Outreach bridge entrypoint: one JSON line on stdin, the run, the exit code."""

from __future__ import annotations

import os
import sys


_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.common.runtime.entrypoint import run_bridge_main
from bridges.tiktok.engagement.runtime.dm_outreach import TikTokDMOutreachBridge


def main():
    """Main entry point - reads config from stdin."""
    run_bridge_main(TikTokDMOutreachBridge, usage="dm_outreach_bridge", config_source="stdin")


if __name__ == "__main__":
    main()
