# [Bot] Mission parallele - Audit et refactor `taktik/core`

## Role de cette page

Cette page sert de feuille de route pour un agent IA ou un developpeur qui attaque le chantier d'architecture du dossier `bot/taktik/core`.

Le but n'est pas de "faire du propre" de maniere vague. Le but est de :

- rendre l'arborescence Bot lisible ;
- eviter les dossiers fourre-tout ;
- aligner la methode avec celle appliquee cote Front ;
- reduire la dette sans casser les bridges, les workflows, ni le mode standalone du Bot.

## Cartographie vivante

Etat 2026-05-30 :

- la cartographie de reference vit dans [bot-core-cartography.md](bot-core-cartography.md) ;
- la proposition de taxonomie cible racine vit dans [bot-core-target-taxonomy.md](bot-core-target-taxonomy.md) ;
- la proposition de taxonomie cible pour `instagram/ui/selectors` vit dans [instagram-ui-selectors-target-taxonomy.md](instagram-ui-selectors-target-taxonomy.md) ;
- le premier lot structurel cible `taktik/core/device` comme boundary de compat vers `taktik/core/shared/device/**`.
- le deuxieme lot structurel sort le bookkeeping `already_processed` / `already_filtered` / `skip` de `social_media/instagram/.../database_helpers.py` vers `taktik/core/database/instagram_workflow_state.py`, en gardant un shim de compatibilite cote plateforme.
- un sous-lot suivant du lot 2 sort aussi le tracking `processed_hashtag_posts` de `social_media/instagram/.../database_helpers.py` vers `taktik/core/database/instagram_hashtag_posts.py`.
- un sous-lot suivant du lot 2 sort le bloc `unfollow sync` (`following_sync`, `followers_sync`, follow-history lookup) de `social_media/instagram/.../database_helpers.py` vers `taktik/core/database/instagram_follow_graph.py`.
- un sous-lot suivant du lot 2 promeut ensuite ce social graph legacy vers `taktik/core/database/repositories/instagram/social_graph/`, en laissant `instagram_follow_graph.py` comme facade de compatibilite.
- un sous-lot suivant reduit les call sites `unfollow` pour appeler `InstagramFollowGraphService` directement, afin d'eviter de garder `DatabaseHelpers` comme delegant pur sur cette famille.
- un sous-lot suivant reduit les call sites `hashtag` pour appeler `InstagramHashtagPostService` directement, afin de continuer a vider `DatabaseHelpers` famille par famille.
- un sous-lot suivant reduit les call sites `workflow_state` (`notifications`, `followers`, `likers`, `feed`, `stats_recording`) pour appeler `InstagramWorkflowStateService` directement, et supprime un faux enregistrement `feed` qui ne correspondait a aucun owner DB et doublonnait la source de verite action-level.
- un sous-lot suivant retire aussi les deux derniers call sites coeur (`profile_processing`, `interaction_engine`) de `DatabaseHelpers`. Le shim reste seulement comme surface de compatibilite package-level en attendant un audit d'usage externe.
- un sous-lot suivant retire enfin le call site cache de `instagram/ui/extractors.py`, ce qui laisse `DatabaseHelpers` sans consommateur interne runtime.
- un sous-lot suivant retire aussi le SQL inline de `instagram/workflows/post_scraping/post_persistence.py` au profit de la facade DB existante, pour eviter une ecriture `instagram_profiles` cachee dans le workflow.
- un sous-lot suivant rend aussi la dependency DB explicite dans le scraping Instagram : `scraping_workflow` partage maintenant un `local_db` unique avec `persistence`, `list_scraping` et `deep_qualify`, au lieu de re-resoudre `get_local_database()` dans plusieurs branches runtime.
- un sous-lot suivant commence le lot 3 en branchant `instagram/core/manager.py` et `tiktok/core/manager.py` directement sur `shared/platform/social_media_base.py` et `shared/device/manager.py`, comme `threads/core/manager.py`.
- un sous-lot suivant etend ce lot 3 aux workflows Instagram qui ne demandent aucune facade plateforme (`scraping`, `post_scraping`, `cold_dm`) afin de reduire les imports runtime qui traversent encore les shims `actions/core/device`.
- un sous-lot suivant corrige aussi la compat top-level `taktik/core/__init__.py`, qui pointait vers un chemin `DeviceFacade` obsolete et n'exposait pas vraiment les symbols annonces dans `__all__`.
- un sous-lot suivant etend enfin ce lot 3 au CLI, qui importait encore `DeviceManager` via le shim Instagram alors qu'il consomme seulement le manager shared canonique.
- un sous-lot suivant aligne aussi les scripts de test/debug Instagram sur `shared/device/manager.py`, pour terminer la convergence des imports internes vers l'owner device shared avant d'auditer les surfaces de compat a conserver.
- un sous-lot suivant commence la migration reelle de `social_media/instagram/ui/selectors` en introduisant `ui/selectors/shell/` comme owner pour `auth`, `popup`, `text_input`, `detection` et `problematic_page`, avec shims top-level conserves pour la compatibilite d'import.
- un sous-lot suivant etend cette migration aux petites surfaces Instagram evidentes (`feed`, `hashtag`, `notifications`, `direct_messages`, `story_viewer`, `content_creation`, `followers_following`) via `ui/selectors/surfaces/`, toujours avec shims top-level de compatibilite.
- un sous-lot suivant termine la taxonomie "evidente" de `ui/selectors` en promouvant `support/` (`debug`, `scroll`) et `flows/` (`unfollow`) comme owners explicites, avec facade publique et shims top-level conserves.
- un sous-lot suivant rattache aussi `navigation.py` a `ui/selectors/shell/navigation.py`, y compris `ButtonSelectors`, pour terminer l'app chrome Instagram avant l'audit des grosses surfaces restantes (`profile`, `post`).
- un sous-lot suivant rattache aussi `profile.py` a `ui/selectors/surfaces/profile.py` sans le splitter, car le fichier reste centré sur la surface profil (header, counters, enrichissement, followers/following links).
- un sous-lot suivant sort aussi le monolithe `post.py` de la racine vers `ui/selectors/surfaces/post/detail.py` comme owner transitoire, en gardant `post.py` comme shim jusqu'au futur split fin (`comments`, `likers`, `share_sheet`, `grid`, `reels`).
- un sous-lot suivant introduit enfin plusieurs catalogues publics specialises pour les posts Instagram (`POST_DETAIL_SELECTORS`, `POST_COMMENTS_SELECTORS`, `POST_LIKERS_SELECTORS`, `POST_SHARE_SHEET_SELECTORS`, `POST_GRID_SELECTORS`, `POST_REELS_SELECTORS`), tout en gardant `POST_SELECTORS` comme facade legacy de compat.
- le meme chantier de taxonomie selectors devra ensuite etre applique a `social_media/tiktok/ui/selectors`, en reprenant la logique `shell` / `surfaces` / `flows` / `support` et des catalogues publics specialises par surface sensible.
- un premier sous-lot TikTok pose maintenant cette taxonomie via [tiktok-ui-selectors-target-taxonomy.md](tiktok-ui-selectors-target-taxonomy.md) et deplace les owners evidents `navigation`, `popup`, `detection` sous `shell/`, ainsi que `scroll` sous `support/`, avec shims top-level conserves.
- un sous-lot TikTok suivant deplace aussi les petites surfaces evidentes `profile`, `search`, `inbox`, `conversation` et `followers` sous `ui/selectors/surfaces/`, toujours avec shims top-level de compatibilite.
- un sous-lot TikTok suivant sort aussi `video.py` et `comment.py` de la racine vers `ui/selectors/surfaces/video/` et expose deja `VIDEO_DETAIL_SELECTORS` / `VIDEO_COMMENTS_SELECTORS` comme facades publiques de surface, en attendant le vrai split fin du catalogue video.
- un sous-lot TikTok suivant rattache aussi `auth.py` a `ui/selectors/shell/auth.py` comme owner de compat transitoire, avant le futur split fin par flow (`login`, `signup`, `country_picker`, `logout`).
- un sous-lot TikTok suivant rattache aussi `publish.py` a `ui/selectors/flows/publish.py`, pour sortir de la racine le dernier gros owner workflow avant son futur decoupage interne.
- un sous-lot TikTok suivant specialise enfin la surface `video` en plusieurs catalogues publics (`VIDEO_CREATOR_SELECTORS`, `VIDEO_ENGAGEMENT_SELECTORS`, `VIDEO_MEDIA_SELECTORS`, `VIDEO_STATE_SELECTORS`), tout en gardant `VIDEO_SELECTORS` comme facade legacy d'agregation.
- un sous-lot TikTok suivant transforme aussi `shell/auth.py` en vrai package `shell/auth/` et split proprement les selectors entre `login.py`, `signup.py`, `country_picker.py` et `logout.py`, tout en gardant `ui/selectors/auth.py` comme shim top-level.
- un sous-lot TikTok suivant aligne aussi les workflows management `signup` et `logout` sur `ui/selectors/shell/auth/*`, afin de reserver `ui/selectors/auth.py` a la compatibilite plutot qu'aux imports internes.
- un sous-lot TikTok suivant retire ensuite les fichiers top-level legacy `ui/selectors/*.py` une fois les imports internes et tests migres vers `shell/`, `surfaces/`, `flows/` et `support/`.
- un sous-lot Instagram suivant retire ensuite les fichiers top-level legacy `ui/selectors/*.py` une fois les imports internes migres vers `shell/`, `surfaces/`, `flows/` et `support/`, pour laisser `ui/selectors/__init__.py` comme seule facade publique de package.
- un sous-lot TikTok suivant transforme aussi `flows/publish.py` en vrai package `flows/publish/` et split les selectors entre `creation_entry.py`, `media_picker.py`, `editor.py`, `composer.py` et `progress.py`, tout en gardant `ui/selectors/publish.py` et `PUBLISH_SELECTORS` comme facades legacy.
- un sous-lot TikTok suivant aligne ensuite les services/runtime `publish` sur les owners directs `ui/selectors/flows/publish/*`, afin de reserver la facade top-level `ui/selectors/publish.py` a la compatibilite plutot qu'aux imports internes.
- un sous-lot suivant du lot 4 clarifie aussi `taktik/core/compat` : le framework selectors/versioning et tracing compat vit maintenant sous `taktik/core/compat/selectors/**`, les bridges internes et `clone/selector_patcher.py` importent ces owners directs, et `compat/selector_registry.py`, `compat/selector_tracer.py`, `compat/setup.py` ne restent plus que comme shims de compatibilite.
- un sous-lot suivant du lot 4 clarifie aussi `taktik/core/clone` : `clone/package_map.py` devient la source de verite des package names officiels et prefixes de clone, remplace les duplications dans `detector.py`, `proxy.py` et `selector_patcher.py`, et verrouille cette frontiere par un test unitaire cible.
- un sous-lot suivant du lot 5 clarifie `taktik/core/recorder` : le human recorder Instagram n'est plus owner au niveau racine et vit maintenant sous `taktik/core/social_media/instagram/recorder/**`, tandis que `taktik/core/recorder/recorder.py` reste une facade de compatibilite pour les scripts et imports legacy.
- un sous-lot suivant du lot 5 assainit aussi `config/security` sans big-bang : `APIEndpointManager` re-expose l'alias legacy `get_primary_endpoint()` attendu par `instagram/actions/business/system/config.py`, et `security/protection.py` n'utilise plus `print(...)` pour eviter tout risque de pollution stdout si ce chemin dormant est reveille.
- un sous-lot suivant du lot 5 clarifie aussi `taktik/core/media` : la capture media Instagram vit maintenant sous `taktik/core/social_media/instagram/media/**`, `taktik/core/media/**` reste une facade de compatibilite pour les imports legacy, et `ProxyManager` resolve desormais ses assets runtime via le dossier repo `scripts/` au lieu de dependre de la profondeur du package Python.
- un sous-lot suivant du lot 5 clarifie `taktik/core/email/gmail` : `gmail_workflow.py` ne depend plus directement de `bridges.common.ipc`, expose un notifier injecte optionnel, et les bridges/workflows appelants (`bridges/gmail`, `bridges/youtube`, TikTok signup) lui passent maintenant leur IPC existant depuis l'exterieur.
- un sous-lot suivant du lot 5 pose aussi la cible de `taktik/core/agent` comme runtime kernel transverse : `agent-runtime-kernel-target.md` documente la separation Front planner / Bot executor, les contrats cibles (`AgentPlan`, `PlanStep`, `WorkflowInvocation`, `AgentEvent`) et la trajectoire de `TaktikAgentWorkflow` vers un scenario historique branche sur un noyau d'execution plus generic.
- un sous-lot suivant du lot 5 commence aussi le decouplage concret de `taktik/core/agent` : `contracts.py` devient la premiere surface runtime du noyau, `TaktikAgentWorkflow` recoit un provider AI injecte ou une factory injectee au lieu d'importer `bridges.common.ai_service`, et le bridge Instagram possede maintenant l'adapter de construction `AIService`.
- un sous-lot suivant du lot 5 applique la meme regle au scraping Instagram : `scraping_workflow.py` ne construit plus lui-meme `IPC` + `AIService`, et recoit maintenant notifier/provider AI depuis ses appelants bridge ou CLI.
- un sous-lot suivant du lot 5 introduit enfin le premier noyau executable de `core/agent` : `registry.py` porte l'enregistrement des workflows canoniques et `executor.py` deroule un `AgentPlan` minimal en emettant des `AgentEvent`, sans encore remplacer les scenarios historiques existants.
- un sous-lot suivant du lot 5 applique aussi la regle "notifier injecte" aux workflows TikTok de management (`login`, `logout`, `signup`) : ils n'instancient plus `bridges.common.ipc.IPC()` dans `core`, et le bridge compte TikTok leur passe maintenant `_ipc` depuis l'exterieur.
- un sous-lot suivant du lot 5 etend cette hygiene au publish TikTok : `upload_workflow.py` garde un fallback standalone mais recoit maintenant son notifier live par injection depuis `tiktok_publish_bridge.py`.
- un sous-lot suivant du lot 5 clarifie aussi `taktik/core/ai` : le provider OpenRouter `AIService` vit maintenant sous `taktik/core/ai/openrouter.py`, les bridges et le CLI importent cet owner canonique, et `bridges/common/ai_service.py` ne reste qu'un shim de compatibilite.
- un sous-lot suivant du lot 5 aligne aussi `core/agent` sur le manifest transversal : `workflow_manifest.py` lit `workflows.manifest.json` et expose les IDs canoniques `platform.family.workflow` utilises par les futurs `AgentPlan`.
- un sous-lot suivant du lot 5 ajoute la boundary d'entree JSON du noyau agent : `plan_io.py` convertit un payload Front/CLI en `AgentPlan` et peut valider les `workflow_id` contre le manifest transversal.

