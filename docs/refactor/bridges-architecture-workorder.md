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
| `bridges/tiktok` | Entry points TikTok + runners dispatcher internes a plat. | Plateforme TikTok bridge. | Front dev path pour les entrypoints, `tiktok_bridge.py` pour les runners internes, tests unitaires. | `bridges.common`, `bridges.tiktok.base`, `taktik/core/social_media/tiktok/**`. | Runners internes sous `workflows/**`; implementations d'entrypoints publics sous `account`, `publish`, `scraping`, `engagement` ou `automation` avec wrappers racine tant que le resolver Front utilise `bridges/<platform>/<name>.py`. |
| `bridges/youtube` | Entry points compte/upload/action test + `base.py`. | Plateforme YouTube bridge. | Front dev path, launcher, manifest. | `taktik/core/social_media/youtube/**`, Gmail/app email pour compte. | Implementations sous `account/`, `publish/`, `diagnostics/` ou `workflows/`; wrappers publics racine stables. |
| `bridges/gmail` | Entry point compte Gmail + `base.py`. | Provider Gmail bridge. | Front dev path, launcher, manifest. | `taktik/core/app/email/gmail/**`. | Implementation account sous `account/`; wrapper public racine stable. |
| `bridges/threads` | Entry point Threads + `base.py`. | Plateforme Threads bridge. | Front dev path, launcher, manifest. | `taktik/core/social_media/threads/**`, Instagram runtime selon dependances historiques. | Garder stable ; surveiller la dependance Instagram lors des lots Threads. |
| `bridges/compat` | Bridges diagnostics compat/selectors/workflow/action tests. | Diagnostics/compat bridge. | Front debug/compat handlers, launcher, manifest. | `taktik/core/compat`, `taktik/core/clone`, plateformes. | Classer par diagnostic si le dossier grossit, mais ne pas melanger avec runtime produit. |

## Regles cible

- `bridges/<platform>/<bridge_name>.py` = entrypoint public seulement si declare dans `bridges.manifest.json` ou lance par le Front en dev.
- `bridges/<platform>/base.py` = runtime bridge local de la plateforme : IPC, helpers stdout, startup commun. Il ne doit pas devenir un workflow.
- `bridges/<platform>/workflows/**` = runners internes appeles par un entrypoint dispatcher, classes par famille de flow (`automation`, `engagement`, `scraping`, etc.).
- `bridges/<platform>/automation|engagement|scraping|account|publish|analysis|agent|diagnostics/**` = implementations extractibles des entrypoints dedies, uniquement si l'entrypoint racine reste mince ou si le resolver Front est migre.
- `bridges/common/device/**` = helpers techniques de bridge lies au device, a la connectivite ou au lifecycle app (`connection.py`, `app_manager.py`, `network.py`).
- `bridges/common/input/**` = helpers de saisie ou interaction input utilises par plusieurs bridges.
- `bridges/common/parsing/**` = parseurs de texte/payload partages par les bridges, sans acces device ni IPC.
- `bridges/common/persistence/**` = facades DB strictement bridge, sans SQL direct ; la vraie persistence reste dans `taktik/core/database/**`.
- `bridges/common/runtime/**` = bootstrap process, stdout JSON IPC, base bridge commune et signal handling.
- Pas de deplacement d'entrypoint public sans mise a jour coordonnee : manifest, `launcher.py`, build PyInstaller et resolver Front.
- Chaque wrapper public racine doit ajouter `bot/` a `sys.path` avant son import delegue, sinon `python bridges/<platform>/<bridge_name>.py` peut echouer hors lancement module.

## Lots

