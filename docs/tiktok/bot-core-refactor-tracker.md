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
- [x] `clone/package_map.py` centralise les package names officiels et prefixes de clone.
- [x] Le human recorder Instagram vit maintenant sous `social_media/instagram/recorder/**` ; `taktik/core/recorder` ne garde qu'une facade de compatibilite.
- [x] Hygiene runtime `config/security` : alias legacy `get_primary_endpoint()` retabli pour `APIEndpointManager` et suppression des `print(...)` dans `core/security`.
- [x] La capture media Instagram vit maintenant sous `social_media/instagram/media/**` ; `taktik/core/media` ne garde qu'une facade de compatibilite et `ProxyManager` resolve ses assets via `scripts/`.
- [x] `core/email/gmail` n'importe plus directement l'IPC bridge ; le workflow Gmail recoit maintenant un notifier injecte depuis ses appelants.
- [x] Cible `core/agent` documentee comme runtime kernel transverse, separe du planner premium cote Front.
- [x] `core/agent` n'importe plus directement `bridges.common.ai_service` ; le provider AI est maintenant injecte par le bridge appelant.
- [x] Le scraping Instagram ne construit plus directement `IPC` + `AIService` dans `core`; bridge et CLI injectent maintenant le provider AI.
- [x] `core/agent` expose maintenant un premier `WorkflowRegistry` et un `AgentPlanExecutor` minimaux, sans brancher encore les workflows historiques.
- [ ] Audit structurel de `clone/**` et `compat/**` encore a faire.
- [ ] Rationaliser l'owner provider dans `core/ai` pour les workflows qui importent encore `bridges.common.ai_service`.
- [ ] Faire emerger `registry.py` / `executor.py` pour sortir `TaktikAgentWorkflow` du role de pseudo-noyau global.
- [ ] Validation manuelle des workflows et bridges sur device reel.
- [ ] Decision finale sur la deprecation ou non des agregateurs publics legacy.

## Point d'attention ouvert

Les agregateurs publics `POST_SELECTORS`, `VIDEO_SELECTORS` et `PUBLISH_SELECTORS` sont volontairement gardes pour le moment.

Pourquoi :

- les usages internes du monorepo ont ete migres vers les owners specialises ;
- mais on n'a pas encore rejoue un panel suffisant de workflows manuels et bridges pour fermer le doute de regression ;
- les supprimer maintenant serait une decision de compatibilite, pas un simple refactor mecanique.

## Lire ensuite

- Pour le contexte TikTok et les risques historiques : [Audit qualite et refactor TikTok](quality-audit.md)
- Pour le contexte Instagram equivalent : ouvrir la meme page cote Instagram depuis le menu local Instagram.
