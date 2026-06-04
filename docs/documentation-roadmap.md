# État de couverture & roadmap

> **Périmètre : `[Transversal]`**
> Cette page suit ce qui est documenté dans la doc consolidee et ce qui reste à couvrir, en séparant clairement `[Bot]`, `[Front]` et `[Transversal]`.

Objectif : chaque gros dossier doit avoir une page d'overview, une page de flux, une référence des classes/configs/events, et des liens vers les couches avec lesquelles il interagit.

## Standards de documentation

Chaque module important doit contenir :

| Élément | Attendu |
|---|---|
| Périmètre | Badge `[Bot]`, `[Front]` ou `[Transversal]` en haut de page |
| Arborescence | Dossiers/fichiers réels, pas une vue simplifiée obsolète |
| Exports publics | Classes/functions exposées par `__init__.py`, preload ou bridges |
| Flux Mermaid | Diagramme de séquence ou flowchart horizontal quand possible |
| Config d'entrée | JSON, dataclasses ou interfaces attendues |
| Events IPC | Messages émis vers Electron et retours attendus |
| Persistance | Tables SQLite/API touchées |
| Dépendances | Bridges, managers, selectors, actions, repositories |
| Limites connues | TODO réels, legacy, points fragiles |

## Synthèse

| Domaine | Couverture | Prochaine action |
|---|---|---|
| Architecture globale | Bonne | Ajouter des séquences par workflow critique. |
| Base SQLite | Bonne | Vérifier régulièrement schéma Python/Electron. |
| Instagram Bot | Très bonne | Ajouter pages dédiées DM/content/tests si nécessaire. |
| Front Electron core | Très bonne | Maintenir handlers spécialisés et lifecycle. |
| Scheduler | Bonne | Maintenir node UI vs node runtime. |
| TikTok | Bonne | Maintenir selectors/bridges avec les prochains dumps UI. |
| YouTube | Bon côté Bot | Ajouter page `[Front]` dédiée si l'UI YouTube grandit. |
| Gmail | Bon côté Bot | Ajouter page `[Front]` dédiée si l'UI Gmail/OTP grandit. |
| Bot core partagé | Bonne | Maintenir avec les nouvelles briques transversales. |
| Compatibilité | Bonne | [Compat Bridge Tooling](compat/bridge-tooling.md), [Framework de test](compat/testing-framework.md) |

## Couverture `[Bot]`

### `bot/bridges/`

| Dossier | État | Page actuelle | Reste |
|---|---|---|---|
| `common/` | Bon | [Services communs](bridges/common-services.md) | Cas d'erreur détaillés, lifecycle process. |
| `instagram/` | Bon | [Bridges Instagram](bridges/instagram.md) | Maintenir avec nouveaux bridges. |
| `tiktok/` | Bon | [Bridges TikTok](bridges/tiktok.md) | Maintenir avec nouveaux workflowType/events. |
| `threads/` | Bon MVP | [Bridges Threads](bridges/threads.md) | Revoir si module grandit. |
| `youtube/` | Bon | [Bridges YouTube](bridges/youtube.md) | Maintenir avec nouveaux workflows seulement s'ils deviennent reellement implementes ; `watch_feed`/`search` sont aujourd'hui des TODO du dispatcher legacy. |
| `gmail/` | Bon | [Bridges Gmail](bridges/gmail.md) | Maintenir avec nouveaux `error_type` OTP/sign-in. |
| `compat/` | Bon | [Compat Bridge Tooling](compat/bridge-tooling.md), compat pages générales | Maintenir avec nouveaux bridges action/selector/workflow. |
| `launcher.py` | Bon | [Bridge Launcher & Packaging](bridges/launcher.md) | Maintenir avec `PLATFORM_BRIDGES` et `build-all.ps1`. |

### `bot/taktik/core/social_media/`

| Module | État | Page actuelle | Reste |
|---|---|---|---|
| `instagram/` | Très avancé | Section Instagram complète | Tests, DM/content si besoin. |
| `tiktok/` | Bon | Section TikTok | Ajouter exemples de configs réelles si besoin. |
| `threads/` | Bon MVP | [Threads](modules/threads/overview.md) | Persistance/actions si ajoutées. |
| `youtube/` | Bon | [YouTube](modules/youtube/overview.md) | Maintenir selectors avec les futurs dumps UI YouTube. |

### `bot/taktik/core/` hors social media

