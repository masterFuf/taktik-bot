# [Transversal] Guide de refactorisation

## Role

Cette page sert de mode d'emploi pour utiliser la documentation avant une refactorisation lourde.

Elle ne remplace pas les tests. Elle aide a voir les dependances implicites entre Front, Bot, API, Web, bases de donnees et workflows.

## Carte des risques

| Zone touchee | Risque principal | Pages a lire avant |
|---|---|---|
| Bridge Python | casser le protocole stdout/stdin attendu par Electron | `bridges/architecture.md`, `bridges/ipc-protocol.md`, page bridge plateforme |
| Handler Electron | changer un payload envoye au bot | `desktop/ipc-handlers.md`, `desktop/platform-bridge-handlers.md`, workflow end-to-end |
| Workflow Bot | casser une feature UI ou scheduler | page module plateforme + `workflows/*.md` |
| Actions business | casser plusieurs workflows qui partagent les memes actions | `modules/*/business-actions.md`, workflows plateforme |
| Actions atomic/selectors | casser l'interaction Android | selectors, compat, versioned selectors |
| SQLite | casser repositories Python/Electron ou sync | `database/schema.md`, `database/repositories.md`, `desktop/electron-database-repositories.md` |
| Licence/API | bloquer le lancement desktop ou device | `taktik-docs/technical/api-current-state.md`, `desktop/auth-license-flow.md` |
| Scheduler/session | casser les executions planifiees | `workflows/sessions.md`, `desktop/scheduler-ui.md`, `desktop/content-planner.md` |
| Site Web | casser creation de licences/API keys | `web/overview.md`, `taktik-docs/technical/api-current-state.md` |

## Process conseille

### 1. Identifier le proprietaire

Avant de modifier, classer le changement :

| Badge | Exemple |
|---|---|
| `[Bot]` | modifier une action Instagram |
| `[Front]` | modifier un panneau React ou handler Electron |
| `[API]` | modifier verification de licence/device |
| `[Web]` | modifier checkout Stripe ou schema Prisma |
| `[Transversal]` | modifier un flow complet ou un payload partage |

### 2. Suivre le flux complet

Pour une feature, partir de l'entree utilisateur et descendre :

```text
UI React
  -> Electron handler
  -> bridge Python
  -> workflow Bot
  -> action business
  -> action atomic
  -> selector/device
  -> database/events
```

Si une couche n'est pas claire dans la doc, c'est un signal : completer la doc avant de refactoriser.

### 3. Chercher les contrats implicites

| Contrat | Exemples |
|---|---|
| Payload IPC | noms de champs envoyes par Electron au bridge |
| Event stdout | `progress`, `log`, `complete`, `error` |
| Config workflow | `deviceId`, `accountId`, `platform`, `workflowType` |
| Schema DB | colonnes lues/ecrites par plusieurs repos |
| Selectors | noms centralises partages par actions |
| Licence | `allowed`, `reason`, `device_registered` |

### 4. Auditer les duplications

Chercher les duplications par famille :

| Famille | Question |
|---|---|
| Workflows | Deux workflows font-ils la meme navigation avec des configs differentes ? |
| Actions | Une action business pourrait-elle remplacer une action custom dans un workflow ? |
| Repositories | Deux repositories ecrivent-ils la meme donnee sous des noms differents ? |
| Tables | Deux tables representent-elles le meme concept avec des colonnes proches ? |
| Handlers | Deux handlers spawn-ils le meme bridge avec des variantes minimes ? |
| UI | Deux composants exposent-ils la meme operation avec des stores differents ? |

## Checklist avant refactor

| Controle | OK |
|---|---|
| Le proprietaire `[Bot]` / `[Front]` / `[API]` / `[Web]` est clair |  |
| Les pages docs concernees ont ete lues |  |
| Les payloads IPC sont listes |  |
| Les events attendus par le Front sont listes |  |
| Les tables et repositories touches sont identifies |  |
| Les workflows consommateurs sont identifies |  |
| Les comportements legacy sont notes |  |
| Les tests ou verifications manuelles sont definis |  |
| L'inventaire produit est mis a jour si une feature visible change |  |

