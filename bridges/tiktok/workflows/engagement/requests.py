#!/usr/bin/env python3
"""TikTok message-requests workflow bridge runner (inbox v2 - Phase 3).

Deux modes (champ ``mode``) :
- ``scrape`` (défaut) : ouvre la page « Demandes de messages », liste les demandes et émet un
  event ``message_request`` par item (sans agir).
- ``execute`` : applique les décisions (champ ``decisions`` : liste de
  {username, action: 'accept'|'decline', message?}) — accepte/refuse, et répond après acceptation
  si un message est fourni. Émet un ``request_result`` par décision.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.engagement.runtime.dm_callbacks import (
    wire_message_requests_read_callbacks,
    wire_request_decision_callbacks,
)


def run_message_requests_workflow(config: Dict[str, Any]):
    """Run the TikTok message-requests workflow (scrape ou execute)."""
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
        workflow = DMWorkflow(
            manager.device_manager.device,
            DMConfig(delay_between_conversations=config.get("delayBetweenActions", 1.0)),
        )
        set_workflow(workflow)

        if mode == "execute":
            decisions = config.get("decisions", [])
            if not decisions:
                send_error("No decisions to process")
                return False

            logger.info(f"📥 Traitement de {len(decisions)} demande(s) sur {device_id}")
            send_status("running", f"Processing {len(decisions)} request(s)")

            wire_request_decision_callbacks(workflow)
            results = workflow.process_message_requests(decisions)
            done = sum(1 for r in results if r.get("success"))

            logger.success(f"✅ Demandes traitées : {done}/{len(decisions)}")
            send_status("completed", f"Processed {done}/{len(decisions)} requests")
            return True

        # mode == "scrape"
        max_items = config.get("maxItems", 30)
        logger.info(f"📥 Scrape des demandes de messages sur {device_id} (max {max_items})")
        send_status("running", "Reading message requests")

        wire_message_requests_read_callbacks(workflow)
        requests = workflow.read_message_requests(max_items=max_items)

        logger.success(f"✅ {len(requests)} demande(s) listée(s)")
        send_status("completed", f"Listed {len(requests)} message requests")
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Message requests error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
