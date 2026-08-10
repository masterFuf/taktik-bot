"""
Business layer.

Structure organisée:
- 🎯 workflows/ : Workflows principaux d'acquisition utilisateurs
- ⚡ actions/ : Actions réutilisables (like, story, interaction)
- 🛠️ management/ : Gestion de données (profils, contenu, filtrage)
- ⚙️ system/ : Configuration et licences
- legacy/ : legacy code kept for compatibility
- 🛠️ common/ : Utilitaires communs

Every historical import stays compatible.
"""

# Imports from the sub-packages
from .workflows import PostUrlBusiness, HashtagBusiness, FollowerBusiness
from .actions import LikeBusiness, StoryBusiness
from .management import ProfileBusiness, ContentBusiness, FilteringBusiness
from .system import ConfigBusiness

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
    'ConfigBusiness'
]