## Prompt pret a coller

```text
Tu travailles dans le monorepo TAKTIK avec acces au dossier `bot/` et au dossier `front/`.

Ta mission porte d'abord sur `bot/taktik/core`.

Avant toute modification :
- lis le `AGENTS.md` racine, puis `bot/AGENTS.md`, puis `front/AGENTS.md` pour comprendre la methode deja appliquee ;
- lis `bot/docs/refactor/bot-core-architecture-workorder.md` ;
- lis `bot/docs/refactor/refactor-readiness.md` ;
- lis `taktik-bot/docs/admin/instagram/quality-audit.md` et `taktik-bot/docs/admin/instagram/audit-remediation-plan.md` sur les sections Bot/core.

Objectif :
- auditer puis assainir l'architecture de `bot/taktik/core` ;
- appliquer une logique proche du Front en termes de cloisonnement des responsabilites, sans recopier aveuglement son arborescence ;
- utiliser SOLID de facon pragmatique ;
- mettre a jour `bot/AGENTS.md` et la documentation a chaque lot qui change la structure ou les regles.

Contraintes fortes :
- pas de big-bang ;
- pas de deplacements massifs sans cartographie prealable ;
- pas de nouveau dossier fourre-tout (`utils`, `helpers`, `misc`, `common`) au niveau `taktik/core` ;
- pas de repository SQLite hors `taktik/core/database/repositories` ;
- pas de code plateforme dans `taktik/core/shared` ;
- ne jamais casser stdout JSON des bridges ;
- le Bot doit rester utilisable en standalone, sans dependre du Front.

Methodologie obligatoire :
1. Cartographier `bot/taktik/core` : dossier -> role -> owner -> imports entrants/sortants -> proposition.
2. Identifier les zones floues ou dupliquees, par exemple `device` vs `shared/device`, `clone` vs `compat`, modules transverses caches dans une plateforme, logique DB hors `database`.
3. Proposer des lots petits, commitables et verifiables.
4. Traiter un lot a la fois.
5. Apres chaque lot :
   - mettre a jour la doc ;
   - mettre a jour `bot/AGENTS.md` si une nouvelle regle structurelle apparait ;
   - lancer les checks les plus proches (`pytest` cible, audits scripts, `git diff --check`) ;
   - commit par famille de changement.

Architecture cible a respecter :
- `taktik/core/social_media/<platform>` : code metier propre a une plateforme ;
- `taktik/core/shared` : primitives Android/ADB/input/actions partagees ;
- `taktik/core/database` : schema, migrations, modeles, repositories ;
- `taktik/core/config|security|device|media|email|ai|agent` : modules runtime/app avec owner explicite ;
- `taktik/core/compat|clone` : compatibilite ou variantes legacy, jamais zone de depot par confort.

Definition of done d'un lot :
- ownership clair ;
- imports coherents ;
- pas de regression bridge/workflow evidente ;
- doc a jour ;
- checks lances ou impossibilite explicitee ;
- commit propre.

Tu dois privilegier les petits refactors robustes et documentes plutot qu'une "grande reorganisation" fragile.
```

