"""
Module Core pour Taktik-Instagram.
Contient la logique métier principale de l'application.
"""

# Temporairement commenté pour éviter l'importation circulaire
# from .social_media.instagram.actions.core.device_facade import DeviceFacade, Direction
# from .device import DeviceManager  # Temporairement commenté - fichier renommé en .old

# Import conditionnel pour éviter les problèmes circulaires
def get_device_facade():
    """Retourne DeviceFacade de manière paresseuse."""
    from .social_media.instagram.actions.core.device_facade import DeviceFacade
    return DeviceFacade

def get_direction():
    """Retourne Direction de manière paresseuse."""
    from .social_media.instagram.actions.core.device_facade import Direction
    return Direction

__all__ = [
    'DeviceFacade',
    'Direction',
    'DeviceManager'
]
