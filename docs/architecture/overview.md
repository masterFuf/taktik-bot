# Architecture — Vue d'ensemble

TAKTIK Bot est le moteur Python de l'application desktop. Il reçoit des ordres d'Electron, pilote des apps Android avec uiautomator2/ADB, écrit les données d'automatisation dans SQLite local, et renvoie l'état de session au front via stdout JSON.

Cette page donne la carte générale. Pour la lecture détaillée des couches, voir [Architecture en couches](layers.md).

## Diagramme global

```mermaid
flowchart LR
    subgraph Front["front/ — App Electron"]
        UI[React UI]
        Handlers[Electron handlers]
        Proc[ProcessManager / bridge launcher]
        DBE[SQLite Electron]
    end

    subgraph Bot["bot/ — Bot Python"]
        Launcher[bridges/launcher.py]
        subgraph Bridges["bridges/"]
            Common[common services]
            IG[Instagram bridges]
            TT[TikTok bridges]
            TH[Threads bridge]
            YT[YouTube bridges]
            GM[Gmail bridge]
            Compat[Compat bridges]
        end

        subgraph Core["taktik/core/"]
            Workflows[Workflows applicatifs]
            Business[Actions business]
            Atomic[Actions atomiques]
            UISelectors[UI selectors / language / detectors]
            Shared[Shared device/input/platform]
            CompatCore[compat + clone]
        end

        subgraph Data["SQLite local"]
            Service[LocalDatabaseService]
            Repos[Repositories]
            Schema[Schema + migrations]
        end
    end

    subgraph Android["Android device / emulator"]
        Apps[Instagram / TikTok / Threads / YouTube / Gmail]
        U2[uiautomator2 server]
        ADB[ADB shell]
    end

    UI --> Handlers
    Handlers --> Proc
    Proc --> Launcher
    Launcher --> Bridges
    Bridges --> Common
    Bridges --> Workflows
    Workflows --> Business
    Business --> Atomic
    Atomic --> UISelectors
    Atomic --> Shared
    Shared --> U2
    Shared --> ADB
    U2 --> Apps
    ADB --> Apps
    Workflows --> Service
    Business --> Service
    Service --> Repos
    Repos --> Schema
    Handlers --> DBE
    CompatCore --> UISelectors
```

## Les grands rôles

| Zone | Rôle |
|---|---|
| Electron UI | Formulaires, live panels, stats, debug, device management. |
| Electron handlers | Adaptation UI vers bridge, spawn process, parsing stdout. |
| Bridges Python | Entrées exécutables par workflow ou famille de workflows. |
| Common services | Connexion device, lancement app, IPC, clavier, AI, DB. |
| Modules sociaux | Logique Instagram, TikTok, Threads, YouTube, Gmail. |
| Compat/Clone | Sélecteurs versionnés, APK clonées, tests de compatibilité. |
| SQLite local | Profils, interactions, sessions, scraping, DMs, settings. Les anciennes tables de campagne Discovery ne font plus partie du schéma neuf. |
| Android | Apps réelles pilotées par uiautomator2 et ADB. |

## Flux d'une session

```mermaid
sequenceDiagram
    participant UI as Electron UI
    participant H as Electron handler
    participant B as Bridge Python
    participant C as Common services
    participant W as Workflow
    participant A as Actions
    participant D as Android device
    participant DB as SQLite

    UI->>H: start workflow(config)
    H->>B: spawn + config
    B->>C: bootstrap + connect device
    C->>D: uiautomator2 / ADB ready
    B->>C: launch/restart app
    B->>W: run(config)
    loop session
        W->>A: action métier
        A->>D: xpath / click / scroll / text
        W->>DB: save profile/interactions/stats
        W-->>B: callbacks / IPC events
        B-->>H: stdout JSON
        H-->>UI: update live state
    end
    B-->>H: final result
```

## Plateformes couvertes

| Plateforme | Module domaine | Bridges | Docs |
|---|---|---|---|
| Instagram | `taktik/core/social_media/instagram/` | automation, scraping, smart comment, DM, account, agent, post scraping | [Instagram](../modules/instagram/overview.md) |
| TikTok | `taktik/core/social_media/tiktok/` | for you, search, followers, scraping, DMs, publish, account, unfollow | [TikTok](../modules/tiktok/overview.md) |
| Threads | `taktik/core/social_media/threads/` | `threads_bridge` | [Threads](../modules/threads/overview.md) |
| YouTube | `taktik/core/social_media/youtube/` | upload, account, action test | [YouTube](../modules/youtube/overview.md) |
| Gmail | `taktik/core/app/email/gmail/` | account/OTP bridge | [Gmail](../modules/gmail/overview.md) |

## Concepts clés

| Concept | Description |
|---|---|
| Bridge | Process Python isolé appelé par Electron. |
| Workflow applicatif | Tâche complète: scraping, upload, signup, OTP, post scraping. |
| Workflow business | Stratégie d'interaction sociale: followers, hashtag, feed, unfollow. |
| Action business | Logique métier composée: like posts, comment, extract profile, filter. |
| Action atomique | Opération UI unitaire: click, scroll, detect, type, navigate. |
| Selector singleton | Dataclass importée partout, patchable en mémoire. |
| IPC event | Ligne JSON envoyée par stdout au front. |
| Repository | Accès SQLite isolé par domaine. |

## Règles architecturales

- Les bridges adaptent et orchestrent, mais ne doivent pas devenir des classes métier géantes.
- Les workflows contiennent la stratégie, pas les XPath inline.
- Les sélecteurs vivent dans `ui/selectors/` et sont patchables par compat/clone.
- Les écritures SQLite passent par services/repositories quand ils existent.
- Les workflows de domaine ne doivent pas dépendre directement du transport IPC quand une injection de callbacks suffit.
- Le code partagé doit aller dans `bridges/common/` ou `taktik/core/shared/`, pas être copié entre plateformes.

## Pages liées

| Besoin | Page |
|---|---|
| Couches détaillées | [Architecture en couches](layers.md) |
| Carte mentale end-to-end | [Carte d'interaction](application-map.md) |
| IPC bridge | [Communication IPC](bridges-ipc.md) |
| Séquences | [Diagrammes de séquence](sequence-diagrams.md) |
| Patterns | [Design Patterns](design-patterns.md) |
| Refactor partagé | [Refactor 2025](refactor-2025.md) |
| SQLite | [Vue d'ensemble SQLite](../database/overview.md) |
