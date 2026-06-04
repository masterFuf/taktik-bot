# Scheduler - Architecture

## Vue d'ensemble

Voir aussi :

- [AI Scheduler Builder](scheduler-ai-builder.md)
- [Smart Target Intelligence](../workflows/scheduler-smart-target-intelligence.md)
- [Taxonomy V2](scheduler-taxonomy-v2.md)

Le scheduler desktop est un editeur visuel base sur **React Flow**. Il permet
de composer des graphes de nodes dans le renderer, de les sauvegarder via
Electron, puis de les executer via `SchedulerEngine`.

Il y a donc 3 couches a distinguer :

1. **Renderer** : pages React, palette, canvas, config panel, AI builder.
2. **Electron** : handlers IPC, persistance SQLite scheduler, moteur
   d'execution.
3. **Bot / bridges** : workflows reels lances par le moteur selon le node
   execute.

## Arborescence actuelle

Le scheduler UI ne vit plus dans un ancien `src/components/scheduler/`.
L'owner courant est :

```text
front/src/features/workspace/scheduler/
|- ai/
|  |- AISchedulerModal.tsx
|  |- SchedulerBuilderPanel.tsx
|  |- SmartTargetFinder.tsx
|  |- schedulerAiCatalog.ts
|  `- schedulerTaxonomyPrompts.ts
|- config-panel/
|  `- NodeConfigPanel.tsx
|- configs/
|  |- common/
|  |- gmail/
|  |- instagram/
|  |- threads/
|  |- tiktok/
|  `- youtube/
|- hooks/
|  `- useLocalInput.ts
|- nodes/
|  |- common/
|  |- gmail/
|  |- instagram/
|  |- threads/
|  |- tiktok/
|  |- youtube/
|  |- schedulerNodeDefaults.ts
|  |- schedulerNodeDisplay.ts
|  |- schedulerNodePalette.ts
|  `- schedulerNodeRegistry.ts
`- pages/
   |- GlobalSchedulerCreatePage.tsx
   |- SchedulerControl.tsx
   |- SchedulerPage.tsx
   `- SchedulerTemplatesPage.tsx
