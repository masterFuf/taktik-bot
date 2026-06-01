#!/usr/bin/env python3
"""TikTok DM Outreach bridge entrypoint."""

from __future__ import annotations

import json
import os
import sys


_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.tiktok.engagement.runtime.dm_outreach import run_dm_outreach_workflow
from bridges.tiktok.runtime.ipc import logger, send_error


def main():
    """Main entry point - reads config from stdin."""
    logger.info("TikTok DM Outreach Bridge started")

    try:
        config_line = sys.stdin.readline()
        if not config_line:
            send_error("No configuration received")
            sys.exit(1)

        config = json.loads(config_line)
        logger.info(f"Received config: {json.dumps(config, indent=2)[:500]}...")

        success = run_dm_outreach_workflow(config)
        if not success:
            sys.exit(1)
    except json.JSONDecodeError as exc:
        send_error(f"Invalid JSON config: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"DM Outreach error: {exc}", exc_info=True)
        send_error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
