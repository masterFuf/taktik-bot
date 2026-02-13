# 📦 Restructuration Architecture Instagram - Option 1

**Date:** 15 octobre 2025  
**Objectif:** Réorganiser le dossier `core/` qui était devenu un "bordel"

---

## ✅ **Changements effectués**

### **Nouveau dossier `workflows/`**
Regroupe toute la logique d'orchestration des workflows Instagram :

```
workflows/
├── __init__.py
├── automation.py      # Anciennement core/automation.py
├── session.py         # Anciennement core/session_manager.py  
└── config.py          # Anciennement core/workflow_config.py
```

**Responsabilités :**
- Orchestration des 4 workflows (Target, Hashtags, URL post, Place)
- Gestion des sessions et limites
- Configuration des probabilités d'actions

---

### **Nouveau dossier `ui/detectors/`**
Regroupe les détecteurs d'interface utilisateur :

```
ui/
├── selectors.py       # Existant
└── detectors/         # NOUVEAU
    ├── __init__.py
    ├── problematic_page.py   # Anciennement core/problematic_page_detector.py
    └── scroll_end.py         # Anciennement core/scroll_end_detector.py
```

**Responsabilités :**
- Détection des pages problématiques (soft ban, etc.)
- Détection de fin de scroll

---

### **Dossier `core/` nettoyé**
```
core/
├── __init__.py
└── manager.py         # Seul fichier restant
```

Le dossier `core/` est maintenant minimaliste.

---

## 🔧 **Imports mis à jour**

### **Avant (❌ Old):**
```python
from taktik.core.social_media.instagram.core.automation import InstagramAutomation
from taktik.core.social_media.instagram.core.session_manager import SessionManager
from taktik.core.social_media.instagram.core.workflow_config import WorkflowConfigBuilder
from taktik.core.social_media.instagram.core.problematic_page_detector import ProblematicPageDetector
from taktik.core.social_media.instagram.core.scroll_end_detector import ScrollEndDetector
```

### **Après (✅ New):**
```python
from taktik.core.social_media.instagram.workflows.automation import InstagramAutomation
from taktik.core.social_media.instagram.workflows.session import SessionManager
from taktik.core.social_media.instagram.workflows.config import WorkflowConfigBuilder
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
```

---

## 📂 **Architecture complète**

```
instagram/
├── actions/              # Business logic & actions
│   ├── business/
│   ├── core/
│   └── compatibility/
│
├── workflows/            # 🆕 Orchestration
│   ├── automation.py
│   ├── session.py
│   └── config.py
│
├── ui/                   # Interface & detection
│   ├── selectors.py
│   └── detectors/        # 🆕 UI detectors
│       ├── problematic_page.py
│       └── scroll_end.py
│
├── core/                 # 🧹 Minimal
│   └── manager.py
│
├── models/               # Data models
├── utils/                # Utilities
└── views/                # UI views
```

---

## 📝 **Fichiers modifiés**

### **Imports mis à jour dans :**
1. `__init__.py` (principal)
2. `workflows/automation.py`
3. `actions/business/actions/like.py`
4. `test/navigation/place/test_place_post_likes.py`
5. `test/navigation/place/test_navigate_to_place.py`
6. `test/navigation/following/test_navigate_to_following.py`
7. `test/navigation/followers/test_navigate_to_followers.py`
8. `test/profile/test_profile_image.py`

---

## ✅ **Avantages**

- ✅ **Clarté** : Séparation logique des responsabilités
- ✅ **Maintenabilité** : Plus facile de trouver les fichiers
- ✅ **Scalabilité** : Structure prête pour évolution
- ✅ **Minimalisme** : `core/` nettoyé

---

## 🧪 **Tests à effectuer**

```bash
# Vérifier que les imports fonctionnent
python -c "from taktik.core.social_media.instagram import InstagramAutomation, SessionManager"

# Lancer le CLI
python main.py

# Tester un workflow
python main.py --workflow target --target-username XXX
```

---

## 📊 **Statistiques**

| Métrique | Avant | Après |
|----------|-------|-------|
| Fichiers dans `core/` | 7 | 2 |
| Lignes dans `core/` | ~115KB | ~2KB |
| Clarté architecture | 3/10 | 8/10 |

---

**Status:** ✅ **REFACTORISATION TERMINÉE**

---

## 🔄 Phase 2 — Extraction core/shared/ & refactoring CLI (12 février 2026)

### **Nouveau dossier `core/shared/`**
Modules de base partagés entre Instagram et TikTok :

```
core/shared/
├── __init__.py                  # Re-exports publics
├── actions/
│   └── base_action.py           # SharedBaseAction (delays, clicks, keyboard input)
├── device/
│   ├── facade.py                # BaseDeviceFacade + Direction enum (ADB/uiautomator2)
│   └── manager.py               # DeviceManager (device listing, connection)
├── input/
│   └── taktik_keyboard.py       # ADB Keyboard utilities (type, clear, activate)
├── platform/
│   └── social_media_base.py     # SocialMediaBase (abstract platform interface)
└── utils/
    └── action_utils.py          # ActionUtils + parse_count (common parsers)
```

### **Héritage Instagram/TikTok → shared**

| Classe plateforme                    | Hérite de                          |
|--------------------------------------|------------------------------------|
| `instagram.DeviceFacade`             | `shared.BaseDeviceFacade`          |
| `instagram.BaseAction`               | `shared.SharedBaseAction`          |
| `instagram.ActionUtils`              | `shared.ActionUtils`               |
| `instagram.taktik_keyboard`          | re-export de `shared.taktik_keyboard` |
| `tiktok.DeviceFacade`                | `shared.BaseDeviceFacade`          |
| `tiktok.BaseAction`                  | `shared.SharedBaseAction`          |
| `tiktok.ActionUtils`                 | `shared.ActionUtils`               |

### **Nouveau dossier `cli/common/`**
Helpers CLI partagés pour réduire la duplication dans `cli/main.py` :

```
cli/common/
├── __init__.py
├── workflow_builder.py          # collect_probabilities, collect_filters, collect_session_settings,
│                                # build_*_config, display_*_rows, display_estimates
└── device_selector.py           # select_device, connect_device, select_and_connect_device
```

### **Refactoring cli/main.py**
- `generate_target_workflow`, `generate_hashtags_workflow`, `generate_post_url_workflow` → utilisent `workflow_builder.py`
- 2× device selection blocks (Instagram + TikTok) → `select_device()`
- 6× connect+check blocks → `connect_device()`
- Fix bugs copier-coller dans `generate_place_workflow` (prompt dupliqué, variables inexistantes)

### **Discovery Workflow**
- Suppression de `discovery_workflow.py` (v1)
- `DiscoveryWorkflowV2` aliasé comme `DiscoveryWorkflow` dans `__init__.py`
- CLI mis à jour pour passer `device_id` au lieu de `device_manager`

### **Nettoyage**
- Suppression du dossier `business/legacy/` (vide)
- Déduplication logique extraction likers dans `BaseBusinessAction._extract_likers_after_click()`
- Nouveaux modules atomiques TikTok (popup, video, search actions/detectors)

### **Statistiques Phase 2**

| Métrique                          | Valeur          |
|-----------------------------------|-----------------|
| Lignes supprimées (duplication)   | ~800            |
| Nouveaux modules partagés         | 6 (core/shared) |
| Nouveaux helpers CLI              | 2 (cli/common)  |
| Commits                           | 7               |
