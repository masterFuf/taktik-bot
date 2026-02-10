# 📁 Architecture du dossier business/

> Dernière mise à jour : 10 février 2026

---

## 📊 Structure complète

```
business/
├── __init__.py                              # Exports rétrocompatibles (tous les *Business)
├── messaging.py                             # Re-export → workflows/messaging/
│
├── common/                                  # 🔧 Utilitaires partagés (business-level)
│   ├── __init__.py
│   ├── database_helpers.py                  # DatabaseHelpers (CRUD profils, interactions)
│   └── workflow_defaults.py                 # Configs par défaut de chaque workflow
│
├── workflows/                               # 🎯 Workflows d'acquisition utilisateurs
│   ├── __init__.py                          # Exporte tous les *Business
│   ├── _likers_common.py                    # Re-export → common/likers_base.py
│   ├── followers_tracker.py                 # Re-export → common/followers_tracker.py
│   ├── feed.py                              # Re-export → feed/workflow.py
│   ├── notifications.py                     # Re-export → notifications/workflow.py
│   │
│   ├── common/                              # 🔧 Code partagé entre workflows
│   │   ├── __init__.py
│   │   ├── likers_base.py                   # LikersWorkflowBase (base hashtag + post_url)
│   │   └── followers_tracker.py             # FollowersTracker (diagnostics navigation)
│   │
│   ├── hashtag/                             # #️⃣ Ciblage par hashtag
│   │   ├── __init__.py                      #   → HashtagBusiness
│   │   ├── workflow.py                      #   Orchestration principale
│   │   ├── extractors.py                    #   Re-export → mixins/
│   │   ├── post_finder.py                   #   Re-export → mixins/
│   │   └── mixins/
│   │       ├── __init__.py
│   │       ├── extractors.py                #   HashtagExtractorsMixin
│   │       └── post_finder.py               #   HashtagPostFinderMixin
│   │
│   ├── post_url/                            # 🔗 Ciblage likers d'un post URL
│   │   ├── __init__.py                      #   → PostUrlBusiness
│   │   ├── workflow.py                      #   Orchestration principale
│   │   ├── extractors.py                    #   Re-export → mixins/
│   │   ├── url_handling.py                  #   Re-export → mixins/
│   │   └── mixins/
│   │       ├── __init__.py
│   │       ├── extractors.py                #   PostUrlExtractorsMixin
│   │       └── url_handling.py              #   PostUrlHandlingMixin
│   │
│   ├── followers/                           # 👥 Ciblage followers d'un compte
│   │   ├── __init__.py                      #   → FollowerBusiness
│   │   ├── workflow.py                      #   Orchestration principale
│   │   ├── mixins/
│   │   │   ├── __init__.py
│   │   │   ├── checkpoints.py               #   Checkpoints & reprise de session
│   │   │   ├── extraction.py                #   Extraction de followers visibles
│   │   │   ├── interactions.py              #   Interactions sur profil
│   │   │   └── navigation.py                #   Navigation dans la liste
│   │   └── workflows/
│   │       ├── __init__.py
│   │       ├── direct.py                    #   FollowerDirectWorkflowMixin (principal)
│   │       ├── legacy.py                    #   Ancien workflow (rétrocompat)
│   │       └── multi_target.py              #   Multi-target followers
│   │
│   ├── unfollow/                            # ➖ Unfollow automatique
│   │   ├── __init__.py                      #   → UnfollowBusiness
│   │   ├── workflow.py                      #   Orchestration principale
│   │   ├── actions.py                       #   Re-export → mixins/
│   │   ├── decision.py                      #   Re-export → mixins/
│   │   └── mixins/
│   │       ├── __init__.py
│   │       ├── actions.py                   #   UnfollowActionsMixin
│   │       └── decision.py                  #   UnfollowDecisionMixin
│   │
│   ├── feed/                                # 📱 Interactions depuis le feed
│   │   ├── __init__.py                      #   → FeedBusiness
│   │   └── workflow.py                      #   Like/comment posts du feed
│   │
│   ├── notifications/                       # 🔔 Interactions depuis les notifications
│   │   ├── __init__.py                      #   → NotificationsBusiness
│   │   └── workflow.py                      #   Interact avec likers/followers/commenters
│   │
│   └── messaging/                           # 💬 Envoi de DMs
│       ├── __init__.py                      #   → MessagingBusiness, send_dm()
│       └── workflow.py                      #   MessagingBusiness + send_dm()
│
├── actions/                                 # ⚡ Actions réutilisables
│   ├── __init__.py
│   ├── like.py                              # LikeBusiness (like posts sur profil)
│   ├── comment.py                           # CommentBusiness (commentaires)
│   ├── story.py                             # StoryBusiness (stories)
│   └── interaction.py                       # InteractionBusiness (interactions génériques)
│
├── management/                              # 🛠️ Gestion de données
│   ├── __init__.py
│   ├── profile.py                           # ProfileBusiness (infos profil)
│   ├── content.py                           # ContentBusiness (extraction contenu)
│   └── filtering.py                         # FilteringBusiness (filtrage profils)
│
├── system/                                  # ⚙️ Configuration & licences
│   ├── __init__.py
│   ├── config.py                            # ConfigBusiness
│   └── license.py                           # LicenseBusiness
│
└── legacy/                                  # 🗂️ Code legacy (déprécié)
    └── __init__.py
```

