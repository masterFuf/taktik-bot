"""Primitives partagees de lecture d'un dump de hierarchie Android.

Owner canonique de la geometrie "bounds" d'un noeud de dump : la chaine
``"[x1,y1][x2,y2]"`` rendue par uiautomator dans l'attribut ``bounds``. Ces
fonctions sont PURES (aucun device), donc testables a partir d'un dump capture.

Historique : le meme parseur avait ete recopie dans plusieurs surfaces
(notifications, thread de commentaires, xpath TikTok). Le nouveau code doit
importer cet owner ; les copies restantes sont une dette a resorber dans un lot
de refactor dedie.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def parse_bounds(value: str) -> Optional[Tuple[int, int, int, int]]:
    """Parse un ``bounds`` Android ``"[x1,y1][x2,y2]"`` en 4-tuple, ou None."""
    if not value:
        return None
    match = _BOUNDS_RE.search(value)
    if not match:
        return None
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def vertical_center(bounds: Sequence[int]) -> float:
    """Centre vertical (y) d'un 4-tuple ``(x1, y1, x2, y2)``."""
    return (bounds[1] + bounds[3]) / 2.0


def center(bounds: Sequence[int]) -> Tuple[int, int]:
    """Centre ``(x, y)`` d'un 4-tuple ``(x1, y1, x2, y2)``."""
    return ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)


def index_of_closest_row(target_y: float, candidate_ys: List[float]) -> Optional[int]:
    """Index du candidat dont le centre vertical est le plus proche de ``target_y``.

    Renvoie ``None`` s'il n'y a aucun candidat. Sert a apparier un libelle et son
    bouton d'action sur la meme bande horizontale quand l'imbrication DOM ne les
    relie pas.
    """
    if not candidate_ys:
        return None
    return min(range(len(candidate_ys)), key=lambda i: abs(candidate_ys[i] - target_y))


__all__ = ["parse_bounds", "vertical_center", "center", "index_of_closest_row"]
