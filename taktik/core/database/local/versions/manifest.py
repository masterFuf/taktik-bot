"""`schema_manifest.json`: the schema version this build expects, readable without Python.

The desktop app reads `schema_version` from it before opening the base. A test keeps the
committed file equal to what the catalog produces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Sequence

from .catalog import MIGRATIONS, VERSIONS_DIR, Migration, schema_version
from .fingerprint import digest
from .runner import baseline_fingerprint, target_fingerprint

MANIFEST_PATH = VERSIONS_DIR / "schema_manifest.json"


def build_manifest(catalog: Sequence[Migration] = MIGRATIONS) -> Dict:
    return {
        "schema_version": schema_version(catalog),
        "migrations": [
            {
                "version": m.version,
                "name": m.name,
                "kind": m.kind,
                "file": m.sql_file,
                "sha256": m.checksum(),
            }
            for m in catalog
        ],
        "baseline_fingerprint_sha256": digest(baseline_fingerprint(catalog)),
        "target_fingerprint_sha256": digest(target_fingerprint(catalog)),
    }


def render_manifest(manifest: Dict) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def load_manifest(path: Path = MANIFEST_PATH) -> Dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_manifest(path: Path = MANIFEST_PATH, catalog: Sequence[Migration] = MIGRATIONS) -> None:
    Path(path).write_text(render_manifest(build_manifest(catalog)), encoding="utf-8", newline="")


__all__ = ["MANIFEST_PATH", "build_manifest", "load_manifest", "render_manifest", "write_manifest"]
