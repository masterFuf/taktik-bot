#!/usr/bin/env python3
"""TikTok scraping bridge entrypoint."""

from __future__ import annotations

import json
import sys

from bridges.tiktok.runtime.ipc import logger, send_error
from bridges.tiktok.scraping.runtime.signals import register_scraping_signal_handlers
from bridges.tiktok.scraping.runtime.workflow import run_scraping_workflow


def main():
    """Main entry point - reads config from stdin."""
    logger.info("TikTok Scraping Bridge started")
    register_scraping_signal_handlers()

    try:
        config_line = sys.stdin.readline()
        if not config_line:
            send_error("No configuration received")
            sys.exit(1)

        config = json.loads(config_line)
        logger.info(f"Received config: {json.dumps(config, indent=2)[:500]}...")

        success = run_scraping_workflow(config)
        if not success:
            sys.exit(1)

    except json.JSONDecodeError as e:
        send_error(f"Invalid JSON config: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Scraping error: {e}", exc_info=True)
        send_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
