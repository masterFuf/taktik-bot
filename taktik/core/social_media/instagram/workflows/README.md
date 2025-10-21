# 📂 Workflows - Structure organisée

Ce dossier contient tous les modules liés à l'orchestration des workflows Instagram.

## 🗂️ Structure

```
workflows/
├── core/                    # 🎯 Orchestration principale
│   ├── automation.py        # Classe principale InstagramAutomation
│   └── workflow_runner.py   # Exécuteur de workflows (targets, hashtags, etc.)
│
├── management/              # ⚙️ Gestion de session et configuration
│   ├── session.py           # SessionManager - Gestion des sessions
│   └── config.py            # WorkflowConfigBuilder - Configuration des workflows
│
├── helpers/                 # 🛠️ Utilitaires et helpers
│   ├── workflow_helpers.py  # Helpers généraux (signaux, finalisation, stats)
│   ├── ui_helpers.py        # Helpers UI (posts, likes, popups)
│   ├── filtering_helpers.py # Helpers de filtrage utilisateurs
│   └── license_helpers.py   # Helpers de gestion de licence
│
├── docs/                    # 📚 Documentation
│   └── REFACTORING.md       # Historique de refactorisation
│
└── __init__.py             # Exports publics du module
```

## 📦 Imports recommandés

### Import depuis le package principal
```python
from taktik.core.social_media.instagram.workflows import (
    InstagramAutomation,      # Classe principale
    WorkflowRunner,           # Exécuteur de workflows
    SessionManager,           # Gestion de session
    WorkflowConfigBuilder,    # Configuration
    WorkflowHelpers,          # Helpers généraux
    UIHelpers,                # Helpers UI
    FilteringHelpers,         # Helpers de filtrage
    LicenseHelpers           # Helpers de licence
)
```

### Import direct (si nécessaire)
```python
from taktik.core.social_media.instagram.workflows.core import InstagramAutomation
from taktik.core.social_media.instagram.workflows.management import SessionManager
from taktik.core.social_media.instagram.workflows.helpers import WorkflowHelpers
```

## 🎯 Responsabilités

### Core (`core/`)
- **automation.py** : Orchestration principale, initialisation, gestion des workflows
- **workflow_runner.py** : Exécution des 4 workflows (targets, hashtags, post_url, place)

### Management (`management/`)
- **session.py** : Gestion des sessions (durée, limites, compteurs, statistiques)
- **config.py** : Configuration des workflows (probabilités, filtres, critères)

### Helpers (`helpers/`)
- **workflow_helpers.py** : Initialisation, finalisation, affichage stats, signaux
- **ui_helpers.py** : Interactions UI bas niveau (posts, likes, popups)
- **filtering_helpers.py** : Décisions de filtrage et d'interaction
- **license_helpers.py** : Vérification licence et limites d'actions

## ✅ Avantages de cette structure

1. **Séparation des responsabilités** : Chaque module a un rôle clair
2. **Maintenabilité** : Fichiers plus petits et focalisés
3. **Testabilité** : Modules indépendants faciles à tester
4. **Extensibilité** : Facile d'ajouter de nouveaux workflows ou helpers
5. **Lisibilité** : Organisation logique et intuitive

## 📝 Notes

- Tous les imports publics sont disponibles via `workflows/__init__.py`
- La rétrocompatibilité est maintenue pour les imports existants
- Les `__pycache__` sont automatiquement ignorés par Git
