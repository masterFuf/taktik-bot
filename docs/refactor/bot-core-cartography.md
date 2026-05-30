# [Bot] Cartographie `taktik/core`

## Scope

Snapshot realise le 2026-05-30 avant les premiers deplacements structurels.

Note de contexte :

- `AGENTS.md` n'existe pas a la racine de `c:\Users\kevin\Documents\taktik-desktop` ; la lecture preparatoire s'est appuyee sur `bot/AGENTS.md`, `front/AGENTS.md` et les docs de refactor demandees.
- Cette page sert de base vivante pour les lots commitables. Elle doit etre mise a jour avant tout deplacement important.

## Cartographie top-level

| Dossier | Owner cible | Role constate | Imports entrants principaux | Imports sortants principaux | Odeurs / risques | Proposition |
|---|---|---|---|---|---|---|
| `social_media/` | Plateformes | Workflows, actions, selectors et managers Instagram/TikTok/YouTube/Threads. 343 fichiers Python, zone dominante du core. | CLI, bridges, `agent`, `recorder`, tests. | `database`, `shared`, `clone`, `config`, `email`, `device` legacy. | Contient encore des decisions DB (`instagram/actions/business/common/database_helpers.py`), des imports de shims legacy et plusieurs sous-familles heterogenes. | Garder comme racine plateforme. Sortir progressivement DB/device/shared legacy par petits lots. |
| `shared/` | Shared technique Android | Primitives ADB/input/actions/platform partagees. | Principalement `social_media/**`. | Aucun import top-level sortant releve. | Frontiere globalement saine, mais `shared/utils/action_utils.py` doit rester tres limite pour ne pas redevenir un fourre-tout. | Canonical owner des primitives Android partagees. Pas de code metier plateforme ici. |
| `database/` | Persistence | Schema, migrations, client SQLite, repositories par domaine. | `social_media`, `agent`, tests unitaires. | Aucun import top-level sortant releve. | Ownership DB plus clair qu'avant, mais la couche plateforme garde encore des helpers DB historiques. | Continuer la migration des acces DB vers repositories/facades `database/**`. Lot 2 deplace deja `processed / filtered / skip`, `processed_hashtag_posts` et le social graph legacy unfollow/sync vers des facades `database/instagram_*.py`, puis promeut ce dernier vers `repositories/instagram/social_graph/`. |
| `device/` | Compat runtime | API legacy tres simple pour bridges/scripts/tests historiques. | Bridges debug/compat, scripts, quelques tests Instagram. | Aucun import top-level sortant releve. | Duplique `shared/device/manager.py` avec une implementation separee. Zone citee explicitement dans l'audit. | Lot 1 : faire de `device/` une boundary de compat vers `shared/device/**`, sans casser l'API statique. |
| `clone/` | Runtime app Android clone-aware | Registry de package actif, proxy clone-aware, patch selectors, scan clones. | CLI, `recorder`, Instagram. | `compat`. | Regroupe a la fois registry runtime et adaptation selectors ; acceptable mais a garder strictement centre sur les clones. | Garder comme couche d'adaptation package/app, pas comme dossier "divers". |
| `compat/` | Compatibilite version/selectors | Routing de selectors par version et overrides YAML. | `clone`, bridges de compat, bridge Instagram desktop. | Aucun import top-level sortant releve. | Frontiere utile mais fragile si on y depose du debug ou du runtime generique. | Garder comme zone de compatibilite explicite, avec plan de sortie quand possible. |
| `agent/` | Runtime app / orchestration | Contexte et workflow d'agent autonome. | Bridge agent, package local. | `social_media`, `database`, `ai`. | Depend directement de plateforme et persistence. | Garder avec owner explicite "agent runtime", favoriser des services injectes pour les acces data. |
| `ai/` | Runtime app / IA | Helpers IA du bot. | `agent`. | Aucun import top-level sortant releve. | Surface faible pour l'instant. | Garder isole ; eviter d'y melanger des effets Android ou DB. |
| `email/` | Integration runtime | Gmail workflow/selectors utilises par YouTube et certains flows de signup. | Bridges Gmail/YouTube, TikTok signup. | Aucun import top-level sortant releve. | Domaine transverse legitime, mais son persistence doit rester sous `database/repositories/gmail`. | Garder comme integration runtime ciblee. |
| `media/` | Integration technique | Capture proxy / interception media. | Bridge Instagram desktop. | Aucun import top-level sortant releve. | Couplage fort au flux desktop de capture ; a surveiller pour ne pas y faire atterrir de persistence metier. | Garder comme technique/media. Pas d'ownership DB ou Instagram metier ici. |
| `recorder/` | Outil runtime / debug | Enregistreur de sessions humaines base sur selectors Instagram + clone rewrite. | Scripts. | `social_media`, `clone`. | Techniquement top-level, mais tres centre Instagram aujourd'hui. | Garder temporairement ; auditer plus tard s'il doit vivre en `social_media/instagram` ou comme outil shared/documente. |
| `config/` | Runtime app | Endpoints et configuration runtime. | Quelques modules Instagram. | Aucun import top-level sortant releve. | Petit package, peu de code. | Garder avec owner explicite. |
| `security/` | Runtime app | Protection / securite. | Aucun entrant releve dans l'audit AST. | Aucun import top-level sortant releve. | Surface actuellement faible ; risque de code mort ou de frontiere floue si on l'etend sans regle. | Garder mais documenter tout nouvel usage. |

