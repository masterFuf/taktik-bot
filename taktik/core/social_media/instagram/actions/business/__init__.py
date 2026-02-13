"""
Couche business - Logique métier pour Instagram.

Structure organisée:
- 🎯 workflows/ : Workflows principaux d'acquisition utilisateurs
- ⚡ actions/ : Actions réutilisables (like, story, interaction)
- 🛠️ management/ : Gestion de données (profils, contenu, filtrage)
- ⚙️ system/ : Configuration et licences
- 🗂️ legacy/ : Code legacy conservé pour compatibilité
- 🛠️ common/ : Utilitaires communs

Tous les imports historiques restent compatibles.
"""

# Imports depuis les sous-packages
from .workflows import PostUrlBusiness, HashtagBusiness, FollowerBusiness
from .actions import LikeBusiness, StoryBusiness
from .management import ProfileBusiness, ContentBusiness, FilteringBusiness
from .system import ConfigBusiness
from .common import DatabaseHelpers

__all__ = [
    # Workflows
    'HashtagBusiness',
    'FollowerBusiness',
    'PostUrlBusiness',
    # Actions
    'LikeBusiness',
    'StoryBusiness',
    # Management
    'ProfileBusiness',
    'ContentBusiness',
    'FilteringBusiness',
    # System
    'ConfigBusiness',
    # Common
    'DatabaseHelpers'
]
