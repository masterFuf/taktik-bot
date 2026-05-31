"""
Common services for all bridges (Instagram & TikTok).
Eliminates code duplication across bridge files.
"""

from .bootstrap import setup_environment
from .ipc import IPC
from .device.connection import ConnectionService
from .device.app_manager import AppService
from .input.keyboard import KeyboardService
from .persistence.database import get_db_path, SentDMService