## Hotspots a traiter par petits lots

| Priorite | Zone | Pourquoi c'est le bon lot | Direction |
|---|---|---|---|
| 1 | `device/` vs `shared/device/` | Duplication immediate, surface petite, nombreux call sites legacy. | Transformer `device/` en boundary de compat ; `shared/device/**` devient l'owner implementation. |
| 2 | `social_media/instagram/actions/business/common/database_helpers.py` | Decision DB encore dans une plateforme, contraire a la taxonomie cible. | Extraction progressive vers `database/**` sans casser les workflows. Sous-lots deja faits : `processed / filtered / skip` via `database/instagram_workflow_state.py`, tracking `processed_hashtag_posts` via `database/instagram_hashtag_posts.py`, puis bloc `unfollow sync` via `database/instagram_follow_graph.py`. |
| 3 | `social_media/*/core/manager.py` et `shared/platform/social_media_base.py` | Plusieurs managers importent encore des chemins Instagram legacy pour des concerns generiques. | Revenir a une base shared claire pour les managers applicatifs. |
| 4 | `clone/` vs `compat/` | Les deux zones sont legitimes mais proches conceptuellement. | Documenter leur frontiere : package/app runtime d'un cote, version/selectors de l'autre. |
| 5 | `recorder/` et `media/` | Zones techniques transverses, mais potentiellement trop couplees a Instagram desktop. | Decider si elles restent top-level runtime ou si une partie doit etre rattachee a une plateforme. |

## Regles deja deduites de la cartographie

- `shared/device/**` est la source de verite pour la connexion device, l'ATX et les primitives Android partagees.
- `device/` peut survivre comme compat import boundary, mais ne doit plus recevoir de nouvelle implementation propre.
- Une facade plateforme peut vivre sous `social_media/<platform>/.../device/` si elle ajoute un sens metier plateforme ; un `DeviceManager` a cet endroit doit etre un shim ou une specialisation explicite, pas une troisieme implementation generique.
- Une aide DB historique reste acceptable temporairement dans une plateforme seulement comme facade de compat documentee ; toute nouvelle logique SQL doit vivre sous `database/**`.

## Lots proposes

1. Lot 1 - boundary `device/` : doc + shim compat vers `shared/device/**` + tests unitaires.
2. Lot 2 - ownership DB Instagram : sous-lots faits pour `processed / filtered / skip`, `processed_hashtag_posts` et `unfollow sync`. Le SQL `following_sync` / `followers_sync` vit maintenant dans `repositories/instagram/social_graph/`, et la famille `unfollow` appelle deja `InstagramFollowGraphService` directement. Prochain pas naturel : reduire `instagram_follow_graph.py` puis supprimer le shim `database_helpers.py` quand les call sites legacy auront disparu.
3. Lot 3 - managers runtime : aligner `instagram/core/manager.py`, `tiktok/core/manager.py`, `threads/core/manager.py` et les bases shared.
4. Lot 4 - clarifier `clone/compat` : regles + petits deplacements si necessaire.
5. Lot 5 - auditer `recorder/media/agent/email/ai` selon l'usage reel.
