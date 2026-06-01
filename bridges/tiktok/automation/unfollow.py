#!/usr/bin/env python3
"""TikTok Unfollow bridge entrypoint."""

from __future__ import annotations

import json
import os
import sys


_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.tiktok.automation.runtime.unfollow import run_unfollow_workflow
from bridges.tiktok.runtime.ipc import logger, send_error


def main():
    """Main entry point - read config from stdin and run workflow."""
    logger.info("ðŸŽµ TikTok Unfollow Bridge starting...")

    try:
        config_line = sys.stdin.readline()
        if not config_line:
            send_error("No config received from stdin")
            logger.error("No config received from stdin")
            sys.exit(1)

        config_data = json.loads(config_line)
        device_id = config_data.get("device_id")
        config = config_data.get("config", {})
        config["deviceId"] = device_id

        logger.info(f"ðŸ“‹ Config received: device={device_id}, maxUnfollows={config.get('maxUnfollows', 20)}")

        success = run_unfollow_workflow(config)

        if success:
            logger.success("âœ… TikTok Unfollow workflow completed successfully")
            sys.exit(0)

        logger.error("âŒ TikTok Unfollow workflow failed")
        sys.exit(1)

    except json.JSONDecodeError as e:
        send_error(f"Invalid JSON config: {e}")
        logger.error(f"JSON decode error: {e}")
        sys.exit(1)
    except Exception as e:
        send_error(f"Startup error: {e}")
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
