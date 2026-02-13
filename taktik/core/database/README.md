# TAKTIK Database — Documentation Technique

## Vue d'ensemble

Toutes les données d'automatisation sont stockées **localement** dans une base SQLite partagée entre l'application Electron et les bridges Python.

```
Emplacement : %APPDATA%/taktik-desktop/taktik-data.db
Mode         : WAL (Write-Ahead Logging) pour accès concurrent Electron + Python
```

L'API distante (`api.taktik-bot.com`) ne gère **que** :
- Authentification (login, JWT)
- Licences (validation, devices, limites)
- Crash reports

---

## Architecture des fichiers

```
database/
├── __init__.py              ← API publique (configure_db_service, get_db_service)
├── models.py                ← Modèles de données (InstagramProfile, etc.)
├── README.md                ← Ce fichier
├── local/
│   ├── __init__.py          ← Re-exports
│   ├── service.py           ← Moteur SQLite (LocalDatabaseService)
│   │                          Crée les tables, gère la connexion, initialise les repos
│   └── client.py            ← Interface publique (LocalDatabaseClient)
│                              Appelé par get_db_service(), fournit les méthodes métier
└── repositories/
    ├── __init__.py           ← Re-exports
    ├── base_repository.py    ← Classe de base (BaseRepository)
    ├── account_repository.py ← Comptes Instagram (CRUD)
    ├── profile_repository.py ← Profils Instagram (CRUD + stats)
    ├── interaction_repository.py ← Historique des interactions
    ├── session_repository.py ← Sessions d'automatisation
    ├── discovery_repository.py ← Campagnes de découverte + scraping
    └── tiktok_repository.py  ← Comptes, profils, sessions TikTok
```

---

## Diagramme de classe

```
┌──────────────────────┐
│   get_db_service()   │  ← Point d'entrée unique (database/__init__.py)
└──────────┬───────────┘
           │ retourne
           ▼
┌──────────────────────────────────────────────┐
│          LocalDatabaseClient                 │  ← local/client.py
│──────────────────────────────────────────────│
│ + get_or_create_account(username) → (id,bool)│
│ + save_profile(profile) → bool               │
│ + get_profile(username) → InstagramProfile   │
│ + record_interaction(...) → bool             │
│ + is_profile_processed(...) → bool           │
│ + mark_profile_as_processed(...) → bool      │
│ + record_filtered_profile(...) → bool        │
│ + is_profile_filtered(...) → bool            │
│ + create_session(...) → int                  │
│ + update_session(...) → bool                 │
│ + get_session_stats(...) → dict              │
│ + check_action_limits() → dict  [no-op]      │
│ + record_action_usage() → bool  [no-op]      │
└──────────┬───────────────────────────────────┘
           │ délègue à
           ▼
┌──────────────────────────────────────────────┐
│        LocalDatabaseService                  │  ← local/service.py
│──────────────────────────────────────────────│
│ - db_path: str                               │
│ - _connection: sqlite3.Connection            │
│──────────────────────────────────────────────│
│ + accounts   → AccountRepository             │
│ + profiles   → ProfileRepository             │
│ + interactions → InteractionRepository       │
│ + sessions   → SessionRepository             │
│ + discovery  → DiscoveryRepository           │
│ + tiktok     → TikTokRepository              │
│──────────────────────────────────────────────│
│ + get_or_create_account(...)                 │
│ + save_profile(...)                          │
│ + record_interaction(...)                    │
│ + check_profile_processed(...)               │
│ + record_filtered_profile(...)               │
│ + create_session(...) / update_session(...)   │
│ + is_hashtag_post_processed(...)             │
│ + record_processed_hashtag_post(...)         │
│ ... (+ ~60 autres méthodes déléguées aux repos)│
└──────────┬───────────────────────────────────┘
           │ utilise
           ▼
┌──────────────────────────────────────────────┐
│           Repositories (7)                   │
│──────────────────────────────────────────────│
│ BaseRepository          ← classe de base     │
│ AccountRepository       ← instagram_accounts │
│ ProfileRepository       ← instagram_profiles │
│ InteractionRepository   ← interaction_history│
│ SessionRepository       ← sessions           │
│ DiscoveryRepository     ← discovery_*        │
│ TikTokRepository        ← tiktok_*           │
└──────────────────────────────────────────────┘
```

