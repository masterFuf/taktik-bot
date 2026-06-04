# Bridges Instagram

Cette page documente les bridges Instagram actifs selon
`bot/bridges/bridges.manifest.json` et `bot/bridges/launcher.py`.

Le contrat Electron/Python est le **bridge name**. Le chemin fichier indique le
module actuel, pas un ancien fichier plat `*_bridge.py`.

| Bridge name | Module actuel | Handler Electron |
|---|---|---|
| `desktop_bridge` | `bot/bridges/instagram/automation/desktop.py` | `handlers/instagram/automation/bot.ts` |
| `account_bridge` | `bot/bridges/instagram/account/account.py` | `handlers/instagram/account/account.ts` |
| `scraping_bridge` | `bot/bridges/instagram/scraping/scraping.py` | `handlers/instagram/scraping/scraping.ts` |
| `dm_bridge` | `bot/bridges/instagram/engagement/dm.py` | `handlers/instagram/engagement/dm.ts` |
| `cold_dm_bridge` | `bot/bridges/instagram/engagement/cold_dm.py` | `handlers/instagram/engagement/coldDm.ts` |
| `smart_comment_bridge` | `bot/bridges/instagram/engagement/smart_comment.py` | `handlers/instagram/engagement/smart-comment.ts` |
| `taktik_agent_bridge` | `bot/bridges/instagram/agent/taktik_agent.py` | `handlers/instagram/agent/taktikAgent.ts` |
| `persona_analysis_bridge` | `bot/bridges/instagram/analysis/persona.py` | `handlers/instagram/agent/personaAnalysis.ts` |
| `publish_bridge` | `bot/bridges/instagram/publish/publish.py` | Instagram publish runtime |

## Lancement

```powershell
python bot/bridges/launcher.py desktop_bridge <config.json>
python bot/bridges/launcher.py scraping_bridge <config.json>
python bot/bridges/launcher.py dm_bridge <args-or-config>
```

En production, Electron utilise `taktik_launcher.exe <bridge_name> ...`.

## Responsabilites

| Bridge | Responsabilite |
|---|---|
| `desktop_bridge` | Workflows d'automatisation classiques : target, hashtag, feed, unfollow. |
| `scraping_bridge` | Scraping target/hashtag/post et qualification liee au scraping. |
| `dm_bridge` | Lecture inbox, envoi DM et auto-reply. |
| `cold_dm_bridge` | Outreach Cold DM, generation IA optionnelle, dedup. |
| `smart_comment_bridge` | Scraping de commentaires et reponse intelligente. |
| `account_bridge` | Login/logout/register et inspection compte. |
| `taktik_agent_bridge` | Execution de Taktik Agent cote bot. |
| `persona_analysis_bridge` | Collecte profil/persona pour contexte IA. |
| `publish_bridge` | Entree publish Instagram cote bot, quand utilisee. |

## Regles

- Ne pas recreer les anciens fichiers plats Instagram comme chemins actifs.
- Ajouter ou renommer un bridge impose de mettre a jour `bridges.manifest.json`,
  `launcher.py`, `front/electron/utils/paths.ts`, cette page et les checks.
- Les logs humains vont sur stderr ; stdout reste reserve aux JSON lines.
