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
from taktik.core.social_media.instagram.actions.business.workflows import PostUrlBusiness, HashtagBusiness, FollowerBusiness
from taktik.core.social_media.instagram.actions.business.actions import LikeBusiness, StoryBusiness
from taktik.core.social_media.instagram.actions.business.management import ProfileBusiness, ContentBusiness, FilteringBusiness
from taktik.core.social_media.instagram.actions.business.system import ConfigBusiness

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
