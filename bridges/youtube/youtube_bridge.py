#!/usr/bin/env python3
"""
YouTube Bridge - Main dispatcher for YouTube workflows.
Routes to specific workflow bridges based on workflowType in config.
"""

import sys
import os
import json

_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.youtube.base import logger, send_error


def main():
    """Main entry point - dispatch to appropriate workflow bridge."""
    if len(sys.argv) < 2:
        send_error("No config file provided")
        logger.error("No config file provided")
        sys.exit(1)

    config_path = sys.argv[1]

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        send_error(f"Failed to load config: {e}")
        logger.error(f"Failed to load config from {config_path}: {e}")
        sys.exit(1)

    workflow_type = config.get('workflowType', 'watch_feed')
    device_id = config.get('deviceId', 'unknown')

    logger.info(f"▶️  YouTube Bridge starting - workflow: {workflow_type}, device: {device_id}")

    try:
        if workflow_type == 'watch_feed':
            # TODO: implement watch_feed_bridge
            send_error(f"Workflow '{workflow_type}' not yet implemented")
            sys.exit(1)

        elif workflow_type == 'search':
            # TODO: implement search_bridge
            send_error(f"Workflow '{workflow_type}' not yet implemented")
            sys.exit(1)

        else:
            send_error(f"Unknown workflowType: {workflow_type}")
            logger.error(f"Unknown workflowType: {workflow_type}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("YouTube Bridge interrupted by user")
        sys.exit(0)
    except Exception as e:
        send_error(str(e))
        logger.exception(f"Unhandled exception in YouTube Bridge: {e}")
        sys.exit(1)
    finally:
        from bridges.common.app_manager import force_stop_app
        force_stop_app(device_id, "youtube")


if __name__ == '__main__':
    main()
