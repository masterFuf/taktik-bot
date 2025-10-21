"""
Utilitaires pour le dump de l'interface utilisateur Android.
"""
import os
import time
from datetime import datetime
from pathlib import Path
from loguru import logger

def dump_ui_hierarchy(device, output_dir: str = "ui_dumps"):
    try:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ui_dump_{timestamp}.xml"
        filepath = os.path.join(output_dir, filename)
        
        logger.info(f"Dumping de l'interface utilisateur vers {filepath}...")
        
        if hasattr(device, 'device') and hasattr(device.device, 'dump_hierarchy'):
            xml_hierarchy = device.device.dump_hierarchy()
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(xml_hierarchy)
        elif hasattr(device, 'dump_hierarchy'):
            xml_hierarchy = device.dump_hierarchy()
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(xml_hierarchy)
        else:
            xml_hierarchy = device.dump_hierarchy()
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(xml_hierarchy)
        
        logger.success(f"Dump de l'interface utilisateur sauvegardé dans {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"Erreur lors du dump de l'interface utilisateur: {e}")
        return None

def capture_screenshot(device, output_dir: str = "screenshots"):
    try:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)
        
        device.screenshot(filepath)
        
        logger.success(f"Capture d'écran sauvegardée dans {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"Erreur lors de la capture d'écran: {e}")
        return None
