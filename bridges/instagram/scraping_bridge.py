#!/usr/bin/env python3
"""
Scraping Bridge for TAKTIK Desktop
Connects the Electron app to the Python scraping workflow
"""

import sys
import json
import os
import threading

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.connection import ConnectionService
from bridges.common.signal_handler import setup_signal_handlers
from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import ScrapingWorkflow
from taktik.core.database import configure_db_service
from loguru import logger

# Signal handlers for graceful shutdown
setup_signal_handlers()

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
    
    # Configure database service with API key from config or environment
    api_key = config.get('apiKey') or os.environ.get('TAKTIK_API_KEY', 'local-mode')
    try:
        configure_db_service(api_key, use_local=True)
        logger.info("Database service configured (local mode)")
    except Exception as e:
        logger.warning(f"Could not configure database service: {e}")
    
    connection = ConnectionService(device_id)
    try:
        # Connect via ConnectionService
        if not connection.connect():
            print(json.dumps({"success": False, "error": "Failed to connect to device"}))
            sys.exit(1)
        device_manager = connection.device_manager
        
        # Build scraping config
        scraping_config = {
            'type': config.get('type', 'target'),
            'session_duration_minutes': config.get('sessionDurationMinutes', 60),
            'max_profiles': config.get('maxProfiles', 500),
            'export_csv': config.get('exportCsv', True),
            'save_to_db': config.get('saveToDb', True),
            'enrich_profiles': config.get('enrichProfiles', False),
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
        if scraping_config.get('enrich_profiles', False):
            logger.info("Enriched scraping enabled - will visit each profile for details")
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
        try:
            connection.disconnect()
        except:
            pass

if __name__ == '__main__':
    main()
