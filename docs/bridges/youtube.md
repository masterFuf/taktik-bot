# Bridges YouTube

| Bridge name | Module actuel | Usage |
|---|---|---|
| `youtube_account_bridge` | `bot/bridges/youtube/account/account.py` | Compte Google/YouTube. |
| `youtube_upload_bridge` | `bot/bridges/youtube/publish/upload.py` | Upload video/Short. |
| `youtube_action_test_bridge` | `bot/bridges/youtube/diagnostics/action_test.py` | Tests selectors/actions. |

## Lancement

```powershell
python bot/bridges/launcher.py youtube_upload_bridge <config.json>
python bot/bridges/launcher.py youtube_account_bridge <config.json>
python bot/bridges/launcher.py youtube_action_test_bridge <config.json>
```

Les flux actifs passent par les modules ci-dessus. Si une page mentionne les
anciens fichiers plats de bridge YouTube comme chemins actifs, elle est
obsolete.

Le dispatcher legacy `bot/bridges/youtube/workflows/dispatcher.py` contient
encore les valeurs `watch_feed` et `search`, mais ces deux branches renvoient
"not yet implemented". Elles ne sont pas des capacites actives.

## IPC

| Bridge | Evenements principaux |
|---|---|
| `youtube_upload_bridge` | `upload_result`, logs/status upload. |
| `youtube_account_bridge` | Resultats compte et preparation Google. |
| `youtube_action_test_bridge` | Resultats de diagnostic action/selecteur. |
