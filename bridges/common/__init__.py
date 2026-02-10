"""
Common services for all bridges (Instagram & TikTok).
Eliminates code duplication across bridge files.
"""

from .bootstrap import setup_environment
from .ipc import IPC
from .connection import ConnectionService
from .app_manager import AppService
from .keyboard import KeyboardService
from .database import get_db_path, SentDMService
