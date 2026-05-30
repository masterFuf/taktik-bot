"""Compatibility shim for post surface selectors.

The legacy monolithic post selector catalog now lives under
`surfaces/post/detail.py` pending a finer split by sub-surface.
"""

from .surfaces.post import PostSelectors, POST_SELECTORS

__all__ = ["PostSelectors", "POST_SELECTORS"]
