#!/usr/bin/env python3
"""
TikTok Bridge - Main dispatcher for TikTok workflows
Routes to specific workflow bridges based on workflowType in config
"""

import sys
import json
from loguru import logger

# Configure loguru for stderr output
logger.remove()
logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}")


def send_error(message: str):
    """Send error message to frontend."""
    print(json.dumps({"type": "error", "message": message}), flush=True)


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
    
    workflow_type = config.get('workflowType', 'for_you')
    device_id = config.get('deviceId', 'unknown')
    
    logger.info(f"🎵 TikTok Bridge starting - workflow: {workflow_type}, device: {device_id}")
    
    try:
        if workflow_type == 'for_you':
            from bridges.tiktok.for_you_bridge import run_for_you_workflow
            success = run_for_you_workflow(config)
            
        elif workflow_type == 'search' or workflow_type == 'target':
            from bridges.tiktok.search_bridge import run_search_workflow
            success = run_search_workflow(config)
            
        elif workflow_type == 'followers':
            from bridges.tiktok.followers_bridge import run_followers_workflow
            success = run_followers_workflow(config)
            
        elif workflow_type == 'dm_read':
            from bridges.tiktok.dm_read_bridge import run_dm_read_workflow
            success = run_dm_read_workflow(config)
            
        elif workflow_type == 'dm_send':
            from bridges.tiktok.dm_send_bridge import run_dm_send_workflow
            success = run_dm_send_workflow(config)
            
        elif workflow_type == 'scraping':
            from bridges.tiktok.scraping_bridge import run_scraping_workflow
            success = run_scraping_workflow(config)
            
        else:
            send_error(f"Unknown workflow type: {workflow_type}")
            logger.error(f"Unknown workflow type: {workflow_type}")
            sys.exit(1)
        
        if success:
            logger.success(f"✅ TikTok {workflow_type} workflow completed successfully")
            sys.exit(0)
        else:
            logger.error(f"❌ TikTok {workflow_type} workflow failed")
            sys.exit(1)
            
    except ImportError as e:
        send_error(f"Failed to import workflow module: {e}")
        logger.error(f"Import error: {e}")
        sys.exit(1)
    except Exception as e:
        send_error(f"Workflow error: {e}")
        logger.exception(f"Unexpected error in {workflow_type} workflow: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
