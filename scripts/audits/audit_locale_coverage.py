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

Un plancher, comme les autres audits à cliquet : `audit_locale_coverage_baseline.json` liste les
entrées de locale mortes d'aujourd'hui, chacune en attente de sa capture (`<langue>:<clé>`). Une
entrée morte absente de la liste est rouge ; une entrée listée qui ne l'est plus l'est aussi, tant
que `--update-baseline` ne l'a pas retirée. La liste ne fait que baisser : `--update-baseline`
refuse d'y ajouter. Chaque ligne rouge nomme le fichier de locale et la clé.

Lancer : ``python scripts/audits/audit_locale_coverage.py`` (``--json`` pour une sortie machine,
``--update-baseline`` pour retirer de la liste ce qui a été rempli).
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Lance depuis `scripts/`, le paquet du bot n'est pas sur le chemin : les autres audits ne lisent
# que des fichiers, celui-ci doit IMPORTER pour mesurer ce que rendent les proprietes.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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


ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name("audit_locale_coverage_baseline.json")
LOCALES_DIR = Path(locales_module.__file__).parent


def _locale_file(langue: str) -> str:
    return (LOCALES_DIR / f"{langue}.py").relative_to(ROOT).as_posix()


def _properties():
    """Every (name, selectors class, property name, its module) of the TikTok catalogues."""
    for package in (surfaces_package, shell_package):
        # Every module, sub-packages included (surfaces/video/...), each class where it is defined.
        for _, module_name, _ in pkgutil.walk_packages(package.__path__, f"{package.__name__}."):
            module = importlib.import_module(module_name)
            for class_name, cls in inspect.getmembers(module, inspect.isclass):
                if not class_name.endswith("Selectors") or cls.__module__ != module.__name__:
                    continue
                for prop_name, _ in inspect.getmembers(cls, lambda member: isinstance(member, property)):
                    yield f"{class_name}.{prop_name}", cls, prop_name, module


def _empty_properties(locale: str) -> Dict[str, Set[str]]:
    """Under `locale`: each property that renders an empty list -> the locale keys it read."""
    locales_module.set_active_locale(locale)
    empty: Dict[str, Set[str]] = {}
    for name, cls, prop_name, module in _properties():
        read: Set[str] = set()
        original = getattr(module, "L", None)

        def recording(key, _original=locales_module.L, _read=read):
            _read.add(key)
            return _original(key)

        if original is not None:
            module.L = recording
        try:
            value = getattr(cls(), prop_name)
        except Exception as error:  # a catalogue that cannot be built is not a measure: said, not counted
            print(f"  (non mesuré : {name} : {error})", file=sys.stderr)
            continue
        finally:
            if original is not None:
                module.L = original
        if isinstance(value, list) and not value:
            empty[name] = read
    return empty


def measure() -> Tuple[Dict[str, Dict[str, Set[str]]], Set[str]]:
    """Dead per language (property -> keys), and the properties empty everywhere."""
    langues = list(locales_module.available_locales())
    vides = {langue: _empty_properties(langue) for langue in langues}
    partout = set.intersection(*(set(v) for v in vides.values())) if vides else set()
    morts = {langue: {nom: cles for nom, cles in vides[langue].items()
                      if nom not in partout and nom not in MESURE_AUTREMENT}
             for langue in langues}
    return morts, partout


def dead_entries(morts) -> Dict[str, str]:
    """`<langue>:<clé>` -> the property it leaves dead, for every dead property's empty keys."""
    entries: Dict[str, str] = {}
    for langue, proprietes in morts.items():
        for nom, cles in proprietes.items():
            vides = [cle for cle in sorted(cles) if not locales_module.L_in(langue, cle)] or sorted(cles)
            for cle in vides:
                entries[f"{langue}:{cle}"] = nom
    return entries


def read_baseline() -> Set[str]:
    if not BASELINE.exists():
        return set()
    return set(json.loads(BASELINE.read_text(encoding="utf-8"))["dead"])


def write_baseline(entries: Set[str]) -> None:
    BASELINE.write_text(json.dumps({"dead": sorted(entries)}, indent=2) + "\n", encoding="utf-8", newline="\n")


def _line(entry: str, nom: str, why: str) -> str:
    langue, cle = entry.split(":", 1)
    return f" - {_locale_file(langue)}: {cle} ({nom}) {why}"


def update_baseline() -> int:
    morts, _ = measure()
    now = set(dead_entries(morts))
    listed = read_baseline()
    rising = now - listed
    if rising and BASELINE.exists():
        print("Locale coverage baseline: refusé, la liste ne fait que baisser. Entrées mortes nouvelles :")
        for entry in sorted(rising):
            print(_line(entry, dead_entries(morts)[entry], "est vide dans cette langue et pleine dans une autre"))
        return 1
    write_baseline(now)
    print(f"Locale coverage baseline: {len(now)} entrée(s) en attente de capture ({len(listed - now)} retirée(s))")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="sortie machine")
    parser.add_argument("--update-baseline", action="store_true", help="retirer de la liste ce qui a été rempli")
    args = parser.parse_args()
    if len(locales_module.available_locales()) < 2:
        print(f"Une seule langue ({locales_module.available_locales()}) : rien à comparer.")
        return 0
    if args.update_baseline:
        return update_baseline()

    morts, partout = measure()
    entries = dead_entries(morts)
    listed = read_baseline()
    new = sorted(set(entries) - listed)
    filled = sorted(listed - set(entries))

    if args.json:
        print(json.dumps({"dead": {e: entries[e] for e in sorted(entries)}, "new": new, "filled_still_listed": filled,
                          "empty_everywhere": sorted(partout), "measured_otherwise": MESURE_AUTREMENT}, indent=2))
        return 1 if new or filled else 0

    if not new and not filled:
        print(f"Locale coverage audit OK — {len(entries)} entrée(s) morte(s), toutes au plancher "
              f"(en attente de capture), {len(partout)} propriété(s) vide(s) partout, "
              f"{len(MESURE_AUTREMENT)} atteinte(s) autrement (mesuré)")
        return 0
    print("Locale coverage audit : une entrée de locale vide ne retombe PAS sur l'autre langue, le contrôle est injoignable.")
    for entry in new:
        print(_line(entry, entries[entry], "est vide dans cette langue et pleine dans une autre, absente du plancher : "
                    "la remplir depuis une capture réelle dans cette langue"))
    for entry in filled:
        langue, cle = entry.split(":", 1)
        print(f" - {_locale_file(langue)}: {cle} n'est plus morte et reste au plancher : "
              f"`python scripts/audits/audit_locale_coverage.py --update-baseline` la retire")
    return 1


if __name__ == "__main__":
    sys.exit(main())
