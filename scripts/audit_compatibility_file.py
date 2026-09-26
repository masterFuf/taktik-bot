"""Audit COMPATIBILITY.md against the sources it is generated from.

COMPATIBILITY.md lists the Instagram and TikTok versions the bot supports, with a download search for
the original APK of each. It is never written by hand: it is rendered from
``taktik/core/compat/data/app_builds.json`` (installable builds and architectures) and
``taktik/core/compat/data/overrides/<app>.yaml`` (selector reference and version adjustments), the
same sources the desktop app generates its version list from. This audit fails when the published
file and those sources disagree.

Run: ``python scripts/audit_compatibility_file.py`` (check), ``--write`` to regenerate,
``--json`` to print the sources as the desktop app reads them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loguru import logger  # noqa: E402

# The registry logs every override file it loads; the audit prints its own verdict.
logger.remove()
logger.add(sys.stderr, level="WARNING")

from taktik.core.compat.selectors.supported_versions import (  # noqa: E402
    COMPATIBILITY_PATH,
    REGENERATE_COMMAND,
    CompatibilitySourceError,
    as_json,
    compatibility_file_drift,
    load_supported_versions,
    render_compatibility_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="regenerate COMPATIBILITY.md")
    parser.add_argument("--json", action="store_true", help="print the sources as JSON")
    args = parser.parse_args()

    try:
        supported = load_supported_versions()
    except CompatibilitySourceError as error:
        print(f"[compatibility] sources are inconsistent: {error}")
        return 1

    if args.json:
        print(json.dumps(as_json(supported)))
        return 0

    if args.write:
        COMPATIBILITY_PATH.write_text(render_compatibility_markdown(supported), encoding="utf-8", newline="\n")
        print(f"[compatibility] written: {COMPATIBILITY_PATH.name}")
        return 0

    drift = compatibility_file_drift()
    if drift:
        print(f"[compatibility] FAILED: {drift}. Regenerate it: {REGENERATE_COMMAND}")
        return 1
    summary = " ; ".join(
        f"{s.name} reference {s.reference}, {len(s.override_versions)} adjusted, {len(s.builds)} installable"
        for s in supported.apps
    )
    print(f"[compatibility] OK - {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
