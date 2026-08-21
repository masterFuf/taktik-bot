"""Census of everything the product can do, and where the layers disagree.

Four independent classifications describe the same capabilities, and none of them is a
subset of another: the JSON manifest (declared intent), the Agent registry (what has a
runnable handler), the bridges manifest (the OTHER execution path, the one Electron
drives), and the Cartography Lab catalogue (atomic screen capabilities). A fifth, the
renderer's page and session unions, decides what an operator can actually reach.

Nobody can hold four lists in their head, which is why a capability keeps landing in
whichever drawer was open at the time. This prints the four side by side and names the
disagreements, so a reorganisation argues from counts rather than from memory.

Deliberately NOT a gate: exit code is always 0. Several disagreements listed here are
legitimate design (a `panel` family is UI-only and has no handler by construction; the
`planned` family is a declared TODO). Failing the build on them would freeze the gap in
place, and an audit that cries wolf stops being read. `audit_workflow_registry.py` is the
gate; this is the map.

The renderer sections are skipped when the app repository is absent — the bot is meant to
stay usable standalone, and a census that crashes without the desktop app would say the
opposite.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parent
APP = ROOT / "app"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(CORE / "scripts"))

MANIFEST_PATH = CORE / "workflows.manifest.json"
BRIDGES_MANIFEST_PATH = CORE / "bridges" / "bridges.manifest.json"
LAB_ACTIONS_DIR = CORE / "bridges" / "compat" / "diagnostics" / "actions"

CARTOGRAPHY_PATH = APP / "src" / "features" / "tools" / "cartography" / "data" / "cartography.json"
LAYOUT_TYPES_PATH = APP / "src" / "app" / "types" / "layout.types.ts"
NAV_HUBS_PATH = APP / "src" / "app" / "layout" / "navHubs.ts"
WORKFLOW_TYPES_PATH = APP / "src" / "app" / "types" / "workflow.types.ts"

# Families that describe where a workflow is DISPLAYED, not what it does. They carry no
# handler by construction, so counting them as unimplemented would be noise.
UI_ONLY_FAMILIES = {"panel", "live_panel"}
# A family that declares intent rather than capability. Its own name says so.
DECLARED_TODO_FAMILIES = {"planned"}

ACTION_RE = re.compile(r'^@action\("([^"]+)"\)', re.M)
TS_ARRAY_RE = re.compile(r"export const (?P<name>[A-Z0-9_]+)[^=]*= \[(?P<body>.*?)\]", re.S)
TS_UNION_RE = re.compile(r"export type GlobalPage = (?P<body>[^\n]+)")
TS_STRING_RE = re.compile(r"'([^']+)'")


def strip_ts_comments(body: str) -> str:
    """Drop TS comments before reading string literals.

    Prose inside these arrays carries apostrophes ("the hub's live-stats grid"), and every
    one of them opens a bogus literal. Same reason, same fix as in
    `audit_workflow_registry.py` — kept local rather than imported so this census still
    runs when that audit is refactored.
    """
    while "/*" in body and "*/" in body:
        start = body.index("/*")
        body = body[:start] + body[body.index("*/", start) + 2:]
    kept = []
    for line in body.splitlines():
        marker = line.find("//")
        kept.append(line if marker == -1 else line[:marker])
    return "\n".join(kept)


def rule(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# --------------------------------------------------------------------------- runs


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))


def load_registry_ids() -> tuple[list[str], list[tuple[str, str]]]:
    """The workflows that have a runnable Agent handler.

    Reuses `audit_cli_coverage.build_full_registry` rather than restating its registrar
    list: that list changes whenever a platform gains a handler module, and two copies of
    it would disagree the first time one is updated alone.
    """
    from audit_cli_coverage import build_full_registry, registered_ids

    registry, failures = build_full_registry()
    return registered_ids(registry), failures


def report_runs(manifest: dict, registry_ids: list[str]) -> list[str]:
    """Declared workflows vs runnable handlers. Returns the disagreement lines."""
    rule("1. RUNS - ce qui se declare, ce qui s'execute")
    registered = set(registry_ids)
    findings: list[str] = []

    print(f"{'plateforme.famille':<34} {'declares':>9} {'handler':>9}  ecart")
    print("-" * 78)
    for platform, families in manifest.items():
        for family, workflows in families.items():
            declared = list(workflows)
            if family in UI_ONLY_FAMILIES:
                print(f"{platform + '.' + family:<34} {len(declared):>9} {'-':>9}  (affichage seul)")
                continue
            if family in DECLARED_TODO_FAMILIES:
                print(f"{platform + '.' + family:<34} {len(declared):>9} {'-':>9}  (TODO declare)")
                continue
            has_handler = [w for w in declared if f"{platform}.{family}.{w}" in registered]
            missing = [w for w in declared if w not in has_handler]
            note = "" if not missing else "sans handler: " + ", ".join(missing)
            print(f"{platform + '.' + family:<34} {len(declared):>9} {len(has_handler):>9}  {note}")
            if missing:
                findings.append(
                    f"{platform}.{family}: {len(missing)} workflow(s) declares sans handler Agent "
                    f"({', '.join(missing)})"
                )

    declared_ids = {
        f"{platform}.{family}.{workflow}"
        for platform, families in manifest.items()
        for family, workflows in families.items()
        for workflow in workflows
    }
    undeclared = sorted(registered - declared_ids)
    if undeclared:
        print()
        print("Handlers Agent absents du manifest :")
        for workflow_id in undeclared:
            print(f"  - {workflow_id}")
        findings.append(f"{len(undeclared)} handler(s) Agent absents du manifest")
    return findings


def report_bridges() -> list[str]:
    """The second execution path, the one Electron drives.

    A workflow can be perfectly implemented and still have no Agent handler, because it is
    reached through a bridge instead. Listing the bridges next to the registry is what
    stops "no handler" from being read as "not implemented".
    """
    rule("2. BRIDGES - le second chemin d'execution (pilote par Electron)")
    if not BRIDGES_MANIFEST_PATH.exists():
        print("bridges.manifest.json introuvable.")
        return []
    bridges = json.loads(BRIDGES_MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    total = 0
    for platform, entries in bridges.items():
        names = sorted(entries) if isinstance(entries, dict) else []
        total += len(names)
        print(f"  {platform:<12} {len(names):>2} : {', '.join(names)}")
    print(f"\n  total : {total} bridges declares")
    return []


# ---------------------------------------------------------------------- capabilities


def load_lab_actions() -> dict[str, list[tuple[str, int]]]:
    """Every `@action` id the bot exposes, per platform, with its source line.

    The line number is kept because the registry is a plain dict assignment
    (`self.actions[action_id] = fn`): a duplicate id silently shadows the earlier one, and
    finding which of the two survived needs the file position.
    """
    per_platform: dict[str, list[tuple[str, int]]] = {}
    for path in sorted(LAB_ACTIONS_DIR.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        platform = path.parent.name
        if platform == "actions":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in ACTION_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            per_platform.setdefault(platform, []).append((match.group(1), line))
    return per_platform


def report_capabilities(lab: dict[str, list[tuple[str, int]]]) -> list[str]:
    rule("3. CAPACITES - les gestes atomiques du Cartography Lab")
    findings: list[str] = []

    for platform, entries in sorted(lab.items()):
        ids = [action_id for action_id, _ in entries]
        domains: dict[str, int] = {}
        for action_id in ids:
            domains[action_id.split(".", 1)[0]] = domains.get(action_id.split(".", 1)[0], 0) + 1
        top = ", ".join(f"{d}:{n}" for d, n in sorted(domains.items(), key=lambda kv: -kv[1]))
        print(f"  {platform:<12} {len(ids):>3} actions sur {len(domains)} domaines")
        print(f"               {top}")

        seen: dict[str, int] = {}
        for action_id, line in entries:
            if action_id in seen:
                findings.append(
                    f"{platform}: '{action_id}' declare deux fois (lignes {seen[action_id]} et "
                    f"{line}) - la seconde ecrase la premiere en silence"
                )
            seen[action_id] = line

    total = sum(len(v) for v in lab.values())
    print(f"\n  total : {total} capacites cablees au Lab")
    return findings


def report_lab_mirror(lab: dict[str, list[tuple[str, int]]]) -> list[str]:
    """The front catalogue must carry the SAME id as the bot action (AGENTS rule).

    An action the bot exposes but the front does not list is a capability no operator can
    test; a front entry with no bot action behind it is a dead button.
    """
    rule("4. MIROIR LAB - bot <-> catalogue front (regle 'meme id')")
    if not CARTOGRAPHY_PATH.exists():
        print("Depot app absent - section ignoree.")
        return []

    catalogue = json.loads(CARTOGRAPHY_PATH.read_text(encoding="utf-8-sig"))
    front_ids = set(catalogue.get("actionCatalog", {}))
    bot_ids = {action_id for entries in lab.values() for action_id, _ in entries}

    missing_front = sorted(bot_ids - front_ids)
    orphan_front = sorted(front_ids - bot_ids)

    print(f"  actions bot            : {len(bot_ids)}")
    print(f"  entrees catalogue front: {len(front_ids)}")
    print(f"  sans miroir front      : {len(missing_front)}")
    print(f"  front sans action bot  : {len(orphan_front)}")

    if missing_front:
        print("\n  Capacites non testables depuis le Lab :")
        for action_id in missing_front:
            print(f"    - {action_id}")
    if orphan_front:
        print("\n  Entrees front sans action bot :")
        for action_id in orphan_front:
            print(f"    - {action_id}")

    findings = []
    if missing_front:
        findings.append(f"{len(missing_front)} capacite(s) bot sans miroir dans le catalogue front")
    if orphan_front:
        findings.append(f"{len(orphan_front)} entree(s) du catalogue front sans action bot")
    return findings


# --------------------------------------------------------------------------- surfaces


def report_surfaces() -> list[str]:
    """Pages an operator can open, and how they are grouped into hubs."""
    rule("5. SURFACES - les pages de l'app et leurs hubs")
    if not LAYOUT_TYPES_PATH.exists() or not NAV_HUBS_PATH.exists():
        print("Depot app absent - section ignoree.")
        return []

    union = TS_UNION_RE.search(LAYOUT_TYPES_PATH.read_text(encoding="utf-8-sig"))
    pages = TS_STRING_RE.findall(union.group("body")) if union else []

    hubs_text = strip_ts_comments(NAV_HUBS_PATH.read_text(encoding="utf-8-sig"))
    hubs: dict[str, list[str]] = {}
    for match in TS_ARRAY_RE.finditer(hubs_text):
        hubs[match.group("name")] = TS_STRING_RE.findall(match.group("body"))

    grouped: set[str] = set()
    for name, members in hubs.items():
        grouped.update(members)
        print(f"  {name:<22} {len(members):>2} : {', '.join(members)}")

    orphans = [p for p in pages if p not in grouped]
    print(f"\n  total pages : {len(pages)}")
    print(f"  hors hub    : {len(orphans)} : {', '.join(orphans)}")

    findings = []
    admin = hubs.get("ADMIN_TOOL_PAGES", [])
    if len(admin) > 1:
        findings.append(
            f"ADMIN_TOOL_PAGES melange {len(admin)} pages sans parente ({', '.join(admin)}) - "
            "c'est un tiroir, pas une categorie"
        )
    return findings


def report_sessions(manifest: dict) -> list[str]:
    """Session families vs the panel families they are supposed to mirror."""
    rule("6. SESSIONS - les familles de run tracees")
    if not WORKFLOW_TYPES_PATH.exists():
        print("Depot app absent - section ignoree.")
        return []

    text = strip_ts_comments(WORKFLOW_TYPES_PATH.read_text(encoding="utf-8-sig"))
    arrays = {
        match.group("name"): TS_STRING_RE.findall(match.group("body"))
        for match in TS_ARRAY_RE.finditer(text)
    }
    sessions = arrays.get("SESSION_WORKFLOW_TYPES", [])
    legacy = arrays.get("LEGACY_WORKFLOW_TYPES", [])

    panels = manifest["instagram"]["panel"] + manifest["tiktok"]["panel"]
    missing = [w for w in panels if w not in sessions]

    print(f"  types de session   : {len(sessions)} : {', '.join(sessions)}")
    print(f"  types legacy       : {len(legacy)} : {', '.join(legacy)}")
    print(f"  panels sans session: {len(missing)} : {', '.join(missing) or '-'}")

    findings = []
    if missing:
        findings.append(f"{len(missing)} panel(s) sans type de session - leurs runs comptent en 'other'")
    if legacy:
        findings.append(f"{len(legacy)} type(s) de session marques legacy et toujours en place")
    return findings


# ------------------------------------------------------------------------------ main


def main() -> int:
    manifest = load_manifest()
    registry_ids, failures = load_registry_ids()

    print("=" * 78)
    print("INVENTAIRE DES CAPACITES TAKTIK")
    print("=" * 78)
    print(f"  manifest workflows : {MANIFEST_PATH.relative_to(ROOT)}")
    print(f"  depot app          : {'present' if CARTOGRAPHY_PATH.exists() else 'ABSENT'}")
    if failures:
        print("\n  Registrars en echec (le recensement est incomplet) :")
        for label, error in failures:
            print(f"    - {label}: {error}")

    lab = load_lab_actions()

    findings: list[str] = []
    findings += report_runs(manifest, registry_ids)
    findings += report_bridges()
    findings += report_capabilities(lab)
    findings += report_lab_mirror(lab)
    findings += report_surfaces()
    findings += report_sessions(manifest)

    rule("RECAP - les desaccords entre couches")
    if not findings:
        print("  Aucun desaccord.")
    for finding in findings:
        print(f"  - {finding}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
