"""Every declared contract, in one place: what the generator and the gates read.

`WORKFLOW_CONTRACTS` the workflows of the manifest, `TOOL_CONTRACTS` the tools the app runs beside
them (their lines only): the diagnostic tools, the check of the DMs written by an AI.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from . import (
    accounts,
    ai_dm,
    diagnostics,
    instagram_agent,
    instagram_automation,
    instagram_engagement,
    instagram_notifications,
    instagram_scraping,
    publish,
    tasks,
    threads,
    tiktok,
    tiktok_automation,
    tiktok_engagement,
    tiktok_profiles,
)
from .schema import OneOf, ToolContract, WorkflowContract

WORKFLOW_CONTRACTS: Tuple[WorkflowContract, ...] = (
    *tiktok.CONTRACTS,
    *tiktok_automation.CONTRACTS,
    *tiktok_profiles.CONTRACTS,
    *tiktok_engagement.CONTRACTS,
    *instagram_automation.CONTRACTS,
    *instagram_scraping.CONTRACTS,
    *instagram_engagement.CONTRACTS,
    *instagram_notifications.CONTRACTS,
    *instagram_agent.CONTRACTS,
    *accounts.CONTRACTS,
    *threads.CONTRACTS,
    *tasks.CONTRACTS,
    *publish.CONTRACTS,
)

TOOL_CONTRACTS: Tuple[ToolContract, ...] = (*diagnostics.TOOLS, *ai_dm.TOOLS)


def contracts_by_id() -> Dict[str, WorkflowContract]:
    """Every id of the manifest a declaration covers, its own and the ones it shares (`also`)."""
    return {
        workflow_id: contract
        for contract in WORKFLOW_CONTRACTS
        for workflow_id in (contract.workflow_id, *contract.also)
    }


def selector_value(contract: WorkflowContract, workflow_id: str) -> Optional[str]:
    """The value of the declaration's selector that picks `workflow_id`: its last segment
    (`instagram.automation.<workflowType>`), when the declaration serves several ids. One declaration
    for one id (the notifications and their commands) keeps its selector as a setting."""
    if not contract.selector or not contract.also:
        return None
    value = workflow_id.rsplit(".", 1)[-1]
    allowed = contract.setting(contract.selector).type
    if not (isinstance(allowed, OneOf) and allowed.allows(value)):
        raise ValueError(f"{workflow_id}: `{value}` is no value of the selector `{contract.selector}`")
    return value


__all__ = ["TOOL_CONTRACTS", "WORKFLOW_CONTRACTS", "contracts_by_id", "selector_value"]
