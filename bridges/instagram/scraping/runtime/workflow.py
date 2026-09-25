"""Workflow runner for the Instagram scraping bridge.

The run is `run_instagram_scraping`, the launcher the Agent handlers `instagram.scraping.*` (and so
the CLI) call too, called by name so the app's config contract test can follow the payload. The
bridge brings its stdout IPC, its AI service factory and the result shape the desktop reads.
"""

from __future__ import annotations

from bridges.instagram.runtime.ipc import _ipc
from bridges.instagram.scraping.runtime.ai import build_scraping_ai_service


def run_scraping_workflow(device_manager, bridge_config: dict) -> dict:
    from taktik.core.social_media.instagram.workflows.scraping.agent_handler import run_instagram_scraping

    result = run_instagram_scraping(
        bridge_config,
        device_manager=device_manager,
        ai_notifier=_ipc,
        instagram_scraping_ai_service=build_scraping_ai_service,
    )

    return {
        "success": result.get('success', False),
        "totalScraped": result.get('total_scraped', 0),
        # Le pourquoi, a cote du combien. Le bridge ACHEMINE ce verdict, il ne le calcule pas :
        # seul le workflow sait distinguer « cette cible n'avait rien » de « on n'y est jamais
        # arrive », et cette nuance est ce qui separe un run sain d'une panne silencieuse.
        "completionReason": result.get('completion_reason'),
        "error": result.get('error'),
    }
