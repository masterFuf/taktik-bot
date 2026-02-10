"""
Backward-compatible re-export.
Actual implementation moved to common/followers_tracker.py
"""

from .common.followers_tracker import FollowersTracker

__all__ = ['FollowersTracker']