| Dossier | État | Reste |
|---|---|---|
| `shared/` | Bon | [Core partagé](core/shared.md) |
| `device/` | Bon legacy | [Core partagé](core/shared.md) explique `shared/device` et l'ancien `core/device`. |
| `agent/` | Bon | [Agent & IA](core/agent-ai.md) |
| `ai/` | Bon | [Agent & IA](core/agent-ai.md) |
| `clone/` | Bon | [Config, Clones & Sécurité](core/config-clone-security.md) |
| `compat/` | Bon | [Compat Bridge Tooling](compat/bridge-tooling.md), [Versioned Selectors](compat/versioned-selectors.md), [Framework de test](compat/testing-framework.md). |
| `media/` | Bon | [Media, Proxy & Recorder](core/media-recorder.md) |
| `recorder/` | Bon | [Media, Proxy & Recorder](core/media-recorder.md) |
| `security/` | Bon legacy | [Config, Clones & Sécurité](core/config-clone-security.md) |
| `config/` | Bon | [Config, Clones & Sécurité](core/config-clone-security.md) |
| `email/` | Bon | [Gmail](modules/gmail/overview.md) détaille workflow, OTP, selectors et persistance. |

### `bot/taktik/core/database/`

| Zone | État | Reste |
|---|---|---|
| Schema | Bon | Garder synchro Python/Electron. |
| Repositories | Bon | Vérifier après changements. |
| Models | Bon | Vérifier après changements. |
| Migrations | Bon | Ajouter chaque nouvelle migration. |

## Couverture `[Front]`

### `front/electron/`

