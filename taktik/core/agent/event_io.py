"""JSON-safe AgentEvent serialization helpers."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from taktik.core.agent.contracts import AgentEvent


def agent_event_to_payload(event: AgentEvent) -> dict[str, Any]:
    """Serialize a runtime event into a JSON-safe dict."""
    return asdict(event)


def agent_events_to_payload(events: Iterable[AgentEvent]) -> list[dict[str, Any]]:
    """Serialize multiple runtime events into JSON-safe dicts."""
    return [agent_event_to_payload(event) for event in events]
