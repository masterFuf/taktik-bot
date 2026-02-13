"""
Module Core pour Taktik.
Contient la logique métier principale de l'application.
"""

# Import conditionnel pour éviter les problèmes circulaires
def get_device_facade():
    """Retourne DeviceFacade de manière paresseuse."""
    from .social_media.instagram.actions.core.device_facade import DeviceFacade
    return DeviceFacade

def get_direction():
    """Retourne Direction de manière paresseuse."""
    from .shared.device.facade import Direction
    return Direction

__all__ = [
    'DeviceFacade',
    'Direction',
    'DeviceManager'
]
