"""Une recherche qui echoue peut vouloir dire deux choses tres differentes.

« Je n'ai pas trouve mon bouton » et « je ne suis plus dans l'application » produisent aujourd'hui
la meme chose : un `False`, un avertissement, et l'action suivante qui echoue pareil. Le run brule
son temps en timeouts, se termine sans avoir rien fait, et aucun motif ne dit lequel des deux cas
c'etait.

Le bot humanise ses gestes : il tape parfois a cote. Une story sponsorisee ouvre le navigateur, un
lien de bio ouvre le Play Store, une banniere ouvre une application tierce. A partir de cet instant
plus aucun selecteur ne repond -- ce qui ressemble exactement a un catalogue perime.

Ce module ne repond qu'a la question « suis-je encore chez moi ? », et seulement quand une
recherche vient d'echouer. Il ne decide rien : il rend le paquet etranger, l'appelant en fait ce
qu'il veut.

**Pourquoi un intervalle plutot qu'un plafond.** Lire le premier plan coute cher -- `app_current()`
mesure ~440 ms sur un Pixel, soit environ DEUX `dump_hierarchy`. Un plafond par run (le choix de
`miss_capture`, pour une autre raison : le cout d'ecriture) rendrait le garde aveugle apres ses
premieres utilisations, or une sortie d'application arrive quand elle arrive. Un intervalle
minimum garde la detection vivante pendant tout le run en bornant le cout : au pire une lecture
toutes les `INTERVALLE_MINIMUM_S` secondes.

**Aucune memoire de la sortie n'est gardee ici.** Un drapeau « ce run est sorti de l'app » devrait
etre remis a zero au demarrage de chaque run, et ce point de depart commun aux deux plateformes
n'existe pas encore cote Python -- `miss_capture.reinitialiser()` le suppose et n'est appele nulle
part. Un etat qui ne sait pas quand recommencer est pire qu'absent : il ferait echouer d'emblee le
run suivant du meme processus. Le seul etat porte ici est l'horodatage du dernier controle, qui ne
peut rien casser en survivant a un run.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from loguru import logger

from taktik.core.clone.packages.package_map import belongs_to_platform
from taktik.core.shared.device.app_inspection import foreground_package

#: Assez court pour qu'une sortie soit vue dans la foulee, assez long pour que le cout reste sous
#: le bruit : ~440 ms toutes les 20 s au pire, soit ~2 % du temps d'un run qui echoue en boucle.
INTERVALLE_MINIMUM_S = 20.0

_dernier_controle = 0.0


def reinitialiser() -> None:
    """Autorise un controle immediat. Utile aux tests et a un demarrage de run."""
    global _dernier_controle
    _dernier_controle = 0.0


def paquet_etranger(device: Any, platform: Optional[str], *, force: bool = False) -> Optional[str]:
    """Le paquet au premier plan s'il n'appartient PAS a `platform`, sinon None.

    `None` couvre trois situations qu'il ne faut surtout pas confondre avec une sortie : le
    controle a ete saute (trop recent), la plateforme est inconnue de l'appelant, ou le premier
    plan n'a pas pu etre lu. Aucune des trois ne prouve quoi que ce soit -- et conclure a tort
    qu'un run est sorti de l'application l'arreterait alors qu'il va bien.

    Ne leve jamais : un diagnostic ne fait pas echouer un run.
    """
    global _dernier_controle
    if not platform:
        return None

    maintenant = time.monotonic()
    if not force and (maintenant - _dernier_controle) < INTERVALLE_MINIMUM_S:
        return None
    _dernier_controle = maintenant

    try:
        paquet = foreground_package(device)
        if not paquet or belongs_to_platform(paquet, platform):
            return None
        return paquet
    except Exception as exc:  # noqa: BLE001 -- un diagnostic ne fait jamais echouer un run
        logger.debug(f"[foreground] controle impossible : {exc}")
        return None


__all__ = ["paquet_etranger", "reinitialiser", "INTERVALLE_MINIMUM_S"]
