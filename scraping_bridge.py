#!/usr/bin/env python3
"""
Scraping Bridge for TAKTIK Desktop
Connects the Electron app to the Python scraping workflow
"""

import sys
import json
import os

# Force UTF-8 encoding for stdout/stderr to support emojis on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import ScrapingWorkflow
from loguru import logger

# Configure loguru for UTF-8 output
logger.remove()
logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}", level="DEBUG", colorize=False)

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No config file provided"}))
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Failed to load config: {e}"}))
        sys.exit(1)
    
    device_id = config.get('deviceId')
    if not device_id:
        print(json.dumps({"success": False, "error": "No deviceId provided"}))
        sys.exit(1)
    
    device_manager = None
    try:
        # Initialize device manager
        logger.info(f"Connecting to device: {device_id}")
        device_manager = DeviceManager(device_id=device_id)
        
        if not device_manager.connect():
            print(json.dumps({"success": False, "error": "Failed to connect to device"}))
            sys.exit(1)
        
        # Build scraping config
        scraping_config = {
            'type': config.get('type', 'target'),
            'session_duration_minutes': config.get('sessionDurationMinutes', 60),
            'max_profiles': config.get('maxProfiles', 500),
            'export_csv': config.get('exportCsv', True),
            'save_to_db': config.get('saveToDb', True),
        }
        
        # Type-specific config
        if config.get('type') == 'target':
            scraping_config['target_usernames'] = config.get('targetUsernames', [])
            scraping_config['scrape_type'] = config.get('scrapeType', 'followers')
        elif config.get('type') == 'hashtag':
            scraping_config['hashtag'] = config.get('hashtag', '')
            scraping_config['scrape_type'] = config.get('scrapeType', 'authors')
            scraping_config['max_posts'] = config.get('maxPosts', 50)
        elif config.get('type') == 'post_url':
            scraping_config['post_url'] = config.get('postUrl', '')
            # Extract post ID from URL
            import re
            match = re.search(r'/p/([^/]+)/', config.get('postUrl', ''))
            if match:
                scraping_config['post_id'] = match.group(1)
            else:
                # Try reel URL format
                match = re.search(r'/reel/([^/]+)/', config.get('postUrl', ''))
                if match:
                    scraping_config['post_id'] = match.group(1)
                else:
                    scraping_config['post_id'] = 'unknown'
        
        # Run scraping workflow
        logger.info(f"Starting scraping workflow: {scraping_config['type']}")
        workflow = ScrapingWorkflow(device_manager, scraping_config)
        result = workflow.run()
        
        # Output result as JSON for Electron to parse
        print(json.dumps({
            "success": result.get('success', False),
            "totalScraped": result.get('total_scraped', 0),
            "error": result.get('error')
        }))
        
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        if device_manager:
            try:
                device_manager.disconnect()
            except:
                pass

if __name__ == '__main__':
    main()
