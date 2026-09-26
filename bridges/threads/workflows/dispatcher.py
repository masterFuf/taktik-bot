#!/usr/bin/env python3
"""Threads Bridge - main dispatcher for Threads workflows.

Routes to specific workflow bridges based on `workflowType` in the config.
Mirrors the TikTok dispatcher pattern. Workflows are added incrementally as
UI selectors are captured from real devices.
"""

import os
import signal
import sys


_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.common.runtime.entrypoint import MISSING_CONFIG, run_bridge_main
from bridges.threads.base import logger, send_error, signal_handler
from bridges.threads.workflows.runtime.feed import run_feed
from bridges.threads.workflows.runtime.search import run_follow


def _report_entry_error(message: str, _reason: str) -> None:
    send_error(message)


class ThreadsDispatch:
    """One Threads run, routed by the `workflowType` of its config file."""

    def __init__(self, config: dict):
        self.config = config

    def run(self) -> int:
        dispatch(self.config)
        return 0


def main() -> None:
    """Dispatch to the appropriate Threads workflow."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    run_bridge_main(ThreadsDispatch, usage="threads_bridge <config_path>",
                    report_error=_report_entry_error, messages={MISSING_CONFIG: "No config file provided"},
                    catch_crashes=False)


def dispatch(config: dict) -> None:
    """Run the workflow of `config` and exit with its outcome."""
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
