# Bridge Threads

Threads utilise un dispatcher unique :

| Bridge name | Module actuel |
|---|---|
| `threads_bridge` | `bot/bridges/threads/workflows/dispatcher.py` |

## Lancement

```powershell
python bot/bridges/launcher.py threads_bridge <config.json>
```

Le dispatcher lit `workflowType` et route vers les workflows Threads supportes.
Les helpers runtime vivent dans `bot/bridges/threads/workflows/runtime/**`.

Ne pas documenter l'ancien fichier plat Threads comme chemin actif : le contrat
actuel est le bridge name `threads_bridge` plus le module dispatcher.