## Lecture minimale obligatoire

Avant de toucher le code :

1. `AGENTS.md` a la racine du monorepo.
2. `bot/AGENTS.md`.
3. `front/AGENTS.md`.
4. `bot/docs/refactor/refactor-readiness.md`.
5. `taktik-bot/docs/admin/instagram/quality-audit.md`.
6. `taktik-bot/docs/admin/instagram/audit-remediation-plan.md`.

## Philosophie d'alignement Front/Bot

L'objectif n'est pas de forcer le Bot a ressembler visuellement au Front. L'objectif est d'appliquer les memes principes de fond :

| Principe | Cote Front | Traduction cote Bot |
|---|---|---|
| Owner clair | `app` / `platforms` / `shared` / `workspace` | `social_media/<platform>` / `shared` / `database` / runtime app explicite |
| Contrats explicites | types centralises, handlers fins, repositories nommes | payloads bridge stables, workflows lisibles, repositories SQLite nommes |
| SOLID | UI, handlers, services, repos separes | bridges, workflows, services, selectors, DB separes |
| Refactor progressif | extraction par lots | cartographie puis deplacements par familles |

Le Bot peut garder ses particularites, mais il ne doit plus accumuler de zones "on ne sait pas trop pourquoi c'est ici".

## Perimetre du chantier

