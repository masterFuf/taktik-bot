#!/usr/bin/env python3
"""TikTok publish bridge entrypoint."""

import os
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.tiktok.publish.runtime.bridge import TikTokPublishBridge
from bridges.common.runtime.entrypoint import CONFIG_ERROR, report_error_message, run_bridge_main


def main():
    run_bridge_main(TikTokPublishBridge, usage="tiktok_publish_bridge.py <config.json>",
                    report_error=report_error_message, messages={CONFIG_ERROR: "Failed to read config: {error}"},
                    catch_crashes=False)


if __name__ == "__main__":
    main()


__all__ = ["TikTokPublishBridge", "main"]