---

## Schéma de la base de données

### Tables Instagram

```
┌─────────────────────────┐       ┌──────────────────────────────┐
│   instagram_accounts    │       │     instagram_profiles       │
│─────────────────────────│       │──────────────────────────────│
│ account_id PK AUTO      │       │ profile_id PK AUTO           │
│ username TEXT UNIQUE     │       │ username TEXT UNIQUE          │
│ is_bot INTEGER           │       │ full_name TEXT                │
│ user_id INTEGER          │       │ biography TEXT                │
│ license_id INTEGER       │       │ followers_count INTEGER       │
│ created_at TEXT          │       │ following_count INTEGER       │
└─────────┬───────────────┘       │ posts_count INTEGER           │
          │                       │ is_private INTEGER            │
          │ 1:N                   │ is_verified INTEGER           │
          ▼                       │ is_business INTEGER           │
┌─────────────────────────┐       │ business_category TEXT        │
│   interaction_history   │       │ website TEXT                  │
│─────────────────────────│       │ profile_pic_path TEXT         │
│ id PK AUTO              │       │ notes TEXT                    │
│ session_id FK → sessions│       │ created_at, updated_at TEXT   │
│ account_id FK           │       └──────────┬───────────────────┘
│ profile_id FK           │──────────────────►│
│ interaction_type TEXT    │                   │
│ interaction_time TEXT    │                   │ 1:N
│ success INTEGER         │                   ▼
│ content TEXT             │       ┌──────────────────────────────┐
└─────────────────────────┘       │     filtered_profiles        │
                                  │──────────────────────────────│
┌─────────────────────────┐       │ id PK AUTO                   │
│       sessions          │       │ profile_id FK                │
│─────────────────────────│       │ account_id FK                │
│ session_id PK AUTO      │       │ username TEXT                 │
│ account_id FK           │       │ filtered_at TEXT              │
│ session_name TEXT       │       │ reason TEXT                   │
│ target_type TEXT        │       │ source_type TEXT              │
│ target TEXT             │       │ source_name TEXT              │
│ start_time TEXT         │       │ session_id INTEGER            │
│ end_time TEXT           │       │ UNIQUE(profile_id, account_id)│
│ duration_seconds INT    │       └──────────────────────────────┘
│ config_used TEXT (JSON) │
│ status TEXT             │       ┌──────────────────────────────┐
│ error_message TEXT      │       │   profile_stats_history      │
│ synced_to_api INTEGER   │       │──────────────────────────────│
│ created_at, updated_at  │       │ id PK AUTO                   │
└─────────────────────────┘       │ profile_id FK                │
                                  │ followers_count INTEGER       │
┌─────────────────────────┐       │ following_count INTEGER       │
│      daily_stats        │       │ posts_count INTEGER           │
│─────────────────────────│       │ engagement_rate REAL          │
│ id PK AUTO              │       │ recorded_at TEXT              │
│ account_id FK           │       └──────────────────────────────┘
│ date TEXT               │
│ total_likes INTEGER     │       ┌──────────────────────────────┐
│ total_follows INTEGER   │       │     instagram_posts          │
│ total_unfollows INTEGER │       │──────────────────────────────│
│ total_comments INTEGER  │       │ post_id PK AUTO              │
│ total_story_views INT   │       │ profile_id FK                │
│ total_story_likes INT   │       │ account_id FK                │
│ total_sessions INTEGER  │       │ instagram_post_id TEXT UNIQUE │
│ completed_sessions INT  │       │ media_type TEXT               │
│ failed_sessions INTEGER │       │ caption TEXT                  │
│ total_duration_seconds  │       │ likes_count, comments_count  │
│ synced_to_api INTEGER   │       │ posted_at TEXT                │
│ UNIQUE(account_id, date)│       │ status TEXT                   │
└─────────────────────────┘       └──────────────────────────────┘
```

