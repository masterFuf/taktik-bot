"""
⚙️ Configuration et système.

Ce package contient les modules de configuration globale
et de gestion des licences.
"""

from .config import ConfigBusiness
from .license import LicenseBusiness

__all__ = [
    'ConfigBusiness',
    'LicenseBusiness'
]
