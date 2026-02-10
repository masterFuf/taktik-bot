"""Backward-compatible re-export. Actual implementation moved to feed/workflow.py"""

from .feed.workflow import FeedBusiness

__all__ = ["FeedBusiness"]
