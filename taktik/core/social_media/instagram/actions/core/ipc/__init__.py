"""IPC event emission — centralized bridge communication.

Single point for all IPC events sent to the Electron frontend.
Eliminates duplicated try/except ImportError blocks across 6+ files.
"""

from taktik.core.social_media.instagram.actions.core.ipc.emitter import IPCEmitter

__all__ = ['IPCEmitter']
