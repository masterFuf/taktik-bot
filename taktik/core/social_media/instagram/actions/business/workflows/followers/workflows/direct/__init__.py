"""Direct followers workflow package.

Facade: re-exports FollowerDirectWorkflowMixin for full backward compatibility.

Internal structure:
- main_loop.py          — Main interaction loop (interact_with_followers_direct)
- profile_processing.py — Single follower processing (click → extract → filter → interact)
- navigation_helpers.py — Setup, recovery, empty screen, scroll/end detection
"""

from .main_loop import FollowerDirectWorkflowMixin

__all__ = ['FollowerDirectWorkflowMixin']
