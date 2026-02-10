"""
Backward-compatible re-export.
Actual implementation moved to workflows/messaging/workflow.py
"""

from .workflows.messaging.workflow import MessagingBusiness, send_dm

__all__ = ['MessagingBusiness', 'send_dm']
