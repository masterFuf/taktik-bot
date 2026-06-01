#!/usr/bin/env python3
"""TikTok workflow dispatcher entrypoint."""

import os
import sys


_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.tiktok.runtime.ipc import logger, send_error
from bridges.tiktok.workflows.runtime.dispatcher import (
    UnknownWorkflowError,
    dispatch_tiktok_workflow,
    force_stop_tiktok,
    load_dispatcher_config,
    reset_network_if_enabled,
)


def main():
    """Main entry point - dispatch to the configured TikTok workflow bridge."""
    config = load_dispatcher_config(sys.argv)
    if config is None:
        sys.exit(1)

    workflow_type = config.get("workflowType", "for_you")
    device_id = config.get("deviceId", "unknown")
    logger.info(f"ðŸŽµ TikTok Bridge starting - workflow: {workflow_type}, device: {device_id}")

    reset_network_if_enabled(config, device_id)

    try:
        success, workflow_type = dispatch_tiktok_workflow(config)

        if success:
            logger.success(f"âœ… TikTok {workflow_type} workflow completed successfully")
            sys.exit(0)

        logger.error(f"âŒ TikTok {workflow_type} workflow failed")
        sys.exit(1)

    except ImportError as e:
        send_error(f"Failed to import workflow module: {e}")
        logger.error(f"Import error: {e}")
        sys.exit(1)
    except UnknownWorkflowError:
        sys.exit(1)
    except Exception as e:
        send_error(f"Workflow error: {e}")
        logger.exception(f"Unexpected error in {workflow_type} workflow: {e}")
        sys.exit(1)
    finally:
        force_stop_tiktok(device_id)


if __name__ == "__main__":
    main()
