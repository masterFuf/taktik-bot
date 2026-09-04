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
etre remis a zero au demarrage de chaque run. Ce point de depart existe depuis le 2026-09-04 :
`bridges/common/runtime/entrypoint.py::run_bridge_main`, le `main()` universel par lequel passe
TOUT pont, appelle `reinitialiser()` sur ce module et sur `miss_capture`. Un etat qui ne sait pas
quand recommencer serait pire qu'absent -- il ferait echouer d'emblee le run suivant du meme
processus. Le seul etat porte ici reste l'horodatage du dernier controle, qui ne peut rien casser
en survivant a un run.
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


def lien_perdu(device: Any) -> bool:
    """Le poste ne parle plus a ce telephone.

    Le mode de defaillance le plus banal d'un run de nuit : veille profonde, cable qui bouge, hub
    USB qui decroche. Chaque appel device leve ensuite, les `except` defensifs les avalent un par
    un, et le run se termine sans avoir rien fait — sans que le processus meure, donc sans rapport
    de crash. Au reveil : un run « termine », zero action, aucune explication.

    Ce n'est PAS la meme question que « l'application a plante » : `window_size` repond encore
    quand l'app est morte, et se tait quand c'est le lien. Les distinguer est tout l'enjeu, parce
    qu'aujourd'hui les deux se presentent comme un selecteur introuvable.

    Ne demande rien de plus qu'une lecture triviale : le but est de savoir si le telephone repond,
    pas ce qu'il affiche.
    """
    if device is None:
        return True
    try:
        cible = getattr(device, "_device", None) or device
        cible.window_size()
        return False
    except Exception:
        return True


__all__ = ["paquet_etranger", "lien_perdu", "reinitialiser", "INTERVALLE_MINIMUM_S"]
