"""Les actions atomiques sont rangées PAR TYPE, comme celles d'Instagram.

Ce test existe parce que rien ne l'empêchait. Le dossier `atomic/` de TikTok avait fini avec
dix-sept modules à plat — `click_actions.py`, `dm_actions.py`, `sound_actions.py`… — pendant
qu'Instagram rangeait les siens en `detection/ interaction/ navigation/ scroll/ text/`. Un dossier
plat ne dit jamais où va le fichier suivant, alors il accueille tout, et six modules de plus y ont
atterri en une seule journée sans que personne ait à décider quoi que ce soit.

Ce que la structure veut dire, et c'est le seul critère :

    detection/    lit l'écran — état, extraction, collecte. Rien n'y agit.
    interaction/  agit sur le contenu — tap, like, commentaire, republication.
    navigation/   déplace d'un écran à l'autre.
    scroll/       le défilement.
    messaging/    la surface DM, seule à n'avoir aucun équivalent atomique Instagram.
"""

import pathlib

import pytest

_ATOMIC = (
    pathlib.Path(__file__).resolve().parents[4]
    / "taktik" / "core" / "social_media" / "tiktok" / "actions" / "atomic"
)
_INSTAGRAM_ATOMIC = (
    pathlib.Path(__file__).resolve().parents[4]
    / "taktik" / "core" / "social_media" / "instagram" / "actions" / "atomic"
)

EXPECTED_FOLDERS = {"detection", "interaction", "navigation", "scroll", "messaging"}


def _folders(path: pathlib.Path) -> set:
    return {d.name for d in path.iterdir() if d.is_dir() and d.name != "__pycache__"}


def test_no_atomic_module_sits_flat_in_the_folder():
    """Le garde qui compte. `__init__.py` est le seul fichier permis à la racine : c'est le
    barillet. Tout le reste doit avoir choisi une famille."""
    flat = sorted(
        f.name for f in _ATOMIC.iterdir()
        if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"
    )

    assert flat == [], (
        f"{len(flat)} module(s) à plat dans actions/atomic/ : {flat}. "
        "Ranger dans detection/ interaction/ navigation/ scroll/ messaging/ selon ce que le "
        "module FAIT — c'est le modèle Instagram, et un dossier plat finit par tout accueillir."
    )


def test_the_folders_are_the_ones_the_barrel_names():
    assert _folders(_ATOMIC) == EXPECTED_FOLDERS


def test_every_folder_carries_its_own_barrel():
    """Sans barillet, un dossier n'est qu'un chemin plus long : rien ne dit ce qu'il exporte."""
    for folder in sorted(EXPECTED_FOLDERS):
        assert (_ATOMIC / folder / "__init__.py").exists(), f"{folder}/ n'a pas de __init__.py"


def test_the_shared_family_names_match_instagram():
    """Les quatre familles communes portent le MÊME nom des deux côtés. Un `detection` ici et un
    `detectors` là-bas obligeraient à réapprendre l'arborescence par plateforme."""
    shared = EXPECTED_FOLDERS & _folders(_INSTAGRAM_ATOMIC)

    assert shared == {"detection", "interaction", "navigation", "scroll"}


@pytest.mark.parametrize("name", sorted([
    "ClickActions", "NavigationActions", "ScrollActions", "DetectionActions", "DMActions",
    "ActivityActions", "AvatarActions", "CommentActions", "FeedTrainingActions", "PopupActions",
    "PopupDetector", "PostLinkActions", "RepostActions", "SearchActions", "SoundActions",
    "VideoActions", "VideoDetector",
]))
def test_the_barrel_still_exports_every_name(name):
    """Le rangement ne doit rien casser en amont : tout ce qui importait depuis `atomic` continue."""
    from taktik.core.social_media.tiktok.actions import atomic

    assert hasattr(atomic, name), f"{name} a disparu du barillet"
