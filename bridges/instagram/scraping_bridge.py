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
    
    try:
        configure_db_service()
        logger.info("Database service configured (local SQLite)")
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

        # Dedup filter:
        #   rescrapeAfterDays not set  → Python defaults: skip all known profiles
        #   rescrapeAfterDays = 0      → always re-scrape (dedup disabled)
        #   rescrapeAfterDays = N > 0  → skip profiles created within N days
        rescrape_after_days = config.get('rescrapeAfterDays')
        if rescrape_after_days is not None:
            scraping_config['rescrape_after_days'] = int(rescrape_after_days)

        # Type-specific config
        if config.get('type') == 'target':
            scraping_config['target_usernames'] = config.get('targetUsernames', [])
            scraping_config['scrape_type'] = config.get('scrapeType', 'followers')
            # Posts sub-options
            scraping_config['scrape_post_likers'] = config.get('scrapePostLikers', True)
            scraping_config['scrape_post_commenters'] = config.get('scrapePostCommenters', False)
        elif config.get('type') == 'hashtag':
            # Frontend sends 'hashtags' (array); fall back to legacy 'hashtag' (string)
            hashtags = config.get('hashtags') or []
            if not hashtags and config.get('hashtag'):
                hashtags = [config.get('hashtag')]
            scraping_config['hashtags'] = hashtags
            scraping_config['hashtag'] = hashtags[0] if hashtags else ''  # backward compat
            scraping_config['scrape_likers'] = config.get('scrapeHashtagLikers', True)
            scraping_config['scrape_commenters'] = config.get('scrapeHashtagCommenters', False)
            scraping_config['max_posts'] = config.get('maxPosts', 50)
        elif config.get('type') == 'post_url':
            # Frontend sends 'postUrls' (array); fall back to legacy 'postUrl' (string)
            post_urls = config.get('postUrls') or []
            if not post_urls and config.get('postUrl'):
                post_urls = [config.get('postUrl')]
            scraping_config['post_urls'] = post_urls
            scraping_config['post_url'] = post_urls[0] if post_urls else ''  # backward compat
            scraping_config['scrape_likers'] = config.get('scrapePostUrlLikers', True)
            scraping_config['scrape_commenters'] = config.get('scrapePostUrlCommenters', False)
            # Extract post ID from first URL (legacy single-url field)
            import re
            first_url = post_urls[0] if post_urls else ''
            match = re.search(r'/p/([^/]+)/', first_url)
            if match:
                scraping_config['post_id'] = match.group(1)
            else:
                match = re.search(r'/reel/([^/]+)/', first_url)
                scraping_config['post_id'] = match.group(1) if match else 'unknown'
        
        # AI Mode config
        ai_config = config.get('ai', {})
        if ai_config and ai_config.get('enabled'):
            scraping_config['ai_mode'] = True
            scraping_config['ai_profile_analysis'] = ai_config.get('profileAnalysis', True)
            scraping_config['ai_niche'] = ai_config.get('niche', '')
            scraping_config['ai_qualification_prompt'] = ai_config.get('qualificationPrompt', '')
            scraping_config['openrouter_api_key'] = ai_config.get('openrouterApiKey', '')
            scraping_config['vision_model'] = ai_config.get('visionModel', '')
            # When re-scraping existing profiles in AI mode: 'full' = redo screenshot+AI, 'stats_only' = skip AI
            scraping_config['ai_rescrape_mode'] = config.get('aiRescrapeMode', 'full')
        else:
            scraping_config['ai_mode'] = False

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
        except Exception:
            pass

if __name__ == '__main__':
    main()
