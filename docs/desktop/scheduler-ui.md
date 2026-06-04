# Scheduler UI

> **Perimetre : `[Front]`**
> Cette page documente la surface renderer du scheduler desktop. Pour le
> runtime Electron -> bridges/Bot, voir [Scheduler & Sessions](../workflows/sessions.md).

Le scheduler UI sert a construire, sauvegarder, lancer et suivre visuellement
des plannings d'automatisation. Il ne pilote pas Android directement.

## Pages et fichiers cles

| Fichier | Role |
|---|---|
| `pages/GlobalSchedulerCreatePage.tsx` | Force le choix du device. |
| `pages/SchedulerPage.tsx` | Canvas principal : edition, save, start, stop, test run, restauration d'etat, console live. |
| `pages/SchedulerControl.tsx` | Monitoring global : liste, regroupement, filtres, skip next, suppression, vue canvas. |
| `pages/SchedulerTemplatesPage.tsx` | Edition de templates et deploiement multi-device. |
| `config-panel/NodeConfigPanel.tsx` | Route un node vers son formulaire de configuration. |
| `nodes/schedulerNodeRegistry.ts` | Mapping `type -> composant React Flow`. |
| `nodes/schedulerNodePalette.ts` | Groupes de palette et presets de nodes. |
| `nodes/schedulerNodeDefaults.ts` | Configs par defaut des nodes. |
| `ai/SchedulerBuilderPanel.tsx` | Generation de graphes via IA + remix du prompt sauvegarde. |
| `ai/SmartTargetFinder.tsx` | Recherche locale de profils cibles. |

## `SchedulerPage`

`SchedulerPage.tsx` est le coeur de l'edition.

Elle gere :

- le canvas `ReactFlow`
- la palette draggable
- la selection et l'edition d'un node
- la sauvegarde SQLite via `window.electronAPI.scheduler.save`
- le lancement manuel via `scheduler.start`
- le stop via `scheduler.stop`
- le **test run** (save + start immediat)
- la restauration d'une execution en cours via `scheduler.getRunning`
- les events runtime (`onExecutionStarted`, `onExecutionProgress`,
  `onDelayStarted`, `onDelayEnded`, `onExecutionCompleted`)
- la console live pour les logs upload TikTok / bridges
- l'integration du contexte IA via `agent:workflow-context` et
  `agent:scheduler-generated`

## Palette actuelle

La palette ne contient plus seulement trigger + automation. Elle est decoupee
par familles metier.

### Triggers

- `trigger`

### Flow control

- `delay`
- `condition`

### Guards

- `time-window`
- `quota-guard`

### Instagram

- Account : `automation` presets notifications / sync / full sync
- Publish : `publish`
- Engagement : `dm`, `dm-responses`, `smart-comment`
- Automation : `automation`
- Maintenance : `unfollow`
- Scraping : `scraping`

### TikTok

- Account : `tiktok-account`
- Engagement : `tiktok-dm`, `tiktok-cold-dm`
- Publish : `tiktok-publish`
- Automation : `tiktok-automation`
- Maintenance : `tiktok-unfollow`
- Scraping : `tiktok-scraping`

### Autres plateformes

- Gmail : `gmail-account`
- YouTube : `youtube-account`, `youtube-upload`
- Threads : `threads-automation`

## `nodeTypes` branches

Le mapping React Flow actuel couvre :

- `trigger`
- `automation`
- `scraping`
- `dm`
- `delay`
- `condition`
- `time-window`
- `quota-guard`
- `unfollow`
- `publish`
- `instagram-reel` (alias visuel du publish)
- `tiktok-automation`
- `tiktok-publish`
- `tiktok-account`
- `tiktok-dm`
- `tiktok-scraping`
- `tiktok-unfollow`
- `dm-responses`
- `smart-comment`
- `tiktok-cold-dm`
- `gmail-account`
- `youtube-account`
- `youtube-upload`
- `threads-automation`

## Config panel

`NodeConfigPanel.tsx` route les formulaires selon `node.type`.

