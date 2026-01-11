# 🎵 TikTok Changelog

Historique des modifications de l'automatisation TikTok dans TAKTIK Desktop.

---

## [1.3.0] - 2026-01-11

### 🎉 Nouveau Workflow: TikTok Followers

Workflow complet pour interagir avec les followers d'un compte cible.

#### Backend Python

- **Followers Workflow** (`followers_workflow.py`)
  - Configuration complète (`FollowersConfig`) avec tous les paramètres
  - Statistiques détaillées (`FollowersStats`) avec `completion_reason`
  - Navigation vers un profil cible via recherche
  - Ouverture de la liste des followers
  - Parcours des followers avec extraction des usernames
  - Visite des profils et interaction avec leurs vidéos
  - Skip automatique des profils déjà interagis (via BDD)
  - Skip des profils "Friends" (déjà suivis mutuellement)
  - Gestion des limites (max profiles, max likes, max follows)

- **Profile Actions** (`profile_actions.py`)
  - `navigate_to_profile()` - Navigation vers son propre profil
  - `_parse_count()` - Parsing robuste des compteurs (1.2K, 166 K, 1,5M, etc.)
  - Support des formats avec espaces, virgules, points décimaux

- **Sélecteurs Followers** (`selectors.py`)
  - `FollowersSelectors` - Sélecteurs pour la liste des followers
  - Boutons Follow/Friends/Following (`rdh`)
  - Username dans la liste (`rdf`)
  - Grille de vidéos profil (`gxd`, `e52`)
  - Bouton back in-app (`b9b`)

#### Détection de pages et navigation robuste

- **Méthodes de détection**
  - `_is_on_video_page()` - Détecte page de lecture vidéo (`long_press_layout`, `f57`)
  - `_is_on_profile_page()` - Détecte page profil (`qh5`, `qfv`, `gxd`)
  - `_is_on_followers_list()` - Détecte liste followers (`w4m`, `s6p`)

- **Navigation sécurisée**
  - `_safe_return_to_followers_list()` - Retour avec vérification après chaque back
  - `_recover_to_followers_list()` - Recovery: restart TikTok + re-navigation si échec
  - 3 tentatives max avant recovery automatique

- **Comptage des posts**
  - `_count_visible_posts()` - Compte les posts visibles sur un profil (max 9)
  - Limite automatique des interactions au nombre de posts disponibles
  - Évite les swipes dans le vide sur profils avec peu de posts

#### Base de données locale

- **Nouvelles tables TikTok** (`local_database.py`)
  - `tiktok_accounts` - Comptes TikTok liés aux devices
  - `tiktok_profiles` - Profils visités avec infos (followers, following, likes)
  - `tiktok_interaction_history` - Historique des interactions
  - `tiktok_sessions` - Sessions avec stats complètes et `completion_reason`

- **Méthodes CRUD**
  - `get_or_create_tiktok_account()` - Gestion des comptes
  - `get_or_create_tiktok_profile()` - Gestion des profils avec upsert
  - `record_tiktok_interaction()` - Enregistrement des interactions
  - `has_interacted_with_tiktok_profile()` - Vérification anti-doublon
  - `start_tiktok_session()` / `end_tiktok_session()` - Gestion sessions
  - `update_tiktok_session_stats()` - Mise à jour stats en temps réel

#### Frontend Electron

- **Page TikTok Followers** (`TikTokFollowers.tsx`)
  - Interface de configuration complète
  - Sélection du compte cible (search_query)
  - Sliders pour probabilités (like, follow, favorite)
  - Configuration posts par profil, temps de visionnage
  - Limites de session (max profiles, likes, follows)

- **Session Live Panel** (`SessionLivePanelTikTok.tsx`)
  - Affichage stats en temps réel (profiles visited, likes, follows)
  - Log d'activité avec événements colorés
  - Cartes de profils visités avec avatar et stats
  - Affichage de la raison de fin de session

- **Handlers IPC** (`tiktok.ts`)
  - `tiktok:start-followers` - Démarrer workflow followers
  - Communication bidirectionnelle avec le bridge Python

- **Traductions** (`i18n.tsx`)
  - Nouvelles clés pour les raisons de fin de session
  - `tiktokSession.reasonMaxProfiles`, `reasonMaxLikes`, `reasonMaxFollows`
  - `tiktokSession.reasonNoMoreFollowers`, `reasonStoppedByUser`

#### Bridge Python

- **TikTok Bridge** (`tiktok_bridge.py`)
  - Support du workflow `followers`
  - Envoi de `completion_reason` avec les stats finales
  - Callbacks pour `bot_profile`, `skip_friends`, `skip_already_interacted`
  - Message `status: completed` avec raison

### 🛡️ Protections

