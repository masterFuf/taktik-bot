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

**Troisieme cas, le blocage (2026-09-24).** Instagram affiche « Reessayer plus tard » : le
detecteur le voyait, fermait le dialogue, et le run agissait de nouveau -- le geste qui transforme
une limite temporaire en restriction durable. Le detecteur pose maintenant `ACTION_BLOCKED` ici
des qu'il voit le dialogue, et les boucles qui decident de continuer le lisent.

**Quatrieme cas : l'application de bureau a disparu** (2026-09-24). Le telephone repond, mais
plus personne ne lit les evenements du pont ni ne peut l'arreter : plantage de l'app, arret force,
fermeture brutale. Pose par le chien de garde du lanceur (`bridges/common/runtime/owner_watchdog.py`),
lu aux memes endroits que les autres, pour que le run finisse par son chemin normal.

**The witness.** The runtime that knows the operated account installs a listener
(`configurer_temoin`), told once when the latch is set: that is where a block becomes one entry
of the account's health history, whoever saw it. This module stays blind to accounts and SQLite.

Un processus de pont sert un run : le verrou y part leve. `run_bridge_main` le remet aussi a zero
au demarrage, comme les autres compteurs partages, pour les ponts qui passent par lui (pas les
ponts Instagram, qui ont leur propre point d'entree). La session persistante du Cartography Lab,
qui sert une action apres l'autre dans un meme processus, le leve avant chaque action -- sans quoi
une action entrerait avec le verrou de la precedente et s'arreterait d'emblee.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from loguru import logger

#: Le lien entre le poste et le telephone est tombe.
DEVICE_DISCONNECTED = "device_disconnected"

#: Android affiche le dialogue de plantage de l'application cible.
TARGET_APP_CRASHED = "target_app_crashed"

#: La plateforme refuse les actions du compte (« Reessayer plus tard ») : agir encore est ce qui
#: transforme une limite temporaire en restriction durable. Le premier signe arrete le run.
ACTION_BLOCKED = "action_blocked"

#: L'application de bureau qui a lance le pont n'existe plus : le run n'a plus de proprietaire.
DESKTOP_GONE = "desktop_gone"

_arret: Optional[Dict[str, Any]] = None

#: Told once, when the latch is set: the platform runtime that knows the operated account installs
#: it (the account's health record). Same shape as the telemetry sink; None = nobody listens.
_temoin: Optional[Callable[[Dict[str, Any]], None]] = None


def reinitialiser() -> None:
    """Lever le verrou. Appele au demarrage d'un run par `run_bridge_main`."""
    global _arret, _temoin
    _arret = None
    _temoin = None


def configurer_temoin(temoin: Optional[Callable[[Dict[str, Any]], None]]) -> None:
    """Install the listener told of the first halt of the run (replaces any previous one)."""
    global _temoin
    _temoin = temoin


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
    temoin = _temoin
    if temoin is not None:
        try:
            temoin(dict(_arret))
        except Exception as exc:  # noqa: BLE001 - a listener must never undo the stop
            logger.debug(f"Halt listener failed: {exc}")


def arret_demande() -> Optional[Dict[str, Any]]:
    """Le constat, ou None. Lu la ou l'on decide de continuer, pas la ou l'on echoue."""
    return dict(_arret) if _arret is not None else None


__all__ = [
    "demander_arret", "arret_demande", "reinitialiser", "configurer_temoin",
    "DEVICE_DISCONNECTED", "TARGET_APP_CRASHED", "ACTION_BLOCKED", "DESKTOP_GONE",
]
