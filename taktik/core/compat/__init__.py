"""
App Compatibility Framework — Core Module
Provides version-aware selector routing on top of existing ui/selectors modules.
"""

from .selector_registry import (
    VersionedSelectorRegistry,
    SelectorNotFound,
    SelectorEntry,
    build_full_selector_map,
    build_selector_map_from_dataclass,
)
from .setup import create_registry

__all__ = [
    'VersionedSelectorRegistry',
    'SelectorNotFound',
    'SelectorEntry',
    'build_full_selector_map',
    'build_selector_map_from_dataclass',
    'create_registry',
]
