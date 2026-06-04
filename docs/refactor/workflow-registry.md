# [Transversal] Workflow Registry

## Role

Le `workflowType` est un contrat transversal : il circule entre React, Electron, les bridges Python, les workflows Bot, le scheduler, les sessions SQLite et les panels live.

Avant ce chantier, ces valeurs etaient dispersees dans des unions TypeScript, des configs React, des handlers Electron et des `if/elif` Python. Le risque principal etait de creer un workflow visible cote UI mais inconnu du bridge, ou l'inverse.

## Sources

| Source | Fichier | Role |
|---|---|---|
| Manifest transversal | `bot/workflows.manifest.json` | Liste documentee des familles de workflows. |
| Registry Electron | `front/electron/services/app/workflows/registry/workflow-registry.ts` | Types TS importables par les handlers et services Electron. |
| Types Renderer | `front/src/app/types/platforms/instagram/bot.types.ts` et types par feature | Types TS importables par React sans importer le main process Electron. |
| Audit legacy | `bot/scripts/audit_workflow_registry.py` | Script historique : il pointe encore vers l'ancien chemin `front/electron/services/workflows/workflow-registry.ts` dans le code actuel. Ne pas le documenter comme garde fiable tant qu'il n'est pas corrige. |

## Familles principales

| Famille | Exemples | Consommateurs |
|---|---|---|
| Instagram automation | `target_followers`, `hashtags`, `feed`, `unfollow` | UI Instagram, scheduler, `desktop_bridge`, sessions SQLite. |
| Instagram scraping | `target`, `hashtag`, `post_url` | UI scraping, `scraping_bridge`, tables scraping/profiles. |
| Instagram panel | `target`, `hashtag`, `post_likers`, `sync` | Live panel React et events `bot:workflow-started`. |
| TikTok automation | `for_you`, `hashtag`, `target`, `followers`, `dm_read`, `dm_send` | UI TikTok, `tiktok_bridge`, sessions TikTok. |
| Account workflows | `login`, `register`, `logout`, `read_otp`, `scan_accounts` | Bridges account Instagram/TikTok/Gmail/YouTube. |
| Publish workflows | `upload_post` | TikTok publish, YouTube upload. |

## Mapping Instagram automation -> panel

Le Bot n'affiche pas toujours les memes noms que le bridge :

| Bridge workflowType | Panel workflowType |
|---|---|
| `target_followers`, `target_following` | `target` |
| `hashtags` | `hashtag` |
| `post_url` | `post_likers` |
| `feed` | `feed` |
| `unfollow`, `sync_following` | `unfollow` |
| `sync_followers_following` | `sync` |
| `notifications` | `other` |

Ce mapping est maintenant centralise dans :

```ts
mapInstagramAutomationToPanelWorkflow()
```

## Garde-fou

Le garde-fou cible reste un audit manifest/registry/types renderer, mais le
script `bot/scripts/audit_workflow_registry.py` doit d'abord etre remis a jour :
il reference encore l'ancien chemin `front/electron/services/workflows/`.

Ne pas presenter `python bot/scripts/audit_workflow_registry.py` comme check
vert attendu tant que ce script n'a pas ete corrige et relance.

## Etat de migration

Le registre est maintenant branche sur les zones sensibles suivantes :

| Zone | Fichier | Detail |
|---|---|---|
| Handler Instagram automation | `front/electron/handlers/instagram/automation/bot.ts` | `BotSessionConfig.workflowType` type depuis les contrats centralises. |
| Preload bot | `front/electron/preload/platforms/instagram/bot.ts`, `front/electron/preload/shared/types.ts` | Contrat expose au renderer aligne sur les workflows Instagram automation et panel. |
| Scheduler Electron | `front/electron/services/app/scheduler/engine/scheduler-engine.ts` | Sous-ensemble planifiable type avec `Extract<InstagramAutomationWorkflow, ...>`. |
| Validation IPC | `front/electron/services/app/validation/ipc/validation-schemas.ts` | `z.enum()` construit depuis les constantes du registry. |
| TikTok handlers | `front/electron/handlers/tiktok/tiktok.ts` | Configs locales derivees de `TikTokAutomationWorkflow`. |
| Threads handlers | `front/electron/handlers/threads/threads.ts` | Config follow/target derivee de `ThreadsAutomationWorkflow`. |
| Renderer sessions | `front/src/app/types/platforms/instagram/bot.types.ts` et `front/src/app/types/features/instagram/session.types.ts` | Types panel/sessions importables sans dependance Electron. |
| Renderer scraping | `front/src/app/types/features/instagram/scraping.types.ts` | `workflowType` derive de `InstagramScrapingWorkflowType`. |

Quand un nouveau workflow est ajoute, modifier d'abord `bot/workflows.manifest.json`, puis mettre a jour les arrays TS. L'audit doit echouer tant que le manifest, le registry Electron et les types renderer ne sont pas alignes.

## Limites volontaires

Certaines constantes restent locales quand elles representent une action concrete et non un contrat extensible, par exemple `workflowType: 'upload_post'` dans un handler d'upload ou `workflowType: 'login'` dans un handler account. Le registry sert surtout a eviter les unions divergentes et les listes partagees entre plusieurs couches.
