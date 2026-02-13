"""IPC event emission — centralized bridge communication.

Single point for all IPC events sent to the Electron frontend.
Eliminates duplicated try/except ImportError blocks across 6+ files.
"""

from .emitter import IPCEmitter

__all__ = ['IPCEmitter']
