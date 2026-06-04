# TikTok - Debug et compatibilite

## Outils utiles

| Outil | Usage |
|---|---|
| Debug panel | Screenshots, UI dumps, tests, mirror debug. |
| Mirror embedded | Observer les workflows dans le workspace. |
| Mirror debug | Isoler scrcpy/ADB. |
| Compat selectors | Verifier selectors apres update TikTok. |
| Logs bridge | Voir stages et erreurs. |
| Live Center | Etat multi-device et publish payload. |

## Artefacts

```text
<temp>\taktik_debug\
```

Conserver :

- screenshot ;
- UI dump XML ;
- logs ;
- version TikTok ;
- langue detectee ;
- serial device ;
- stage workflow.

## Diagnostic publish

| Symptome | Verification |
|---|---|
| Home non detecte | selectors navigation + screenshot. |
| Gallery non ouverte | create/upload selectors. |
| Description screen absent | dump apres selection media. |
| Caption non saisie | Taktik Keyboard + field selector. |
| Upload inconnu | chercher pourcentage/progress UI. |
| Success faux positif | verifier stabilisation post-publish. |

## Scrcpy / mirror

Si le mirror debug fonctionne mais le panneau embarque echoue, le probleme est probablement dans le chemin embedded : arguments, server jar, websocket, runtime ADB, cleanup ou session mirror. On garde le controle/touch/keyboard, on corrige le chemin qui echoue.

## Compat

Compat TikTok doit couvrir :

- version TikTok cible ;
- langue FR/EN ;
- home/create/gallery/publish ;
- popups contacts/consent ;
- feed/video ;
- DM/inbox ;
- profile/search/followers.