## Garde-fous automatises disponibles

Ces commandes sont volontairement read-only : elles ne modifient ni le code, ni la base locale. Elles servent a verifier que les gros contrats transversaux restent coherents avant une refactorisation.

| Commande | Verifie | A lancer avant |
|---|---|---|
| `python bot/scripts/check_bridge_manifest.py` | Alignement entre `bot/bridges/bridges.manifest.json`, `bot/bridges/launcher.py::BRIDGE_MODULES` et `front/electron/utils/paths.ts::PLATFORM_BRIDGES`. | Ajout, renommage ou suppression d'un bridge. |
| `python bot/scripts/audit_bridge_handler_usage.py` | Absence de `getSpawnArgs()` / `getBridgeCommand()` direct dans les handlers Electron. | Refactor ou ajout d'un handler qui lance un bridge Python. |
| `python bot/scripts/audit_workflow_registry.py` | Alignement entre `bot/workflows.manifest.json`, `front/electron/services/workflows/workflow-registry.ts` et les types renderer derives. | Ajout, renommage ou suppression d'un `workflowType`. |
| `python bot/scripts/audit_sqlite_schema_docs.py` | Presence de toutes les tables SQLite source dans `bot/docs/database/schema.md`. | Modification de `schema.py`, `migrations.py`, `schema.ts`, `schema.sql`, repositories DB ou doc SQLite. |
| `python bot/scripts/audit_selector_hardcodes.py` | Absence de nouveaux selectors Android inline dans le runtime Instagram/TikTok hors `ui/selectors/**` et `ui/language.py`, avec dette legacy allowlistee. | Refactor ou ajout d'un workflow/action/service Instagram ou TikTok qui touche l'UI Android. |

Ces checks ne remplacent pas les tests fonctionnels. Ils evitent surtout les oublis silencieux : bridge connu du Front mais absent du launcher, table creee par migration mais non documentee, ou documentation devenue obsolete.

## Checklist apres refactor

| Controle | OK |
|---|---|
| La doc module est a jour |  |
| Le workflow end-to-end est a jour |  |
| Le schema DB est a jour |  |
| Les pages API/Web sont a jour si necessaire |  |
| L'audit de couverture ne signale pas de trou |  |
| Les points d'attention obsoletes ont ete retires |  |

## Refactor base de donnees

Avant de fusionner ou supprimer une table :

1. verifier `database/schema.md` ;
2. chercher les repositories Python et Electron ;
3. chercher les handlers ou workflows qui lisent/ecrivent la table ;
4. verifier les migrations ;
5. identifier les donnees historiques a migrer ;
6. documenter le mapping ancien -> nouveau ;
7. seulement ensuite modifier le code.

Exemple de questions :

| Question | Pourquoi |
|---|---|
| La table est-elle ecrite par Python, Electron, ou les deux ? | eviter une migration incomplete |
| Est-elle une table source ou un cache ? | savoir si la perte est acceptable |
| A-t-elle des contraintes uniques utiles ? | eviter les doublons apres fusion |
| Est-elle synchronisee Turso ? | risque cross-device |
| Est-elle visible dans l'UI ? | risque regression utilisateur |

## Refactor workflows

Pour mutualiser deux workflows :

1. comparer les configs d'entree ;
2. comparer les actions business appelees ;
3. comparer les selectors ;
4. comparer la persistance ;
5. comparer les events stdout ;
6. extraire seulement ce qui est stable.

Ne pas mutualiser uniquement parce que deux workflows se ressemblent : l'automation Android est fragile, et une petite difference de contexte peut justifier deux chemins.

## Sortie attendue d'un gros refactor

Un refactor propre doit produire :

- un code plus simple ;
- une doc mise a jour ;
- un inventaire des contrats preserves ;
- une liste des comportements retires ;
- une migration DB si necessaire ;
- une note produit si la feature visible change.
