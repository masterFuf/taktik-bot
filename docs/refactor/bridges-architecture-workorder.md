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
| `bridges/instagram` | Implementations bridge Instagram rangees par owner + `base.py`. | Plateforme Instagram bridge. | Launcher, manifest, scripts build, handlers Front via `bridge_name`. | `bridges.common`, `taktik/core/social_media/instagram/**`, DB/services. | Garder la racine sans wrappers publics ; `launcher.py` route directement vers `automation`, `engagement`, `scraping`, `account`, `agent`, `analysis`. |
| `bridges/tiktok` | Dispatcher TikTok, runners internes et implementations dediees par owner. | Plateforme TikTok bridge. | Launcher, manifest, scripts build, handlers Front via `bridge_name`. | `bridges.common`, `bridges.tiktok.base`, `taktik/core/social_media/tiktok/**`. | Continuer a classer par flow/owner (`workflows/**`, `account`, `publish`, `scraping`, `engagement`, `automation`) ; pas de nouveau `*_bridge.py` racine. |
| `bridges/youtube` | Implementations compte/upload/action test + `base.py`. | Plateforme YouTube bridge. | Launcher, manifest. | `taktik/core/social_media/youtube/**`, Gmail/app email pour compte. | Implementations sous `account/`, `publish/`, `diagnostics/` ou `workflows/`; pas de wrapper public racine. |
| `bridges/gmail` | Bridge provider Gmail + `base.py`. | Provider Gmail bridge. | Launcher, manifest. | `taktik/core/app/email/gmail/**`. | Implementation account sous `account/`; pas de wrapper public racine. |
| `bridges/threads` | Bridge Threads + `base.py`. | Plateforme Threads bridge. | Launcher, manifest. | `taktik/core/social_media/threads/**`, Instagram runtime selon dependances historiques. | Dispatcher sous `workflows/dispatcher.py`; pas de wrapper public racine. |
| `bridges/compat` | Bridges diagnostics compat/selectors/workflow/action tests. | Diagnostics/compat bridge. | Front debug/compat handlers, launcher, manifest. | `taktik/core/compat`, `taktik/core/clone`, plateformes. | Implementations sous `diagnostics/`; pas de wrapper public racine. |

## Regles cible

