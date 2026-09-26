"""Every declared workflow contract, in one place: what the generator and the gates read."""

from __future__ import annotations

from typing import Dict, Tuple

from . import tiktok
from .schema import WorkflowContract

WORKFLOW_CONTRACTS: Tuple[WorkflowContract, ...] = (*tiktok.CONTRACTS,)


def contracts_by_id() -> Dict[str, WorkflowContract]:
    return {contract.workflow_id: contract for contract in WORKFLOW_CONTRACTS}


__all__ = ["WORKFLOW_CONTRACTS", "contracts_by_id"]
