#!/usr/bin/env python3
"""
Discovery Bridge V2 for TAKTIK Desktop
Uses DiscoveryWorkflowV2 with:
- Modular post scraping (likers + comments with replies)
- Progress tracking for resume capability
- Sequential execution: profile -> posts -> likers -> comments -> next post
"""
import sys
import json
import os

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.connection import ConnectionService
from bridges.common.signal_handler import setup_signal_handlers
from taktik.core.social_media.instagram.workflows.discovery import DiscoveryWorkflowV2
from taktik.core.database import configure_db_service
from loguru import logger

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
    
    api_key = config.get('apiKey') or os.environ.get('TAKTIK_API_KEY', 'local-mode')
    try:
        configure_db_service(api_key, use_local=True)
    except Exception as e:
        logger.warning(f"Could not configure db service: {e}")
    
    try:
        # Build V2 config
        discovery_config = {
            'campaign_name': config.get('campaignName', 'Discovery'),
            'account_id': config.get('accountId', 1),
            'niche_keywords': config.get('nicheKeywords', []),
            'targets': config.get('targetAccounts', []),
            'hashtags': config.get('hashtags', []),
            'post_urls': config.get('postUrls', []),
            'max_posts_per_source': config.get('maxPostsPerSource', 5),
            'max_likers_per_post': config.get('maxLikersPerPost', 100),
            'max_comments_per_post': config.get('maxCommentsPerPost', 200),
            'enrich_profiles': config.get('enrichProfiles', True),
            'max_profiles_to_enrich': config.get('maxProfilesToEnrich', 50),
            'comment_sort': config.get('commentSort', 'most_recent'),
            'session_duration_minutes': config.get('sessionDurationMinutes', 60),
            'resume': config.get('resume', False),
            'campaign_id': config.get('campaignId'),
        }
        
        logger.info(f"Starting Discovery V2 on device {device_id}")
        logger.info(f"Targets: {len(discovery_config['targets'])}, Hashtags: {len(discovery_config['hashtags'])}, Posts: {len(discovery_config['post_urls'])}")
        
        workflow = DiscoveryWorkflowV2(device_id, discovery_config)
        result = workflow.run()
        
        print(json.dumps(result))
        
    except Exception as e:
        logger.error(f"Discovery error: {e}")
        import traceback
        traceback.print_exc()
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()