Le chantier vise surtout :

- `bot/taktik/core/social_media/**`
- `bot/taktik/core/shared/**`
- `bot/taktik/core/database/**`
- `bot/taktik/core/device/**`
- `bot/taktik/core/media/**`
- `bot/taktik/core/compat/**`
- `bot/taktik/core/clone/**`
- `bot/taktik/core/agent/**`
- `bot/taktik/core/ai/**`
- `bot/taktik/core/email/**`
- `bot/taktik/core/config/**`
- `bot/taktik/core/security/**`

Le chantier n'autorise pas par defaut :

- une redefinition complete des bridges ;
- une migration schema non necessaire au lot ;
- des renommages massifs de packages sans couche de transition ;
- des changements silencieux du protocole Electron <-> Bot.

## Plan conseille

### Lot 0 - Cartographie

Produire un inventaire :

| Champ | Attendu |
|---|---|
| Dossier | chemin |
| Owner | plateforme, shared, persistence, runtime app, compat |
| Role | ce que le dossier est cense porter |
| Odeur | duplication, nom trompeur, melange de responsabilites, legacy |
| Dependances | imports entrants/sortants principaux |
| Action | garder, deplacer, splitter, documenter, deprecier |

### Lot 1 - Frontieres de persistence

Verifier que :

- les repositories restent dans `database/repositories` ;
- les services/workflows plateforme ne recreent pas leur propre couche DB ;
- les modules transverses n'ecrivent pas directement SQLite "par facilite".

