"""Core security runtime exports."""

from taktik.core.security.protection.runtime import SecurityManager, protected_call

__all__ = ["protected_call", "SecurityManager"]
