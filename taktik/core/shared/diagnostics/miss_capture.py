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

from typing import Any, Dict, Optional, Sequence

from loguru import logger

from taktik.core.shared.diagnostics.surface_capture import capture_surface

#: Assez pour qu'un run rapporte du neuf, assez peu pour que le coût reste borné.
MAX_PAR_RUN = 6

#: Toutes les captures d'échec partagent une série : l'empreinte de `capture_surface` compare à la
#: DERNIÈRE de la série, donc dix-neuf échecs de suite sur le même écran n'en écrivent qu'un.
SURFACE = "selector_miss"

#: Combien de fois le MEME selecteur doit echouer d'affilee avant qu'on parle de blocage.
#: Un run sain rate un selecteur puis passe a autre chose ; un run bloque redemande le meme.
SEUIL_BLOCAGE = 8

_captures = 0
_dernier_selecteur: Optional[str] = None
_repetitions = 0
_blocage_signale = False


def reinitialiser() -> None:
    """Remet le plafond ET la serie de blocage à zéro. Appelé au démarrage d'un run."""
    global _captures, _dernier_selecteur, _repetitions, _blocage_signale
    _captures = 0
    _dernier_selecteur = None
    _repetitions = 0
    _blocage_signale = False


def _compter_repetition(selecteur: str) -> int:
    """Compte les echecs consecutifs sur le MEME selecteur. Rend le compte courant.

    Pourquoi le selecteur et non l'empreinte de l'ecran : l'empreinte coute un `dump_hierarchy`
    (~225 ms), et le plafond d'ecriture existe precisement pour ne pas le payer en boucle — une
    garde qui s'appuierait dessus deviendrait aveugle au moment ou la boucle s'installe. Le
    selecteur, lui, est deja dans la main de l'appelant : le comptage est gratuit.

    Et il dit la meme chose : un workflow bloque redemande le meme bouton introuvable.
    """
    global _dernier_selecteur, _repetitions, _blocage_signale
    if selecteur != _dernier_selecteur:
        _dernier_selecteur = selecteur
        _repetitions = 1
        _blocage_signale = False
    else:
        _repetitions += 1
    return _repetitions


def blocage_a_signaler() -> bool:
    """Le seuil vient d'etre franchi — une seule fois par serie, pour ne pas inonder le fil."""
    global _blocage_signale
    if _repetitions >= SEUIL_BLOCAGE and not _blocage_signale:
        _blocage_signale = True
        return True
    return False


def repetitions() -> int:
    """Combien de fois le selecteur courant a echoue d'affilee."""
    return _repetitions


def capturer_echec(
    device: Any,
    *,
    selectors: Sequence[str],
    platform: str = "unknown",
    app_version: str = "",
    language: str = "",
) -> Optional[Dict[str, Any]]:
    """Capture l'écran d'un échec de recherche. Rend le RECORD de la capture, ou None.

    Le record plutôt que le seul chemin : l'empreinte, le paquet au premier plan et le drapeau
    `lossy` sont ce qui rend la capture exploitable **ailleurs** — dans un rapport d'incident, par
    exemple, où le fichier lui-même ne voyage pas. Un chemin seul sur la machine de l'utilisateur
    est un diagnostic que personne n'ira chercher.

    `platform` vaut `"unknown"` par défaut et non `"tiktok"` : le défaut précédent rangeait sous
    TikTok tous les échecs Instagram, puisque l'appelant partagé ne le passait pas. Un rangement
    honnête vaut mieux qu'un faux.

    Ne lève jamais : un run ne rate pas parce qu'un diagnostic n'a pas pu écrire.
    """
    global _captures
    if not selectors:
        return None
    # Compte d'abord : la serie doit continuer a se mesurer une fois le plafond d'ECRITURE
    # atteint, sinon la garde de blocage s'eteint juste quand la boucle commence.
    _compter_repetition(str(selectors[0])[:110])
    if _captures >= MAX_PAR_RUN:
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
        return record
    except Exception as exc:  # noqa: BLE001 — un diagnostic ne fait jamais echouer un run
        logger.debug(f"[miss] capture impossible : {exc}")
        return None


__all__ = ["capturer_echec", "reinitialiser", "blocage_a_signaler", "repetitions",
           "MAX_PAR_RUN", "SEUIL_BLOCAGE", "SURFACE"]