Les formulaires sont classes par owner :

- `configs/common/*`
- `configs/instagram/*`
- `configs/tiktok/*`
- `configs/gmail/*`
- `configs/youtube/*`
- `configs/threads/*`

Le panel supporte les 2 layouts :

- vertical
- horizontal (bottom panel dans `SchedulerPage`)

## Configs par defaut verifiees

Exemples de defaults reels :

| Type | Default verifie |
|---|---|
| `trigger` | `triggerType: "time"`, `time: "09:00"`, `repeat: "daily"` |
| `delay` | `duration: 30`, `unit: "minutes"` |
| `condition` | `conditionType: "time"`, `operator: "after"`, `value: "12:00"` |
| `time-window` | `09:00 -> 18:00`, `days: "daily"` |
| `quota-guard` | `platform: "instagram"`, likes 80, follows 30, comments 20, stories 100 |
| `automation` | `workflowType: "target_followers"`, session 60 min, `maxConsecutiveKnownUsernames: 150` |
| `scraping` | `scrapeType: "followers"`, `targets: []`, `maxProfiles: 100`, IA/deep qualify disponibles |
| `publish` | `publishType: "post"`, `mediaPath: ""`, `caption: ""` |
| `tiktok-automation` | `workflowType: "for_you"`, delays et pauses locales par defaut |
| `tiktok-publish` | `videoPath: ""`, `caption: ""`, `hashtags: []` |
| `tiktok-account` | `action: "login"` ; route scheduler presente, mais login TikTok reste `not_implemented` cote Bot |
| `gmail-account` | `action: "login"` |
| `youtube-upload` | `uploadType: "short"`, `visibility: "public"` |
| `threads-automation` | `workflowType: "feed"` |

## Appels preload / IPC

Le renderer passe par `window.electronAPI.scheduler`.

CRUD et execution :

- `getByDevice(deviceId)`
- `getById(scheduleId)`
- `getAll()`
- `save(schedule)`
- `start(deviceId, scheduleId)`
- `stop(executionId)`
- `skipNext(scheduleId)`
- `delete(scheduleId)`
- `deleteAll(deviceId?)`
- `getRunning(deviceId)`

Templates :

- `templates.getAll()`
- `templates.save()`
- `templates.delete(templateId)`
- `templates.deploy(templateId, deviceIds)`

## Events runtime ecoutes

`SchedulerPage` ecoute :

- `onExecutionStarted`
- `onExecutionProgress`
- `onDelayStarted`
- `onDelayEnded`
- `onExecutionCompleted`

Ces events servent a restaurer / mettre a jour :

- le badge running/stopped
- le step courant
- le node surligne
- le prochain node
- le countdown de delay

## `SchedulerControl.tsx`

La page de controle :

- charge tous les schedules
- parse `nodes` / `edges`
- recalcule la prochaine execution cote renderer
- supporte les filtres device + date
- groupe par jour ou par device
- supporte `skip next`
- ouvre un apercu canvas
- peut reouvrir un schedule directement dans l'editeur

## Templates

`SchedulerTemplatesPage.tsx` est un deuxieme editeur React Flow oriente
reutilisation.

Le deploiement de template :

- ne lance pas le workflow
- cree des schedules pour les devices cibles

## AI builder dans l'UI

Le scheduler UI integre le builder via `ai/*`.

Capacites visibles :

- generation IA ou fallback deterministe
- remix du prompt sauvegarde
- Smart Target context local
- taxonomy audit snapshot
- persistence du metadata `aiGeneration` avec le schedule

## Points d'attention

- Les nodes `condition`, `time-window` et `quota-guard` ne sont pas des
  placeholders UI : ils sont executes par `SchedulerEngine`.
- `dm` et `dm-responses` sont eux aussi executes par le moteur scheduler.
- `tiktok-account` est branche cote Electron, mais le login TikTok reste
  partiellement implemente cote Bot.
- Les graphs `nodes` / `edges` sont stockes comme JSON ; toute migration doit
  rester retrocompatible.
