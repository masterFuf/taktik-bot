# Proposition - Taxonomie cible `social_media/instagram/ui/selectors`

## Probleme actuel

Etat 2026-05-30 :

- `shell/` est maintenant introduit et possede deja `auth.py`, `popups.py`, `text_input.py`, `screen_state.py` et `blocking_states.py`.
- `shell/` possede aussi maintenant `navigation.py`.
- `surfaces/` est maintenant introduit et possede deja `feed.py`, `hashtag.py`, `notifications.py`, `direct_messages.py`, `story_viewer.py`, `content_creation.py` et `followers_following.py`.
- `surfaces/` possede aussi maintenant `profile.py`.
- `surfaces/post/` est maintenant introduit avec `detail.py` comme owner transitoire du legacy `post.py`.
- `surfaces/post/` expose maintenant aussi plusieurs catalogues publics specialises : `POST_DETAIL_SELECTORS`, `POST_COMMENTS_SELECTORS`, `POST_LIKERS_SELECTORS`, `POST_SHARE_SHEET_SELECTORS`, `POST_GRID_SELECTORS`, `POST_REELS_SELECTORS`.
- `support/` est maintenant introduit et possede deja `debug.py` et `scroll.py`.
- `flows/` est maintenant introduit et possede deja `unfollow.py`.
- les anciens chemins top-level (`auth.py`, `popup.py`, `text_input.py`, `detection.py`, `problematic_page.py`) restent volontairement des shims de compatibilite.
- l'ancien chemin top-level `navigation.py` reste lui aussi un shim de compatibilite.
- les anciens chemins top-level des petites surfaces (`feed.py`, `hashtag.py`, `notification.py`, `dm.py`, `story.py`, `content.py`, `followers_list.py`) restent eux aussi des shims de compatibilite.
- l'ancien chemin top-level `profile.py` reste lui aussi un shim de compatibilite.
- l'ancien chemin top-level `post.py` reste lui aussi un shim de compatibilite.
- les anciens chemins top-level `debug.py`, `scroll.py` et `unfollow.py` restent eux aussi des shims de compatibilite.

Le dossier actuel :

```text
ui/selectors/
  auth.py
  content.py
  debug.py
  detection.py
  dm.py
  feed.py
  followers_list.py
  hashtag.py
  navigation.py
  notification.py
  popup.py
  post.py
  problematic_page.py
  profile.py
  scroll.py
  story.py
  text_input.py
  unfollow.py
```

est deja mieux qu'un seul gros fichier, mais il reste melange sur deux axes :

1. certains fichiers sont classes par **surface ecran**
2. d'autres par **fonction technique**
3. d'autres encore par **workflow**

Exemples :

- `feed.py`, `profile.py`, `hashtag.py` sont des surfaces
- `navigation.py`, `popup.py`, `text_input.py`, `detection.py` sont transverses
- `unfollow.py` est plutot un flux metier
- `post.py` devient un "gros tiroir" pour like, comments, share sheet, likers popup, reel hints, etc.

## Regle cible

Un selector doit d'abord etre classe par **perimetre UI reel** :

- shell / app chrome
- page / surface
- flow specialise
- composant transversal

Le developpeur doit pouvoir repondre vite a :

- "sur quel ecran suis-je ?"
- "dans quel flow UI suis-je ?"
- "si je cherche le like button, dans quelle surface il vit ?"

## Recommandation

Je recommande cette cible :

```text
social_media/instagram/ui/
  selectors/
    shell/
      auth.py
      navigation.py
      popups.py
      text_input.py
      blocking_states.py
      screen_state.py

    surfaces/
      feed.py
      profile.py
      hashtag.py
      notifications.py
      direct_messages.py
      followers_following.py
      story_viewer.py
      content_creation.py

      post/
        detail.py
        comments.py
        likers.py
        share_sheet.py
        grid.py
        reels.py

    flows/
      unfollow.py

    support/
      debug.py
      scroll.py

    __init__.py
```

## Mapping propose fichier par fichier

### `shell/`

Regroupe tout ce qui concerne l'armature globale de l'app.

- `auth.py` -> `shell/auth.py`
- `navigation.py` -> `shell/navigation.py`
- `popup.py` -> `shell/popups.py`
- `text_input.py` -> `shell/text_input.py`
- `problematic_page.py` -> `shell/blocking_states.py`
- `detection.py` -> `shell/screen_state.py`

Raison :

- ce ne sont pas des pages metier ; ce sont des etats ou controles globaux

### `surfaces/`

