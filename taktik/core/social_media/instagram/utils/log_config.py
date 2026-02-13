"""
Configuration du logging pour Instagram.

Ce module configure le logger pour le module Instagram avec des formats de sortie personnalisés
et des gestionnaires de logs appropriés.
"""

import logging
import sys
from typing import Optional, Dict, Any
from pathlib import Path
from loguru import logger

class InterceptHandler(logging.Handler):
    """Redirige les logs de logging vers loguru."""
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logger(
    name: str = "instagram",
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    rotation: str = "10 MB",
    retention: str = "30 days",
    serialize: bool = False,
    backtrace: bool = True,
    diagnose: bool = False,
) -> logger:
    """
    Configure le logger pour le module Instagram.

    Args:
        name: Nom du logger
        log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Fichier de sortie pour les logs (optionnel)
        rotation: Rotation des fichiers de log (ex: "10 MB", "1 day")
        retention: Rétention des fichiers de log (ex: "30 days")
        serialize: Si True, sérialise les logs en JSON
        backtrace: Si True, inclut la trace complète dans les logs d'erreur
        diagnose: Si True, affiche les variables locales dans les logs d'erreur

    Returns:
        Instance du logger configuré
    """
    # Configuration des logs
    log_config = {
        "handlers": [
            {
                "sink": sys.stderr,
                "format": "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                         "<level>{level: <8}</level> | "
                         "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
            }
        ],
        "levels": [
            {"name": "DEBUG", "color": "<blue>"},
            {"name": "INFO", "color": "<green>"},
            {"name": "WARNING", "color": "<yellow>"},
            {"name": "ERROR", "color": "<red>"},
            {"name": "CRITICAL", "color": "<red><bold>"},
        ]
    }

    # Ajout d'un fichier de log si spécifié
    if log_file:
        log_config["handlers"].append({
            "sink": log_file,
            "rotation": rotation,
            "retention": retention,
            "serialize": serialize,
            "enqueue": True,
            "backtrace": backtrace,
            "diagnose": diagnose,
            "level": log_level,
        })

    # Configuration du logger
    logger.configure(**log_config)
    logger.level("INFO", color="<green>")
    logger.level("WARNING", color="<yellow>")
    logger.level("ERROR", color="<red>")
    
    # Intercepter les logs de la bibliothèque standard
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Désactiver les logs trop verbeux
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uiautomator2").setLevel(logging.WARNING)
    
    # Retourner une instance du logger avec le nom spécifié
    return logger.bind(module=f"instagram.{name}")

# Créer une instance par défaut du logger
instagram_logger = setup_logger()
