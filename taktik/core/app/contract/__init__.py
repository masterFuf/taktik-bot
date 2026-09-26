"""The bot/app contract, declared once: settings each workflow reads, lines each bridge prints.

`schema` is the vocabulary, `shared` what every bridge shares, one module per platform declares its
workflows, `registry` lists them. Plain data that imports no workflow: the generator of the app's
types (`scripts/workflow_contract.py`) never builds a run nor touches a phone.
"""

from .registry import WORKFLOW_CONTRACTS, contracts_by_id
from .schema import WorkflowContract

__all__ = ["WORKFLOW_CONTRACTS", "WorkflowContract", "contracts_by_id"]
