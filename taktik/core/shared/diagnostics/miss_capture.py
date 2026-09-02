"""Quand une recherche échoue, garder l'écran — c'est le seul moment où sa capture vaut quelque chose.

Il reste des contrôles qu'on ne peut pas écrire parce qu'on n'a jamais vu l'écran. Un popup ne se
convoque pas : il apparaît pendant un vrai run, la nuit, sur un téléphone que personne ne regarde.
Aller le chercher à la main coûte une session d'appareil par contrôle, et rate ceux qu'on ne sait
pas chercher.

Un échec de recherche est l'application qui dit « j'affiche quelque chose que ton catalogue ne sait
pas nommer ». Une capture périodique ramènerait mille fils vidéo ; celle-ci ramène les surfaces qui
manquent.

Rien n'est réinventé ici : `capture_surface` fait déjà l'empreinte, l'écriture conditionnelle et la
série append-only, et son commentaire décrit exactement ce cas — « an action that just failed is the
reason that matters: that is the screen nobody can reconstruct later ». Ce module n'ajoute que la
POLITIQUE : quand on capture, combien de fois, et ce qu'on note pour s'en servir plus tard.

Deux garde-fous, chacun pour une raison mesurée :

**Un plafond par run.** Un run du 2026-09-02 a raté le même bouton retour dix-neuf fois. Sans
plafond, un run parti en boucle d'échecs paie un `dump_hierarchy` (~300 ms) à chaque tour.

**Ce qu'on cherchait est noté.** Un dump sans cela est une image de plus dans un dossier ; avec, on
peut demander plus tard « quel écran affichait quelque chose qu'on ne savait pas nommer, et quoi ».
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from loguru import logger

from taktik.core.shared.diagnostics.surface_capture import capture_surface

#: Assez pour qu'un run rapporte du neuf, assez peu pour que le coût reste borné.
MAX_PAR_RUN = 6

#: Toutes les captures d'échec partagent une série : l'empreinte de `capture_surface` compare à la
#: DERNIÈRE de la série, donc dix-neuf échecs de suite sur le même écran n'en écrivent qu'un.
SURFACE = "selector_miss"

_captures = 0


def reinitialiser() -> None:
    """Remet le plafond à zéro. Appelé au démarrage d'un run."""
    global _captures
    _captures = 0


def capturer_echec(
    device: Any,
    *,
    selectors: Sequence[str],
    platform: str = "tiktok",
    app_version: str = "",
    language: str = "",
) -> Optional[str]:
    """Capture l'écran d'un échec de recherche. Rend le chemin XML écrit, ou None.

    Ne lève jamais : un run ne rate pas parce qu'un diagnostic n'a pas pu écrire.
    """
    global _captures
    if _captures >= MAX_PAR_RUN or not selectors:
        return None

    try:
        cherche = str(selectors[0])[:110]
        record = capture_surface(
            device,
            platform=platform,
            surface=SURFACE,
            app_version=app_version,
            language=language,
            # Le champ est libre, et c'est ce qui donne son sens a la capture : sans lui on garde
            # une image, avec lui on garde une QUESTION.
            action_outcome=f"cherchait|{len(selectors)}|{cherche}",
        )
        if not record:
            return None
        _captures += 1
        chemin = record.get("xmlPath")
        if chemin:
            logger.debug(f"[miss] ecran inconnu garde : {chemin}")
        return chemin
    except Exception as exc:  # noqa: BLE001 — un diagnostic ne fait jamais echouer un run
        logger.debug(f"[miss] capture impossible : {exc}")
        return None


__all__ = ["capturer_echec", "reinitialiser", "MAX_PAR_RUN", "SURFACE"]