| Zone | État | Page actuelle | Reste |
|---|---|---|---|
| `main.ts` | Bon | [App Lifecycle](desktop/app-lifecycle.md), [Vue d'ensemble Electron](desktop/overview.md) | Maintenir CSP, handlers, cleanup. |
| `preload.ts` + `preload/` | Bon | [Preload API](desktop/preload-api.md) | Typage progressif et smoke tests. |
| `handlers/` | Bon | [Handlers IPC Electron](desktop/ipc-handlers.md), [ADB & Device Setup Handlers](desktop/adb-device-handlers.md), [Platform Bridge Handlers](desktop/platform-bridge-handlers.md), [AI Handlers](desktop/ai-handlers.md) | Maintenir avec nouveaux handlers spécialisés. |
| `database/` | Bon | [Base SQLite Electron](desktop/database.md), [SQLite Repositories Electron](desktop/electron-database-repositories.md) | Garder synchro avec schema/migrations/repositories. |
| `front/docs/database/` | Bon | `front/docs/database/SCHEMA.md` synchronisé avec [Schéma SQLite](database/schema.md) | Garder la copie Front alignée avec la reference Bot consolidee. |
| `services/app/scheduler/` | Bon | [Scheduler & Sessions](workflows/sessions.md) | Maintenir node runtime. |
| `managers/` | Bon | [Managers, Sync & Updater](desktop/electron-managers-sync-updater.md) | Relier chaque handler à son ProcessManager. |
| `sync/` | Bon | [Managers, Sync & Updater](desktop/electron-managers-sync-updater.md) | Ajouter contexte renderer si besoin. |
| `updater/` | Bon | [Managers, Sync & Updater](desktop/electron-managers-sync-updater.md) | Relier build/publish releases. |
| `scripts/build`, `scripts/publish` | Bon | [Build, Packaging & Auto-Update](desktop/build-update.md) | Maintenir avec `package.json`, `build-all.ps1`, `publish-update.ps1`. |
| `utils/` | Bon | [Electron Utils & Types](desktop/electron-utils-types.md) | Maintenir avec registry bridges et env Python. |
| `types/` | Bon | [Electron Utils & Types](desktop/electron-utils-types.md) | Garder les types partagés légers. |

### `front/src/features/`

| Zone | État | Page actuelle | Reste |
|---|---|---|---|
| `workspace/scheduler/` | Bon | [Scheduler UI](desktop/scheduler-ui.md) | Garder synchronisé avec nodes. |
| `workspace/sessions/` | Bon | [Sessions UI](desktop/sessions-ui.md), [Scheduler & Sessions](workflows/sessions.md) | Maintenir mapping workflow et stop methods. |
| `workspace/device/` | Bon | [Workspace Device](desktop/device-workspace.md), [ADB & Device Setup Handlers](desktop/adb-device-handlers.md) | Approfondir MirrorPanel/NoDeviceConnected si besoin. |
| `workspace/dashboard/` | Bon overview | [Analytics & Settings](desktop/settings-analytics.md) | Approfondir routes/dashboard complet si besoin. |
| `workspace/analytics/` | Bon | [Analytics & Settings](desktop/settings-analytics.md) | Maintenir mapping Instagram/TikTok. |
| `platforms/instagram/` | Bon avance | [Features par plateforme](desktop/platform-features.md), [Target Search Instagram](desktop/target-search.md) | Pages dediees possibles : Smart Comment, DM, upload. |
| `platforms/tiktok/` | Bon overview | [Features par plateforme](desktop/platform-features.md) | Approfondir après reprise du bot TikTok. |
| `platforms/threads/` | Bon overview | [Features par plateforme](desktop/platform-features.md) | Revoir si module grandit. |
| `platforms/gmail/` | Bon overview | [Features par plateforme](desktop/platform-features.md) | Détailler OTP si nécessaire. |
| `platforms/youtube/` | Bon overview | [Features par plateforme](desktop/platform-features.md) | Détailler upload end-to-end. |
| `shared/` | Bon | [Shared Frontend Components](desktop/shared-frontend-components.md) | Maintenir avec nouveaux composants partagés. |
| `tools/` | Bon | [Tools, Debug & Compatibility](desktop/tools-debug.md), [Video Tools](desktop/video-tools.md) | Maintenir avec les nouveaux outils de capture/montage. |
| `app/settings` | Bon | [Analytics & Settings](desktop/settings-analytics.md) | Maintenir avec les nouvelles sections settings. |
| `app/` autres | Bon | [App Lifecycle](desktop/app-lifecycle.md), [Auth, Licence & Device Access](desktop/auth-license-flow.md) | Approfondir welcome/theme/updater si nécessaire. |

## Couverture `[Transversal]`

| Flow | État | Page actuelle | Reste |
|---|---|---|---|
| Electron ↔ Bot IPC | Bon | [Communication IPC](architecture/bridges-ipc.md), [Protocole IPC](bridges/ipc-protocol.md) | Standardiser events par plateforme. |
| Scheduler -> sessions bot | Bon | [Scheduler & Sessions](workflows/sessions.md) | Maintenir avec nodes runtime. |
| SQLite Python + Electron | Bon | [Schéma SQLite](database/schema.md), [Base SQLite Electron](desktop/database.md), [SQLite Repositories Electron](desktop/electron-database-repositories.md) | Surveiller divergences. |
| Licence/auth/device | Bon | [Auth, Licence & Device Access](desktop/auth-license-flow.md) | Maintenir avec API `/desktop/login` et device access. |
| Upload content | Bon | [Upload Content](workflows/upload-content.md), [Platform Bridge Handlers](desktop/platform-bridge-handlers.md), [Features par plateforme](desktop/platform-features.md) | Maintenir si les events Instagram gagnent un `deviceId` ou si un historique d'uploads est ajouté. |
| Sync cross-device | Bon | [Sync cross-device](architecture/sync-cross-device.md), [Managers, Sync & Updater](desktop/electron-managers-sync-updater.md) | Maintenir tables sync, conflits et migrations `sync_id`. |

## Priorités conseillées

### 1. Front Electron spécialisé `[Front]`

Pourquoi : le coeur Electron est maintenant couvert; il reste à approfondir certaines familles très spécialisées si elles évoluent.

Pages à créer/compléter :

- Continuer à maintenir les pages quand de nouveaux handlers, workflows ou tables SQLite sont ajoutés.

### 2. YouTube/Gmail `[Bot]` + `[Front]`

Pourquoi : la partie Bot est maintenant couverte; il reste seulement à créer des pages front dédiées si l'UI devient plus riche.

Pages Bot couvertes :

- `modules/youtube/overview.md`
- `bridges/youtube.md`
- `modules/gmail/overview.md`
- `bridges/gmail.md`

## Règle de maintenance

Chaque fois qu'un fichier schema, bridge, workflow, selector ou repository est modifié, vérifier :

1. la page module ;
2. la page bridge ;
3. la page DB si persistence ;
4. le protocole IPC si event nouveau ;
5. `SUMMARY.md` et `_sidebar.md` si nouvelle page.

## Règle de séparation Bot / Front

Chaque page doit indiquer son propriétaire logique.

| Périmètre | Quand l'utiliser |
|---|---|
| `[Bot]` | Code Python dans `bot/`, workflows, bridges, actions, selectors, repositories Python. |
| `[Front]` | Code Electron/React dans `front/`, handlers, pages, UI, scheduler renderer, database Electron. |
| `[Transversal]` | Flow complet traversant `front/`, `bot/`, SQLite, Android ou API. |

Les pages `[Transversal]` doivent toujours nommer les fichiers des deux côtés pour éviter de donner l'impression que tout appartient au bot.

## Notes de cohérence récentes

| Sujet | Décision documentaire |
|---|---|
| Quotas d'actions | Ne plus documenter comme mécanisme actif de blocage. Les anciens champs API comme `max_actions_per_day` sont compat/legacy ; les limites opérationnelles sont locales aux sessions/workflows. |
| Devices licence | Documenter comme limite Android par licence. Les PC desktop sont enregistrés mais exclus du comptage de devices. |
| Base SQLite | La reference documentaire consolidee reste `bot/database/schema.md`, a verifier contre les schemas Python/Electron ; `front/docs/database/SCHEMA.md` est une copie synchronisee pour la doc Electron. |
| Scheduler Front | Distinguer les nodes modélisés côté UI des nodes réellement exécutés par `scheduler-engine.ts`. |
