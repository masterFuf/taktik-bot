#!/usr/bin/env python3
"""TikTok unreplied-conversations workflow bridge runner (inbox v2 - Phase 2).

Mode SCRAPE uniquement : ouvre la messagerie, liste les conversations en marquant celles
non-répondues (dernier message = eux), et émet un event ``unreplied_conversation`` par item.
La RÉPONSE aux conversations sélectionnées réutilise le workflow ``dm_send`` existant.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.engagement.runtime.dm_callbacks import wire_unreplied_callbacks


def run_unreplied_workflow(config: Dict[str, Any]):
    """Run the TikTok unreplied-conversations scrape workflow."""
    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    max_items = config.get("maxItems", 30)
    only_unreplied = config.get("onlyUnreplied", True)

    logger.info(f"📨 Scrape conversations non-répondues sur {device_id} (max {max_items})")
    send_status("running", "Reading conversations")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import (
            DMConfig,
            DMWorkflow,
        )

        manager, _ = tiktok_startup(device_id, fetch_profile=True)
        workflow = DMWorkflow(manager.device_manager.device, DMConfig())
        set_workflow(workflow)
        wire_unreplied_callbacks(workflow)

        conversations = workflow.read_unreplied_conversations(
            max_items=max_items, only_unreplied=only_unreplied
        )
        unreplied = sum(1 for c in conversations if c.get("unreplied"))

        logger.success(f"✅ {len(conversations)} conversation(s), {unreplied} non-répondue(s)")
        send_status("completed", f"{unreplied} unreplied / {len(conversations)} conversations")
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Unreplied scrape error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
