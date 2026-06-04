# Pourquoi cette documentation existe

> **Perimetre : `[Transversal]`**
> Cette page explique le role de la documentation TAKTIK dans la maintenance, les refactors, l'audit technique et les futures extractions produit.

## Objectif

Cette documentation n'est pas seulement un manuel de lecture du code.

Elle sert de base de connaissance primaire pour :

- comprendre comment les projets `bot/`, `front/`, `taktik-api/` et `taktik-bot/` interagissent ;
- faciliter la reprise par un nouveau developpeur ;
- preparer des refactorisations lourdes sans perdre les dependances implicites ;
- auditer la base SQLite et la base MySQL ;
- identifier les duplications et les abstractions possibles ;
- extraire plus tard une documentation produit/marketing a partir d'une source technique fiable.

## Les quatre niveaux de lecture

| Niveau | Question | Pages principales |
|---|---|---|
| Systeme | Comment tout s'assemble ? | Architecture, cartes, sequence diagrams |
| Projet | Qui possede quel code ? | `[Bot]`, `[Front]`, `[API]`, `[Web]` |
| Workflow | Quel chemin suit une feature ? | Workflows end-to-end, bridges, IPC |
| Donnee | Ou une information est-elle creee, transformee, stockee ? | SQLite, MySQL/API, repositories |

## Pourquoi documenter aussi le Front et l'API dans la doc consolidee

La doc privee canonique vit dans `taktik-docs`, mais elle garde un miroir des
anciennes pages `bot/docs` parce que l'application reelle est transverse.

Une action Instagram typique traverse :

```text
[Front] React UI
  -> [Front] Electron handler
  -> [Bot] bridge Python
  -> [Bot] workflow
  -> [Bot] actions business
  -> [Bot] actions atomic
  -> Android/uiautomator2
  -> SQLite local
  -> [Front] rendu UI
```

La documenter uniquement cote Bot ferait perdre les configs, events et contraintes UI. La documenter uniquement cote Front ferait perdre la logique d'execution.

## Usage pour refactor

Avant un gros refactor, la doc doit permettre de repondre a ces questions :

| Question | Source |
|---|---|
| Qui appelle cette classe/fonction ? | Pages module + bridges + workflows |
| Quelle config arrive depuis Electron ? | Pages workflows end-to-end |
| Quels events stdout/IPC sont attendus ? | Bridges + desktop handlers |
| Quelle table est modifiee ? | Schema SQLite / MySQL API |
| Peut-on fusionner deux tables ? | Schema + repositories + workflows consommateurs |
| Peut-on mutualiser deux workflows ? | Actions business + workflows par plateforme |
| Quelle feature utilisateur risque de casser ? | Inventaire fonctionnel |

## Usage pour audit base de donnees

La documentation de DB doit aider a distinguer :

- tables centrales ;
- tables de cache ;
- tables legacy ;
- tables miroir Python/Electron ;
- tables candidates a fusion ;
- tables qui manquent d'index ;
- tables qui ont des champs redondants.

La page `database/schema.md` represente l'etat reel detecte dans le code. Elle doit rester la source de verite quand on touche au SQLite.

## Usage pour extraction produit

La couche technique peut etre transformee en inventaire fonctionnel :

| Source technique | Extraction produit |
|---|---|
| Workflows | fonctionnalites visibles |
| Selectors/actions | capacites d'automation |
| Scheduler/session engine | promesse de planification |
| AI services/prompts | capacites IA |
| Database/repositories | donnees exploitables et analytics |
| API/licence | packaging commercial |

Cette extraction doit rester honnete : elle doit decrire ce que le produit fait vraiment, les plateformes supportees et les limites connues.

## Usage marketing responsable

La documentation pourra alimenter :

- une page de presentation produit ;
- une grille de fonctionnalites par reseau social ;
- des comparatifs ;
- des cas d'usage ;
- des prompts d'agents qui evaluent si un topic public merite une reponse utile.

Regle importante : si un agent aide a repondre sur des forums ou communautes, il doit favoriser la valeur apportee, eviter le spam et ne pas masquer une affiliation quand le produit est recommande. La signature peut exister, mais la reponse doit d'abord resoudre le probleme de la personne.

## Convention de proprietaire

| Badge | Projet | Sens |
|---|---|---|
| `[Bot]` | `bot/` | Python, Android automation, bridges, workflows, actions |
| `[Front]` | `front/` | Electron, React, handlers, scheduler, UI, SQLite Electron |
| `[API]` | `taktik-api/` | FastAPI, JWT, licences, devices, updates, APKs |
| `[Web]` | `taktik-bot/` | Site Next.js, Prisma, Stripe, dashboard, support |
| `[Transversal]` | plusieurs projets | flow complet ou architecture commune |
| `[Produit]` | abstraction produit | fonctionnalites, cas d'usage, extraction marketing |

## Definition de "complet"

Une page est consideree complete quand elle couvre :

| Axe | Attendu |
|---|---|
| Fichiers reels | chemins exacts et classes/fonctions principales |
| Flux | sequence d'appel ou diagramme |
| Entrees | configs, payloads, arguments |
| Sorties | events, retours, effets UI |
| Donnees | tables, repositories, persistance |
| Limites | comportements incomplets, legacy, points d'attention |
| Liens | pages connexes pour suivre le flow |

## Regle de maintenance

Quand un module evolue :

1. mettre a jour la page du module ;
2. mettre a jour le workflow end-to-end si le flux change ;
3. mettre a jour la DB si une table/colonne/index change ;
4. mettre a jour l'inventaire produit si une fonctionnalite visible apparait/disparait ;
5. mettre a jour l'audit de couverture si le changement ouvre une zone non documentee.
