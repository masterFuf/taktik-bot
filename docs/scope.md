# Perimetre du guide

> **Perimetre : `[Transversal]`**
> Cette page definit les badges utilises dans la documentation.

La doc privee canonique est servie depuis `taktik-docs`, mais elle couvre le
monorepo quand une feature traverse plusieurs projets.

## Badges

| Badge | Projet | Code concerne | Ce que la page documente |
|---|---|---|---|
| `[Bot]` | Bot Python | `bot/` | bridges, workflows, actions, selectors, database locale cote Python |
| `[Front]` | App desktop | `front/` | Electron main, React renderer, handlers IPC, scheduler UI, database Electron |
| `[API]` | API distante | `taktik-api/` | FastAPI, JWT, licences, devices, updates, APKs, crash reports |
| `[Web]` | Site commercial | `taktik-bot/` | Next.js, Prisma, Stripe, dashboard, support, MySQL source |
| `[Transversal]` | Plusieurs projets | multi-dossiers | flux de bout en bout, architecture, bridges, sync, DB |
| `[Produit]` | Abstraction produit | docs derivees | inventaire fonctionnel, extraction marketing, cas d'usage |

## Pourquoi un seul guide transverse

Certaines fonctionnalites ne peuvent pas etre comprises en regardant seulement un dossier.

Exemple : une session Instagram planifiee traverse :

```text
front/src/features/workspace/scheduler
  -> front/electron/handlers/scheduler
  -> front/electron/services/app/scheduler
  -> front/electron/handlers/instagram
  -> bot/bridges/instagram
  -> bot/taktik/core/social_media/instagram/workflows
  -> bot/taktik/core/database/local
  -> Android / Instagram
```

Si on documente uniquement le bot Python, on perd l'origine des configs. Si on documente uniquement le front, on perd la logique d'execution.

## Regle de proprietaire

| Type de changement | Page a lire en premier |
|---|---|
| Python automation | pages `[Bot]` |
| UI/handler Electron | pages `[Front]` |
| Licence/device/update | pages `[API]` |
| Stripe/Prisma/dashboard | pages `[Web]` |
| Feature complete | pages `[Transversal]` |
| Fonctionnalite commerciale | pages `[Produit]` |

## Convention pour les nouvelles pages

Chaque nouvelle page doit commencer par un badge :

```md
> **Perimetre : `[Bot]`**
> Cette page documente uniquement le code Python du dossier `bot/...`.
```

ou :

```md
> **Perimetre : `[Transversal]`**
> Cette page suit le flow complet entre React, Electron, Python, SQLite et Android.
```

## A eviter

| A eviter | Pourquoi |
|---|---|
| Mettre une page Front dans une section Bot sans badge | brouille le proprietaire du code |
| Documenter un flow complet comme s'il appartenait seulement au bot | les configs/events viennent souvent d'Electron |
| Dupliquer un schema dans deux pages | preferer une page transverse et des liens |
| Oublier `SUMMARY.md` et `_sidebar.md` | la navigation devient vite difficile |
| Promettre une feature produit non implementee | l'inventaire marketing doit rester lie au code reel |
