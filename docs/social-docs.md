# Docs dediees par reseau

> **Perimetre : `[Transversal]`**
> Cette page reference les parcours specialises par plateforme sociale dans la documentation privee unique `taktik-docs`. Les sections Instagram et TikTok ne sont pas des documentations separees : elles sont des parcours de travail Bot + Electron integres a la doc canonique.

## Pourquoi ces entrees existent

La doc principale reste la source complete du monorepo. Mais quand on travaille une seule plateforme, on perd du temps a traverser :

- des pages desktop transversales ;
- des bridges multi-plateformes ;
- des workflows qui ne concernent pas le sujet du jour ;
- des details API/Web qui ne sont pas utiles au debug courant.

Les sections ci-dessous servent donc de **parcours par reseau** :

- navigation plus courte ;
- vision Bot + Electron au meme endroit ;
- duplication volontaire des modules partages quand c'est utile ;
- cahier des charges feature ;
- sequence diagrams ;
- contrats DB/sync ;
- audit des zones a refactoriser ;
- checks anti-regression.

## Points d'entree

Quand la documentation consolidee est servie en local depuis `taktik-docs` :

| Plateforme | URL locale | Contenu |
|---|---|---|
| Instagram | `http://localhost:3000/#/bot/instagram/` | Parcours Bot + Electron Instagram : architecture, Electron, Bot, bridges, selectors, workflows, scheduler/live, data, network, debug, qualite. |
| TikTok | `http://localhost:3000/#/bot/tiktok/` | Parcours Bot + Electron TikTok : architecture, Electron, Bot, bridges, selectors, workflows, publish, scheduler/live, data, network, debug, qualite. |
| Threads | `http://localhost:3000/#/bot/threads/` | Hub compact Threads MVP. |
| YouTube | `http://localhost:3000/#/bot/youtube/` | Hub compact YouTube upload/account/debug. |
| Gmail | `http://localhost:3000/#/bot/gmail/` | Hub compact Gmail OTP/account/debug. |

## Ce qu'ils contiennent

Instagram et TikTok suivent la meme logique :

1. architecture plateforme ;
2. runtime Electron ;
3. runtime Bot Python ;
4. contrats donnees et sync ;
5. modules partages a reutiliser ;
6. audit qualite/refactor ;
7. template feature.

Threads, YouTube et Gmail restent pour l'instant des hubs compacts.

## Ce qu'ils ne doivent pas devenir

- une copie divergente et non maintenue de la doc principale ;
- un endroit ou l'on documente des suppositions non verifiees ;
- une excuse pour dupliquer le code.

La logique est :

- **doc principale `taktik-docs`** = reference exhaustive ;
- **sections par reseau** = parcours de travail pour developper sans casser.

## Workflow avant une feature

Pour une feature Instagram ou TikTok :

1. ouvrir la doc dediee ;
2. remplir mentalement le template feature ;
3. lister l'existant a reutiliser ;
4. dessiner le sequence diagram ;
5. decrire l'impact DB/migration/sync ;
6. definir les checks stop/cancel/scheduler ;
7. coder seulement ensuite.

## Liens utiles

| Besoin | Page |
|---|---|
| Carte de navigation principale | [Plan du guide technique](guidebook-map.md) |
| Hub Instagram | [ouvrir la section Instagram](instagram/) |
| Hub TikTok | [ouvrir la section TikTok](tiktok/) |
| Workspace reseau | [Network Control Center](desktop/network-control-center.md) |
| Control room runtime | [Live Center](desktop/live-center.md) |
