"""The bot/app contract, declared once: settings each workflow reads, lines each bridge prints.

`schema` is the vocabulary, `shared` what every bridge shares, `stop_reasons` the catalogues of why
a run ends, one module per platform declares its workflows, `diagnostics` the lines of the
diagnostic tools, `registry` lists them. Plain data that imports no workflow: the generator of the app's
types (`scripts/workflow_contract.py`) never builds a run nor touches a phone.
"""

from .registry import TOOL_CONTRACTS, WORKFLOW_CONTRACTS, contracts_by_id
from .schema import ToolContract, WorkflowContract

__all__ = ["TOOL_CONTRACTS", "ToolContract", "WORKFLOW_CONTRACTS", "WorkflowContract", "contracts_by_id"]
