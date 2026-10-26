"""What every Agent handler reads the same way, whatever its platform.

`merge_invocation_payload` lays the step's own params over the payload the executor carries;
`value_param` reads a parameter under the first of its names that is set; `text_param` under the
first of its names that holds text; `package_name_from_payload` the app package a run starts.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

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


def text_param(payload: Mapping[str, Any], *names: str) -> Optional[str]:
    """The text under the first of `names` that holds some, spaces dropped; None: none does.

    A blank value counts as absent, so it never hides a name after it."""
    for name in names:
        value = payload.get(name)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def package_name_from_payload(payload: Mapping[str, Any]) -> Optional[str]:
    """The app package a run starts (a clone); None: the installed app.

    Instagram and TikTok alike: `packageName` (the app's key) or `package_name` (a CLI call, an
    Agent plan). Every launcher reads it here and hands it to the host's connection.
    """
    return text_param(payload, "packageName", "package_name")