- **Skip des profils déjà interagis**
  - Vérification en BDD avant chaque interaction
  - Log `⏭️ Skipping @username - already interacted`

- **Skip des "Friends"**
  - Détection du statut "Friends" (suivi mutuel)
  - Log `👥 Skipping @username - already friends`

- **Recovery automatique**
  - Si navigation échoue après 3 tentatives
  - Restart TikTok + re-navigation vers followers list
  - Reprise automatique grâce au skip des profils déjà traités

- **Limite de posts intelligente**
  - Compte les posts avant interaction
  - N'essaie pas de swiper au-delà des posts disponibles

### 📊 Nouvelles statistiques

- `followers_seen` - Followers vus dans la liste
- `profiles_visited` - Profils visités
- `posts_watched` - Vidéos regardées
- `likes` - Likes effectués
- `follows` - Follows effectués
- `favorites` - Favoris ajoutés
- `already_friends` - Profils skippés (déjà amis)
- `skipped` - Profils skippés (déjà interagis)
- `completion_reason` - Raison de fin de session

---

## [1.2.0] - 2026-01-10

### ✨ Améliorations Scheduler

- **Scheduler Engine** (`scheduler-engine.ts`)
  - Planification des workflows TikTok
  - Support des schedules récurrents
  - Vérification des triggers chaque minute

- **Interface Scheduler** (`Scheduler.tsx`)
  - Création/édition de schedules
  - Sélection device et workflow
  - Configuration horaires et jours

---

## [1.1.0] - 2026-01-07

### ✨ Améliorations

#### Protections
- **Section commentaires** - Détection et fermeture automatique si ouverte accidentellement pendant le scroll
  - Nouveaux sélecteurs: `qx0`, `qx_`, `qx1`, `jt3` (section commentaires ouverte)
  - Méthode `has_comments_section_open()` dans DetectionActions
  - Méthode `close_comments_section()` dans ClickActions
  - Intégration dans la boucle principale du workflow

#### Interface utilisateur
- **Affichage des publicités** - Design spécial pour les vidéos publicitaires
  - Bordure orange sur la carte vidéo en cours
  - Badge "AD" visible
  
- **Affichage des pauses** - Les pauses sont maintenant visibles dans l'activité en direct
  - Nouveau callback `on_pause` dans le workflow
  - Fonction `send_pause(duration)` dans le bridge
  - Affichage `⏸️ Pause de Xs` dans le frontend

#### Performance
- **Timeouts optimisés** - Réduction de 2s à 1s pour la récupération des infos vidéo
- **Suppression de `comment_count`** - Non utilisé, économise ~1s par vidéo
- **Affichage vidéo plus réactif** - Gain estimé de 4-5 secondes par vidéo

---

## [1.0.0] - 2026-01-07

### 🎉 Release initiale

Première implémentation complète de l'automatisation TikTok.

### ✨ Ajouté

#### Backend Python

- **TikTok Bridge** (`bridges/tiktok_bridge.py`)
  - Communication Electron ↔ Python via JSON
  - Envoi des stats en temps réel avec `os.fsync()` pour latence minimale
  - Gestion des signaux d'arrêt (SIGINT, SIGTERM)
  - Callbacks pour vidéos, likes, follows, stats

- **Sélecteurs UI** (`taktik/core/social_media/tiktok/ui/selectors.py`)
  - `NavigationSelectors` - Bottom bar, header tabs
  - `VideoSelectors` - Like, follow, comment, share, favorite, ad label
  - `ProfileSelectors` - Infos profil, compteurs, grille vidéos
  - `InboxSelectors` - Messages, conversations
  - `PopupSelectors` - Collections, notifications, promos, suggestions
  - `ScrollSelectors` - Indicateurs de chargement
  - `DetectionSelectors` - États, erreurs, soft ban

- **Actions atomiques**
  - `ClickActions` - Like, follow, favorite, popups, suggestions
  - `DetectionActions` - Page courante, vidéo likée, ads, popups, suggestions
  - `NavigationActions` - Home, profile, inbox, search
  - `ScrollActions` - Next/prev video, watch video

- **Workflow For You** (`for_you_workflow.py`)
  - Configuration complète (`ForYouConfig`)
  - Statistiques détaillées (`ForYouStats`)
  - Visionnage avec temps variable
  - Like/Follow/Favorite avec probabilités
  - Filtrage par hashtags et likes
  - Pauses automatiques
  - Limites de session

#### Frontend Electron

- **Handlers IPC** (`electron/handlers/tiktok.ts`)
  - `tiktok:start-foryou` - Démarrer workflow
  - `tiktok:stop` - Arrêter workflow
  - `tiktok:session-status` - Statut session
  - `tiktok:all-sessions` - Sessions actives
  - Variable d'environnement `PYTHONUNBUFFERED=1`

