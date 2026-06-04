# Glossaire & conventions

Cette page définit les mots utilisés dans la documentation TAKTIK Bot.

Elle évite les ambiguïtés entre les couches : bridge, workflow, action business, action atomique, sélecteur, repository, session, etc.

## Concepts principaux

| Terme | Définition |
|---|---|
| App Electron | Interface desktop utilisateur, située dans `front/` |
| Handler Electron | Code TypeScript qui reçoit une action UI, crée une config JSON et lance un bridge Python |
| Bridge | Script Python lancé en sous-processus par Electron |
| IPC | Communication JSON entre Electron et Python, principalement via stdout/stdin |
| Common services | Services partagés des bridges : bootstrap, connexion device, IPC, clavier, app manager |
| Module social | Dossier métier par plateforme : Instagram, TikTok, Threads, YouTube |
| Workflow applicatif | Tâche complète lancée par un bridge : scraping, publish, auto-reply |
| Workflow business | Stratégie métier réutilisable : followers, hashtag, feed, unfollow |
| Action business | Opération composée : liker des posts, commenter, extraire un profil, filtrer |
| Action atomique | Opération UI bas niveau : clic, scroll, détection, saisie texte, navigation |
| Sélecteur UI | Resource-id, XPath, content-desc ou texte utilisé pour trouver un élément Android |
| Extractor | Code qui lit une donnée depuis l'UI : username, bio, compteur, likes |
| Detector | Code qui répond à une question d'état : écran ouvert, popup visible, fin de scroll |
| Repository | Classe d'accès à la base SQLite |
| Session | Exécution d'un workflow avec limites, stats, dates, statut |
| Limites de session | Limites locales de durée, profils et actions configurées pour une exécution de workflow |
| Quota | Ancien terme historique. Le système actif ne consomme plus de quota d'action distant ; il reste des limites locales de session et des limites licence/devices |

## Couches d'exécution

```text
Electron UI
  -> Handler Electron
  -> Bridge Python
  -> Workflow applicatif
  -> Workflow business
  -> Action business
  -> Action atomique
  -> DeviceFacade / uiautomator2
  -> Application Android
```

Toutes les fonctionnalités ne passent pas par toutes les couches. Exemple :

- Threads n'a pas encore de couche `actions/atomic/` complète ;
- certains bridges autonomes appellent directement un workflow applicatif ;
- certains workflows Instagram passent par `ModernInstagramActions`, d'autres instancient directement des actions.

## Conventions de nommage

| Zone | Convention |
|---|---|
| Python | `snake_case` |
| TypeScript / Electron | `camelCase` |
| Tables SQLite | `snake_case` |
| Events IPC | `snake_case` |
| Classes Python | `PascalCase` |
| Fichiers docs | `kebab-case.md` quand possible |

## Configs

La plupart des configs naissent côté Electron en `camelCase`, puis sont converties côté bridge.

Exemple :

| Electron | Python |
|---|---|
| `deviceId` | `device_id` |
| `maxProfiles` | `max_profiles` |
| `workflowType` | `workflow_type` |
| `sessionDurationMinutes` | `session_duration_minutes` |
| `saveToDb` | `save_to_db` |

## Events IPC

Les messages IPC sont des objets JSON écrits sur stdout.

Exemples fréquents :

| Event | Usage |
|---|---|
| `status` | État global du bridge |
| `log` | Log affiché dans Electron |
| `profile_captured` | Profil scrapé en temps réel |
| `ai_profile_analyzing` | Début d'analyse IA |
| `ai_profile_analyzed` | Résultat IA |
| `threads_stats` | Stats workflow Threads |
| `sync_step` | Avancement sync followers/following |
| `sync_complete` | Fin de synchronisation |
| `account_result` | Résultat login/register/logout |

## Termes Instagram

| Terme | Définition |
|---|---|
| `ModernInstagramActions` | Façade qui regroupe les actions business Instagram modernes |
| `BaseAction` | Base des actions atomiques Instagram |
| `BaseBusinessAction` | Base des workflows/actions business Instagram |
| `ProfileBusiness` | Extraction et persistance des profils Instagram |
| `FilteringBusiness` | Filtrage configurable des profils |
| `ScrapingWorkflow` | Scraping générique targets/hashtags/posts |
| Discovery legacy | Ancien workflow dedie supprime. La prospection avancee passe par scraping avance, post scraping et qualification IA. |
| `WorkflowRunner` | Dispatch des steps de config d'une session Instagram |

## États de documentation

| Statut | Signification |
|---|---|
| Couvert | La page décrit la structure, les flux, configs et interactions principales |
| Couvert en synthèse | La page explique le rôle, mais pas chaque méthode en détail |
| À approfondir | Le code existe mais la doc manque de détails |
| À documenter | La zone n'a pas encore de page dédiée fiable |
| Legacy | Toujours présent pour compatibilité, mais pas le chemin recommandé |
| Stub | Interface prévue mais pas encore implémentée |

## Règle importante

Quand la documentation et le code divergent, le code gagne.

La bonne méthode est :

1. inspecter l'arborescence réelle ;
2. lire les exports `__init__.py` ;
3. lire les bridges qui appellent le module ;
4. lire les workflows ;
5. mettre à jour la page de documentation consolidee ;
6. mettre à jour `SUMMARY.md` et `_sidebar.md`.
