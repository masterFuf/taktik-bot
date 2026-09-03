"""La profondeur d'imbrication ne doit plus augmenter.

Mesure sur les fonctions du moteur : chaque `if`, `for`, `while`, `try` ou `with` imbriqué ajoute
un niveau. Le corpus est sain — **profondeur médiane 1** — et ce sont les extrêmes qui coûtent :
un humain suit trois ou quatre niveaux, à quatorze il lui faut un crayon.

**Ce garde-fou ne demande pas de refactorer.** Il fige les fonctions profondes qui existent
aujourd'hui dans une liste nommée, et refuse qu'une nouvelle apparaisse ou qu'une existante
s'aggrave. Le refactor de celles qui restent se fait quand elles ont un filet — `cli()` est un menu
interactif dont les tests couvrent les sous-commandes et pas le menu, `ensure_account_added()` est
une machine à états dont aucun test ne joue les transitions. Les refactorer sans ce filet
échangerait une dette lisible contre un risque invisible.

Le plafond baisse à mesure que les fonctions sont traitées : `_close_problematic_page` est passée
de 14 à 3 le 2026-09-03 et a quitté cette liste.

Usage :
    python scripts/audit_nesting_depth.py          # vert / rouge
    python scripts/audit_nesting_depth.py --list   # les dix plus profondes
"""

from __future__ import annotations

import ast
import io
import os
import sys

RACINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Au-delà, une fonction demande un crayon pour être suivie.
SEUIL = 8

#: Ce qui existe aujourd'hui et qui attend son filet. Une entrée par fonction, avec la profondeur
#: constatée : la dépasser fait rougir l'audit, la réduire demande de mettre la liste à jour.
#: Volontairement nominatif — un seuil global sans liste laisserait une nouvelle fonction profonde
#: se glisser sous le plafond des anciennes.
TOLERE = {
    # Les trois que l'audit G-04 a nommees : un menu interactif, une machine a etats, un workflow
    # d'inscription. Chacune attend son filet — leurs tests couvrent les sous-commandes ou les
    # handlers, jamais les transitions elles-memes.
    "taktik/cli/main.py::cli": 15,
    "taktik/core/app/email/gmail/workflows/account.py::ensure_account_added": 17,
    "taktik/core/social_media/tiktok/workflows/management/signup/signup_workflow.py::execute": 12,
    # Les sept autres au-dessus du seuil le jour ou ce garde-fou a ete pose. Les nommer plutot que
    # de relever le seuil : un plafond global assez haut pour les couvrir laisserait passer une
    # nouvelle fonction profonde sans rien dire.
    "taktik/core/social_media/instagram/workflows/core/config_builder.py::build_instagram_automation_config": 11,
    "taktik/core/social_media/instagram/workflows/core/workflow_runner.py::run_workflow_step": 11,
    "taktik/core/social_media/instagram/actions/business/workflows/unfollow/workflow.py::run_unfollow_workflow": 10,
    "taktik/cli/commands/management_cmds.py::dm_read_all": 9,
    "taktik/core/social_media/instagram/actions/business/workflows/hashtag/mixins/post_finder.py::_extract_current_post_metadata": 9,
    "taktik/core/social_media/instagram/ui/watchdog.py::_attempt_recovery": 9,
    "taktik/core/social_media/instagram/workflows/post_scraping/engagement_scraping.py::_scrape_comments": 9,
}

IMBRIQUANTS = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.AsyncFor, ast.AsyncWith)


def profondeur(node: ast.AST, niveau: int = 0) -> int:
    maxi = niveau
    for enfant in ast.iter_child_nodes(node):
        pas = 1 if isinstance(enfant, IMBRIQUANTS) else 0
        maxi = max(maxi, profondeur(enfant, niveau + pas))
    return maxi


def fonctions():
    for dossier, _, fichiers in os.walk(os.path.join(RACINE, "taktik")):
        if "__pycache__" in dossier:
            continue
        for fichier in fichiers:
            if not fichier.endswith(".py"):
                continue
            chemin = os.path.join(dossier, fichier)
            relatif = os.path.relpath(chemin, RACINE).replace(os.sep, "/")
            try:
                arbre = ast.parse(io.open(chemin, encoding="utf-8").read())
            except Exception:
                continue
            for noeud in ast.walk(arbre):
                if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{relatif}::{noeud.name}", profondeur(noeud)


def main() -> int:
    mesures = sorted(fonctions(), key=lambda kv: kv[1], reverse=True)

    if "--list" in sys.argv:
        print("Les dix fonctions les plus imbriquees :")
        for nom, p in mesures[:10]:
            marque = "  (tolere)" if nom in TOLERE else ""
            print(f"  {p:3d}  {nom}{marque}")
        mediane = sorted(p for _, p in mesures)[len(mesures) // 2]
        print(f"\n{len(mesures)} fonctions, profondeur mediane {mediane}.")
        return 0

    nouvelles = []
    aggravees = []
    ameliorees = []
    for nom, p in mesures:
        plafond = TOLERE.get(nom)
        if plafond is None:
            if p > SEUIL:
                nouvelles.append((nom, p))
        elif p > plafond:
            aggravees.append((nom, p, plafond))
        elif p < plafond:
            ameliorees.append((nom, p, plafond))

    for nom, p, plafond in ameliorees:
        print(f"  ameliore : {nom} passe de {plafond} a {p} — mettre TOLERE a jour")

    if not nouvelles and not aggravees:
        print(f"Nesting depth OK ({len(mesures)} fonctions, seuil {SEUIL}, "
              f"{len(TOLERE)} tolerance(s) nommee(s))")
        return 0

    for nom, p in nouvelles:
        print(f"ECHEC : {nom} atteint {p} niveaux (seuil {SEUIL}). "
              f"Un dispatch par chaine se remplace par une table.")
    for nom, p, plafond in aggravees:
        print(f"ECHEC : {nom} passe de {plafond} a {p} niveaux — cette fonction devait baisser.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
