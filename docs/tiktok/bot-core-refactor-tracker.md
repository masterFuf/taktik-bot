# Chantier transverse - Bot core

Cette page suit le refactor de `bot/taktik/core` pour TikTok et Instagram. Elle existe pour eviter de cacher l'avancement du Bot core dans une seule doc plateforme.

## Pourquoi cette page existe

- Le GitBook local du Bot expose des docs dediees TikTok et Instagram.
- Le chantier `bot/taktik/core` est transverse et ne doit pas etre enterre dans un seul audit plateforme.
- Cette page est l'entree canonique pour savoir ou on en est avant d'ouvrir les audits specialises.

## Etat global au 2026-05-31

- [x] Cartographie vivante de `bot/taktik/core` produite.
- [x] Trajectoire cible documentee pour mieux separer `social_media`, `shared`, `database`, runtime/app et compat.
- [x] Boundary `device` clarifiee : `shared/device/**` est l'owner canonique.
- [x] Ownership DB Instagram assainie sur `workflow_state`, `hashtag_posts` et `follow_graph`.
- [x] `DatabaseHelpers` reduit a une facade legacy documentee, sans consommateur runtime interne.
- [x] Managers plateforme, workflows Instagram concernes, CLI et tooling interne realignes sur les boundaries shared/runtime.
- [x] Taxonomie selectors Instagram posee par scope reel : `shell/`, `surfaces/`, `flows/`, `support/`.
- [x] Taxonomie selectors TikTok posee par scope reel : `shell/`, `surfaces/`, `flows/`, `support/`.
- [x] Surface `post` Instagram specialisee avec catalogues publics dedies.
- [x] Surface `video` TikTok specialisee avec catalogues publics dedies.
- [x] `auth` TikTok splitte par flow.
- [x] `publish` TikTok splitte par etape.
- [x] Fichiers legacy top-level `ui/selectors/*.py` retires pour Instagram et TikTok apres migration des imports internes.
- [x] `compat/selectors/**` est maintenant l'owner interne du framework selectors/versioning ; `compat/*.py` ne restent plus qu'en shims de compatibilite.
- [x] `clone/package_map.py` centralise les package names officiels, variantes installables TikTok et prefixes de clone.
- [x] Le human recorder Instagram vit maintenant sous `social_media/instagram/recorder/**` ; `taktik/core/recorder` ne garde qu'une facade de compatibilite.
- [x] Hygiene runtime `config/security` : alias legacy `get_primary_endpoint()` retabli pour `APIEndpointManager` et suppression des `print(...)` dans `core/security`.
- [x] La capture media Instagram vit maintenant sous `social_media/instagram/media/**` ; `taktik/core/media` ne garde qu'une facade de compatibilite et `ProxyManager` resolve ses assets via `scripts/`.
- [x] `core/app/email/gmail/workflows/account.py` n'importe plus directement l'IPC bridge ; le workflow Gmail recoit maintenant un notifier injecte depuis ses appelants.
- [x] Cible `core/agent` documentee comme runtime kernel transverse, separe du planner premium cote Front.
- [x] `core/agent` n'importe plus directement `bridges.common.ai_service` ; le provider AI est maintenant injecte par le bridge appelant.
- [x] Le scraping Instagram ne construit plus directement `IPC` + `AIService` dans `core`; bridge et CLI injectent maintenant le provider AI.
- [x] `core/agent` expose maintenant un premier `WorkflowRegistry` et un `AgentPlanExecutor` minimaux, sans brancher encore les workflows historiques.
- [x] Les workflows TikTok `login/logout/signup` n'instancient plus `IPC()` dans `core`; le notifier live est injecte par le bridge compte.
- [x] Le workflow `tiktok publish` n'instancie plus le notifier bridge dans `core`; `tiktok_publish_bridge.py` le lui injecte maintenant.
- [x] `core/ai` possede maintenant le provider OpenRouter ; l'ancien shim `bridges/common/ai_service.py` a ete retire.
- [x] `core/ai` est maintenant classe par owners internes : `providers/` pour OpenRouter et `comments/` pour l'IA commentaire/persona.
- [x] `core/agent` lit maintenant le manifest transversal pour exposer des IDs canoniques `platform.family.workflow`.
- [x] `core/agent` sait parser/serialiser un payload JSON en `AgentPlan` avec validation optionnelle du manifest.
- [x] `TaktikAgentWorkflow` charge maintenant un payload `agent_plan` / `agentPlan` dans son contexte runtime sans changer le scenario historique.
- [x] `core/agent/kernel/runtime.py` fournit maintenant une facade parse/execute autour d'un `WorkflowRegistry` injecte, sans brancher les workflows Android par defaut.
- [x] `core/agent/io/events.py` expose une serialisation JSON-safe des `AgentEvent` pour les futurs bridges.
- [x] `core/agent` est maintenant classe par owners internes : `kernel/`, `io/`, `decision/`, `scenarios/`, avec une racine limitee a la facade publique `__init__.py`.
- [x] `core/agent/kernel` separe les dataclasses de plan/event, les ports injectes et les erreurs runtime structurees.
- [x] Le runtime TikTok publish resolve les packages TikTok via la source de verite `clone/package_map.py`, plus via `tiktok/core/manager.py`.
- [x] Le workflow TikTok publish delegue le restart package a `services/runtime/app_control.py`, pour garder le workflow centre sur le publish.
- [x] Premier handler reel Agent brancheable : `tiktok.standalone.upload_post` peut etre enregistre dans `WorkflowRegistry` avec device/notifier injectes.
- [x] Deuxieme handler publish Agent brancheable : `youtube.publish.upload_post` suit le meme pattern injectable sans modifier son bridge.
- [x] TikTok Followers peut maintenant etre enregistre comme handler Agent `tiktok.automation.followers`, avec un contrat single-target et des parametres normalises vers `FollowersConfig`.
- [x] TikTok For You peut maintenant etre enregistre comme handler Agent `tiktok.automation.for_you`, avec un contrat video-feed injectable et sans dependance au bridge startup.
- [x] TikTok Search/Hashtag/Target peuvent maintenant etre enregistres comme handlers Agent single-query (`tiktok.automation.search`, `tiktok.automation.hashtag`, `tiktok.automation.target`), sans reprendre le multi-query du bridge.
- [x] Les handlers Agent TikTok partagent maintenant leurs primitives d'adaptation locales via `actions/business/workflows/_internal/agent_runtime.py`, sans nouveau helper transversal.
- [x] TikTok Unfollow peut maintenant etre enregistre comme handler Agent `tiktok.standalone.tiktok_unfollow`, avec mapping conserve de `skipFriends` vers `include_friends`.
- [x] TikTok Scraping peut maintenant etre enregistre comme handler Agent `tiktok.automation.scraping` / `tiktok.standalone.tiktok_scraping`, avec persistence profile injectable plutot que DB bridge integree.
- [x] TikTok DM read/send peuvent maintenant etre enregistres comme handlers Agent `tiktok.automation.dm_read` / `tiktok.automation.dm_send`, sans melanger la logique `dm_outreach_bridge.py` encore bridge-owned.
- [x] TikTok cold DM outreach n'est plus une classe metier dans le bridge : `dm/outreach.py` porte le workflow et le bridge injecte notifier + dedup SQLite.
- [x] TikTok cold DM outreach peut maintenant etre enregistre comme handler Agent `tiktok.standalone.tiktok_dm_outreach`, avec notifier et dedup injectes.
- [x] TikTok account login/logout/register peuvent maintenant etre enregistres comme handlers Agent `tiktok.account.login/logout/register`, sans reprendre le startup bridge.
- [x] Gmail login/logout/read_otp/scan_accounts peuvent maintenant etre enregistres comme handlers Agent `gmail.account.login/logout/read_otp/scan_accounts`, avec persistence account injectee.
- [x] YouTube account login/logout vivent maintenant sous `social_media/youtube/workflows/account/**`; le bridge ne garde que connexion device, DB bootstrap, `force_stop` et stdout JSON.
- [x] YouTube account peut maintenant etre enregistre comme handler Agent `youtube.account.login/logout`, avec notifier et persistence injectables.
- [x] Instagram account login/logout/register peuvent maintenant etre enregistres comme handlers Agent `instagram.account.login/logout/register`, sans reprendre le startup bridge.
- [x] Instagram scraping target/hashtag/post_url peuvent maintenant etre enregistres comme handlers Agent `instagram.scraping.target/hashtag/post_url`, avec `device_manager` et provider AI injectes.
- [x] Audit structurel de `clone/**` et `compat/**` documente : owners confirmes, shims top-level limites, pas de deplacement mecanique recommande.
- [x] Garde-fou selectors ajoute : `python scripts/audit_selector_hardcodes.py` bloque les nouveaux hardcodes UI Android dans le runtime Instagram/TikTok et affiche la dette legacy allowlistee.
- [ ] Brancher progressivement les autres handlers reels de workflows dans `WorkflowRegistry`, apres validation du contrat bridge/payload de chaque workflow.
- [ ] Replier `TaktikAgentWorkflow` en scenario/autopilot historique quand le noyau `AgentRuntime` aura au moins un flow reel valide.
- [ ] Validation manuelle des workflows et bridges sur device reel.
- [ ] Decision finale sur la deprecation ou non des agregateurs publics legacy.