| Lot | Statut | Portee | Verification |
|---|---|---|---|
| B1 | Fait | Deplacer les runners TikTok internes `for_you`, `search`, `followers`, `dm_read`, `dm_send` sous `bridges/tiktok/workflows/{automation,engagement}/`. | `pytest` ciblé, `check_bridge_manifest`, `compileall`, `git diff --check`. |
| B2 | Fait | Deplacer le reset reseau commun sous `bridges/common/device/network.py` et migrer les deux consommateurs Instagram/TikTok. | `check_bridge_manifest`, `compileall`, `git diff --check`. |
| B3 | Fait | Deplacer la saisie clavier sous `bridges/common/input/keyboard.py` et le parseur de compte sous `bridges/common/parsing/counts.py`; supprimer les modules plats `keyboard.py` et `utils.py`. | Import graph + `compileall` + `git diff --check`. |
| B4 | Fait | Deplacer la facade DB bridge sous `bridges/common/persistence/database.py` et migrer Instagram/TikTok consumers. | Import graph + `compileall` + `git diff --check`. |
| B5 | Fait | Supprimer le shim IA inutilise `bridges/common/ai_service.py`; l'owner IA reste `taktik/core/app/ai/**`. | Import graph + `compileall` + `git diff --check`. |
| B6 | Fait | Deplacer `ConnectionService`, `AppService` et `force_stop_app` sous `bridges/common/device/**`; supprimer les modules plats `connection.py` et `app_manager.py`. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B7 | Fait | Deplacer `bootstrap`, `ipc`, `bridge_base` et `signal_handler` sous `bridges/common/runtime/**`; la racine `common` devient une facade package. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B8 | Fait | Deplacer l'implementation Smart Comment sous `bridges/instagram/engagement/smart_comment.py` et garder `smart_comment_bridge.py` comme entrypoint public mince. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B9 | Fait | Deplacer les implementations Instagram DM et Cold DM sous `bridges/instagram/engagement/{dm,cold_dm}.py`; garder `dm_bridge.py` et `cold_dm_bridge.py` comme entrypoints publics minces. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B10 | Fait | Deplacer l'implementation Instagram account sous `bridges/instagram/account/account.py`; garder `account_bridge.py` comme entrypoint public mince. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B11 | Fait | Deplacer l'implementation Instagram scraping sous `bridges/instagram/scraping/scraping.py`; garder `scraping_bridge.py` comme entrypoint public mince. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B12 | Fait | Deplacer l'implementation Instagram Persona Analysis sous `bridges/instagram/analysis/persona.py`; garder `persona_analysis_bridge.py` comme entrypoint public mince et sortir ses selectors inline vers les catalogues post. | Import graph + selector audit + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B13 | Fait | Deplacer l'implementation Instagram Taktik Agent sous `bridges/instagram/agent/taktik_agent.py`; garder `taktik_agent_bridge.py` comme entrypoint public mince sans deplacer le noyau `taktik/core/agent`. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B14 | Fait | Deplacer l'implementation Instagram desktop automation sous `bridges/instagram/automation/desktop.py`; garder `desktop_bridge.py` comme entrypoint public mince. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B15 | Fait | Deplacer l'implementation TikTok account sous `bridges/tiktok/account/account.py`; garder `tiktok_account_bridge.py` comme entrypoint public mince. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B16 | Fait | Deplacer l'implementation TikTok publish sous `bridges/tiktok/publish/publish.py`; garder `tiktok_publish_bridge.py` comme entrypoint public mince. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B17 | Fait | Deplacer l'implementation TikTok scraping sous `bridges/tiktok/scraping/scraping.py`; garder `scraping_bridge.py` comme entrypoint public mince et migrer le dispatcher TikTok vers l'owner scope. | Import graph + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B18 | Fait | Deplacer l'implementation TikTok DM outreach sous `bridges/tiktok/engagement/dm_outreach.py`; garder `dm_outreach_bridge.py` comme entrypoint public mince. | Import graph + direct-launch smoke + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B19 | Fait | Deplacer l'implementation TikTok unfollow sous `bridges/tiktok/automation/unfollow.py`; garder `tiktok_unfollow_bridge.py` comme entrypoint public mince. | Import graph + direct-launch smoke + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B20 | Fait | Deplacer l'implementation du dispatcher TikTok sous `bridges/tiktok/workflows/dispatcher.py`; garder `tiktok_bridge.py` comme entrypoint public mince. | Import graph + direct-launch smoke + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B21 | Fait | Deplacer les implementations YouTube sous `account/`, `publish/`, `diagnostics/` et `workflows/`; garder les entrypoints publics racine. | Direct-launch smoke + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B22 | Fait | Deplacer l'implementation Gmail account sous `bridges/gmail/account/account.py`; garder `gmail_account_bridge.py` comme entrypoint public mince. | Direct-launch smoke + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B23 | A faire | Examiner Threads pour ne pas sur-organiser le dossier. | Manifest + compileall. |

## Notes de compatibilite

Le Front lance en dev `python bridges/<platform>/<bridge_name>.py` via `front/electron/utils/paths.ts`. Cette contrainte explique pourquoi les entrypoints publics restent a la racine plateforme pour l'instant. Ce ne sont pas des fichiers legacy a oublier : ce sont les portes d'entree contractuelles. Le code durable doit, lui, continuer a migrer vers un owner clair.
