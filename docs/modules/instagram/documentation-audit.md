# Audit documentation Instagram

Etat de couverture du dossier `bot/taktik/core/social_media/instagram/`.

## Couverture actuelle

| Dossier | Taille approx. | Page doc consolidee | Statut |
|---|---:|---|---|
| `actions/core/` | moyen | [Infrastructure & Actions Atomiques](atomic-actions.md) | Couvert |
| `actions/atomic/` | moyen | [Infrastructure & Actions Atomiques](atomic-actions.md) | Couvert |
| `actions/compatibility/` | petit | [Infrastructure & Actions Atomiques](atomic-actions.md) | Couvert |
| `actions/business/` | gros | [Actions Business](business-actions.md) | Couvert, mais a maintenir avec les nouveaux workflows |
| `auth/` | moyen | [Authentification](auth.md) | Couvert |
| `ui/selectors/` | gros | [UI — Sélecteurs, Extractors, Détecteurs](selectors.md) | Couvert |
| `ui/extractors.py` | moyen | [UI — Sélecteurs, Extractors, Détecteurs](selectors.md) | Couvert |
| `ui/language.py` | petit | [UI — Sélecteurs, Extractors, Détecteurs](selectors.md) | Couvert |
| `ui/watchdog.py` | petit | [UI — Sélecteurs, Extractors, Détecteurs](selectors.md) | Couvert |
| `ui/detectors/` | petit | [UI — Sélecteurs, Extractors, Détecteurs](selectors.md) | Couvert |
| `actions/business/management/filtering.py` | moyen | [Filtrage des profils](filtering.md) | Couvert |
| `workflows/core/` | moyen | [Workflows haut niveau](workflows.md) | Couvert |
| `workflows/management/` | gros | [Workflows haut niveau](workflows.md) | Couvert en synthese |
| `workflows/scraping/` | gros | [Scraping & qualification](scraping-workflows.md) | Couvert |
| `workflows/post_scraping/` | moyen | [Scraping & qualification](scraping-workflows.md) | Couvert |
| `workflows/cold_dm/` | petit | [Workflows haut niveau](workflows.md) | Couvert en synthese |
| `workflows/common/` | petit | [Workflows haut niveau](workflows.md) | Couvert |
| `workflows/helpers/` | petit | [Workflows haut niveau](workflows.md) | Couvert |
| `core/manager.py` | petit | [Vue d'ensemble Instagram](overview.md) | Couvert en synthese |
| `models/` | petit | [Vue d'ensemble Instagram](overview.md) | Couvert en synthese |
| `utils/` | petit | [Vue d'ensemble Instagram](overview.md) | Couvert en synthese |
| `test/` | petit | [Tests Instagram](tests.md) | Couvert |

## Couverture Complémentaire

| Sujet | Page |
|---|---|
| Bridges Instagram détaillés | [Bridges Instagram](../../bridges/instagram.md), [Platform Bridge Handlers](../../desktop/platform-bridge-handlers.md) |
| Database locale liée à Instagram | [Schéma SQLite](../../database/schema.md), [Base SQLite Electron](../../desktop/database.md), [SQLite Repositories Electron](../../desktop/electron-database-repositories.md) |
| Smart Comment | [Actions Business](business-actions.md), [Platform Bridge Handlers](../../desktop/platform-bridge-handlers.md), [SQLite Repositories Electron](../../desktop/electron-database-repositories.md) |
| DM workflows | [Workflows haut niveau](workflows.md), [Workflows Instagram](../../workflows/instagram.md) |
| Content/upload | [Upload Content](../../workflows/upload-content.md), [Features par plateforme](../../desktop/platform-features.md) |
| Sequence diagrams | [Diagrammes de flux](../../workflows/flow-diagrams.md), [Scraping & qualification](scraping-workflows.md) |

## Etat

Le module Instagram est maintenant couvert par domaine : actions, business workflows, UI/selectors, auth, scraping/qualification, bridges, upload/content, persistence et tests device. Les futures mises à jour doivent surtout maintenir les pages existantes quand un nouveau bridge, workflow ou handler est ajouté.
