"""The one rule that tells whether a run asks for the AI, and so needs a key.

The declaration is on the workflow (`WorkflowContract.ai_request`, `schema.py`): the settings that turn
the AI on (the run's `ai` block switched on, its messages written by an AI), or none, for a workflow whose
every run asks (the Taktik Agent). This is the only reader of it. The CLI refuses a run that asks without a usable key by it
(`missing_ai_key`, `contract/error_codes.py`), and a host that launches runs elsewhere can read the same
declaration instead of keeping a table of its own.

A workflow that declares no request never asks, whatever its payload carries, and so does an id nobody
declares: the declarations are held to the settings that read an AI key by
`tests/unit/contract/test_workflow_contract_ai_request.py`, so a workflow that can use the AI cannot be
left out without the tests saying so.
"""

from __future__ import annotations

from typing import Any, Mapping

from .bounds import holds
from .registry import contracts_by_id


def asks_for_ai(workflow_id: str, payload: Mapping[str, Any]) -> bool:
    """True when a run of `workflow_id` with these settings asks for the AI (so needs an AI key).

    `payload` is what the launcher reads: the settings of the run, under the names the declaration gives
    them or their aliases (`messageMode` or `message_mode`), a missing one at its declared default.
    """
    contract = contracts_by_id().get(workflow_id)
    if contract is None or contract.ai_request is None:
        return False
    return holds(contract.settings, payload, contract.ai_request.when)


__all__ = ["asks_for_ai"]
