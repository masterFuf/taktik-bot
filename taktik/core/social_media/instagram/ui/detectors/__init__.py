"""UI detection utilities for Instagram automation."""

from .problematic_page import ProblematicPageDetector
from .scroll_end import ScrollEndDetector

__all__ = [
    'ProblematicPageDetector',
    'ScrollEndDetector'
]
