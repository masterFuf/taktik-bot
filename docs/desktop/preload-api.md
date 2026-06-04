# Preload API Electron `[Front]`

Cette page documente la surface `window.electronAPI` exposee au renderer React.
Elle a ete reverifiee contre `front/electron/preload/index.ts` et les modules
`front/electron/preload/**`.

## Role

Le preload est la frontiere securisee entre React et le process main Electron.
React n'appelle pas `ipcRenderer` directement : il passe par les methodes
exposees par `window.electronAPI`.

```text
React renderer
  -> window.electronAPI
  -> preload/<domain>.ts
  -> ipcRenderer.invoke/on
  -> handlers Electron
  -> services / repositories / bridges
```

## Arborescence actuelle

```text
front/electron/preload/
+-- app/
|   +-- automation.ts
|   +-- core.ts
|   +-- db.ts
|   +-- license.ts
|   +-- sync.ts
+-- devices/
|   +-- adb.ts
|   +-- mirror.ts
+-- platforms/
|   +-- gmail/gmail.ts
|   +-- instagram/
|   +-- threads/threads.ts
|   +-- tiktok/tiktok.ts
|   +-- youtube/youtube.ts
+-- shared/types.ts
+-- tools/
|   +-- ai.ts
|   +-- compat.ts
+-- index.ts
```

Ne pas recreer l'ancien `preload.ts` monolithique ni des modules a plat.

## Modules exports

| Module | API |
|---|---|
| `app/core.ts` | Fenetre, shell, config, debug, storage, updater. |
| `app/automation.ts` | Scheduler, target search, content planner, AI scheduler. |
| `app/db.ts` | Acces DB expose au renderer. |
| `app/license.ts` | Auth/licence/device rights. |
| `app/sync.ts` | Sync locale/cloud. |
| `devices/adb.ts` | Devices Android et commandes ADB autorisees. |
| `devices/mirror.ts` | Mirroring scrcpy. |
| `platforms/instagram/*` | Bot, scraping, DM, upload/account, smart comment. |
| `platforms/tiktok/tiktok.ts` | TikTok automation, scraping, DM, upload, account. |
| `platforms/threads/threads.ts` | Threads workflows. |
| `platforms/gmail/gmail.ts` | Gmail account workflows. |
| `platforms/youtube/youtube.ts` | YouTube account/upload. |
| `tools/ai.ts` | Providers IA et outils associes. |
| `tools/compat.ts` | Compat diagnostics, action tester, cartography lab. |
| `shared/types.ts` | Types preload partages. |

## Automation API actuelle

`automationAPI` ne contient plus de namespace Discovery. Elle expose :

| Zone | Exemples |
|---|---|
| Scheduler | save/start/stop/templates/events/notify completion |
| Target search | search/export/profile detail/filter options/scout pre-filter |
| Content planner | generate schedules + aliases upload legacy |
| AI scheduler | recherche profils Instagram/TikTok, taxonomy audit, smart target context |

Le terme "discovery" peut encore apparaitre comme mot produit generique dans
l'intelligence scheduler, mais pas comme ancien workflow/campaign API.

## Conventions

| Convention | Pourquoi |
|---|---|
| Les listeners retournent toujours une fonction cleanup | Evite les listeners dupliques apres remount React. |
| Les payloads passent par des types centralises | Evite les types inline dans les handlers/preload. |
| Les methodes sont regroupees par domaine | Limite la taille cognitive de `window.electronAPI`. |
| Le preload ne contient pas de logique metier | Il route vers les handlers. |
| Ajouter une methode exige un handler correspondant | Evite les APIs mortes cote renderer. |

## Reste a surveiller

| Zone | Risque |
|---|---|
| `DbAPI` | Plusieurs retours restent larges et doivent etre types progressivement. |
| `CompatAPI` | Le Cartography Lab evolue vite ; garder les types synchronises avec les handlers. |
| Upload/scheduler notifications | Les events `notify*Complete` doivent rester alignes avec le moteur scheduler. |

## Sources verifiees

- `front/electron/preload/index.ts`
- `front/electron/preload/app/automation.ts`
- `front/electron/preload/**`
- `front/electron/handlers/**`
