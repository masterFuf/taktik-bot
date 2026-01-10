# 🎵 TikTok Changelog

Historique des modifications de l'automatisation TikTok dans TAKTIK Desktop.

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

*Dernière mise à jour: 7 janvier 2026*
