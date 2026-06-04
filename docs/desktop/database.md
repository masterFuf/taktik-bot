# Base SQLite cote Electron `[Front]`

Cette page documente l'ouverture et l'usage de la base locale par
`front/electron`. Pour l'ownership table par table, voir
`technical/database-ownership.md`.

## Role

La base desktop est `taktik-data.db` dans le dossier `userData` Electron. Elle
est partagee par Electron et le Bot Python via `TAKTIK_DB_PATH`.

```text
Electron main
  -> DatabaseService.initialize()
  -> DatabaseConnection.open()
  -> createTables(schema.ts / schema.sql)
  -> runMigrations(migrations.ts)
  -> RepositoryContainer
  -> services owners
```

## Fichiers verifies

| Fichier | Role |
|---|---|
| `front/electron/database/connection.ts` | Ouvre `better-sqlite3`, configure WAL et foreign keys. |
| `front/electron/database/schema.ts` | Cree les tables depuis `schema.sql` ou fallback inline. |
| `front/electron/database/schema.sql` | Schema SQL source quand disponible. |
| `front/electron/database/migrations.ts` | Migrations defensives locales. |
| `front/electron/database/database-service.ts` | Facade historique encore utilisee par certains services. |
| `front/electron/database/repositories/index.ts` | Container de repositories. |
| `front/electron/database/models/**` | Types et modeles DB centralises. |

## Repositories principaux

| Zone | Repositories |
|---|---|
| Instagram | accounts, profiles, profile geo, interactions, sessions, scraped profiles, stats, smart comment, graph, following sync |
| TikTok | compte, profil, interaction, scraping, session, stats, repository facade TikTok |
| App | scheduler, taxonomy, target intelligence, device groups, network pools/history, Gmail, media cache, Turso sync, agent context, database explorer |

`DiscoveryRepository` n'existe plus dans l'etat actuel. La prospection avancee
Instagram est rattachee au scraping avance et a la qualification.

## Services et handlers

Les handlers IPC doivent appeler un service owner ou une facade existante. Ils
ne doivent pas contenir de SQL direct.

| Couche | Exemple |
|---|---|
| Handler | `front/electron/handlers/**` |
| Service owner | `front/electron/services/app/**`, `services/platforms/**`, `services/tools/**` |
| Repository | `front/electron/database/repositories/**` |

## Ownership avec le Bot

Electron et Python peuvent lire/ecrire la meme base. La regle n'est pas
"tout le monde ecrit tout", mais "chaque table a un owner explicite".

| Producteur | Ecritures typiques |
|---|---|
| Electron | UI-only, scheduler, templates, device groups, settings, certains cleanups. |
| Bot Python | Sessions runtime, interactions, profils captures, scraping, stats workflow. |
| Partage | Tables necessaires aux deux cotes, documentees dans `technical/database-ownership.md`. |

## Points sensibles

| Sujet | Regle |
|---|---|
| `schema.sql` vs fallback inline | Les deux doivent rester compatibles. |
| Migrations | Idempotentes et testees au demarrage. |
| Types | Centralises dans `database/models/**` ou `src/app/types/**`. |
| Logs | Pas de pollution stdout qui pourrait casser les bridges JSON. |
| Discovery legacy | Ne pas le reintroduire sous forme de repository/service/campaign. |

## Pages liees

- `bot/desktop/electron-database-repositories.md`
- `technical/database-ownership.md`
- `front/docs/business-logic/database-layer.md`
- `front/docs/database/SCHEMA.md`
