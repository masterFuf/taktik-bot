# 🎵 TikTok Implementation - Guide Complet

**Date de création:** 7 janvier 2026  
**Objectif:** Implémenter l'automatisation TikTok en réutilisant l'architecture Instagram existante

---

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Analyse UI TikTok](#analyse-ui-tiktok)
4. [Sélecteurs UI](#sélecteurs-ui)
5. [Actions Atomiques](#actions-atomiques)
6. [Workflows](#workflows)
7. [Checklist d'implémentation](#checklist-dimplémentation)
8. [Règles Importantes](#règles-importantes)

---

## 🎯 Vue d'ensemble

### Package TikTok
- **Package name:** `com.zhiliaoapp.musically`
- **Main Activity:** `com.ss.android.ugc.aweme.splash.SplashActivity`

### Fonctionnalités à implémenter (par priorité)

1. **Phase 1 - Core** ✅ COMPLÉTÉ
   - [x] TikTokManager (launch/stop) - EXISTE DÉJÀ
   - [x] Sélecteurs UI complets (`ui/selectors.py` - 740 lignes)
   - [x] Actions atomiques (click, scroll, navigation, detection)
   - [x] Détection d'états (page courante, popups, vidéo likée, etc.)

2. **Phase 2 - Workflows d'automatisation** 🚧 EN COURS
   - [x] For You Feed Workflow (like, follow sur le feed) ✅
   - [ ] Hashtag Workflow (recherche et interaction par hashtag)
   - [ ] Target Users Workflow (cibler followers/following d'un compte)

3. **Phase 3 - Avancé**
   - [ ] DM Workflow (messages directs)
   - [ ] Sound/Music Workflow (cibler par son)
   - [ ] Scraping de profils

---

## 🏗️ Architecture

```
taktik/core/social_media/tiktok/
├── __init__.py                    # Exports publics
├── manager.py                     # TikTokManager (EXISTE)
│
├── actions/
│   ├── __init__.py
│   ├── atomic/                    # Actions bas niveau
│   │   ├── __init__.py
│   │   ├── click_actions.py       # Like, Follow, Comment, Share, Favorite
│   │   ├── navigation_actions.py  # Tabs, Search, Profile navigation
│   │   ├── scroll_actions.py      # Swipe vertical (next/prev video)
│   │   ├── detection_actions.py   # Détection d'états UI
│   │   └── text_actions.py        # Saisie de texte
│   │
│   ├── core/                      # Classes de base
│   │   ├── __init__.py
│   │   ├── base_action.py         # Hérite de Instagram BaseAction
│   │   └── device_facade.py       # Réutilise Instagram DeviceFacade
│   │
│   └── business/
│       ├── __init__.py
│       ├── actions/               # Actions métier
│       │   ├── like_action.py
│       │   ├── follow_action.py
│       │   └── comment_action.py
│       └── workflows/             # Workflows complets
│           ├── for_you_workflow.py
│           ├── hashtag_workflow.py
│           └── target_workflow.py
│
├── ui/
│   ├── __init__.py
│   ├── selectors.py               # Sélecteurs XPath TikTok
│   └── detectors/
│       ├── __init__.py
│       ├── problematic_page.py    # Détection soft ban, erreurs
│       └── video_state.py         # État de la vidéo courante
│
├── models/
│   ├── __init__.py
│   ├── video.py                   # Modèle vidéo TikTok
│   ├── user.py                    # Modèle utilisateur
│   └── stats.py                   # Statistiques
│
├── workflows/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── automation.py          # TikTokAutomation principale
│   └── management/
│       ├── __init__.py
│       └── session.py             # Gestion de session
│
└── utils/
    ├── __init__.py
    ├── filters.py                 # Filtres utilisateurs
    └── helpers.py                 # Helpers généraux
```

---

## 📱 Analyse UI TikTok

### Page For You (Feed principal)

#### Navigation Header (onglets horizontaux)
| Élément | Sélecteur | Type |
|---------|-----------|------|
| LIVE | `content-desc="LIVE"` | Tab |
| Explore | `text="Explore"` | Tab |
| Following | `text="Following"` | Tab |
| Shop | `text="Shop"` | Tab |
| **For You** | `text="For You"` + `selected="true"` | Tab (actif) |
| Search | `content-desc="Search"` | Button |

#### Boutons d'interaction vidéo (côté droit)
| Élément | Resource-ID | Content-desc | Sélecteur XPath |
|---------|-------------|--------------|-----------------|
| Profil créateur | `yx4` | `"{username} profile"` | `//android.widget.ImageView[contains(@content-desc, "profile")]` |
| Follow | `hi1` | `"Follow {username}"` | `//android.widget.Button[contains(@content-desc, "Follow")]` |
| Like | `f57` | `"Like video"` | `//android.widget.Button[contains(@content-desc, "Like video")]` |
| Comments | `dtv` | `"Read or add comments"` | `//android.widget.Button[contains(@content-desc, "comments")]` |
| Favorites | `guh` | `"Add or remove this video from Favourites"` | `//android.widget.Button[contains(@content-desc, "Favourites")]` |
| Share | `f57` | `"Share video"` | `//android.widget.Button[contains(@content-desc, "Share video")]` |
| Sound | `nhe` | `"Sound: {sound_name}"` | `//android.widget.Button[contains(@content-desc, "Sound:")]` |

#### Infos vidéo (bas de l'écran)
| Élément | Resource-ID | Sélecteur XPath |
|---------|-------------|-----------------|
| Username | `title` | `//*[@resource-id="com.zhiliaoapp.musically:id/title"]` |
| Description | `desc` | `//*[@resource-id="com.zhiliaoapp.musically:id/desc"]` |
| Like count | `f4z` | `//*[@resource-id="com.zhiliaoapp.musically:id/f4z"]` |
| Comment count | `dp9` | `//*[@resource-id="com.zhiliaoapp.musically:id/dp9"]` |
| Share count | `t_2` | `//*[@resource-id="com.zhiliaoapp.musically:id/t_2"]` |
| Favorite count | `gtv` | `//*[@resource-id="com.zhiliaoapp.musically:id/gtv"]` |

### Bottom Navigation Bar
| Tab | Resource-ID | Content-desc | Selected |
|-----|-------------|--------------|----------|
| Home | `mkq` | `"Home"` | `selected="true/false"` |
| Friends | `mkp` | `"Friends"` | `selected="true/false"` |
| Create | `mkn` | `"Create"` | - |
| Inbox | `mkr` | `"Inbox"` | `selected="true/false"` |
| Profile | `mks` | `"Profile"` | `selected="true/false"` |

### Page Inbox (Messages)

#### Header
| Élément | Resource-ID | Content-desc |
|---------|-------------|--------------|
| Add people | `ehp` | `"Add people"` |
| Title | `title` | `text="Inbox"` |
| Activity status | `jlc` | `"Activity status: turned off"` |
| Search | `j6u` | `"Search"` |

#### Sections de notification
| Section | Resource-ID | Texte |
|---------|-------------|-------|
| New followers | `b8h` | `text="New followers"` |
| Activity | `b8h` | `text="Activity"` |
| System notifications | `b8h` | `text="System notifications"` |

#### Conversations
| Élément | Resource-ID | Description |
|---------|-------------|-------------|
| Conversation item | `t5a` | Container de conversation |
| Avatar | `b5h` | Image de profil |
| Username | `z05` | Nom d'utilisateur |
| Last message | `l35` | Dernier message |
| Time | `l3a` | Timestamp |
| Unread badge | `fa7` | Badge non lu |

### Page Profile

#### Header
| Élément | Resource-ID | Content-desc |
|---------|-------------|--------------|
| Add friend | - | Icône gauche |
| Profile views | `h9p` | `"Profile views"` |
| Profile views count | `xvy` | Nombre de vues |
| Share profile | - | Icône partage |
| Profile menu | - | `"Profile menu"` |

#### Infos profil
| Élément | Resource-ID | Description |
|---------|-------------|-------------|
| Profile photo | `b5s` | `content-desc="Profile photo"` |
| Create Story | - | `content-desc="Create a Story"` |
| Display name | `qf8` | Nom affiché |
| Username | `qh5` | @username |
| Edit button | - | `text="Edit"` |
| Following count | `qfw` | Premier élément |
| Following label | `qfv` | `text="Following"` |
| Followers count | `qfw` | Deuxième élément |
| Followers label | `qfv` | `text="Followers"` |
| Likes count | `qfw` | Troisième élément |
| Likes label | `qfv` | `text="Likes"` |
| Bio | - | Texte de bio |
| TikTok Studio | `a_l` | `text="TikTok Studio"` |

#### Onglets de contenu
| Tab | Content-desc | Selected |
|-----|--------------|----------|
| Videos | `"Videos"` | `selected="true/false"` |
| Private videos | `"Private videos"` | `selected="true/false"` |
| Favourites | `"Favourites"` | `selected="true/false"` |
| Liked videos | `"Liked videos"` | `selected="true/false"` |

#### Grille de vidéos
| Élément | Resource-ID | Description |
|---------|-------------|-------------|
| Video grid | `gxd` | GridView des vidéos |
| Video item | `e52` | Container vidéo |
| Video cover | `cover` | Image de couverture |
| View count | `xxy` | Nombre de vues |

---

## 🎯 Sélecteurs UI

### Principes IMPORTANTS

> ⚠️ **JAMAIS de bounds en dur !**  
> Tous les sélecteurs doivent être basés sur :
> - `resource-id`
> - `content-desc`
> - `text`
> - Combinaisons XPath avec attributs
> 
> Cela garantit la compatibilité avec **toutes les résolutions d'écran**.

### Structure des sélecteurs (comme Instagram)

```python
@dataclass
class VideoSelectors:
    """Sélecteurs pour les éléments vidéo TikTok."""
    
    # Bouton Like - plusieurs variantes pour robustesse
    like_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@content-desc, "Like video")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/f57"][contains(@content-desc, "Like")]',
        '//android.widget.Button[contains(@content-desc, "likes")]',
    ])
    
    # Bouton Follow
    follow_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@content-desc, "Follow")]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/hi1"]',
    ])
    
    # etc...
```

---

## 🔧 Actions Atomiques

### ClickActions
| Méthode | Description |
|---------|-------------|
| `click_like_button()` | Like la vidéo courante |
| `double_tap_like()` | Like par double tap sur la vidéo |
| `click_follow_button()` | Follow le créateur |
| `click_comment_button()` | Ouvre les commentaires |
| `click_share_button()` | Ouvre le menu de partage |
| `click_favorite_button()` | Ajoute aux favoris |
| `click_sound_button()` | Accède au son de la vidéo |

### NavigationActions
| Méthode | Description |
|---------|-------------|
| `navigate_to_home()` | Aller au feed For You |
| `navigate_to_friends()` | Aller à l'onglet Friends |
| `navigate_to_inbox()` | Aller aux messages |
| `navigate_to_profile()` | Aller au profil |
| `navigate_to_user_profile(username)` | Aller au profil d'un utilisateur |
| `navigate_to_search()` | Ouvrir la recherche |
| `search_hashtag(hashtag)` | Rechercher un hashtag |
| `search_user(username)` | Rechercher un utilisateur |
| `go_back()` | Retour arrière |

### ScrollActions
| Méthode | Description |
|---------|-------------|
| `scroll_to_next_video()` | Swipe vers le haut (vidéo suivante) |
| `scroll_to_previous_video()` | Swipe vers le bas (vidéo précédente) |
| `watch_video(duration)` | Regarder la vidéo pendant X secondes |
| `scroll_feed(count)` | Scroller N vidéos |

### DetectionActions
| Méthode | Description |
|---------|-------------|
| `is_on_for_you_page()` | Vérifie si on est sur For You |
| `is_on_profile_page()` | Vérifie si on est sur un profil |
| `is_on_inbox_page()` | Vérifie si on est sur Inbox |
| `is_video_liked()` | Vérifie si la vidéo est likée |
| `is_user_followed()` | Vérifie si l'utilisateur est suivi |
| `detect_popup()` | Détecte les popups à fermer |
| `detect_soft_ban()` | Détecte un éventuel soft ban |

---

## 🚀 Workflows

### 1. For You Feed Workflow

```
1. Lancer TikTok
2. Vérifier qu'on est sur For You
3. Pour chaque vidéo:
   a. Regarder X secondes (variable)
   b. Extraire infos (username, hashtags, engagement)
   c. Appliquer filtres (hashtags, engagement min/max)
   d. Si match: Like / Follow selon config
   e. Scroll vers vidéo suivante
4. Respecter les limites et pauses
```

### 2. Hashtag Workflow

```
1. Lancer TikTok
2. Naviguer vers Search
3. Rechercher le hashtag
4. Pour chaque vidéo du hashtag:
   a. Regarder X secondes
   b. Extraire infos créateur
   c. Appliquer filtres
   d. Si match: Like / Follow
   e. Scroll suivant
5. Respecter les limites
```

### 3. Target Users Workflow

```
1. Lancer TikTok
2. Naviguer vers le profil cible
3. Ouvrir la liste followers/following
4. Pour chaque profil:
   a. Visiter le profil
   b. Extraire infos (followers, bio, vidéos)
   c. Appliquer filtres
   d. Si match: Follow / Like dernières vidéos
   e. Retour à la liste
5. Respecter les limites
```

---

## ✅ Checklist d'implémentation

### Phase 1 - Core (Priorité HAUTE)

- [x] **Sélecteurs UI** (`ui/selectors.py`) ✅ (740 lignes)
  - [x] NavigationSelectors (resource-ids: mkq, mkp, mkn, mkr, mks)
  - [x] VideoSelectors (resource-ids: f57, hi1, dtv, guh, nhe, title, desc)
  - [x] ProfileSelectors (resource-ids: qf8, qh5, qfw, qfv, b5s)
  - [x] InboxSelectors (resource-ids: ehp, j6u, t5a, z05, l35)
  - [x] PopupSelectors
  - [x] DetectionSelectors

- [x] **Actions Atomiques** ✅
  - [x] `actions/core/base_action.py` (hérite d'Instagram)
  - [x] `actions/atomic/click_actions.py` (270 lignes)
  - [x] `actions/atomic/navigation_actions.py` (293 lignes)
  - [x] `actions/atomic/scroll_actions.py` (180 lignes)
  - [x] `actions/atomic/detection_actions.py` (300 lignes)
  - [ ] `actions/atomic/text_actions.py` (à faire si nécessaire)

- [x] **Détecteurs** ✅
  - [x] `actions/atomic/detection_actions.py` (intégré aux actions atomiques)

### Phase 2 - Workflows (Priorité MOYENNE)

- [x] **For You Workflow** ✅
  - [x] `actions/business/workflows/for_you_workflow.py` (423 lignes)
  - [x] `ForYouConfig` - Configuration du workflow
  - [x] `ForYouStats` - Statistiques de session

- [ ] **Hashtag Workflow**
  - [ ] `actions/business/workflows/hashtag_workflow.py`

- [ ] **Target Workflow**
  - [ ] `actions/business/workflows/target_workflow.py`

### Phase 3 - Avancé (Priorité BASSE)

- [ ] **DM Workflow**
- [ ] **Sound Workflow**
- [ ] **Scraping avancé**

---

## ⚠️ Règles Importantes

### 1. Compatibilité Multi-Résolution
```
❌ INTERDIT: bounds="[600,770][720,883]"
✅ CORRECT: content-desc="Like video" ou resource-id="com.zhiliaoapp.musically:id/f57"
```

### 2. Sélecteurs Multiples
Toujours fournir plusieurs variantes de sélecteurs pour la robustesse:
```python
like_button: List[str] = [
    '//android.widget.Button[contains(@content-desc, "Like video")]',
    '//*[@resource-id="com.zhiliaoapp.musically:id/f57"]',
    '//android.widget.Button[contains(@content-desc, "likes")]',
]
```

### 3. Réutilisation du Code Instagram
- `BaseAction` → Hériter de la version Instagram
- `DeviceFacade` → Réutiliser directement
- `HumanBehavior` → Réutiliser (singleton partagé)
- Patterns de sélecteurs → Même structure dataclass

### 4. Comportement Humain
- Délais variables entre actions
- Watch time variable sur les vidéos
- Pauses régulières
- Pas de patterns répétitifs

### 5. Gestion des Erreurs
- Détection de popups et fermeture automatique
- Détection de soft ban
- Recovery automatique si navigation échoue

---

## 📊 Différences TikTok vs Instagram

| Aspect | Instagram | TikTok |
|--------|-----------|--------|
| Feed | Scroll horizontal (stories) + vertical (posts) | Scroll vertical uniquement |
| Like | Bouton ou double tap sur image | Bouton ou double tap sur vidéo |
| Navigation | Bottom bar 5 tabs | Bottom bar 5 tabs (similaire) |
| Contenu | Photos + Vidéos + Stories + Reels | Vidéos uniquement |
| Hashtags | Dans description | Dans description |
| Sons | Non applicable | Élément central |
| Package | `com.instagram.android` | `com.zhiliaoapp.musically` |

---

## 📝 Notes de développement

### UI Dumps analysés
1. `ui_dump_20260107_205804.xml` - Page For You
2. `ui_dump_20260107_210126.xml` - Page Inbox
3. `ui_dump_20260107_210156.xml` - Page Profile

### Resource-IDs clés identifiés
- `mky` - Bottom navigation container
- `mkq/mkp/mkn/mkr/mks` - Tabs de navigation
- `f57` - Bouton Like/Share
- `hi1` - Bouton Follow
- `title` - Username sur vidéo
- `desc` - Description vidéo
- `qf8` - Display name profil
- `qh5` - Username profil (@)
- `qfw` - Compteurs (following/followers/likes)

---

**Status:** ✅ PHASE 1 & 2 COMPLÉTÉES

**Dernière mise à jour:** 7 janvier 2026

---

## 🚀 Utilisation rapide

```python
from taktik.core.social_media.tiktok import (
    TikTokManager,
    ForYouWorkflow,
    ForYouConfig,
)

# Configuration du workflow
config = ForYouConfig(
    max_videos=50,
    like_probability=0.3,
    follow_probability=0.1,
    favorite_probability=0.05,
    min_watch_time=2.0,
    max_watch_time=8.0,
    skip_ads=True,
    follow_back_suggestions=False,
)

# Initialisation
manager = TikTokManager(device_id="emulator-5554")
device = manager.device_manager.device

# Lancer le workflow
workflow = ForYouWorkflow(device, config)
stats = workflow.run()

print(f"Vidéos vues: {stats.videos_watched}")
print(f"Likes: {stats.videos_liked}")
print(f"Follows: {stats.users_followed}")
print(f"Favoris: {stats.videos_favorited}")
print(f"Pubs skipées: {stats.ads_skipped}")
print(f"Suggestions gérées: {stats.suggestions_handled}")
```

---

## 📱 Intégration Frontend (Electron)

### Fichiers Frontend modifiés

| Fichier | Description |
|---------|-------------|
| `front/electron/handlers/tiktok.ts` | Handlers IPC pour TikTok (start, stop, status) |
| `front/electron/preload.ts` | Méthodes TikTok exposées au renderer |
| `front/src/pages/TikTokForYou.tsx` | Page de configuration du workflow For You |
| `front/src/components/session/SessionLivePanelTikTok.tsx` | Panel de session live TikTok |
| `front/src/App.tsx` | Intégration du type 'tiktok' dans les sessions |
| `front/src/components/layout/MainSidebar.tsx` | Support du type 'tiktok' |

### Communication IPC

```typescript
// Démarrer un workflow
window.electronAPI.startTikTokForYou(config)

// Arrêter un workflow
window.electronAPI.stopTikTok(deviceId)

// Écouter les événements
window.electronAPI.onTikTokOutput(callback)      // Logs bruts
window.electronAPI.onTikTokStats(callback)       // Stats en temps réel
window.electronAPI.onTikTokVideoInfo(callback)   // Info vidéo courante
window.electronAPI.onTikTokAction(callback)      // Actions (like, follow)
window.electronAPI.onTikTokSessionEnded(callback) // Fin de session
```

### Bridge Python

**Fichier:** `bot/bridges/tiktok_bridge.py`

Le bridge gère:
- Réception de la config JSON depuis Electron
- Lancement du workflow TikTok
- Envoi des messages en temps réel (stats, vidéos, actions)
- Gestion des signaux d'arrêt

---

## 🛡️ Fonctionnalités de protection

### Détection et gestion automatique

| Fonctionnalité | Description |
|----------------|-------------|
| **Skip Ads** | Détecte les vidéos sponsorisées (label "Ad") et les passe automatiquement |
| **Popups** | Ferme automatiquement les popups (collections, notifications, promos) |
| **Suggestions** | Gère les pages "Follow back / Not interested" |
| **Restart App** | Redémarre TikTok au début de chaque workflow pour un état propre |

### Sélecteurs de protection

```python
# Publicités
ad_label: '//*[@resource-id="com.zhiliaoapp.musically:id/ru3"][@text="Ad"]'

# Popups
collections_popup: '//*[contains(@text, "Create shared collections")]'
not_now_button: '//*[@resource-id="com.zhiliaoapp.musically:id/ny9"]'
close_button: '//android.widget.ImageView[@content-desc="Close"]'

# Page de suggestion
suggestion_not_interested: '//*[@resource-id="com.zhiliaoapp.musically:id/bjl"]'
suggestion_follow_back: '//*[@resource-id="com.zhiliaoapp.musically:id/bjk"]'
```

---

## 📊 Statistiques trackées

| Stat | Description |
|------|-------------|
| `videos_watched` | Nombre de vidéos regardées |
| `videos_liked` | Nombre de likes effectués |
| `users_followed` | Nombre de follows effectués |
| `videos_favorited` | Nombre de vidéos ajoutées aux favoris |
| `videos_skipped` | Nombre de vidéos skipées (filtres) |
| `ads_skipped` | Nombre de publicités passées |
| `popups_closed` | Nombre de popups fermées |
| `suggestions_handled` | Nombre de pages de suggestion gérées |
| `errors` | Nombre d'erreurs rencontrées |

---

## ⚙️ Paramètres de configuration

### ForYouConfig

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `max_videos` | int | 50 | Nombre max de vidéos à traiter |
| `min_watch_time` | float | 2.0 | Temps min de visionnage (secondes) |
| `max_watch_time` | float | 8.0 | Temps max de visionnage (secondes) |
| `like_probability` | float | 0.3 | Probabilité de like (0-1) |
| `follow_probability` | float | 0.1 | Probabilité de follow (0-1) |
| `favorite_probability` | float | 0.05 | Probabilité de favori (0-1) |
| `max_likes_per_session` | int | 50 | Limite de likes par session |
| `max_follows_per_session` | int | 20 | Limite de follows par session |
| `skip_already_liked` | bool | True | Skip les vidéos déjà likées |
| `skip_ads` | bool | True | Skip les publicités |
| `follow_back_suggestions` | bool | False | Follow back au lieu de "Not interested" |
| `pause_after_actions` | int | 10 | Pause après N actions |
| `pause_duration_min` | float | 30.0 | Durée min de pause (secondes) |
| `pause_duration_max` | float | 60.0 | Durée max de pause (secondes) |
| `required_hashtags` | list | [] | Hashtags requis pour interagir |
| `excluded_hashtags` | list | [] | Hashtags à exclure |
| `min_likes` | int | None | Minimum de likes pour interagir |
| `max_likes` | int | None | Maximum de likes pour interagir |
