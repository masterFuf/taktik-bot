"""What every Agent handler reads the same way, whatever its platform.

`merge_invocation_payload` lays the step's own params over the payload the executor carries;
`value_param` reads a parameter under the first of its names that is set.
"""

from __future__ import annotations

from typing import Any, Mapping

from taktik.core.kernel.contracts import WorkflowInvocation


def merge_invocation_payload(invocation: WorkflowInvocation, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Merge executor variables and step params, keeping step params authoritative."""
    merged = dict(payload)
    merged.update(invocation.params)
    return merged


def value_param(payload: Mapping[str, Any], *names: str, default: Any) -> Any:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return value
    return default
