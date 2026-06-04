# Electron database repositories `[Front]`

Cette page documente la couche repositories SQLite cote desktop apres la
refactorisation par domaines. Elle a ete reverifiee contre
`front/electron/database/repositories/index.ts`.

## Frontiere

Les repositories ne contiennent que l'acces SQLite. La logique metier vit dans
`front/electron/services/**`, et les handlers IPC ne doivent pas requeter la
base directement.

```text
Renderer React
  -> preload
  -> handlers Electron
  -> services owner
  -> repositories
  -> better-sqlite3 / taktik-data.db
```

## Arborescence actuelle

```text
front/electron/database/repositories/
+-- base/
|   +-- BaseRepository.ts
+-- app/
|   +-- agent/
|   +-- database-explorer/
|   +-- device-group/
|   +-- gmail/
|   +-- interaction/
|   +-- media/
|   +-- network-history/
|   +-- network-pool/
|   +-- scheduler/
|   +-- sync/
+-- platforms/
|   +-- instagram/
|   |   +-- account/
|   |   +-- following-sync/
|   |   +-- graph/
|   |   +-- interaction/
|   |   +-- profile/
|   |   +-- scraping/
|   |   +-- session/
|   |   +-- smart-comment/
|   |   +-- stats/
|   +-- tiktok/
|       +-- account/
|       +-- interaction/
|       +-- profile/
|       +-- scraping/
|       +-- session/
|       +-- stats/
+-- index.ts
```

Ne pas recreer l'ancienne organisation a plat (`repositories/profile`,
`repositories/discovery`, etc.).

## Container

`RepositoryContainer` est le point d'injection unique. Il instancie tous les
repositories avec la meme connexion `better-sqlite3`.

| Propriete | Repository |
|---|---|
| `accounts` | `platforms/instagram/account/AccountRepository` |
| `profiles` | `platforms/instagram/profile/ProfileRepository` |
| `profileGeoEnrichment` | `platforms/instagram/profile/GeoEnrichmentRepository` |
| `interactions` | `platforms/instagram/interaction/InteractionRepository` |
| `sessions` | `platforms/instagram/session/SessionRepository` |
| `scrapedProfiles` | `platforms/instagram/scraping/ScrapedProfileRepository` |
| `stats` | `platforms/instagram/stats/StatsRepository` |
| `smartComment` | `platforms/instagram/smart-comment/SmartCommentRepository` |
| `graph` | `platforms/instagram/graph/RelationshipGraphRepository` |
| `followingSync` | `platforms/instagram/following-sync/FollowingSyncRepository` |
| `tiktok` | `platforms/tiktok/TikTokRepository` |
| `scheduler` | `app/scheduler/SchedulerRepository` |
| `schedulerTaxonomy` | `app/scheduler/SchedulerTaxonomyRepository` |
| `schedulerTargetIntelligence` | `app/scheduler/SchedulerTargetIntelligenceRepository` |
| `deviceGroups` | `app/device-group/DeviceGroupRepository` |
| `networkPools` | `app/network-pool/NetworkPoolRepository` |
| `networkHistory` | `app/network-history/NetworkHistoryRepository` |
| `gmailAccounts` | `app/gmail/GmailAccountRepository` |
| `databaseExplorer` | `app/database-explorer/DatabaseExplorerRepository` |
| `tursoLocalSync` | `app/sync/TursoLocalSyncRepository` |
| `mediaCache` | `app/media/MediaCacheRepository` |
| `agentOrchestrationContext` | `app/agent/AgentOrchestrationContextRepository` |
| `interactionDetails` | `app/interaction/InteractionDetailsRepository` |

## Discovery legacy

Il n'existe plus de `DiscoveryRepository` ni de `DiscoveryService` actifs dans
`front/electron/database/repositories`. Le scoring IA des profils scrapes passe
par :

| Besoin | Chemin actuel |
|---|---|
| Lien profil/session de scraping | `ScrapedProfileRepository` |
| Qualification et scores IA | `ScrapingQualificationService` |
| Recherche de cibles Instagram | `InstagramTargetSearchService` |

Ne pas recreer les tables ou services `discovery_campaigns`,
`discovered_profiles`, `discovery_templates` pour le workflow Discovery legacy.

## Services owners

La logique autour des repositories est dans `front/electron/services/` :

| Domaine | Dossier |
|---|---|
| Services app transverses | `services/app/**` |
| Services plateformes | `services/platforms/<platform>/**` |
| Services partages | `services/shared/**` |
| Outils internes | `services/tools/**` |

Exemples :

| Besoin | Service owner |
|---|---|
| Sessions app | `services/app/sessions/**` |
| Scheduler | `services/app/scheduler/**` |
| Instagram automation | `services/platforms/instagram/automation/**` |
| Instagram scraping | `services/platforms/instagram/scraping/**` |
| TikTok workflows | `services/platforms/tiktok/**` |
| Cartography Lab | `services/tools/cartography/**` |

## Regles

| Regle | Pourquoi |
|---|---|
| Pas de SQL brut dans les handlers | Les handlers restent une frontiere IPC, pas une couche DB. |
| Pas de type inline dans les repositories | Les types vivent dans `front/electron/database/models/**` ou `front/src/app/types/**`. |
| Pas de repository dans `services/` | Un repository appartient a `database/repositories/**`. |
| Pas de service owner dans `database/repositories/` | Le repository ne porte pas la logique metier. |
| Pas de stdout parasite | Les repositories utilisent le logger, jamais `print`/`console.log` non controle pour les bridges JSON. |

## Sources verifiees

- `front/electron/database/repositories/index.ts`
- `front/electron/database/models/**`
- `front/electron/services/**`
- `technical/database-ownership.md`
