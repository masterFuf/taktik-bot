# TAKTIK - Documentation Bot

> **Perimetre : `[Bot]`**
> Documentation historique du moteur Python, des bridges, des workflows et des
> anciennes pages transverses liees au Bot.
>
> Cette doc n'est plus le point d'entree canonique. La documentation privee
> unique et consolidee se lance depuis la racine `taktik-docs/` avec `yarn dev`.

## Statut

`bot/docs` est conserve temporairement comme source historique Bot pendant la
consolidation. Il peut contenir des pages anciennes, sensibles ou partiellement
remplacees. Il ne doit pas etre republie tel quel dans le bot open source.

La source de lecture canonique est :

```powershell
cd <repo>\taktik-docs
yarn dev
```

## A Quoi Sert Encore Ce Dossier

| Usage | Page de depart |
|---|---|
| Retrouver une page Bot encore conservee | `_sidebar.md` |
| Comprendre le perimetre historique | `scope.md` |
| Lire les anciennes notes de strategie documentaire | `documentation-strategy.md` |
| Comprendre la base SQLite cote Bot | `database/schema.md` puis `database/overview.md` |
| Preparer un gros refactor Bot | `refactor/refactor-readiness.md` |
| Lire les docs historiques par reseau | `social-docs.md` |
| Suivre le changelog Bot canonique | `CHANGELOG.md` |

Les pages produit, API, marketing ou transverses doivent etre consultees dans
`taktik-docs`, pas dans `bot/docs`, sauf audit historique explicite.

## Carte Rapide

| Zone | Role | Vigilance |
|---|---|---|
| `architecture/`, `core/`, `workflows/` | Architecture et flows generiques du bot. | Verifier avec le code avant promotion canonique. |
| `database/` | Schema, repositories, ownership SQLite Bot/Python. | Ne pas melanger avec la DB Electron sans contrat explicite. |
| `bridges/`, `compat/` | Interface Bot/Front et diagnostics. | Frontiere public/prive sensible. |
| `instagram/`, `tiktok/`, `youtube/`, `threads/`, `gmail/` | Docs historiques par plateforme. | Selectors, strategies et workflows doivent etre audites avant publication. |
| `refactor/` | Workorders et audits refacto Bot. | Certaines notes peuvent etre sensibles ou datees. |
| `security/` | Notes securite historiques. | A garder public-safe ; le sensible va dans `taktik-docs/premium/security/`. |

## Regle De Lecture

Quand tu veux comprendre une feature, pars toujours de l'entree utilisateur puis
descends les couches :

```text
React UI
  -> Electron handler
  -> Python bridge
  -> workflow
  -> business action
  -> atomic action
  -> selector/device
  -> database/events
```

Cette chaine doit etre verifiee dans le code avant de presenter une page comme
canonique.

## A Ne Plus Faire

- Ne plus lancer `npx docsify-cli serve docs --port 3000` depuis `bot/` comme
  documentation de reference.
- Ne plus presenter `bot/docs` comme "GitBook" ou doc transverse complete.
- Ne plus pointer vers `SUMMARY.md` : ce fichier a ete retire ; utiliser
  `_sidebar.md` et `taktik-docs` pour la navigation.
- Ne plus pointer vers des pages exclues ou supprimees comme
  `documentation-coverage-audit.md`, `product/feature-inventory.md` ou
  `api-reference/architecture.md` sans verifier leur statut dans `taktik-docs`.
- Ne plus ajouter de nouvelle spec produit dans `bot/docs` : la spec doit aller
  dans `taktik-docs`, puis le changelog Bot seulement si le code Bot change.
