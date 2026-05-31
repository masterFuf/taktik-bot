"""Compatibility shim for the OpenRouter AI provider.

The runtime owner is `taktik.core.ai.openrouter`. Bridges can import the
canonical owner directly; this module only keeps historical imports working.
"""

from taktik.core.ai.openrouter import AIService, DEFAULT_TEXT_MODEL, DEFAULT_VISION_MODEL

__all__ = ["AIService", "DEFAULT_TEXT_MODEL", "DEFAULT_VISION_MODEL"]
