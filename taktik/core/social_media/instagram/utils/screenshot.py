"""
Gestion des captures d'écran pour le débogage.

Ce module fournit des fonctions pour capturer et enregistrer des captures d'écran
durant l'exécution des automations Instagram.
"""

import os
import time
from pathlib import Path
from typing import Optional, Union, Tuple
from datetime import datetime
import logging

from loguru import logger

# Créer un logger spécifique pour ce module
logger = logger.bind(module="instagram.utils.screenshot")

def take_screenshot(device, filename: Optional[str] = None, folder: str = "screenshots") -> Optional[bytes]:
    """
    Prend une capture d'écran de l'appareil.

    Args:
        device: Instance de l'appareil uiautomator2
        filename: Nom du fichier pour enregistrer la capture (optionnel)
        folder: Dossier de destination (par défaut: "screenshots")

    Returns:
        bytes: Données brutes de l'image ou None en cas d'erreur
    """
    try:
        # Créer le dossier de destination s'il n'existe pas
        os.makedirs(folder, exist_ok=True)
        
        # Générer un nom de fichier basé sur la date/heure si non spécifié
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"screenshot_{timestamp}.png"
        
        # S'assurer que le nom de fichier a l'extension .png
        if not filename.lower().endswith('.png'):
            filename += '.png'
        
        # Chemin complet du fichier
        filepath = os.path.join(folder, filename)
        
        # Prendre la capture d'écran
        screenshot = device.screenshot()
        
        # Sauvegarder l'image
        with open(filepath, "wb") as f:
            f.write(screenshot)
        
        logger.debug(f"Capture d'écran enregistrée: {filepath}")
        return screenshot
        
    except Exception as e:
        logger.error(f"Erreur lors de la capture d'écran: {e}")
        return None

def save_screenshot(screenshot_data: bytes, filename: str, folder: str = "screenshots") -> Optional[str]:
    """
    Enregistre des données brutes de capture d'écran dans un fichier.

    Args:
        screenshot_data: Données brutes de l'image
        filename: Nom du fichier de sortie
        folder: Dossier de destination (par défaut: "screenshots")

    Returns:
        str: Chemin du fichier enregistré ou None en cas d'erreur
    """
    try:
        # Créer le dossier de destination s'il n'existe pas
        os.makedirs(folder, exist_ok=True)
        
        # S'assurer que le nom de fichier a l'extension .png
        if not filename.lower().endswith('.png'):
            filename += '.png'
        
        # Chemin complet du fichier
        filepath = os.path.join(folder, filename)
        
        # Écrire les données dans le fichier
        with open(filepath, "wb") as f:
            f.write(screenshot_data)
        
        logger.debug(f"Capture d'écran enregistrée: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de la capture d'écran: {e}")
        return None

def take_and_save_screenshot(device, context: str = "", folder: str = "screenshots") -> Optional[str]:
    """
    Prend une capture d'écran et l'enregistre avec un nom basé sur le contexte.
    
    Args:
        device: Instance de l'appareil uiautomator2
        context: Contexte ou action en cours (sera inclus dans le nom du fichier)
        folder: Dossier de destination (par défaut: "screenshots")
        
    Returns:
        str: Chemin du fichier enregistré ou None en cas d'erreur
    """
    try:
        # Créer un nom de fichier basé sur le contexte et l'horodatage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        context_safe = "".join(c if c.isalnum() else "_" for c in context)
        filename = f"{timestamp}_{context_safe}.png" if context else f"{timestamp}.png"
        
        # Prendre et enregistrer la capture d'écran
        screenshot = take_screenshot(device, filename, folder)
        if screenshot is not None:
            return os.path.join(folder, filename)
        return None
        
    except Exception as e:
        logger.error(f"Erreur lors de la prise de capture d'écran: {e}")
        return None
