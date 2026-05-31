"""Dependency-injection ports for the Taktik Agent runtime kernel."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class AgentAIService(Protocol):
    """Minimal AI provider contract consumed by the agent runtime."""

    vision_model: str
    text_model: str

    def vision_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        image_path: str,
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        ...

    def text_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
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
