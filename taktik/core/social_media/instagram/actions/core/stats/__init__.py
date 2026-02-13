"""Real-time statistics — workflow stats tracking and display.

Sub-modules:
- stats_manager.py    — BaseStatsManager (real-time counters, display, IPC callback)
- workflow_stats.py   — Standardized stats dict factory for all workflow types
"""

from .stats_manager import BaseStatsManager, create_stats_manager
from .workflow_stats import create_workflow_stats, sync_aliases

__all__ = ['BaseStatsManager', 'create_stats_manager', 'create_workflow_stats', 'sync_aliases']
