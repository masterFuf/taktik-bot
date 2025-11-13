# 📦 Architecture TikTok - Structure Organisée

**Date:** 13 novembre 2025  
**Objectif:** Architecture modulaire pour l'automatisation TikTok, inspirée de la structure Instagram

---

## 📂 **Architecture Complète**

```
tiktok/
├── actions/              # Business logic & actions
│   ├── atomic/           # Actions atomiques bas niveau
│   │   ├── click_actions.py       # Clics (like, follow, comment)
│   │   ├── navigation_actions.py  # Navigation (tabs, profils, hashtags)
│   │   ├── scroll_actions.py      # Scroll (vidéos, feed)
│   │   └── text_actions.py        # Saisie de texte
│   │
│   ├── core/             # Classes de base
│   │   ├── base_action.py         # Classe de base pour toutes les actions
│   │   ├── device_facade.py       # Wrapper pour uiautomator2
│   │   └── utils.py               # Utilitaires (parsing, validation)
│   │
│   └── business/         # Logique métier
│       ├── actions/      # Actions métier (like, follow, comment)
│       └── workflows/    # Workflows d'automatisation
│
├── workflows/            # 🆕 Orchestration
│   ├── core/             # Orchestration principale
│   │   ├── automation.py          # Classe principale TikTokAutomation
│   │   └── workflow_runner.py     # Exécuteur de workflows
│   │
│   ├── management/       # Gestion de session et configuration
│   │   ├── session.py             # SessionManager
│   │   └── config.py              # WorkflowConfigBuilder
│   │
│   └── helpers/          # Helpers pour workflows
│       ├── workflow_helpers.py    # Helpers généraux
│       ├── ui_helpers.py          # Helpers UI
│       └── filtering_helpers.py   # Helpers de filtrage
│
├── ui/                   # Interface & détection
│   ├── selectors.py      # Sélecteurs XPath pour UI TikTok
│   └── detectors/        # Détecteurs d'états UI
│       ├── problematic_page.py    # Détection soft ban, erreurs
│       └── scroll_end.py          # Détection fin de feed
│
├── auth/                 # Authentification
│   └── login.py          # Gestion du login TikTok
│
├── models/               # Data models
│   ├── user.py           # Modèle utilisateur TikTok
│   ├── video.py          # Modèle vidéo
│   └── stats.py          # Modèle statistiques
│
├── utils/                # Utilities
│   ├── filters.py        # Filtres utilisateurs
│   └── helpers.py        # Helpers généraux
│
├── manager.py            # TikTokManager principal
└── __init__.py           # Exports publics
```

---

## 🎯 **Workflows TikTok**

### **1. Target Users Workflow**
Cible les followers/following d'un utilisateur spécifique :
- Navigate to user profile
- Scroll through followers/following
- Like videos, follow users
- Filter by criteria (followers count, bio keywords)

### **2. Hashtag Workflow**
Cible les vidéos d'un hashtag spécifique :
- Search hashtag
- Scroll through videos
- Like, comment, follow creators
- Filter by engagement metrics

### **3. For You Feed Workflow**
Interagit avec le feed "For You" :
- Watch videos
- Like, comment, share
- Follow interesting creators
- Skip videos based on criteria

### **4. Sound/Music Workflow**
Cible les vidéos utilisant un son spécifique :
- Search sound
- Scroll through videos
- Like, comment, follow creators

---

## 🔧 **Actions Atomiques**

### **ClickActions** (`actions/atomic/click_actions.py`)
- `click_follow_button()` - Suivre un utilisateur
- `click_like_button()` - Liker une vidéo (bouton)
- `double_tap_like()` - Liker une vidéo (double tap)
- `click_comment_button()` - Ouvrir les commentaires
- `click_share_button()` - Partager une vidéo
- `click_favorite_button()` - Ajouter aux favoris

### **NavigationActions** (`actions/atomic/navigation_actions.py`)
- `navigate_to_home()` - Aller au feed principal
- `navigate_to_discover()` - Aller à la page Découvrir
- `navigate_to_profile()` - Aller au profil
- `navigate_to_user_profile(username)` - Aller au profil d'un utilisateur
- `search_hashtag(hashtag)` - Rechercher un hashtag
- `go_back()` - Retour arrière

