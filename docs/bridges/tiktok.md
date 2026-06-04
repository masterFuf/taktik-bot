# Bridges TikTok

Cette page reflete le manifest actif.

| Bridge name | Module actuel | Usage |
|---|---|---|
| `tiktok_bridge` | `bot/bridges/tiktok/workflows/dispatcher.py` | Dispatcher automation : feed, search/hashtag, target/followers, DM read/send. |
| `tiktok_unfollow_bridge` | `bot/bridges/tiktok/automation/unfollow.py` | Unfollow. |
| `dm_outreach_bridge` | `bot/bridges/tiktok/engagement/dm_outreach.py` | Outreach DM TikTok. |
| `tiktok_scraping_bridge` | `bot/bridges/tiktok/scraping/scraping.py` | Scraping TikTok. |
| `tiktok_account_bridge` | `bot/bridges/tiktok/account/account.py` | Login/logout/register compte. |
| `tiktok_publish_bridge` | `bot/bridges/tiktok/publish/publish.py` | Publish/upload. |

## Lancement

```powershell
python bot/bridges/launcher.py tiktok_bridge <config.json>
python bot/bridges/launcher.py tiktok_publish_bridge <config.json>
python bot/bridges/launcher.py tiktok_scraping_bridge <config.json>
```

## Notes

- `tiktok_bridge` lit `workflowType` et route vers
  `bot/bridges/tiktok/workflows/**`.
- `tiktok_publish_bridge` utilise le workflow publish TikTok.
- `tiktok_scraping_bridge` est le chemin scraping dedie.
- Ne pas documenter les anciens fichiers plats TikTok comme chemins actifs.
