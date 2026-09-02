"""Shared helpers for TikTok video selector catalogs.

Un id, UN selecteur — pas un par package. Les trois variantes (`musically`, `trill`, `aweme`)
sont reelles et doivent rester couvertes, mais un appareil n'en fait tourner qu'une : les deux
autres etaient deux essais payes a chaque recherche, sur chaque liste.

Mesure du 2026-09-02 : le bouton like etait trouve au rang 7 sur 46.6.3 (4,2 s de moyenne sur six
tirs) et les commentaires au rang 5. Six des sept essais perdus etaient des paquets absents ou un
id d'une autre version. La forme `@resource-id="a" or @resource-id="b" or ...` couvre les trois
paquets en une passe, en egalite EXACTE — `contains(":id/f57")` aurait tire aussi sur `f57x`,
et un faux positif sur un bouton like coute plus qu'un essai.
"""

from typing import List

_PKG = [
    "com.zhiliaoapp.musically",
    "com.ss.android.ugc.trill",
    "com.ss.android.ugc.aweme",
]


def _any_package(rid: str) -> str:
    """`@resource-id` egal a cet id, quel que soit le paquet — en une seule condition."""
    return " or ".join(f'@resource-id="{pkg}:id/{rid}"' for pkg in _PKG)


def resource_ids(*ids: str) -> List[str]:
    """Un selecteur par id, couvrant les trois paquets."""
    return [f"//*[{_any_package(rid)}]" for rid in ids]


def resource_ids_with(*ids: str, xpath_filter: str) -> List[str]:
    """Idem, avec un filtre XPath commun accroche a chaque selecteur."""
    return [f"//*[{_any_package(rid)}]{xpath_filter}" for rid in ids]


def resource_id_with_descendant(parent_id: str, child_id: str) -> List[str]:
    """Un parent stable qui CONTIENT un enfant stable — le couple qui departage.

    Necessaire parce que le conteneur est partage : `f57` designe le like ET le partage sur
    43.1.4, `g2w` fait de meme sur 46.6.3. C'est l'enfant (`f4u` / `g2c`, l'icone) qui tranche.

    Le paquet n'est plus croise entre parent et enfant : les deux appartiennent au meme
    processus, donc au meme paquet, et produire les neuf combinaisons pour n'en voir repondre
    qu'une etait huit essais pour rien.
    """
    return [f"//*[({_any_package(parent_id)}) and .//*[{_any_package(child_id)}]]"]