Regroupe ce qui appartient a un ecran ou une famille d'ecrans claire.

- `feed.py` -> `surfaces/feed.py`
- `profile.py` -> `surfaces/profile.py`
- `hashtag.py` -> `surfaces/hashtag.py`
- `notification.py` -> `surfaces/notifications.py`
- `dm.py` -> `surfaces/direct_messages.py`
- `followers_list.py` -> `surfaces/followers_following.py`
- `story.py` -> `surfaces/story_viewer.py`
- `content.py` -> `surfaces/content_creation.py`

### `surfaces/post/`

`post.py` est le meilleur candidat a un split par sous-perimetre.

Je recommande :

- `post.py` -> `surfaces/post/detail.py`
- commentaires / replies / sorting -> `surfaces/post/comments.py`
- likers popup -> `surfaces/post/likers.py`
- share sheet / copy link -> `surfaces/post/share_sheet.py`
- grid / first post / post cards -> `surfaces/post/grid.py`
- reel-specific hints -> `surfaces/post/reels.py`

Raison :

- "les selectors pour liker" ne devraient plus etre cherches dans un gros `post.py`
- ils vivraient dans `surfaces/post/detail.py`

### `flows/`

Pour les selectors lies a un flux metier specialise plus qu'a une page reusable.

- `unfollow.py` -> `flows/unfollow.py`

### `support/`

Pour ce qui aide les outils ou heuristiques mais n'est ni une vraie surface ni un shell.

- `debug.py` -> `support/debug.py`
- `scroll.py` -> `support/scroll.py`

## Exemple concret

Si demain on cherche :

- les selectors de like sur un post -> `ui/selectors/surfaces/post/detail.py`
- les selectors de la liste followers/following -> `ui/selectors/surfaces/followers_following.py`
- les popups generiques -> `ui/selectors/shell/popups.py`
- les ecrans bloquants / challenge / wrong page -> `ui/selectors/shell/blocking_states.py`

## Regles de split

### Quand un fichier doit etre split

- il depasse largement un seul perimetre ecran
- il contient a la fois detail post, comments, share, popup, reel, grid
- il devient difficile de predire ou chercher un selector

### Quand il doit rester unique

- le perimetre ecran reste coherent
- les selectors sont relus ensemble naturellement

## Strategie de migration recommandee

Pas de big-bang.

### Lot S1 - introduire les sous-dossiers + re-exports

- creer `shell/`, `surfaces/`, `flows/`, `support/`
- garder `ui/selectors/__init__.py` comme facade publique
- fait pour `shell/`, `surfaces/`, `flows/`, `support/`

### Lot S2 - deplacer les petits fichiers faciles

- `auth`, `popup`, `text_input`, `feed`, `hashtag`, `notification`, `dm`, `story`
- fait pour `feed`, `hashtag`, `notification`, `dm`, `story`, `content`, `followers_list`
- termine aussi `debug`, `scroll` et `unfollow`

### Lot S3 - traiter les gros fichiers

- split `post.py`
- split `profile.py` seulement si necessaire
- split `navigation.py` seulement si le contenu melange shell/tab/search/result list
- `navigation.py` n'a finalement pas eu besoin de split interne : il a simplement bascule sous `shell/navigation.py`
- `profile.py` n'a pas eu besoin de split non plus a ce stade : il a simplement bascule sous `surfaces/profile.py`
- `post.py` n'est pas encore split finement, mais il a deja quitte la racine au profit de `surfaces/post/detail.py`, ce qui clarifie au moins son owner de surface avant le vrai decoupage interne.
- premier pas concret du split fin : les call sites peuvent maintenant cibler des catalogues specialises, sans attendre la disparition immediate de `POST_SELECTORS`.

## Detail important sur `profile.py` et `navigation.py`

Je ne recommande **pas** de les exploser tout de suite sans audit fin.

### `profile.py`

Peut probablement rester unique si le contenu reste centré sur :

- header profil
- counters
- bio
- website
- about account
- follow/message buttons

### `navigation.py`

Peut etre split plus tard si on voit au moins 2 scopes differents :

- tab bar / back / home
- search navigation / search results

## Recommandation pratique

Je recommande de commencer par :

1. documenter cette taxonomie
2. deplacer les fichiers a scope evident
3. garder `__init__.py` en facade de compat
4. traiter `post.py` en premier gros split

Le premier lot rentable ici n'est pas de tout bouger.
Le premier lot rentable est de faire en sorte que :

- un developpeur sache **ou chercher**
- un nouveau selector ait **une place evidente**
