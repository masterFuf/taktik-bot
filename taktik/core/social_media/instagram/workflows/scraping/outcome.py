"""Un scraping qui n'a rien ramené : est-ce un succès ou un échec ?

Les quatre chemins de retour du scraping Instagram posaient `success: True` inconditionnellement,
après la boucle, sans jamais regarder ce qu'elle avait produit. `success: True, total_scraped: 0`
était donc un résultat parfaitement exprimable — et c'est ce que l'application recevait quand la
grille d'un hashtag ne s'était jamais ouverte.

**Le critère n'est PAS le nombre collecté.** `success = total_scraped > 0` ferait échouer des runs
parfaitement sains : une cible dont tous les profils sont déjà en base rend zéro nouveau profil et
a très bien fonctionné. Le critère est **« a-t-on atteint la surface »**, c'est-à-dire la liste
d'abonnés, la grille du hashtag, le post. Trois situations que le code confondait :

- la surface a été atteinte : succès, que la récolte soit pleine ou vide ;
- la cible existe mais ne donne rien à collecter (un compte privé, par exemple) : succès aussi —
  le bot a fait son travail, il a appris quelque chose sur la cible ;
- la surface n'a jamais été atteinte (navigation échouée, liste jamais ouverte) : échec, et c'est
  le cas le plus fréquent en pratique.

Cette fonction est pure et vit à part parce que les quatre appelants sont répartis sur deux
fichiers de la même famille de mixins. La recopier quatre fois aurait produit quatre verdicts qui
divergent — le défaut que ce lot corrige, à l'échelle du dessus.
"""

from __future__ import annotations

from typing import Any, Dict

#: La surface a été ouverte et des profils en sont sortis.
COMPLETED = "completed"
#: La surface a été ouverte (ou la cible correctement écartée) et il n'y avait rien à prendre.
NOTHING_TO_SCRAPE = "nothing_to_scrape"
#: Aucune surface n'a été ouverte : navigation échouée, liste jamais affichée.
TARGET_NEVER_REACHED = "target_never_reached"


def scraping_outcome(
    *,
    sources_reached: int,
    sources_skipped: int,
    sources_failed: int,
    total_scraped: int,
) -> Dict[str, Any]:
    """Le verdict d'un run de scraping, à partir de ce que la boucle a réellement fait.

    Args:
        sources_reached: sources dont la surface a été ouverte (liste, grille, post).
        sources_skipped: sources écartées pour une raison CONNUE et légitime — un compte privé
            dont la liste est inaccessible par construction. Ce n'est pas une panne.
        sources_failed: sources jamais atteintes (navigation ou ouverture en échec).
        total_scraped: profils réellement collectés.

    Returns:
        `{"success": bool, "completion_reason": str}`, à fusionner dans le retour de l'appelant.

    Une boucle qui n'a rien tenté du tout — zéro source des trois compteurs, parce que le temps de
    session était déjà écoulé ou le plafond déjà atteint avant le premier tour — est un succès :
    rien n'a échoué, il n'y avait simplement plus rien à faire.
    """
    if sources_reached > 0:
        return {
            "success": True,
            "completion_reason": COMPLETED if total_scraped > 0 else NOTHING_TO_SCRAPE,
        }

    if sources_failed > 0:
        return {"success": False, "completion_reason": TARGET_NEVER_REACHED}

    # Aucune surface ouverte, aucun échec : soit tout a été écarté pour une raison connue, soit la
    # boucle n'a jamais tourné. Les deux sont des fins légitimes.
    return {"success": True, "completion_reason": NOTHING_TO_SCRAPE}


__all__ = [
    "scraping_outcome",
    "COMPLETED",
    "NOTHING_TO_SCRAPE",
    "TARGET_NEVER_REACHED",
]