- **Preload** (`electron/preload.ts`)
  - `startTikTokForYou(config)`
  - `stopTikTok(deviceId)`
  - `getTikTokSessionStatus(deviceId)`
  - `getAllTikTokSessions()`
  - Listeners pour output, stats, video-info, action, session-ended

- **Page TikTok For You** (`src/pages/TikTokForYou.tsx`)
  - Configuration complète du workflow
  - Sliders pour probabilités
  - Inputs pour limites et filtres
  - Switches pour comportements

- **Panel de session** (`src/components/session/SessionLivePanelTikTok.tsx`)
  - Affichage stats en temps réel
  - Log d'activité
  - Intégration MirrorPanel

- **Intégration App** (`src/App.tsx`)
  - Type `'tiktok'` dans `workflowType`
  - Helpers pour sessions TikTok
  - Listeners pour événements TikTok

### 🛡️ Protections

- **Skip des publicités**
  - Détection via `resource-id="ru3"` avec `text="Ad"`
  - Passage automatique à la vidéo suivante
  - Compteur `ads_skipped`

- **Gestion des popups**
  - Popup "Create shared collections"
  - Bannières promotionnelles
  - Notifications
  - Fermeture automatique via boutons "Not now" ou "Close"

- **Pages de suggestion**
  - Détection via `resource-id="bjl"` (Not interested) ou `bjk` (Follow back)
  - Option `follow_back_suggestions` pour choisir le comportement
  - Par défaut: "Not interested"

- **Redémarrage de l'app**
  - TikTok est forcé à s'arrêter (`am force-stop`)
  - Relancé (`am start`) avant chaque workflow
  - Garantit un état propre (feed For You)

### 🔧 Améliorations MirrorPanel

- **Reconnexion automatique complète**
  - 3 tentatives de reconnexion WebSocket
  - Si échec: redémarrage complet du stream (stop + restart scrcpy)
  - État `needsFullRestart` pour déclencher le redémarrage

- **Heartbeat**
  - Ping envoyé toutes les 30 secondes
  - Maintient la connexion WebSocket active
  - Nettoyage propre à la fermeture

### 📊 Statistiques

Nouvelles métriques trackées:
- `videos_watched` - Vidéos visionnées
- `videos_liked` - Likes effectués
- `users_followed` - Follows effectués
- `videos_favorited` - Favoris ajoutés
- `videos_skipped` - Vidéos filtrées
- `ads_skipped` - Publicités passées
- `popups_closed` - Popups fermées
- `suggestions_handled` - Suggestions gérées
- `errors` - Erreurs rencontrées

### ⚡ Performance

- **Stats temps réel**
  - `line_buffering=True` sur stdout/stderr
  - `os.fsync()` après chaque message
  - `PYTHONUNBUFFERED=1` dans l'environnement
  - Callback `_on_stats_callback` appelé après chaque action

---

## Fichiers modifiés

### Backend (`bot/`)

| Fichier | Action | Lignes |
|---------|--------|--------|
| `bridges/tiktok_bridge.py` | Créé | ~295 |
| `taktik/core/social_media/tiktok/ui/selectors.py` | Modifié | +60 |
| `taktik/core/social_media/tiktok/actions/atomic/click_actions.py` | Modifié | +70 |
| `taktik/core/social_media/tiktok/actions/atomic/detection_actions.py` | Modifié | +10 |
| `taktik/core/social_media/tiktok/actions/business/workflows/for_you_workflow.py` | Modifié | +80 |

### Frontend (`front/`)

| Fichier | Action | Lignes |
|---------|--------|--------|
| `electron/handlers/tiktok.ts` | Créé | ~212 |
| `electron/preload.ts` | Modifié | +80 |
| `src/pages/TikTokForYou.tsx` | Modifié | +30 |
| `src/components/session/SessionLivePanelTikTok.tsx` | Créé | ~470 |
| `src/components/mirror/MirrorPanel.tsx` | Modifié | +60 |
| `src/App.tsx` | Modifié | +120 |
| `src/components/layout/MainSidebar.tsx` | Modifié | +2 |

---

## UI Dumps analysés

| Fichier | Page | Éléments identifiés |
|---------|------|---------------------|
| `ui_dump_20260107_205804.xml` | For You | Navigation, boutons vidéo, infos |
| `ui_dump_20260107_210126.xml` | Inbox | Messages, conversations |
| `ui_dump_20260107_210156.xml` | Profile | Infos, compteurs, grille |
| `ui_dump_20260107_215103.xml` | Ad video | Label "Ad" (ru3) |
| `ui_dump_20260107_215919.xml` | Popup | Collections, Not now, Close |
| `ui_dump_20260107_223235.xml` | Suggestion | Follow back, Not interested |

---

*Dernière mise à jour: 11 janvier 2026*
