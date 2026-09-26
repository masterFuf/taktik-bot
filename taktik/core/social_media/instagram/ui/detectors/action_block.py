"""Where an Instagram business action keeps its block detector.

The detection is `ProblematicPageDetector.is_action_blocked`; the look after a gesture is the
shared `look_for_action_block` (`shared/diagnostics/action_block.py`).
"""

from __future__ import annotations

from typing import Any, Optional


def detector_of(owner: Any) -> Optional[Any]:
    """The production detector a business action carries (`nav_actions.problematic_page_detector`)."""
    return getattr(getattr(owner, 'nav_actions', None), 'problematic_page_detector', None)


__all__ = ['detector_of']
