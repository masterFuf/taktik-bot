# Chantier transverse - Bot core

Cette page suit le refactor de `bot/taktik/core` pour TikTok et Instagram. Elle existe pour eviter de cacher l'avancement du Bot core dans une seule doc plateforme.

## Pourquoi cette page existe

- Le GitBook local du Bot expose des docs dediees TikTok et Instagram.
- Le chantier `bot/taktik/core` est transverse et ne doit pas etre enterre dans un seul audit plateforme.
- Cette page est l'entree canonique pour savoir ou on en est avant d'ouvrir les audits specialises.

## Etat global au 2026-05-30

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
- [ ] Audit structurel de `clone/**` et `compat/**` encore a faire.
- [ ] Cartographie puis assainissement des familles runtime/app restantes : `media`, `recorder`, `email`, `ai`, `agent`, `config`, `security`.
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
