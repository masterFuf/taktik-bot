# Electron utils & types `[Front]`

Cette page documente les helpers partages dans `front/electron/utils/` et les
types main-process dans `front/electron/types/`.

## Utils

| Fichier | Role |
|---|---|
| `front/electron/utils/paths.ts` | Chemins bot, registry bridges, commande dev/prod, environnement Python. |
| `front/electron/utils/adb.ts` | Helpers ADB sync/async. |
| `front/electron/utils/ipc-helpers.ts` | Broadcast multi-window et logs structures. |

## Registry bridges

Le registry doit rester synchronise avec les bridges Python reels et le
launcher packaging. Ne pas ajouter un bridge dans un seul cote.

| Plateforme | Bridges attendus |
|---|---|
| Instagram | `desktop_bridge`, `dm_bridge`, `scraping_bridge`, `cold_dm_bridge`, `smart_comment_bridge`, `account_bridge`, `taktik_agent_bridge`, `persona_analysis_bridge`, `publish_bridge` |
| TikTok | `tiktok_bridge`, `tiktok_unfollow_bridge`, `dm_outreach_bridge`, `tiktok_scraping_bridge`, `tiktok_account_bridge`, `tiktok_publish_bridge` |
| Threads | `threads_bridge` |
| Gmail | `gmail_account_bridge` |
| YouTube | `youtube_account_bridge`, `youtube_upload_bridge`, `youtube_action_test_bridge` |
| Compat/tools | `compat_bridge`, `selector_test_bridge`, `workflow_test_bridge`, `action_test_bridge`, `action_session_bridge`, `tiktok_action_test_bridge` |

`discovery_bridge` n'est plus un bridge Instagram actif.

## Resolution dev/prod

| Fonction | Role |
|---|---|
| `BOT_PATH` | Chemin bot en dev, override possible via `TAKTIK_BOT_PATH`. |
| `getPythonPath()` | Chemin Python embarque en prod ou bot source en dev. |
| `getBridgePath(name)` | Bridge Python en dev, launcher en prod. |
| `getBridgeCommand(name)` | Commande executable adaptee au mode. |
| `getSpawnArgs(name, extraArgs)` | Arguments de spawn dev/prod. |
| `buildPythonSpawnEnv(extraVars)` | Environnement allowlist pour subprocess Python. |

`buildPythonSpawnEnv()` doit injecter `TAKTIK_DB_PATH` pour partager la base
SQLite locale avec le Bot sans transmettre tout `process.env`.

## Types

Les types Electron main-process doivent etre centralises dans
`front/electron/types/**` ou dans les dossiers de types applicatifs existants.
Ne pas importer des types depuis des handlers si cela cree une dependance
circulaire.

## Regles

| Regle | Pourquoi |
|---|---|
| Pas de bridge fantome dans le registry | Evite les options UI non executables et les erreurs packaging. |
| Pas de `...process.env` aveugle | Evite les fuites de tokens et les environnements non reproductibles. |
| Sanitizer les valeurs renderer avant ADB shell | Le renderer est une frontiere non fiable. |
| Garder dev/prod synchronises | Le launcher doit connaitre les memes noms que `paths.ts`. |

## Sources verifiees

- `front/electron/utils/paths.ts`
- `front/electron/preload/index.ts`
- `bot/bridges/**`
- `bot/bridges/launcher.py`
