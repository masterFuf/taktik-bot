"""Les derniers ecrans traverses par le run, gardes en memoire jusqu'a ce qu'un incident arrive.

C'est la piece qui manque pour qu'un incident se lise. Aujourd'hui le moteur ne photographie que
les ECHECS : `miss_capture` ecrit quand une recherche de selecteur echoue. Un run qui fait
n'importe quoi sans jamais rater un selecteur -- il navigue, il defile, il ne trouve simplement
plus rien a faire -- ne laisse aucune image. Une boite noire enregistre TOUT LE TEMPS et ne garde
que quand ca casse.

**Aucun cout appareil.** L'anneau ne demande jamais de `dump_hierarchy` : il prend celui que
l'appelant tient DEJA. `capture_surface` en fait un, le fermeur de popups en fait un a chaque
tour ; ces XML etaient lus puis jetes. Empreinte et squelette se calculent sur une chaine, en
memoire. Prendre une capture d'ecran a chaque tour aurait coute ~300 ms par pas et ralenti tous
les runs pour servir les rares qui echouent -- c'est le contraire de ce qu'on veut. L'image, elle,
se prend une seule fois, au moment de l'incident (`incident_capture`).

**Les repetitions se replient.** Six emplacements remplis de six copies du meme ecran ne disent
rien. Un ecran identique au precedent -- meme empreinte -- incremente son compteur au lieu de
consommer une place. Six emplacements valent donc six ecrans DIFFERENTS, ce qui est la seule
version informative, et le compteur porte en prime « on est reste 40 tours sur cette page ».

**Ce qui se lit ensuite, c'est le mouvement.** Entre deux ecrans, la difference de squelette dit
en une ligne ce qui est apparu et ce qui est parti (`+wb_guide -pcw`) : une phrase, la ou deux
empreintes hexadecimales ne sont que deux etiquettes. C'est ce que la note de `screen_skeleton`
reclamait, et le seul endroit ou on tient deux ecrans consecutifs pour le calculer.

L'etat est remis a zero au demarrage de chaque run par `run_bridge_main`, comme `miss_capture` et
`foreground_guard`.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from taktik.core.shared.diagnostics.layout_fingerprint import layout_fingerprint, screen_skeleton

#: Six ecrans DISTINCTS. Assez pour raconter comment on est arrive la -- ouvrir un profil, defiler,
#: tomber sur une page inconnue -- sans faire grossir un dossier d'incident au dela du raisonnable.
CAPACITE = 6

#: Un squelette entier peut porter deux cents identifiants. Ce qui se lit, c'est le mouvement ;
#: au-dela de cette taille, la difference n'est plus une phrase mais une liste.
MAX_DELTA = 12

_anneau: List[Dict[str, Any]] = []


def reinitialiser() -> None:
    """Vide l'anneau. Appele au demarrage d'un run par `run_bridge_main`."""
    _anneau.clear()


def noter(xml: Optional[str], *, platform: Optional[str] = None,
          note: Optional[str] = None) -> None:
    """Enregistrer l'ecran que decrit ce dump. Ne demande rien a l'appareil.

    `xml` est un `dump_hierarchy` que l'appelant tient deja. Un dump vide ou illisible est ignore
    en silence : un ecran sans forme n'est pas un ecran, et le stocker ferait passer chaque dump
    casse pour une etape du parcours.
    """
    if not xml:
        return
    try:
        empreinte = layout_fingerprint(xml)
        if empreinte is None:
            return
        squelette = screen_skeleton(xml) or []

        if _anneau and _anneau[-1]['fingerprint'] == empreinte:
            dernier = _anneau[-1]
            dernier['repetitions'] += 1
            dernier['lastAt'] = time.time()
            if note:
                dernier['note'] = note
            return

        entree: Dict[str, Any] = {
            'fingerprint': empreinte,
            'skeleton': squelette,
            'platform': platform,
            'note': note,
            'at': time.time(),
            'lastAt': None,
            'repetitions': 1,
            'entered': [],
            'left': [],
        }
        if _anneau:
            precedent = set(_anneau[-1]['skeleton'])
            courant = set(squelette)
            entree['entered'] = sorted(courant - precedent)[:MAX_DELTA]
            entree['left'] = sorted(precedent - courant)[:MAX_DELTA]

        _anneau.append(entree)
        del _anneau[:-CAPACITE]
    except Exception:  # noqa: BLE001 -- un diagnostic ne doit jamais terminer un run
        return


def derniers() -> List[Dict[str, Any]]:
    """Les ecrans traverses, du plus ancien au plus recent. Copie : l'appelant peut la serialiser."""
    return [dict(entree) for entree in _anneau]


def resume() -> List[str]:
    """Le parcours en une ligne par ecran, pour un journal ou un ticket.

    Lisible sans outil : `#3 a1b2c3d4 x40  +wb_guide -pcw`. C'est la forme qui repond a « comment
    est-il arrive la », qu'aucun champ du rapport ne portait.
    """
    lignes = []
    for index, entree in enumerate(_anneau, start=1):
        mouvement = ' '.join(
            [f"+{identifiant}" for identifiant in entree['entered']]
            + [f"-{identifiant}" for identifiant in entree['left']]
        )
        repetitions = f" x{entree['repetitions']}" if entree['repetitions'] > 1 else ''
        note = f"  ({entree['note']})" if entree.get('note') else ''
        lignes.append(f"#{index} {entree['fingerprint'][:12]}{repetitions}{note}  {mouvement}".rstrip())
    return lignes


__all__ = ['noter', 'derniers', 'resume', 'reinitialiser', 'CAPACITE']
