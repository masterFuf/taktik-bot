#!/usr/bin/env python3
"""TikTok new-followers workflow bridge runner (inbox v2 - Phase 1).

Deux modes (champ `mode` du config) :
- ``scrape`` (défaut) : ouvre la page « Nouveaux followers », liste les items et les émet en
  stdout JSON (event ``new_follower``) sans agir. Le front affiche + l'utilisateur sélectionne.
- ``follow_back`` : suit en retour les usernames sélectionnés (champ ``usernames``) et émet un
  event ``follow_back_result`` par username.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.engagement.runtime.dm_callbacks import (
    wire_follow_back_callbacks,
    wire_new_followers_read_callbacks,
)


def run_new_followers_workflow(config: Dict[str, Any]):
    """Run the TikTok new-followers workflow (scrape ou follow-back)."""
    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    mode = config.get("mode", "scrape")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import (
            DMConfig,
            DMWorkflow,
        )

        manager, _ = tiktok_startup(device_id, fetch_profile=True)

        workflow_config = DMConfig(
            delay_between_conversations=config.get("delayBetweenActions", 1.0),
        )
        workflow = DMWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)

        if mode == "follow_back":
            usernames = config.get("usernames", [])
            if not usernames:
                send_error("No usernames to follow back")
                return False

            logger.info(f"➕ Follow-back de {len(usernames)} follower(s) sur {device_id}")
            send_status("running", f"Following back {len(usernames)} follower(s)")

            wire_follow_back_callbacks(workflow)
            results = workflow.follow_back_users(usernames)
            done = sum(1 for r in results if r.get("success"))

            logger.success(f"✅ Follow-back terminé : {done}/{len(usernames)}")
            send_status("completed", f"Followed back {done}/{len(usernames)}")
            return True

        # mode == "scrape"
        max_items = config.get("maxItems", 50)
        logger.info(f"👥 Scrape des nouveaux followers sur {device_id} (max {max_items})")
        send_status("running", "Reading new followers")

        wire_new_followers_read_callbacks(workflow)
        followers = workflow.read_new_followers(max_items=max_items)

        logger.success(f"✅ {len(followers)} nouveaux followers listés")
        send_status("completed", f"Listed {len(followers)} new followers")
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"New followers error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
