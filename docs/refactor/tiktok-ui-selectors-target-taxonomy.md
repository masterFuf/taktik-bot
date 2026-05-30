# Proposition - Taxonomie cible `social_media/tiktok/ui/selectors`

## Probleme actuel

Le dossier actuel :

```text
ui/selectors/
  auth.py
  comment.py
  conversation.py
  detection.py
  followers.py
  inbox.py
  navigation.py
  popup.py
  profile.py
  publish.py
  scroll.py
  search.py
  video.py
```

melange encore :

- des surfaces metier (`video`, `profile`, `search`, `inbox`, `conversation`, `followers`)
- des etats globaux d'app (`navigation`, `popup`, `detection`)
- des flows lourds (`publish`, une partie de `auth`)
- du support transversal (`scroll`)

Les deux plus gros sujets a traiter apres les petits lots evidents sont :

- `auth.py` : login + signup + country picker + logout dans le meme fichier ;
- `publish.py` : un monolithe workflow qui merite sa propre famille `flows/publish/*`.

## Regle cible

Comme pour Instagram, un selector TikTok doit d'abord etre classe par perimetre UI reel :

- `shell/` pour l'app chrome, les modales globales et la detection d'etat ;
- `surfaces/` pour les ecrans metier ;
- `flows/` pour les workflows lourds ;
- `support/` pour les aides transverses comme le scroll.

## Recommandation

```text
social_media/tiktok/ui/
  selectors/
    shell/
      auth/
        login.py
        signup.py
        country_picker.py
        logout.py
      navigation.py
      popups.py
      screen_state.py

    surfaces/
      video/
        detail.py
        comments.py
        engagement.py
        creator.py
        media.py
        state.py
      profile.py
      search.py
      inbox.py
      conversation.py
      followers.py

    flows/
      publish/
        creation_entry.py
        media_picker.py
        editor.py
        composer.py
        progress.py

    support/
      scroll.py

    __init__.py
```

## Etat 2026-05-30

- `shell/` est maintenant introduit et possede deja `navigation.py`, `popups.py` et `screen_state.py`.
- `shell/auth/` est maintenant un vrai package et possede `login.py`, `signup.py`, `country_picker.py`, `logout.py`.
- `support/` est maintenant introduit et possede deja `scroll.py`.
- `surfaces/` est maintenant introduit et possede deja `profile.py`, `search.py`, `inbox.py`, `conversation.py` et `followers.py`.
- `surfaces/video/` est maintenant introduit avec `detail.py`, `comments.py`, `creator.py`, `engagement.py`, `media.py` et `state.py`.
- `flows/publish/` est maintenant un vrai package et possede `creation_entry.py`, `media_picker.py`, `editor.py`, `composer.py`, `progress.py`.
- les anciens chemins top-level correspondants restent volontairement des shims de compatibilite.
- `video/detail.py` est maintenant une facade d'agregation legacy au-dessus de catalogues specialises (`creator`, `engagement`, `media`, `state`).
- `publish/` n'est plus un monolithe : `PUBLISH_SELECTORS` est maintenant une facade d'agregation au-dessus de catalogues specialises par etape.
- les services/runtime TikTok `publish` pointent maintenant vers `ui/selectors/flows/publish/*` directement ; le shim top-level `publish.py` reste pour la compatibilite.

## Strategie de migration

### Lot T1 - shell/support evidents

- introduire `shell/` et `support/`
- deplacer `navigation`, `popup`, `detection`, `scroll`
- garder `__init__.py` et les fichiers top-level comme facades de compat

### Lot T2 - petites surfaces evidentes

- `search`, `inbox`, `conversation`, `followers`, `profile`
- fait

### Lot T3 - gros blocs

- eclater `auth.py` par flow
- sortir `publish.py` vers `flows/publish/*`
- introduire plusieurs catalogues publics specialises pour `video.py`

### Lot T2b - surface video

- `video.py` -> `surfaces/video/detail.py`
- `comment.py` -> `surfaces/video/comments.py`
- exposition de `VIDEO_DETAIL_SELECTORS` et `VIDEO_COMMENTS_SELECTORS`

### Lot T2c - shell auth

- `auth.py` -> `shell/auth/`
- split reel en `login.py`, `signup.py`, `country_picker.py`, `logout.py`
- conservation du shim top-level `auth.py`

### Lot T2d - publish owner

- `publish.py` -> `flows/publish/`
- split reel en `creation_entry.py`, `media_picker.py`, `editor.py`, `composer.py`, `progress.py`
- conservation du shim top-level `publish.py`

### Lot T2e - video catalogs specialises

- `surfaces/video/detail.py` devient une facade legacy
- les owners reels vivent maintenant dans `creator.py`, `engagement.py`, `media.py`, `state.py`
- exposition publique de `VIDEO_CREATOR_SELECTORS`, `VIDEO_ENGAGEMENT_SELECTORS`, `VIDEO_MEDIA_SELECTORS`, `VIDEO_STATE_SELECTORS`

## Point important

Le chantier TikTok doit reprendre les memes principes qu'Instagram, sans copier aveuglement ses noms :

- TikTok est video-first, donc `video/` est la surface prioritaire
- `publish/` est un vrai flow lourd, pas juste une surface
- `auth.py` concentre deja plusieurs owners qui meritent des catalogues publics distincts