### Lot 2 - Shared vs plateforme

Verifier que :

- `shared` ne porte pas de logique Instagram/TikTok cachee ;
- une logique specifique a une seule plateforme ne fuit pas dans `shared` ;
- les helpers techniques reutilisables n'ont pas ete recopies dans plusieurs plateformes.

### Lot 3 - Runtime app et compat

Verifier que :

- `device`, `media`, `email`, `ai`, `agent`, `config`, `security`, `clone`, `compat` ont chacun un owner clair ;
- les dossiers legacy servent vraiment a la compat, pas a stocker le code qu'on ne sait pas classer.

### Lot 4 - Rationalisation finale

Seulement apres les lots precedents :

- petits deplacements ;
- re-exports temporaires si necessaire ;
- nettoyage de la doc ;
- checks et commits.

## Checks minimaux par lot

| Type de lot | Checks minimaux |
|---|---|
| Structure pure/doc | `git diff --check` |
| Bridge impacte | `python scripts/check_bridge_manifest.py` + verification import/bridge cible |
| Workflow impacte | `pytest` cible + `python scripts/audit_workflow_registry.py` si registre touche |
| DB impactee | `pytest tests/unit/test_db_schema.py` + audit doc schema si necessaire |

## Ce qu'on veut eviter

- "J'ai tout deplace, on verra ce qui casse".
- "J'ai cree `helpers/` parce que je ne savais pas ou mettre le code".
- "J'ai mis un repository dans une plateforme parce que c'etait plus simple".
- "J'ai aligne le nom d'un dossier sans verifier les bridges/imports".
- "J'ai recopie le Front tel quel alors que le Bot a des contraintes differentes".

## Sortie attendue

Une bonne execution de cette mission doit produire :

- une cartographie claire de `taktik/core` ;
- une convention d'architecture explicite ;
- des petits refactors robustes ;
- une documentation tenue a jour ;
- des commits par famille ;
- moins de melange entre plateforme, shared, persistence et compat.
