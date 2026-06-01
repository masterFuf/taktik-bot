#!/usr/bin/env python3
"""
TikTok Scraping Bridge - Scrape profiles from TikTok (followers, following, hashtag)
Runs as standalone script, reads config from stdin
"""

import sys
import time
import json
from typing import Dict, Any

from bridges.tiktok.runtime.ipc import (
    logger, send_status, send_message, send_error, set_workflow, get_workflow
)
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.scraping.runtime.events import (
    send_scraped_profile,
    send_scraping_completed,
    send_scraping_progress,
)
from bridges.tiktok.scraping.runtime.persistence import (
    save_scraped_profile,
    save_scraping_session,
    update_scraping_session,
)


def run_scraping_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok scraping workflow."""
    from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.tiktok.actions.business.workflows.scraping.workflow import (
        ScrapingWorkflow, ScrapingConfig
    )

    device_id = config.get('deviceId')
    if not device_id:
        send_error("No device ID provided")
        return False

    enrich_profiles = config.get('enrichProfiles', True)
    max_profiles_to_enrich = config.get('maxProfilesToEnrich', 50)
    save_to_db = config.get('saveToDb', True)

    logger.info(f"Starting TikTok Scraping workflow on device: {device_id}")
    logger.info(f"Enrichment: {'enabled' if enrich_profiles else 'disabled'}, max: {max_profiles_to_enrich}")
    send_status("starting", "Initializing TikTok Scraping workflow")

    try:
        # Common startup: connect, restart, navigate home
        manager, _ = tiktok_startup(device_id, fetch_profile=True)
        device = manager.device_manager.device
        navigation = NavigationActions(device)

        # Build core config
        scrape_type = config.get('type', 'target')
        target_scrape_type = config.get('scrapeType', 'followers')

        wf_config = ScrapingConfig(
            scrape_type=scrape_type,
            target_usernames=config.get('targetUsernames', []),
            target_scrape_type=target_scrape_type,
            hashtag=config.get('hashtag', ''),
            max_profiles=config.get('maxProfiles', 500),
            max_videos=config.get('maxPosts', 50),
            enrich_profiles=enrich_profiles,
            max_profiles_to_enrich=max_profiles_to_enrich,
        )

        workflow = ScrapingWorkflow(device, navigation, wf_config)
        set_workflow(workflow)

        # Create DB session
        session_id = None
        if save_to_db:
            target_usernames = config.get('targetUsernames', [])
            source_name = target_usernames[0] if target_usernames else config.get('hashtag', '')
            session_id = save_scraping_session(
                source_type=target_scrape_type.upper() if scrape_type == 'target' else 'HASHTAG',
                source_name=source_name,
                total_scraped=0,
                status='RUNNING',
                duration_seconds=0,
                platform='tiktok'
            )

        # Wire IPC + DB callbacks
        workflow.set_on_status_callback(lambda s, m: send_status(s, m))
        workflow.set_on_progress_callback(lambda scraped, total, current: send_scraping_progress(scraped, total, current))
        workflow.set_on_profile_callback(lambda p: send_scraped_profile(p))
        workflow.set_on_error_callback(lambda m: send_error(m))

        if save_to_db and session_id:
            workflow.set_on_save_profile_callback(
                lambda p: save_scraped_profile(session_id, p, 'tiktok')
            )

        # Run
        start_time = time.time()
        all_profiles = workflow.run()
        duration = int(time.time() - start_time)

        # Finalize DB session
        if save_to_db and session_id:
            update_scraping_session(
                session_id,
                len(all_profiles),
                'COMPLETED' if not workflow.stopped else 'STOPPED',
                duration
            )

        send_scraping_completed(len(all_profiles))
        send_status("completed", f"Scraped {len(all_profiles)} profiles")
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Scraping workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


def signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {signum}, stopping workflow...")
    workflow = get_workflow()
    if workflow:
        workflow.stop()
    sys.exit(0)


def main():
    """Main entry point - reads config from stdin."""
    logger.info("TikTok Scraping Bridge started")

    # Register signal handlers for graceful shutdown
    import signal
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Read config from stdin
        config_line = sys.stdin.readline()
        if not config_line:
            send_error("No configuration received")
            sys.exit(1)

        config = json.loads(config_line)
        logger.info(f"Received config: {json.dumps(config, indent=2)[:500]}...")

        # Run workflow
        success = run_scraping_workflow(config)

        if not success:
            sys.exit(1)

    except json.JSONDecodeError as e:
        send_error(f"Invalid JSON config: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Scraping error: {e}", exc_info=True)
        send_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
