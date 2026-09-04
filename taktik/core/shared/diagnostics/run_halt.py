"""Quand un run ne peut plus rien faire : le constater ici, l'arreter ailleurs.

Deux modes de defaillance etaient DETECTES sans que rien ne s'arrete. Le lien ADB tombe, ou
l'application cible plante : `base_action` le voit, emet son etape, journalise -- et le workflow
continue. Chaque appel suivant leve, chaque `except` l'avale, et le run se termine des heures plus
tard avec zero action et aucune explication. C'est exactement le reveil que le lot d'observabilite
existe pour eviter : « run termine, zero action, va savoir ».

**Pourquoi un verrou plutot qu'une exception.** Une exception serait avalee comme les autres :
les `except Exception` sont partout dans les workflows, par construction defensive, et c'est
justement ce qui rend ces deux pannes invisibles. Un verrou se lit a l'endroit ou l'on decide de
continuer, pas la ou l'on echoue.

**Pourquoi ici et pas dans un catalogue de plateforme.** La detection vit dans `shared/`, qui ne
doit jamais importer `social_media/<plateforme>`. Ce module ne porte donc qu'un CODE et un detail ;
chaque plateforme le traduit dans son propre vocabulaire d'arret. C'est la meme separation que
`miss_capture`, qui compte sans savoir ce que l'appelant fera du compte.

**Ce n'est pas une erreur transitoire.** Un lien perdu ne revient pas tout seul dans une session ;
reessayer indefiniment transforme un arret propre en run fantome de plusieurs heures. Le premier
constat gagne et ne bouge plus : les suivants decriraient la meme panne avec moins de contexte.

Remis a zero au demarrage de chaque run par `run_bridge_main`, comme les autres compteurs
partages -- sans quoi un run entrerait avec le verrou du precedent et s'arreterait d'emblee.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from loguru import logger

#: Le lien entre le poste et le telephone est tombe.
DEVICE_DISCONNECTED = "device_disconnected"

#: Android affiche le dialogue de plantage de l'application cible.
TARGET_APP_CRASHED = "target_app_crashed"

_arret: Optional[Dict[str, Any]] = None


def reinitialiser() -> None:
    """Lever le verrou. Appele au demarrage d'un run par `run_bridge_main`."""
    global _arret
    _arret = None


def demander_arret(code: str, detail: Optional[str] = None, **contexte: Any) -> None:
    """Constater qu'il n'y a plus rien a tenter. Le PREMIER constat gagne.

    Le premier plutot que le dernier : c'est celui qui a le plus de contexte. Une fois le lien
    perdu, les constats suivants ne savent plus rien de l'ecran ni du paquet au premier plan.
    """
    global _arret
    if _arret is not None:
        return
    _arret = {"code": code, "detail": detail, "at": time.time(), **contexte}
    logger.warning(f"⛔ Arret demande : {code}" + (f" — {detail}" if detail else ""))


def arret_demande() -> Optional[Dict[str, Any]]:
    """Le constat, ou None. Lu la ou l'on decide de continuer, pas la ou l'on echoue."""
    return dict(_arret) if _arret is not None else None


__all__ = [
    "demander_arret", "arret_demande", "reinitialiser",
    "DEVICE_DISCONNECTED", "TARGET_APP_CRASHED",
]
