"""Le dialogue par lequel Android annonce qu'une application vient de mourir.

Recherche sur tout le moteur avant d'ecrire ce module : aucune occurrence de `aerr`, de
`isn't responding`, de `has stopped` ni de `ne repond pas`. Quand l'application cible plante ou se
fige, le bot voit donc un ecran qu'aucun selecteur ne reconnait — au mieux `miss_capture` en garde
une trace, sans savoir que c'est un crash. Le run enchaine ensuite ses timeouts et se termine sans
rien dire d'utile.

**Ce module vit dans `shared/` et pas sous une plateforme**, parce que ce dialogue appartient au
systeme : il est identique qu'Instagram, TikTok ou Threads vienne de mourir. Le nom de
l'application y figure, mais la structure est celle d'Android.

**Pourquoi les identifiants et non les libelles.** `android:id/aerr_*` sont poses par le framework
et survivent aux versions et aux langues. Les libelles, eux, changent d'une locale a l'autre
(« ne repond pas », « isn't responding », « keeps stopping ») et d'une surcouche a l'autre. Ils
sont gardes en second, pour les surcouches constructeur qui renomment leurs identifiants — jamais
seuls.

**Un crash n'est pas une page a fermer.** C'est une condition d'arret : l'application cible n'est
plus la, et continuer a chercher des boutons dedans n'a pas de sens. Ce module ne ferme donc rien,
il constate.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from loguru import logger

#: Identifiants poses par le framework Android sur son dialogue « l'application s'est arretee »
#: et sur le dialogue ANR (« ne repond pas »). Stables entre versions et entre langues.
IDENTIFIANTS = (
    "android:id/aerr_close",
    "android:id/aerr_restart",
    "android:id/aerr_report",
    "android:id/aerr_wait",
    "android:id/aerr_mute",
)

#: Repli pour les surcouches constructeur qui renomment leurs identifiants. Volontairement
#: specifiques : « stopped » seul repondrait sur une page de reglages parlant de comptes arretes.
LIBELLES = (
    "isn't responding",
    "is not responding",
    "keeps stopping",
    "has stopped",
    "ne répond pas",
    "ne repond pas",
    "s'est arrêtée",
    "s'est arretee",
    "continue de s'arrêter",
)

_ID = re.compile(r'resource-id="([^"]*)"')


def dialogue_de_crash(dump: str) -> Optional[str]:
    """La signature trouvee dans ce dump, ou None. Ne touche pas l'appareil.

    Prend le XML deja en main plutot que de le redemander : ce module est appele depuis un chemin
    qui vient d'en obtenir un, et un `dump_hierarchy` coute ~225 ms.
    """
    if not dump:
        return None
    for identifiant in IDENTIFIANTS:
        if identifiant in dump:
            return identifiant
    bas = dump.lower()
    for libelle in LIBELLES:
        if libelle.lower() in bas:
            return libelle
    return None


def constater(device: Any) -> Optional[str]:
    """Interroge l'appareil. A n'appeler que quand quelque chose ne va deja pas.

    Ne leve jamais : un diagnostic ne fait pas echouer un run.
    """
    try:
        return dialogue_de_crash(device.dump_hierarchy())
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"[android-crash] lecture impossible : {exc}")
        return None


__all__ = ["dialogue_de_crash", "constater", "IDENTIFIANTS", "LIBELLES"]