### Tables TikTok

```
┌─────────────────────────┐       ┌──────────────────────────────┐
│    tiktok_accounts      │       │     tiktok_profiles          │
│─────────────────────────│       │──────────────────────────────│
│ account_id PK AUTO      │       │ profile_id PK AUTO           │
│ username TEXT UNIQUE     │       │ username TEXT UNIQUE          │
│ display_name TEXT        │       │ display_name TEXT             │
│ is_bot INTEGER           │       │ followers_count INTEGER       │
│ user_id, license_id     │       │ following_count INTEGER       │
│ created_at TEXT          │       │ likes_count INTEGER           │
└─────────┬───────────────┘       │ videos_count INTEGER          │
          │ 1:N                   │ is_private, is_verified       │
          ▼                       │ biography TEXT                │
┌─────────────────────────┐       └──────────────────────────────┘
│ tiktok_interaction_hist │
│─────────────────────────│       ┌──────────────────────────────┐
│ id PK AUTO              │       │   tiktok_filtered_profiles   │
│ session_id FK           │       │──────────────────────────────│
│ account_id FK           │       │ id PK AUTO                   │
│ profile_id FK           │       │ profile_id FK, account_id FK │
│ interaction_type TEXT    │       │ username, reason TEXT         │
│ video_id TEXT            │       │ UNIQUE(profile_id, account_id)│
│ success INTEGER          │       └──────────────────────────────┘
└─────────────────────────┘
                                  ┌──────────────────────────────┐
┌─────────────────────────┐       │    tiktok_daily_stats        │
│    tiktok_sessions      │       │──────────────────────────────│
│─────────────────────────│       │ id PK AUTO                   │
│ session_id PK AUTO      │       │ account_id FK                │
│ account_id FK           │       │ date TEXT                    │
│ session_name TEXT       │       │ total_likes, follows, etc.   │
│ workflow_type TEXT       │       │ UNIQUE(account_id, date)     │
│ likes, follows, etc.    │       └──────────────────────────────┘
│ status TEXT              │
└─────────────────────────┘
```

### Tables Discovery & Scraping

```
┌──────────────────────┐     ┌────────────────────┐     ┌─────────────────────┐
│ discovery_campaigns  │────►│ discovery_progress │     │ discovered_profiles │
│──────────────────────│     │────────────────────│     │─────────────────────│
│ campaign_id PK       │     │ progress_id PK     │     │ profile_id PK       │
│ account_id FK        │     │ campaign_id FK     │     │ campaign_id FK      │
│ name TEXT            │     │ source_type TEXT    │     │ username TEXT        │
│ niche_keywords JSON  │     │ current_post_index │     │ engagement_score    │
│ target_hashtags JSON │     │ status TEXT         │     │ ai_score REAL       │
│ status TEXT          │     └────────────────────┘     │ status TEXT          │
└──────────────────────┘                                └─────────────────────┘

┌──────────────────────┐     ┌────────────────────┐     ┌─────────────────────┐
│  scraping_sessions   │────►│  scraped_profiles  │     │  scraped_comments   │
│──────────────────────│     │────────────────────│     │─────────────────────│
│ scraping_id PK       │     │ id PK              │     │ comment_id PK       │
│ account_id FK        │     │ scraping_id FK     │     │ scraping_session_id │
│ scraping_type TEXT   │     │ profile_id FK      │     │ username TEXT        │
│ source_type TEXT     │     │ ai_score INTEGER   │     │ content TEXT         │
│ total_scraped INT    │     │ ai_qualified INT   │     │ likes_count INT     │
│ status TEXT          │     └────────────────────┘     └─────────────────────┘
└──────────────────────┘

┌────────────────────────────┐
│  processed_hashtag_posts   │
│────────────────────────────│
│ id PK AUTO                 │
│ account_id FK              │
│ hashtag TEXT               │
│ post_author TEXT            │
│ post_caption_hash TEXT     │
│ likers_processed INTEGER   │
│ interactions_made INTEGER  │
│ UNIQUE(account_id, hashtag,│
│   post_author, hash)       │
└────────────────────────────┘
```

