"""Audit COMPATIBILITY.md against the sources it is generated from.

COMPATIBILITY.md lists the Instagram and TikTok versions the bot supports, with a download search for
the original APK of each. It is never written by hand: it is rendered from
``taktik/core/compat/data/app_builds.json`` (installable builds, their validation and architectures) and
``taktik/core/compat/data/overrides/<app>.yaml`` (selector reference and version adjustments), the
same sources the desktop app generates its version list from. This audit fails when the published
file and those sources disagree.

Run: ``python scripts/audits/audit_compatibility_file.py`` (check), ``--write`` to regenerate,
``--json`` to print the sources as the desktop app reads them, ``--promote <verdict.json>`` to record
the verdict the desktop app's ``npm run lab:exit -- --promote`` hands the bot (then ``--write``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from loguru import logger  # noqa: E402

# The registry logs every override file it loads; the audit prints its own verdict.
logger.remove()
logger.add(sys.stderr, level="WARNING")

from taktik.core.compat.selectors.supported_versions import (  # noqa: E402
    BUILDS_PATH,
    COMPATIBILITY_PATH,
    REGENERATE_COMMAND,
    CompatibilitySourceError,
    as_json,
    compatibility_file_drift,
    load_supported_versions,
    promote_file,
    render_compatibility_markdown,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="regenerate COMPATIBILITY.md")
    parser.add_argument("--json", action="store_true", help="print the sources as JSON")
    parser.add_argument("--promote", metavar="VERDICT", help="record the validation blocks of a verdict file in app_builds.json")
    args = parser.parse_args(argv)

    if args.promote:
        try:
            promoted = promote_file(Path(args.promote), BUILDS_PATH)
        except CompatibilitySourceError as error:
            print(f"[compatibility] promotion refused, app_builds.json left as it was: {error}")
            return 1
        names = ", ".join(f"{app} {version}" for app, version in promoted)
        print(f"[compatibility] promoted: {names}. Now regenerate: {REGENERATE_COMMAND}")
        return 0

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