```

Les types partages du scheduler sont centralises dans :

- `front/src/app/types/features/scheduler/scheduler.types.ts`
- `front/src/app/types/features/scheduler/ai.types.ts`

## Cote renderer

### Pages principales

| Fichier | Role |
|---|---|
| `pages/GlobalSchedulerCreatePage.tsx` | Force le choix du device avant d'ouvrir le canvas. |
| `pages/SchedulerPage.tsx` | Canvas principal React Flow : edition, sauvegarde, start/stop, test run, restauration de l'etat d'execution. |
| `pages/SchedulerControl.tsx` | Vue de supervision globale : liste, prochaine execution, skip next, suppression, apercu. |
| `pages/SchedulerTemplatesPage.tsx` | Templates reutilisables et deploiement multi-device. |

### Sous-modules UI

| Zone | Owner actuel |
|---|---|
| Node registry | `nodes/schedulerNodeRegistry.ts` |
| Palette | `nodes/schedulerNodePalette.ts` |
| Defaults | `nodes/schedulerNodeDefaults.ts` |
| Affichage / badges | `nodes/schedulerNodeDisplay.ts` |
| Router des formulaires | `config-panel/NodeConfigPanel.tsx` |
| Formulaires de config | `configs/**` |
| AI builder | `ai/**` |

### Node families exposees

Le renderer expose aujourd'hui :

- `trigger`
- `delay`
- `condition`
- `time-window`
- `quota-guard`
- `automation`
- `scraping`
- `dm`
- `dm-responses`
- `unfollow`
- `publish`
- `smart-comment`
- `tiktok-automation`
- `tiktok-publish`
- `tiktok-account`
- `tiktok-dm`
- `tiktok-scraping`
- `tiktok-unfollow`
- `tiktok-cold-dm`
- `gmail-account`
- `youtube-account`
- `youtube-upload`
- `threads-automation`

Le mapping React Flow canonique est porte par
`nodes/schedulerNodeRegistry.ts`.

## Cote Electron

### Frontiere runtime

Le scheduler ne parle pas directement au Bot depuis React.
Le chemin reel est :

```text
SchedulerPage / Templates / Control
-> window.electronAPI.scheduler
-> electron/handlers/scheduler/**
-> electron/database/repositories/scheduler/**
-> electron/services/app/scheduler/**
-> bridges / handlers plateforme / renderer events
```

Owners principaux :

| Owner | Role |
|---|---|
| `front/electron/handlers/scheduler/scheduler.ts` | CRUD scheduler + start/stop/skip + events runtime exposes au renderer |
| `front/electron/handlers/scheduler/content-planner.ts` | Generation de schedules depuis Content Planner |
| `front/electron/database/models/scheduler/schedule.ts` | Contrats DB scheduler |
| `front/electron/database/repositories/scheduler/SchedulerRepository.ts` | Persistance SQLite scheduler |
| `front/electron/services/app/scheduler/engine/scheduler-engine.ts` | Moteur d'execution des nodes |

### Ce que fait reellement `SchedulerEngine`

`SchedulerEngine` n'est pas limite a `trigger` + `delay`.
Il execute aujourd'hui :

- les nodes de controle `condition`, `time-window`, `quota-guard`
- les workflows Instagram (`automation`, `scraping`, `dm`,
  `dm-responses`, `smart-comment`, `unfollow`, `publish`)
- les workflows TikTok (`tiktok-automation`, `tiktok-publish`,
  `tiktok-account`, `tiktok-dm`, `tiktok-scraping`, `tiktok-unfollow`,
  `tiktok-cold-dm`)
- les nodes compte `gmail-account`, `youtube-account`
- le node `youtube-upload`
- `threads-automation`

Le moteur attend aussi les fins d'execution typed cote renderer via ses maps de
completions (`pendingBotCompletions`, `pendingUploadCompletions`,
`pendingScrapingCompletions`, `pendingAccountCompletions`).

## Persistance

Les graphes restent stockes comme JSON `nodes` / `edges` dans SQLite.
Le scheduler persiste aussi la generation IA (`ai_generation`) pour permettre
le remix du prompt et le suivi du contexte de generation.

Cela couvre notamment :

- nom du schedule
- nodes / edges React Flow
- metadata de generation IA
- historique d'execution scheduler

## AI builder dans l'architecture

Le builder scheduler ne vit plus comme une note separee hors runtime. Il est
branche au canvas courant :

- `SchedulerPage` publie `agent:workflow-context`
- `SchedulerBuilderPanel` genere un graphe a partir d'un prompt et du catalogue
  de nodes
- le panel applique le resultat via `agent:scheduler-generated`
- `SchedulerPage` injecte alors `nodes`, `edges` et `aiGeneration`

Le builder peut aussi enrichir le contexte avec :

- `window.electronAPI.aiScheduler.getSmartTargetContext()`
- `window.electronAPI.aiScheduler.getTaxonomyAudit()`
- `window.electronAPI.aiProvider.textCompletion()`

## Conventions dextension

Pour ajouter un node :

1. creer le composant visuel dans `nodes/<family>/`
2. creer le formulaire dans `configs/<family>/`
3. brancher `schedulerNodeRegistry.ts`
4. brancher `schedulerNodePalette.ts`
5. brancher `schedulerNodeDefaults.ts`
6. brancher `NodeConfigPanel.tsx`
7. brancher `SchedulerEngine` si le node doit etre executable
8. documenter la nouvelle surface dans cette page et dans la page runtime si le
   contrat Electron/Bot change

## Points d'attention

- Un node visible en UI doit etre considere comme **produit** seulement si son
  handler Electron et son execution runtime sont verifies.
- `tiktok-account` est bien route dans le scheduler Electron, mais le flow
  `login` TikTok reste `not_implemented` cote Bot.
- Les nodes de garde (`condition`, `time-window`, `quota-guard`) sont des
  nodes moteur internes : ils n'ont pas de bridge externe a stopper.
- Toute evolution du shape `nodes` / `edges` / `aiGeneration` doit rester
  retrocompatible avec les schedules deja en base.