- `bridges/launcher.py <bridge_name>` = entrypoint public unique en dev ; `taktik_launcher.exe <bridge_name>` = entrypoint public unique en production.
- `bridges/<platform>/base.py` = runtime bridge local de la plateforme : IPC, helpers stdout, startup commun. Il ne doit pas devenir un workflow.
- `bridges/<platform>/workflows/**` = runners internes appeles par un entrypoint dispatcher, classes par famille de flow (`automation`, `engagement`, `scraping`, etc.).
- `bridges/<platform>/automation|engagement|scraping|account|publish|analysis|agent|diagnostics/**` = implementations d'entrypoints dedies routees directement par le launcher et le manifest.
- `bridges/<platform>/automation/runtime/**` = support local d'un bridge automation volumineux : parsing payload, lifecycle device/app, media capture, setup IA, runner. Ne pas laisser ces modules plats a cote de l'entrypoint automation.
- `bridges/<platform>/engagement/runtime/**` = support local des bridges engagement : commandes CLI, parsing payload, navigation partagee, emitters JSON. Ne pas laisser ces modules gonfler l'entrypoint `engagement/<flow>.py`.
- `bridges/common/device/**` = helpers techniques de bridge lies au device, a la connectivite ou au lifecycle app (`connection.py`, `app_manager.py`, `network.py`).
- `bridges/common/input/**` = helpers de saisie ou interaction input utilises par plusieurs bridges.
- `bridges/common/parsing/**` = parseurs de texte/payload partages par les bridges, sans acces device ni IPC.
- `bridges/common/persistence/**` = facades DB strictement bridge, sans SQL direct ; la vraie persistence reste dans `taktik/core/database/**`.
- `bridges/common/runtime/**` = bootstrap process, stdout JSON IPC, base bridge commune et signal handling.
- Pas de deplacement d'entrypoint public sans mise a jour coordonnee : manifest, `launcher.py`, `scripts/build_exe.py`, `taktik_launcher.spec`, `front/scripts/build/build-all.ps1` et resolver Front.
- Ne pas recreer de wrapper public racine. Le launcher doit ajouter `bot/` a `sys.path`, puis importer l'implementation scopee.

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
| B23 | Fait | Deplacer l'implementation dispatcher Threads sous `bridges/threads/workflows/dispatcher.py`; garder `threads_bridge.py` comme entrypoint public mince. | Direct-launch smoke + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B24 | Fait | Deplacer les implementations compat/action/selector/workflow diagnostics sous `bridges/compat/diagnostics/**`; garder les entrypoints publics racine. | Direct-launch smoke + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B25 | Fait | Migrer dev/prod vers le launcher unique, pointer manifest/launcher/build sur les modules scopees, supprimer les wrappers racine. | Launcher smoke + `compileall` + `check_bridge_manifest` + `git diff --check`. |
| B26 | Fait | Decouper le bridge Instagram desktop automation : diagnostics debug sous `instagram/diagnostics/`, parsing CLI/stdin sous `automation/runtime/input.py`, media capture sous `automation/runtime/media_capture.py`. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B27 | Fait | Extraire le runner workflow Instagram desktop sous `automation/runtime/workflow.py` et le setup IA sous `automation/runtime/ai.py`. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B28 | Fait | Extraire le runtime bridge Instagram desktop sous `automation/runtime/session.py` : SQLite, device connection, app launch, network reset et cleanup app. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B29 | Fait | Harmoniser l'arborescence Instagram automation avec le pattern TikTok : entrypoint `automation/desktop.py`, support sous `automation/runtime/**`. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B30 | Fait | Extraire les commandes CLI/read/send du bridge Instagram DM sous `engagement/runtime/dm_commands.py`. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B31 | Fait | Extraire la navigation inbox/conversation du bridge Instagram DM sous `engagement/runtime/dm_navigation.py`. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B32 | Fait | Extraire la lecture de conversations et l'extraction des messages Instagram DM sous `engagement/runtime/dm_reader.py`. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B33 | Fait | Extraire le parsing config/CLI du bridge Instagram Cold DM sous `engagement/runtime/cold_dm_commands.py`. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B34 | Fait | Extraire l'adapter persistence sent-DM du bridge Instagram Cold DM sous `engagement/runtime/cold_dm_persistence.py`. | Import smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B35 | Fait | Extraire l'adapter OpenRouter du bridge Instagram Cold DM sous `engagement/runtime/cold_dm_ai.py`. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B36 | Fait | Extraire la navigation search/profile/home du bridge Instagram Cold DM sous `engagement/runtime/cold_dm_navigation.py`. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B37 | Fait | Extraire le composer/send-button/invite-state du bridge Instagram Cold DM sous `engagement/runtime/cold_dm_sender.py`. | Import smoke + launcher smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B38 | Fait | Extraire le parsing config et le routing `scrape`/`reply_all` du bridge Instagram Smart Comment sous `engagement/runtime/smart_comment_commands.py`. | Import smoke + launcher JSON smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B39 | Fait | Extraire les modeles `ScrapedComment`, `TargetProfile` et `PostContext` du bridge Instagram Smart Comment sous `engagement/runtime/smart_comment_models.py`. | Import smoke + launcher JSON smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B40 | Fait | Extraire le parsing Litho dumpsys des commentaires Smart Comment sous `engagement/runtime/smart_comment_parsing.py` et utiliser le parseur de compte commun. | Import smoke + launcher JSON smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B41 | Fait | Extraire la capture screenshot post Smart Comment sous `engagement/runtime/smart_comment_media.py`. | Import smoke + launcher JSON smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B42 | Fait | Extraire la navigation profil cible, le scraping profile et l'ouverture du premier post Smart Comment sous `engagement/runtime/smart_comment_target.py`. | Import smoke + launcher JSON smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B43 | Fait | Extraire la phase comments Smart Comment (`open_comments`, sort, scraping visible, dumpsys, scroll, expand replies) sous `engagement/runtime/smart_comment_comments.py`. | Import smoke + launcher JSON smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B44 | Fait | Extraire la phase reply Smart Comment (`reply_to_comment`, recherche Reply, saisie clavier, batching et events reply) sous `engagement/runtime/smart_comment_reply.py`. | Import smoke + launcher JSON smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |
| B45 | Fait | Extraire le contexte post Smart Comment (caption, auteur, date, stats, URL post) sous `engagement/runtime/smart_comment_post_context.py`. | Import smoke + launcher JSON smoke + `compileall` + `check_bridge_manifest` + `audit_selector_hardcodes` + `git diff --check`. |

## Notes de compatibilite

Depuis le lot B25, le Front lance en dev `python bridges/launcher.py <bridge_name>` via `front/electron/utils/paths.ts`, comme la production lance `taktik_launcher.exe <bridge_name>`. Les fichiers `bridges/<platform>/<bridge_name>.py` racine ont ete supprimes pour eviter une couche legacy oubliee. Le contrat public devient `bridge_name + manifest + launcher`, et le code durable reste sous un owner clair.
