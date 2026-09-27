"""Every declared workflow contract, in one place: what the generator and the gates read."""

from __future__ import annotations

from typing import Dict, Tuple

from . import (
    accounts,
    instagram_agent,
    instagram_automation,
    instagram_engagement,
    instagram_scraping,
    publish,
    tasks,
    threads,
    tiktok,
    tiktok_automation,
    tiktok_engagement,
    tiktok_profiles,
)
from .schema import WorkflowContract

WORKFLOW_CONTRACTS: Tuple[WorkflowContract, ...] = (
    *tiktok.CONTRACTS,
    *tiktok_automation.CONTRACTS,
    *tiktok_profiles.CONTRACTS,
    *tiktok_engagement.CONTRACTS,
    *instagram_automation.CONTRACTS,
    *instagram_scraping.CONTRACTS,
    *instagram_engagement.CONTRACTS,
    *instagram_agent.CONTRACTS,
    *accounts.CONTRACTS,
    *threads.CONTRACTS,
    *tasks.CONTRACTS,
    *publish.CONTRACTS,
)


def contracts_by_id() -> Dict[str, WorkflowContract]:
    """Every id of the manifest a declaration covers, its own and the ones it shares (`also`)."""
    return {
        workflow_id: contract
        for contract in WORKFLOW_CONTRACTS
        for workflow_id in (contract.workflow_id, *contract.also)
    }


__all__ = ["WORKFLOW_CONTRACTS", "contracts_by_id"]
