"""Dependency-injection ports for the Taktik Agent runtime kernel."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class AgentAIService(Protocol):
    """Minimal AI provider contract consumed by the agent runtime."""

    vision_model: str
    text_model: str

    # `kind` is the spend category the provider reports the call's cost under (see
    # `taktik.core.app.ai.spend`). Part of the contract, not an implementation detail: an
    # agent decision is a PAID call, and a provider that drops the kind makes it land in the
    # `other` bucket of the operator's cost breakdown.
    def vision_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        image_path: str,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        label: str = "vision",
        kind: str = "other",
    ) -> Dict[str, Any]:
        ...

    def text_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        label: str = "text",
        kind: str = "other",
    ) -> Dict[str, Any]:
        ...


class AgentAIServiceFactory(Protocol):
    """Factory injected by a bridge or a standalone caller."""

    def __call__(
        self,
        *,
        api_key: str,
        ipc: Any = None,
        vision_model: Optional[str] = None,
        text_model: Optional[str] = None,
    ) -> AgentAIService:
        ...