---

## 🏗️ Pattern architectural

Chaque workflow suit le même pattern (inspiré de `followers/`) :

```
workflow_name/
├── __init__.py          # Exporte la classe *Business
├── workflow.py          # Classe principale (orchestration)
└── mixins/              # Logique découpée en mixins
    ├── __init__.py
    └── *.py             # Un mixin par responsabilité
```

**Héritage type :**
```python
class HashtagBusiness(
    HashtagPostFinderMixin,      # mixins/post_finder.py
    HashtagExtractorsMixin,      # mixins/extractors.py
    LikersWorkflowBase           # common/likers_base.py
):
    ...
```

---

## � Fichiers de re-export (rétrocompatibilité)

Les anciens fichiers plats sont conservés comme shims de re-export pour ne casser aucun import existant :

| Ancien fichier (shim)              | Redirige vers                              |
|------------------------------------|--------------------------------------------|
| `workflows/_likers_common.py`      | `workflows/common/likers_base.py`          |
| `workflows/followers_tracker.py`   | `workflows/common/followers_tracker.py`    |
| `workflows/feed.py`                | `workflows/feed/workflow.py`               |
| `workflows/notifications.py`       | `workflows/notifications/workflow.py`      |
| `business/messaging.py`            | `workflows/messaging/workflow.py`          |
| `hashtag/extractors.py`            | `hashtag/mixins/extractors.py`             |
| `hashtag/post_finder.py`           | `hashtag/mixins/post_finder.py`            |
| `post_url/extractors.py`           | `post_url/mixins/extractors.py`            |
| `post_url/url_handling.py`         | `post_url/mixins/url_handling.py`          |
| `unfollow/actions.py`              | `unfollow/mixins/actions.py`               |
| `unfollow/decision.py`             | `unfollow/mixins/decision.py`              |

---

## 🎯 Imports recommandés

```python
# Workflows (via le package workflows/)
from ..business.workflows import PostUrlBusiness, HashtagBusiness, FollowerBusiness
from ..business.workflows import FeedBusiness, NotificationsBusiness, UnfollowBusiness

# Ou via le package principal (rétrocompatible)
from ..business import PostUrlBusiness, HashtagBusiness, FollowerBusiness

# Actions
from ..business.actions import LikeBusiness, StoryBusiness, InteractionBusiness

# Management
from ..business.management import ProfileBusiness, ContentBusiness, FilteringBusiness

# System
from ..business.system import ConfigBusiness, LicenseBusiness

# Common
from ..business.common import DatabaseHelpers

# Messaging (les deux fonctionnent)
from ..business.messaging import send_dm                          # via re-export
from ..business.workflows.messaging import send_dm                # direct
```

---

## 📝 Historique

| Date              | Changement                                                         |
|-------------------|--------------------------------------------------------------------|
| 14 octobre 2025   | Réorg initiale : business/ découpé en actions/, management/, etc.  |
| 10 février 2026   | Réorg workflows/ : mixins/, common/, sous-dossiers par workflow    |
