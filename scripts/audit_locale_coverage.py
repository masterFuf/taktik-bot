"""Audit : aucune langue ne laisse mort un contrôle qu'une autre sait atteindre.

`L(clé)` rend les fragments de la langue active, et **`[]` quand la clé est absente ou vide**. Pas
de repli sur l'autre langue : une entrée vide n'est pas neutre, elle est muette. Quand la propriété
qui la sert n'a aucun sélecteur structurel à côté, le contrôle devient injoignable — et l'appel
cherche zéro sélecteur pendant tout son timeout avant d'annoncer « aucun élément trouvé », phrase
qui envoie chercher un sélecteur cassé là où la liste était vide.

Mesuré sur un run For You réel (2026-09-02) : le bot détecte la page de suggestion, décide de
cliquer « Pas intéressé », et perd 3 s à ne rien chercher parce que
`popup.suggestion_not_interested` vaut `[]` en français. Neuf autres propriétés étaient dans le
même cas, dont `profile.private_indicator` — sur un téléphone français, aucun compte privé ne
pouvait être reconnu, donc le filtre `allow_private` ne pouvait jamais se déclencher.

La mesure ne lit pas les fichiers de locale : elle **appelle chaque propriété** sous chaque langue.
C'est la seule façon de distinguer un vide légitime (le contrôle n'a pas de texte dans cette
langue, et des sélecteurs structurels le trouvent quand même) d'un contrôle mort.

Lancer : ``python scripts/audit_locale_coverage.py`` (``--json`` pour une sortie machine).
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import sys
from pathlib import Path
from typing import Dict, List, Set

# Lance depuis `scripts/`, le paquet du bot n'est pas sur le chemin : les autres audits ne lisent
# que des fichiers, celui-ci doit IMPORTER pour mesurer ce que rendent les proprietes.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from taktik.core.social_media.tiktok.ui.selectors import locales as locales_module
import taktik.core.social_media.tiktok.ui.selectors.shell as shell_package
import taktik.core.social_media.tiktok.ui.selectors.surfaces as surfaces_package

#: Vide dans une langue, plein dans l'autre — et pourtant CORRECT, parce que le contrôle est
#: atteint autrement. Une entrée par propriété, avec la mesure qui l'établit : sans ça, la seule
#: façon de faire taire l'audit serait de recopier l'anglais en français, c'est-à-dire d'inventer
#: un libellé que personne n'a lu sur un écran.
#:
#: Volontairement court. Un contrôle qu'on n'a pas encore VU reste rouge : « pas encore rencontré »
#: n'est pas « mesuré et répondu autrement ».
MESURE_AUTREMENT: Dict[str, str] = {
    "VideoStateSelectors.user_followed_indicator": (
        "Mesuré sur appareil français le 2026-09-04 (TikTok 46.x, Pixel 3a, langue détectée `fr`, "
        "FR=10.5 EN=0.5). Le bouton « Following » / « Friends » que nomme l'entrée anglaise "
        "n'existe pas sur le fil : sur « Pour toi » l'auteur non suivi porte un bouton "
        "content-desc « Suivre <auteur> », et sur « Suivis » il n'y a AUCUN bouton de suivi. "
        "is_user_followed() répond donc par ABSENCE, et rend bien « pas suivi » sur le premier "
        "fil et « déjà suivi » sur le second, l'entrée française restant vide."
    ),
}


#: Vides dans TOUTES les langues : le contrôle n'existe simplement pas encore. Ce n'est pas une
#: dérive entre langues, et le signaler ici noierait celles qui en sont une. Elles restent
#: visibles dans la sortie `--json`.
def _empty_properties(locale: str) -> Set[str]:
    """Les propriétés de sélecteurs qui rendent une liste vide sous `locale`."""
    locales_module.set_active_locale(locale)
    empty: Set[str] = set()
    for package in (surfaces_package, shell_package):
        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(f"{package.__name__}.{module_name}")
            for class_name, cls in inspect.getmembers(module, inspect.isclass):
                if not class_name.endswith("Selectors"):
                    continue
                try:
                    instance = cls()
                except Exception:
                    continue
                for prop_name, _ in inspect.getmembers(
                    type(instance), lambda member: isinstance(member, property)
                ):
                    try:
                        value = getattr(instance, prop_name)
                    except Exception:
                        continue
                    if isinstance(value, list) and not value:
                        empty.add(f"{class_name}.{prop_name}")
    return empty


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="sortie machine")
    args = parser.parse_args()

    langues = list(locales_module.available_locales())
    if len(langues) < 2:
        print(f"Une seule langue ({langues}) : rien à comparer.")
        return 0

    vides: Dict[str, Set[str]] = {langue: _empty_properties(langue) for langue in langues}
    partout = set.intersection(*vides.values())

    #: Vide ici, plein ailleurs — le contrôle est mort dans cette langue-là.
    morts: Dict[str, List[str]] = {
        langue: sorted(vides[langue] - partout - set(MESURE_AUTREMENT)) for langue in langues
    }
    #: Vide ici, plein ailleurs, mais mesuré comme atteint autrement — affiché, jamais compté.
    mesures: Dict[str, List[str]] = {
        langue: sorted((vides[langue] - partout) & set(MESURE_AUTREMENT)) for langue in langues
    }
    total = sum(len(v) for v in morts.values())

    if args.json:
        print(json.dumps({
            "dead": morts,
            "empty_everywhere": sorted(partout),
            "measured_otherwise": {nom: MESURE_AUTREMENT[nom]
                                   for noms in mesures.values() for nom in noms},
        }, indent=2))
        return 1 if total else 0

    mesurees = sum(len(v) for v in mesures.values())

    if not total:
        print(
            f"Locale coverage audit OK — {len(langues)} langue(s), "
            f"{len(partout)} propriété(s) vide(s) partout (contrôle absent, pas une dérive)"
            + (f", {mesurees} atteinte(s) autrement (mesuré)" if mesurees else "")
        )
        return 0

    print(f"Locale coverage audit : {total} contrôle(s) mort(s) dans une langue et vivant(s) dans une autre")
    print("Une entrée de locale vide ne retombe PAS sur l'autre langue — le contrôle est injoignable.")
    for langue, propriétés in morts.items():
        if not propriétés:
            continue
        print(f"\n  [{langue}] {len(propriétés)} :")
        for propriété in propriétés:
            print(f"      {propriété}")
    if partout:
        print(f"\n  (et {len(partout)} vide(s) dans toutes les langues — contrôle absent, non compté)")
    for langue, propriétés in mesures.items():
        for propriété in propriétés:
            print()
            print(f"  [{langue}] {propriété} — atteint autrement, non compté :")
            print(f"      {MESURE_AUTREMENT[propriété]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
