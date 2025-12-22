#!/usr/bin/env python3
"""
Cold DM Bridge - Interface between Electron and Cold DM Workflow
"""

import sys
import json
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from taktik.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.workflows.cold_dm.cold_dm_workflow import ColdDMWorkflow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)

def main():
    if len(sys.argv) < 2:
        logger.error("Usage: cold_dm_bridge.py <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        # Load configuration
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        device_id = config['deviceId']
        logger.info(f"Starting Cold DM workflow for device: {device_id}")
        
        # Initialize device manager
        device_manager = DeviceManager()
        device = device_manager.get_device(device_id)
        
        if not device:
            logger.error(f"Device {device_id} not found")
            print(json.dumps({"success": False, "error": "Device not found"}))
            sys.exit(1)
        
        # Prepare workflow config
        cold_dm_config = {
            'recipients': config.get('recipients', []),
            'message_mode': config.get('messageMode', 'manual'),
            'messages': config.get('messages', []),
            'ai_prompt': config.get('aiPrompt', ''),
            'delay_min': config.get('delayMin', 30),
            'delay_max': config.get('delayMax', 60),
            'max_dms': config.get('maxDmsPerSession', 50),
            'skip_private': config.get('skipPrivateAccounts', True),
            'skip_verified': config.get('skipVerifiedAccounts', False),
        }
        
        logger.info(f"Cold DM config: {cold_dm_config['message_mode']} mode, {len(cold_dm_config['recipients'])} recipients")
        
        # Run Cold DM workflow
        workflow = ColdDMWorkflow(device_manager, cold_dm_config)
        result = workflow.run()
        
        # Output result as JSON for Electron to parse
        print(json.dumps({
            "success": result.get('success', False),
            "dmsSent": result.get('dms_sent', 0),
            "dmsSuccess": result.get('dms_success', 0),
            "dmsFailed": result.get('dms_failed', 0),
            "error": result.get('error')
        }))
        
    except Exception as e:
        logger.error(f"Cold DM workflow error: {e}", exc_info=True)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
