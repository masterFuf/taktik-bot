#!/usr/bin/env python3
"""Threads Bridge - main dispatcher for Threads workflows.

Routes to specific workflow bridges based on `workflowType` in the config.
Mirrors the TikTok dispatcher pattern. Workflows are added incrementally as
UI selectors are captured from real devices.
"""

import json
import os
import signal
import sys


_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.threads.base import logger, send_error, signal_handler
from bridges.threads.workflows.runtime.feed import run_feed
from bridges.threads.workflows.runtime.search import run_follow


def main() -> None:
    """Dispatch to the appropriate Threads workflow."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if len(sys.argv) < 2:
        send_error("No config file provided")
        logger.error("No config file provided")
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as file_obj:
            config = json.load(file_obj)
    except Exception as exc:
        send_error(f"Failed to load config: {exc}")
        logger.error(f"Failed to load config from {config_path}: {exc}")
        sys.exit(1)

    workflow_type = config.get("workflowType", "follow")
    device_id = config.get("deviceId", "unknown")
    logger.info(f"Threads bridge starting - workflow={workflow_type} device={device_id}")

    try:
        if workflow_type in ("follow", "target"):
            success = run_follow(config)
        elif workflow_type == "feed":
            success = run_feed(config)
        else:
            send_error(f"Unknown workflow type: {workflow_type}", error_code="threads.unknown_workflow")
            logger.error(f"Unknown workflow type: {workflow_type}")
            sys.exit(1)

        if success:
            logger.success(f"Threads {workflow_type} workflow completed")
            sys.exit(0)
        logger.error(f"Threads {workflow_type} workflow failed")
        sys.exit(1)

    except ImportError as exc:
        send_error(f"Failed to import workflow module: {exc}")
        logger.error(f"Import error: {exc}")
        sys.exit(1)
    except Exception as exc:
        send_error(f"Workflow error: {exc}")
        logger.exception(f"Unexpected error in {workflow_type} workflow: {exc}")
        sys.exit(1)
    finally:
        from bridges.common.device.app_manager import force_stop_app

        force_stop_app(device_id, "threads")


if __name__ == "__main__":
    main()
