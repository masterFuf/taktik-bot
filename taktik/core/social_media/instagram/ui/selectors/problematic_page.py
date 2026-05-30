"""Compatibility shim for shell blocking-state selectors."""

from .shell.blocking_states import ProblematicPageSelectors, PROBLEMATIC_PAGE_SELECTORS

__all__ = ["ProblematicPageSelectors", "PROBLEMATIC_PAGE_SELECTORS"]