## Point d'attention ouvert

Les agregateurs publics `POST_SELECTORS`, `VIDEO_SELECTORS` et `PUBLISH_SELECTORS` sont volontairement gardes pour le moment.

Pourquoi :

- les usages internes du monorepo ont ete migres vers les owners specialises ;
- mais on n'a pas encore rejoue un panel suffisant de workflows manuels et bridges pour fermer le doute de regression ;
- les supprimer maintenant serait une decision de compatibilite, pas un simple refactor mecanique.

## Reste handlers Agent au 2026-05-31

Les IDs manifest sans handler reel ne sont plus des petits adapters evidents :

- Instagram automation est maintenant branche sur `WorkflowRegistry` via `social_media/instagram/workflows/core/agent_handler.py` apres extraction des builders config/session, hooks IA et setup runtime. Attention residuelle : connexion device, lancement app, reset network et media capture restent volontairement chez le caller/bridge.
- Instagram engagement (`dm_read`, `dm_send`, `coldDm`, `smart_comment`, `taktik_agent`) reste heterogene : DM read/send contient encore du metier dans `dm_bridge.py`, `coldDm` a une logique bridge historique, et `taktik_agent` doit rester orchestrateur transverse avec planner Front. Prochain lot recommande : traiter chaque bridge/workflow separement, pas un handler global.
- Threads (`follow`, `target`, `feed`) est maintenant branche sur `WorkflowRegistry` via `social_media/threads/workflows/agent_handler.py`; le caller doit fournir le `startup` afin que le handler n'ouvre pas de connexion device.

## Lire ensuite

- Pour le contexte TikTok et les risques historiques : [Audit qualite et refactor TikTok](quality-audit.md)
- Pour le contexte Instagram equivalent : ouvrir la meme page cote Instagram depuis le menu local Instagram.