---

## Flux de données

```
                    ┌─────────────────────┐
                    │   Electron App      │
                    │  (better-sqlite3)   │
                    │                     │
                    │  ┌───────────────┐  │
                    │  │ database-     │  │
                    │  │ service.ts    │  │
                    │  └───────┬───────┘  │
                    │          │           │
                    └──────────┼───────────┘
                               │
                    ╔══════════╧══════════╗
                    ║  taktik-data.db     ║  ← SQLite WAL mode
                    ║  (shared file)      ║
                    ╚══════════╤══════════╝
                               │
                    ┌──────────┼───────────┐
                    │          │           │
                    │  ┌───────┴───────┐  │
                    │  │ LocalDatabase │  │
                    │  │ Service       │  │
                    │  └───────────────┘  │
                    │   Python Bridges    │
                    │   (sqlite3 natif)   │
                    └─────────────────────┘
```

### Accès concurrent

- **Electron** : Utilise `better-sqlite3` (synchrone, un seul thread Node.js)
- **Python** : Utilise `sqlite3` natif avec `check_same_thread=False`
- **WAL mode** : Permet la lecture simultanée pendant l'écriture
- **Timeout** : 30 secondes pour éviter les deadlocks

---

## Utilisation dans le code

### Depuis un workflow Python

```python
from taktik.core.database import get_db_service, get_local_database

# Via le client (interface haut-niveau)
db = get_db_service()
account_id, created = db.get_or_create_account("username")
db.record_interaction(account_id=1, username="target", interaction_type="LIKE")
is_done = db.is_profile_processed(account_id=1, username="target")

# Via le service local directement (accès aux repositories)
local_db = get_local_database()
local_db.accounts.get_all()
local_db.profiles.search("keyword")
local_db.sessions.get_by_account(account_id=1)
local_db.tiktok.create_session(...)
```

### Depuis l'Electron app

```typescript
import { databaseService } from '../database/database-service';

// Lecture directe SQLite (pas d'API)
const sessions = databaseService.getSessions(accountId);
const stats = databaseService.getDailyStats(accountId, days);
const profiles = databaseService.getProfiles(accountId);
```

---

## Types d'interactions

| Type | Description | Plateforme |
|------|-------------|------------|
| `LIKE` | Like sur un post | Instagram |
| `FOLLOW` | Follow d'un profil | Instagram |
| `UNFOLLOW` | Unfollow d'un profil | Instagram |
| `COMMENT` | Commentaire sur un post | Instagram |
| `STORY_WATCH` | Vue de story | Instagram |
| `STORY_LIKE` | Like de story | Instagram |
| `PROFILE_VISIT` | Visite de profil | Instagram |
| `LIKE` | Like sur une vidéo | TikTok |
| `FOLLOW` | Follow d'un profil | TikTok |
| `FAVORITE` | Ajout aux favoris | TikTok |
| `COMMENT` | Commentaire | TikTok |
| `SHARE` | Partage | TikTok |

---

## Historique des migrations

| Date | Description |
|------|-------------|
| 2026-01 | Création de la DB locale SQLite (migration depuis API distante) |
| 2026-01 | Ajout des tables TikTok |
| 2026-01 | Ajout des tables Discovery (campagnes, scraping) |
| 2026-02 | Suppression de `api_client.py`, `api_database_service.py`, `config.py` (dead code) |
| 2026-02 | Suppression de `sync_to_remote()` (route `/desktop/sync/*` supprimée) |
| 2026-02 | Réorganisation : `local/service.py`, `local/client.py`, `repositories/` |
| 2026-02 | Simplification de `get_db_service()` → `LocalDatabaseClient` direct |
