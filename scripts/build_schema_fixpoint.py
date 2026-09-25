"""Rebuild the 1.9.8 schema of a new base from the current code of both halves.

    python scripts/build_schema_fixpoint.py --out PATH [--bot-first]

An empty file is opened by the desktop app, the bot, then the app again (or the bot first),
until the schema stops changing: that is the schema a new 1.9.8 base ends with. The bot's side
runs its own un-numbered steps; the app's side runs `schema.ts` + `migrations.ts` bundled by the
app's esbuild and executed on node:sqlite through `schema_fixpoint/app_shim.cjs`, never in
Electron and never on a real base.

Needs the desktop app next to core (`../app`, as for check_bridge_manifest.py) with its
node_modules, and Node 22.5 or later.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parent
APP = ROOT / "app"
SHIM = Path(__file__).resolve().parent / "schema_fixpoint" / "app_shim.cjs"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from taktik.core.database.local.versions.backup import remove_database_file  # noqa: E402
from taktik.core.database.local.versions.fingerprint import fingerprint  # noqa: E402
from taktik.core.database.local.versions.legacy import run_bot_legacy_steps  # noqa: E402
from taktik.core.database.local.versions.sql_text import strip_comments  # noqa: E402

MAX_OPENINGS = 9


class FixpointUnavailable(RuntimeError):
    """The app, its node_modules or a recent enough Node is missing."""


def _esbuild() -> Path:
    for name in ("esbuild.cmd", "esbuild"):
        candidate = APP / "node_modules" / ".bin" / name
        if candidate.exists():
            return candidate
    raise FixpointUnavailable(f"esbuild not found under {APP / 'node_modules'}")


def requirements_missing() -> Optional[str]:
    if not (APP / "electron" / "database" / "migrations.ts").exists():
        return f"desktop app not found next to core ({APP})"
    try:
        _esbuild()
    except FixpointUnavailable as exc:
        return str(exc)
    node = shutil.which("node")
    if not node:
        return "node not found"
    probe = subprocess.run([node, "-e", "require('node:sqlite')"], capture_output=True)
    if probe.returncode != 0:
        return "node:sqlite unavailable (Node 22.5 or later needed)"
    return None


def bundle_app(workdir: Path) -> Path:
    database = (APP / "electron" / "database").as_posix()
    entry = workdir / "entry.ts"
    entry.write_text(
        f"import {{ createTables }} from '{database}/schema'\n"
        f"import {{ runMigrations }} from '{database}/migrations'\n"
        "export function bootstrap(db: unknown): void {\n"
        "  // eslint-disable-next-line @typescript-eslint/no-explicit-any\n"
        "  createTables(db as any)\n"
        "  // eslint-disable-next-line @typescript-eslint/no-explicit-any\n"
        "  runMigrations(db as any)\n"
        "}\n",
        encoding="utf-8",
        newline="",
    )
    bundle = workdir / "bundle.cjs"
    proc = subprocess.run(
        [str(_esbuild()), str(entry), "--bundle", "--platform=node", "--format=cjs",
         "--external:better-sqlite3", "--external:electron", f"--outfile={bundle}", "--log-level=error"],
        capture_output=True, cwd=str(APP), shell=False,
    )
    if proc.returncode != 0:
        raise FixpointUnavailable("esbuild failed: " + proc.stderr.decode("utf-8", "replace")[-2000:])
    return bundle


def run_app(bundle: Path, db: Path) -> Dict:
    proc = subprocess.run([shutil.which("node"), str(SHIM), str(bundle), str(db)], capture_output=True)
    lines = [line for line in proc.stdout.decode("utf-8", "replace").splitlines() if line.startswith("{")]
    if proc.returncode != 0 or not lines:
        raise RuntimeError("app migrations did not run: " + proc.stderr.decode("utf-8", "replace")[-2000:])
    result = json.loads(lines[-1])
    if result.get("error"):
        raise RuntimeError("app migrations threw: " + result["error"][:2000])
    return result


def schema_state(db: Path):
    conn = sqlite3.connect(str(db))
    try:
        objects = {
            (typ, name): " ".join(strip_comments(sql or "").split())
            for typ, name, sql in conn.execute("SELECT type, name, sql FROM sqlite_master")
        }
        return objects, fingerprint(conn)
    finally:
        conn.close()


def build(out: Path, *, bot_first: bool = False, workdir: Optional[Path] = None) -> List[str]:
    """Open an empty base alternately until a full round changes nothing. Returns the openings."""
    missing = requirements_missing()
    if missing:
        raise FixpointUnavailable(missing)
    if "roaming" in str(out.resolve()).lower():
        raise SystemExit("refused: the fixpoint is never built in the app's data folder")
    own_workdir = workdir is None
    workdir = workdir or Path(tempfile.mkdtemp(prefix="schema-fixpoint-"))
    try:
        bundle = bundle_app(workdir)
        remove_database_file(out)
        order = ["bot", "app"] if bot_first else ["app", "bot"]
        openings: List[str] = []
        states = []
        for index in range(MAX_OPENINGS):
            side = order[index % 2]
            if side == "app":
                run_app(bundle, out)
            else:
                run_bot_legacy_steps(out)
            openings.append(side)
            states.append(schema_state(out))
            if len(states) >= 3 and states[-1] == states[-2] == states[-3]:
                return openings
        raise RuntimeError(f"the schema still changes after {MAX_OPENINGS} openings")
    finally:
        if own_workdir:
            shutil.rmtree(workdir, ignore_errors=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bot-first", action="store_true")
    args = parser.parse_args(argv)
    try:
        openings = build(args.out, bot_first=args.bot_first)
    except FixpointUnavailable as exc:
        print(f"cannot build the fixpoint: {exc}")
        return 2
    print(f"{args.out}: stable after {len(openings)} openings ({', '.join(openings)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
