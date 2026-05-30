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
        share_sheet.py
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
- `support/` est maintenant introduit et possede deja `scroll.py`.
- `surfaces/` est maintenant introduit et possede deja `profile.py`, `search.py`, `inbox.py`, `conversation.py` et `followers.py`.
- les anciens chemins top-level correspondants restent volontairement des shims de compatibilite.
- `auth.py`, `video.py` et `publish.py` restent les trois gros prochains sujets a auditer avant move.

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

## Point important

Le chantier TikTok doit reprendre les memes principes qu'Instagram, sans copier aveuglement ses noms :

- TikTok est video-first, donc `video/` est la surface prioritaire
- `publish/` est un vrai flow lourd, pas juste une surface
- `auth.py` concentre deja plusieurs owners qui meritent des catalogues publics distincts
