"""
Taktik Automation Module
========================

Module d'automatisation programmatique pour Instagram et TikTok.
Permet de lancer des sessions sans passer par la CLI interactive.

Usage:
    # Depuis un fichier de config
    from taktik.core.automation import SessionRunner
    runner = SessionRunner.from_config("config.json")
    result = runner.execute()
    
    # Depuis un dictionnaire
    config = {
        "platform": "instagram",
        "device_id": "emulator-5566",
        "account": {...},
        "workflow": {...}
    }
    runner = SessionRunner.from_dict(config)
    result = runner.execute()

CLI:
    python -m taktik.core.automation --config my_config.json
    python -m taktik.core.automation --config my_config.json --dry-run
"""

from .session_runner import SessionRunner
from .config_loader import ConfigLoader
from .device_registry import DeviceRegistry
from .result_handler import SessionResult

__all__ = [
    'SessionRunner',
    'ConfigLoader',
    'DeviceRegistry',
    'SessionResult',
]

__version__ = '1.0.0'