### **ScrollActions** (`actions/atomic/scroll_actions.py`)
- `scroll_to_next_video()` - Passer à la vidéo suivante
- `scroll_to_previous_video()` - Revenir à la vidéo précédente
- `watch_video(duration)` - Regarder une vidéo pendant X secondes
- `scroll_through_videos(count)` - Scroller N vidéos
- `is_end_of_list()` - Vérifier si fin de feed

---

## 📦 **Sélecteurs UI**

Les sélecteurs sont organisés par catégorie dans `ui/selectors.py` :

### **AuthSelectors**
- Champs de login (username, password)
- Boutons d'authentification
- Détection de la page de login

### **NavigationSelectors**
- Bottom navigation bar (Home, Discover, Inbox, Profile)
- Bouton retour

### **ProfileSelectors**
- Boutons d'action (Follow, Message)
- Informations profil (username, bio, stats)

### **VideoSelectors**
- Boutons d'interaction (Like, Comment, Share, Favorite)
- Informations vidéo (author, description)

### **SearchSelectors**
- Barre de recherche
- Filtres (Users, Videos, Hashtags, Sounds)

### **PopupSelectors**
- Boutons de fermeture
- Popups spécifiques (age verification, notifications)

---

## 🚀 **Utilisation**

### **Import des modules**
```python
from taktik.core.social_media.tiktok import TikTokManager
from taktik.core.social_media.tiktok.actions.atomic import (
    ClickActions,
    NavigationActions,
    ScrollActions
)
from taktik.core.social_media.tiktok.ui import (
    VIDEO_SELECTORS,
    PROFILE_SELECTORS,
    NAVIGATION_SELECTORS
)
```

### **Exemple basique**
```python
# Initialiser le manager
manager = TikTokManager(device_id="emulator-5554")

# Lancer TikTok
manager.launch()

# Créer des actions
nav = NavigationActions(manager.device_manager.device)
click = ClickActions(manager.device_manager.device)
scroll = ScrollActions(manager.device_manager.device)

# Naviguer vers un profil
nav.navigate_to_user_profile("username")

# Suivre l'utilisateur
click.follow_user("username")

# Scroller les vidéos
scroll.scroll_through_videos(count=5, watch_duration=3.0)
```

---

## ✅ **Avantages de cette architecture**

1. **Modularité** : Chaque composant a une responsabilité claire
2. **Réutilisabilité** : Actions atomiques réutilisables dans différents workflows
3. **Maintenabilité** : Structure claire et organisée
4. **Extensibilité** : Facile d'ajouter de nouveaux workflows
5. **Testabilité** : Modules indépendants faciles à tester
6. **Cohérence** : Architecture similaire à Instagram pour faciliter la maintenance

---

## 🎯 **Spécificités TikTok**

### **Différences avec Instagram**
- **Feed vertical** : Scroll up/down pour changer de vidéo
- **Double tap to like** : Alternative au bouton like
- **For You algorithm** : Feed personnalisé par défaut
- **Sounds/Music** : Élément central de la plateforme
- **Duets & Stitches** : Fonctionnalités de collaboration

### **Actions spécifiques TikTok**
- `double_tap_like()` - Like par double tap
- `watch_video(duration)` - Regarder une vidéo
- `scroll_to_next_video()` - Navigation verticale
- `search_sound()` - Recherche par son

---

## 📝 **TODO**

- [ ] Implémenter les workflows d'automatisation
- [ ] Créer les actions business (like, follow, comment)
- [ ] Implémenter l'authentification
- [ ] Créer les détecteurs UI (soft ban, erreurs)
- [ ] Ajouter les filtres utilisateurs
- [ ] Implémenter les statistiques
- [ ] Tests unitaires
- [ ] Documentation complète

---

## 📊 **Statistiques**

| Métrique | Valeur |
|----------|--------|
| Fichiers créés | 15+ |
| Actions atomiques | 3 modules |
| Sélecteurs UI | 9 catégories |
| Workflows prévus | 4 |
| Clarté architecture | 9/10 |

---

**Status:** 🚧 **EN COURS DE DÉVELOPPEMENT**
