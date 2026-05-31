# Bridges architecture workorder

## Objectif

Assainir `bot/bridges` sans casser le contrat Electron :

- stdout reste reserve aux events JSON ;
- le Bot reste lancable en standalone ;
- les entrypoints publics declares dans `bridges/bridges.manifest.json` restent auditables ;
- la logique durable sort progressivement des bridges vers `taktik/core/**`.

## Cartographie initiale

| Dossier | Role actuel | Owner | Imports entrants | Imports sortants | Proposition |
|---|---|---|---|---|---|
| `bridges/common` | Runtime bridge partage : IPC stdout, bootstrap, DB facade, reset reseau, keyboard, app manager. | Bridge runtime. | Instagram, TikTok, compat et entrypoints divers. | `taktik/core/**`, stdlib, uiautomator/ADB selon module. | Scoper progressivement par capacite (`device`, `input`, `parsing`, `runtime`, `persistence`) si le dossier grossit. Ne pas y mettre de metier plateforme. |
| `bridges/instagram` | Entry points Electron Instagram et beaucoup d'adaptation metier encore a plat. | Plateforme Instagram bridge. | Front dev path, launcher, manifest, scripts build, tests possibles. | `bridges.common`, `taktik/core/social_media/instagram/**`, DB/services. | Garder la racine pour les entrypoints publics + `base.py`. Extraire les implementations par famille (`automation`, `engagement`, `scraping`, `account`, `agent`) lot par lot. |
| `bridges/tiktok` | Entry points TikTok + runners dispatcher internes a plat. | Plateforme TikTok bridge. | Front dev path pour les entrypoints, `tiktok_bridge.py` pour les runners internes, tests unitaires. | `bridges.common`, `bridges.tiktok.base`, `taktik/core/social_media/tiktok/**`. | Runners internes sous `workflows/**`; entrypoints publics racine tant que le resolver Front utilise `bridges/<platform>/<name>.py`. |
| `bridges/youtube` | Entry points compte/upload/action test + `base.py`. | Plateforme YouTube bridge. | Front dev path, launcher, manifest. | `taktik/core/social_media/youtube/**`, Gmail/app email pour compte. | Split futur par `account/`, `publish/`, `diagnostics/` si implementation extraite ; garder entrypoints publics stables. |
| `bridges/gmail` | Entry point compte Gmail + `base.py`. | Provider Gmail bridge. | Front dev path, launcher, manifest. | `taktik/core/app/email/gmail/**`. | Petit dossier acceptable pour l'instant ; extraire seulement si plusieurs flows Gmail apparaissent. |
| `bridges/threads` | Entry point Threads + `base.py`. | Plateforme Threads bridge. | Front dev path, launcher, manifest. | `taktik/core/social_media/threads/**`, Instagram runtime selon dependances historiques. | Garder stable ; surveiller la dependance Instagram lors des lots Threads. |
| `bridges/compat` | Bridges diagnostics compat/selectors/workflow/action tests. | Diagnostics/compat bridge. | Front debug/compat handlers, launcher, manifest. | `taktik/core/compat`, `taktik/core/clone`, plateformes. | Classer par diagnostic si le dossier grossit, mais ne pas melanger avec runtime produit. |

## Regles cible

- `bridges/<platform>/<bridge_name>.py` = entrypoint public seulement si declare dans `bridges.manifest.json` ou lance par le Front en dev.
- `bridges/<platform>/base.py` = runtime bridge local de la plateforme : IPC, helpers stdout, startup commun. Il ne doit pas devenir un workflow.
- `bridges/<platform>/workflows/**` = runners internes appeles par un entrypoint dispatcher, classes par famille de flow (`automation`, `engagement`, `scraping`, etc.).
- `bridges/<platform>/account|publish|diagnostics/**` = implementations extractibles des entrypoints dedies, uniquement si l'entrypoint racine reste mince ou si le resolver Front est migre.
- `bridges/common/device/**` = helpers techniques de bridge lies au device, a la connectivite ou au lifecycle app (`connection.py`, `app_manager.py`, `network.py`).
- `bridges/common/input/**` = helpers de saisie ou interaction input utilises par plusieurs bridges.
- `bridges/common/parsing/**` = parseurs de texte/payload partages par les bridges, sans acces device ni IPC.
- `bridges/common/persistence/**` = facades DB strictement bridge, sans SQL direct ; la vraie persistence reste dans `taktik/core/database/**`.
- Pas de deplacement d'entrypoint public sans mise a jour coordonnee : manifest, `launcher.py`, build PyInstaller et resolver Front.

## Lots

| Lot | Statut | Portee | Verification |
|---|---|---|---|
| B1 | Fait | Deplacer les runners TikTok internes `for_you`, `search`, `followers`, `dm_read`, `dm_send` sous `bridges/tiktok/workflows/{automation,engagement}/`. | `pytest` ciblé, `check_bridge_manifest`, `compileall`, `git diff --check`. |
| B2 | Fait | Deplacer le reset reseau commun sous `bridges/common/device/network.py` et migrer les deux consommateurs Instagram/TikTok. | `check_bridge_manifest`, `compileall`, `git diff --check`. |
| B3 | Fait | Deplacer la saisie clavier sous `bridges/common/input/keyboard.py` et le parseur de compte sous `bridges/common/parsing/counts.py`; supprimer les modules plats `keyboard.py` et `utils.py`. | Import graph + `compileall` + `git diff --check`. |
| B4 | Fait | Deplacer la facade DB bridge sous `bridges/common/persistence/database.py` et migrer Instagram/TikTok consumers. | Import graph + `compileall` + `git diff --check`. |
| B5 | Fait | Supprimer le shim IA inutilise `bridges/common/ai_service.py`; l'owner IA reste `taktik/core/app/ai/**`. | Import graph + `compileall` + `git diff --check`. |
| B6 | Fait | Deplacer `ConnectionService`, `AppService` et `force_stop_app` sous `bridges/common/device/**`; supprimer les modules plats `connection.py` et `app_manager.py`. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B7 | A faire | Extraire les implementations Instagram engagement (`dm`, `cold_dm`, `smart_comment`) derriere des entrypoints publics minces ou deplacer seulement les helpers internes sans casser les chemins dev. | Tests/imports bridge + manifest + audit stdout. |
| B8 | A faire | Continuer `bridges/common` par capacite (`runtime/ipc`, `runtime/bootstrap`, `runtime/signal_handler`) si les imports peuvent etre migres sans shim. | Import graph + checks bridge. |
| B9 | A faire | Examiner YouTube/Gmail/Threads pour ne pas sur-organiser les petits dossiers. | Manifest + compileall. |

## Notes de compatibilite

Le Front lance en dev `python bridges/<platform>/<bridge_name>.py` via `front/electron/utils/paths.ts`. Cette contrainte explique pourquoi les entrypoints publics restent a la racine plateforme pour l'instant. Ce ne sont pas des fichiers legacy a oublier : ce sont les portes d'entree contractuelles. Le code durable doit, lui, continuer a migrer vers un owner clair.
