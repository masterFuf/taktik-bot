"""Ce qui manque encore, et ce que les runs ont fini par capturer.

Deux listes se rejoignent ici.

D'un côté, les contrôles **encore injoignables** : `audit_locale_coverage.py` compte les entrées
vides dans une langue et pleines dans une autre, et chacune veut dire qu'un bouton ne sera jamais
trouvé sur un téléphone de cette langue. On ne peut pas les écrire tant qu'on n'a pas vu l'écran,
et un popup ne se convoque pas.

De l'autre, les écrans que les runs ont **gardés au moment où ils échouaient** — le seul moment où
la capture vaut quelque chose, puisque c'est l'application qui dit « j'affiche ce que ton catalogue
ne sait pas nommer » (`diagnostics/miss_capture.py`).

Ce script rapproche les deux : pour chaque contrôle mort, il cherche dans les captures accumulées
un écran qui porte un libellé plausible. La réponse est une PISTE, pas un sélecteur : c'est un
humain qui reconnaît le bon nœud, et un sélecteur écrit depuis une ressemblance vaut moins que rien
parce qu'il a l'air d'une preuve.

    python scripts/mine_captured_screens.py            # l'état des lieux
    python scripts/mine_captured_screens.py --details  # les nœuds candidats, un par un
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from taktik.core.shared.diagnostics.miss_capture import SURFACE
from taktik.core.shared.diagnostics.surface_capture import captures_dir

#: Contrôle encore vide -> les mots qui trahissent son écran. Volontairement LARGES : le but est
#: de trouver l'écran, pas d'écrire le sélecteur. Un mot trop précis ne trouverait que ce qu'on
#: sait déjà.
PISTES = {
    "popup.suggestion_not_interested": ("intéress", "interess", "suggér", "Non merci"),
    "popup.collections_not_now": ("Pas maintenant", "Plus tard", "collection"),
    "profile.unable_to_send_message": ("Impossible d'envoyer", "ne peut pas recevoir", "message"),
    "video_state.user_followed_indicator": ("Suivi(e)", "Ami(e)s", "Se désabonner"),
    "country_picker.screen_indicator": ("pays", "région"),
    # Cherché sur appareil le 2026-09-03, en 43.1.4 ET en 46.6.3, sur les onglets « Top » et
    # « Utilisateurs » d'une recherche, quatre défilements chacun : ni l'id anglais `:id/sm6`, ni
    # un libellé de ce genre n'apparaissent. Les onglets de résultats semblent avoir remplacé le
    # bouton. Ces mots sont donc une PISTE pour le jour où un run le rencontrera ailleurs — pas
    # une description de ce qu'on a vu.
    "search.view_all_button": ("Voir tout", "Tout afficher", "Afficher tout", "Voir plus"),
}

_TEXTE = re.compile(r'(?:\stext|content-desc)="([^"]{2,80})"')
_ID = re.compile(r'resource-id="[^"]*/([^"]+)"')


def dossier_captures(plateforme: str = "tiktok") -> str:
    """Le MÊME dossier que celui où l'écrivain dépose — demandé à lui, jamais réécrit.

    Un chemin recopié ici aurait cherché à côté sans rien dire : la première mesure a rendu
    « 0 capture » alors que le fichier venait d'être écrit deux lignes plus haut.
    """
    return captures_dir(plateforme, SURFACE)


def corpus(plateforme: str = "tiktok") -> list:
    """Les captures d'échec accumulées par les runs, la plus récente d'abord."""
    dossier = dossier_captures(plateforme)
    if not os.path.isdir(dossier):
        return []
    fichiers = glob.glob(os.path.join(dossier, "**", "*.xml"), recursive=True)
    return sorted(fichiers, key=os.path.getmtime, reverse=True)


def journal() -> list:
    """La série append-only : une ligne par capture, même celles sans fichier."""
    lignes = []
    dossier = dossier_captures()
    if not os.path.isdir(dossier):
        return lignes
    for chemin in glob.glob(os.path.join(dossier, "**", "captures.jsonl"), recursive=True):
        try:
            for ligne in io.open(chemin, encoding="utf-8"):
                ligne = ligne.strip()
                if ligne:
                    lignes.append(json.loads(ligne))
        except Exception:
            continue
    return lignes


def manquants() -> dict:
    """Les contrôles morts, mesurés — jamais une liste recopiée à la main."""
    # L'audit tourne en SOUS-PROCESSUS a dessein : il pose la locale active globalement, et la
    # poser dans ce processus fausserait tout ce qui suit.
    import subprocess
    racine = Path(__file__).resolve().parents[1]
    out = subprocess.run(
        [sys.executable, str(racine / "scripts" / "audit_locale_coverage.py"), "--json"],
        capture_output=True, cwd=str(racine),
    ).stdout.decode("utf-8", "replace")
    try:
        return json.loads(out).get("dead", {})
    except Exception:
        return {}


def plateforme_du_dump(dump: str) -> str:
    """La plateforme dont cet écran vient VRAIMENT, lue dans le dump.

    Le dossier ne suffit pas : jusqu'au 2026-09-03 l'appelant partagé ne passait pas sa plateforme
    à `capturer_echec`, dont le défaut valait « tiktok » — donc les écrans Instagram atterrissaient
    ici. Sans ce filtre, l'outil proposait `message_composer_container` et
    `profile_header_following_stacked_familiar`, deux identifiants **Instagram**, comme pistes pour
    des contrôles TikTok. Une piste venue de la mauvaise application est pire qu'aucune piste : elle
    ressemble à une preuve.

    Le paquet le plus fréquent hors barre système : le premier `package=` d'un dump est celui de
    `com.android.systemui`, pas celui de l'application à l'écran.
    """
    from collections import Counter

    from taktik.core.clone.packages.package_map import belongs_to_platform

    paquets = Counter(
        p for p in re.findall(r'package="([^"]+)"', dump)
        if p not in ("com.android.systemui", "android")
    )
    for paquet, _ in paquets.most_common(3):
        for plateforme in ("tiktok", "instagram"):
            if belongs_to_platform(paquet, plateforme):
                return plateforme
    return "inconnue"


def candidats(chemin: str, mots, plateforme_attendue: str = "tiktok") -> list:
    """Les nœuds de cette capture dont le libellé porte un des mots."""
    try:
        dump = io.open(chemin, encoding="utf-8", errors="replace").read()
    except Exception:
        return []
    if plateforme_du_dump(dump) not in (plateforme_attendue, "inconnue"):
        return []
    trouves = []
    for noeud in re.findall(r"<node[^>]*/?>", dump):
        libelles = _TEXTE.findall(noeud)
        if not libelles:
            continue
        for libelle in libelles:
            if any(m.lower() in libelle.lower() for m in mots):
                rid = _ID.search(noeud)
                trouves.append(((rid.group(1) if rid else "-"), libelle))
                break
    return trouves


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--details", action="store_true", help="les nœuds candidats")
    args = parser.parse_args()

    captures = corpus()
    serie = journal()

    print(f"CAPTURES ACCUMULÉES : {len(captures)} fichier(s), {len(serie)} passage(s) enregistré(s)")
    if serie:
        cherchait = Counter()
        for r in serie:
            issue = (r.get("actionOutcome") or "")
            if issue.startswith("cherchait|"):
                cherchait[issue.split("|", 2)[-1][:70]] += 1
        if cherchait:
            print("\n  ce que les runs n'ont pas trouvé, du plus fréquent au moins :")
            for quoi, n in cherchait.most_common(8):
                print(f"    x{n:<4} {quoi}")

    morts = manquants()
    total = sum(len(v) for v in morts.values())
    print(f"\nCONTRÔLES ENCORE INJOIGNABLES : {total}")
    if not total:
        print("  aucun — rien à chercher dans les captures.")
        return 0

    for langue, propriétés in morts.items():
        for propriété in propriétés:
            clé = _clé_de(propriété)
            mots = PISTES.get(clé)
            print(f"\n  [{langue}] {propriété}")
            if not mots:
                print("      aucune piste déclarée — ajouter une entrée dans PISTES pour le chercher")
                continue
            vus = []
            for chemin in captures[:400]:
                trouves = candidats(chemin, mots)
                if trouves:
                    try:
                        origine = plateforme_du_dump(
                            io.open(chemin, encoding="utf-8", errors="replace").read())
                    except Exception:
                        origine = "inconnue"
                    vus.append((chemin, trouves, origine))
            if not vus:
                print(f"      pas encore vu   (mots cherchés : {', '.join(mots)})")
                continue
            print(f"      TROUVÉ dans {len(vus)} capture(s) :")
            for chemin, trouves, origine in vus[:3]:
                marque = "" if origine == "tiktok" else f"   [ecran {origine} — a lire avec prudence]"
                print(f"        {os.path.basename(chemin)}{marque}")
                if args.details:
                    for rid, libelle in trouves[:4]:
                        print(f"           id={rid:<10} « {libelle} »")
    print("\n  Une piste n'est pas un sélecteur : ouvrir la capture, reconnaître le bon nœud,")
    print("  et vérifier qu'il sait dire NON sur les écrans où il ne doit pas répondre.")
    return 0


def _clé_de(propriété: str) -> str:
    """`PopupSelectors.collections_not_now` -> `popup.collections_not_now`."""
    classe, _, nom = propriété.partition(".")
    surface = re.sub(r"Selectors$", "", classe)
    surface = re.sub(r"(?<!^)(?=[A-Z])", "_", surface).lower()
    return f"{surface}.{nom}"


if __name__ == "__main__":
    sys.exit(main())
