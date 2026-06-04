# Bridge Gmail

Le bridge Gmail actif est `gmail_account_bridge`. Il pointe vers :

```text
bot/bridges/gmail/account/account.py
```

Source verifiee : `bot/bridges/bridges.manifest.json`.

## Lancement

```powershell
python bot/bridges/launcher.py gmail_account_bridge <config.json>
```

En production :

```powershell
taktik_launcher.exe gmail_account_bridge <config.json>
```

## Role

| Zone | Description |
|---|---|
| Login/logout/register | Route les workflows Gmail account. |
| Scan OTP | Lit les codes OTP utiles aux workflows compte. |
| Persistence | Persiste les comptes via la couche database Python dediee. |
| IPC | Emet `account_result` et les logs/status attendus par Electron. |

Le module runtime est organise sous `bot/bridges/gmail/account/runtime/**`.
Ne pas documenter l'ancien chemin plat Gmail comme fichier actif.
