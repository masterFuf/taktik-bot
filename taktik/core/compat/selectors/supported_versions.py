"""
The Instagram and TikTok versions TAKTIK supports, from the files the bot already runs on.

Three sources, none of them written twice:

- the selector reference: ``meta.baseline_version`` of ``compat/data/overrides/<app>.yaml``, the
  build the Python catalogues of ``ui/selectors/**`` describe;
- the version adjustments: the version keys of that same YAML, read by the bot's own registry;
- the installable builds: ``compat/data/app_builds.json`` (version, status, the one recommended
  build, the CPU architectures builds are installed for).

``COMPATIBILITY.md`` at the repository root and the desktop app's version list are both generated
from here. ``scripts/audit_compatibility_file.py`` fails when the published file and these sources
disagree.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import yaml

from .registry import VersionedSelectorRegistry

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUILDS_PATH = DATA_DIR / "app_builds.json"
OVERRIDES_DIR = DATA_DIR / "overrides"
REPO_ROOT = Path(__file__).resolve().parents[4]
COMPATIBILITY_PATH = REPO_ROOT / "COMPATIBILITY.md"

BUILD_STATUSES = ("validated", "testing")
# A search, never a guessed release page: the mirror's page slugs are not derivable from a version.
APKMIRROR_SEARCH = "https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s={query}"
REGENERATE_COMMAND = "python scripts/audit_compatibility_file.py --write"


class CompatibilitySourceError(ValueError):
    """The sources contradict themselves; nothing can be generated from them."""


@dataclass(frozen=True)
class AppBuild:
    version: str
    status: str
    recommended: bool = False


@dataclass(frozen=True)
class AppSupport:
    app: str
    name: str
    package: str
    reference: str
    override_versions: Tuple[str, ...]
    builds: Tuple[AppBuild, ...]


@dataclass(frozen=True)
class SupportedVersions:
    architectures: Tuple[str, ...]
    apps: Tuple[AppSupport, ...] = field(default_factory=tuple)

    def app(self, app: str) -> AppSupport:
        for support in self.apps:
            if support.app == app:
                return support
        raise KeyError(app)


def version_tuple(version: str) -> Optional[Tuple[int, ...]]:
    try:
        return tuple(int(part) for part in str(version).split("."))
    except ValueError:
        return None


def version_family(key: str) -> str:
    """The build family an override key stands for: its trailing ``.0`` segments mean any build
    (``447.0.0.0`` covers every 447), the rule the desktop app applies to the same keys."""
    parts = key.split(".")
    while len(parts) > 1 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)


def is_family_key(key: str) -> bool:
    return version_family(key) != key


def search_query(key: str) -> str:
    """What to search on the mirror: the exact build, or a family key down to three segments
    (``447.0.0.0`` -> ``447.0.0``), which is how released builds are numbered."""
    parts = key.split(".")
    while len(parts) > 3 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)


def apkmirror_search_url(app_name: str, version: str) -> str:
    return APKMIRROR_SEARCH.format(query=quote_plus(f"{app_name} {search_query(version)}"))


def _read_builds(data: Dict[str, Any], app: str) -> Tuple[AppBuild, ...]:
    raw = data.get("builds")
    if not isinstance(raw, list) or not raw:
        raise CompatibilitySourceError(f"{app}: no builds declared")
    builds = []
    seen = set()
    for entry in raw:
        version = str(entry.get("version", ""))
        status = entry.get("status")
        if version_tuple(version) is None:
            raise CompatibilitySourceError(f"{app}: {version!r} is not a dotted numeric version")
        if version in seen:
            raise CompatibilitySourceError(f"{app}: {version} declared twice")
        if status not in BUILD_STATUSES:
            raise CompatibilitySourceError(f"{app}: {version} has an unknown status {status!r}")
        seen.add(version)
        builds.append(AppBuild(version=version, status=status, recommended=bool(entry.get("recommended"))))

    recommended = [b for b in builds if b.recommended]
    if len(recommended) != 1:
        raise CompatibilitySourceError(f"{app}: exactly one recommended build expected, got {len(recommended)}")
    if recommended[0].status != "validated":
        raise CompatibilitySourceError(f"{app}: recommended build {recommended[0].version} is not validated")
    for newer, older in zip(builds, builds[1:]):
        if version_tuple(newer.version) <= version_tuple(older.version):
            raise CompatibilitySourceError(
                f"{app}: builds are not newest first ({newer.version} is declared above {older.version})"
            )
    return tuple(builds)


def _read_meta(app: str, overrides_dir: Path) -> Dict[str, Any]:
    path = overrides_dir / f"{app}.yaml"
    if not path.exists():
        raise CompatibilitySourceError(f"{app}: {path.name} is missing")
    meta = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("meta") or {}
    if not meta.get("baseline_version") or not meta.get("package"):
        raise CompatibilitySourceError(f"{app}: {path.name} declares no meta.baseline_version or meta.package")
    return meta


def load_supported_versions(
    builds_path: Path = BUILDS_PATH, overrides_dir: Path = OVERRIDES_DIR
) -> SupportedVersions:
    data = json.loads(Path(builds_path).read_text(encoding="utf-8"))
    architectures = data.get("architectures")
    if not isinstance(architectures, list) or not architectures or len(set(architectures)) != len(architectures):
        raise CompatibilitySourceError("architectures: a non-empty list without duplicates is expected")

    registry = VersionedSelectorRegistry(overrides_dir=str(overrides_dir))
    apps = []
    for app, entry in (data.get("apps") or {}).items():
        meta = _read_meta(app, Path(overrides_dir))
        registry.register_app(app, {}, "")
        overrides = tuple(registry.get_override_versions(app))
        for key in overrides:
            if version_tuple(key) is None:
                raise CompatibilitySourceError(f"{app}: override key {key!r} is not a version")
        apps.append(
            AppSupport(
                app=app,
                name=str(entry.get("name") or app),
                package=str(meta["package"]),
                reference=str(meta["baseline_version"]),
                override_versions=overrides,
                builds=_read_builds(entry, app),
            )
        )
    if not apps:
        raise CompatibilitySourceError("no app declared")
    return SupportedVersions(architectures=tuple(architectures), apps=tuple(apps))


@dataclass(frozen=True)
class CompatibilityRow:
    version: str
    display: str
    status: str
    overrides_applied: Tuple[str, ...]
    desktop_app: str
    download_url: str


def compatibility_rows(support: AppSupport) -> List[CompatibilityRow]:
    """One row per version worth naming: the reference, each override key, each installable build.
    Newest first; the overrides applied are the keys at or below the version, as the patcher does."""
    builds = {b.version: b for b in support.builds}
    versions = {support.reference, *support.override_versions, *builds}
    rows = []
    for version in sorted(versions, key=version_tuple, reverse=True):
        build = builds.get(version)
        if version == support.reference:
            status = "Reference"
        elif version in support.override_versions:
            status = "Supported"
        elif build is not None and build.status == "validated":
            status = "Validated"
        else:
            status = "Under validation"

        if build is None:
            desktop = "-"
        elif build.recommended:
            desktop = "Installed by default"
        elif build.status == "validated":
            desktop = "Installable"
        else:
            desktop = "Installable, under validation"

        applied = tuple(
            key for key in support.override_versions if version_tuple(key) <= version_tuple(version)
        )
        display = f"{version_family(version)}.x" if is_family_key(version) else version
        rows.append(
            CompatibilityRow(
                version=version,
                display=display,
                status=status,
                overrides_applied=applied,
                desktop_app=desktop,
                download_url=apkmirror_search_url(support.name, version),
            )
        )
    return rows


def render_compatibility_markdown(supported: SupportedVersions) -> str:
    archs = ", ".join(f"`{a}`" for a in supported.architectures)
    lines = [
        "# App compatibility",
        "",
        "<!-- GENERATED - do not edit. Sources: taktik/core/compat/data/app_builds.json and",
        f"     taktik/core/compat/data/overrides/<app>.yaml. Regenerate: {REGENERATE_COMMAND} -->",
        "",
        "The Instagram and TikTok versions TAKTIK supports. Install the **original, unmodified** APK",
        "of a listed version; the download column opens a search for that exact version on",
        "[APKMirror](https://www.apkmirror.com), a public mirror of the original packages.",
        "",
        "Status:",
        "",
        "- **Reference**: the build the selectors are written against. The safest choice.",
        "- **Supported**: the bot carries selector adjustments for this version",
        "  (`taktik/core/compat/data/overrides/<app>.yaml`). A version written `447.x` covers every",
        "  build of that family.",
        "- **Under validation**: being tested end to end; expect gaps.",
        "",
        "Overrides applied: the adjustment sets the bot loads on that version (every key at or below",
        "it). \"Desktop app\" tells what the TAKTIK desktop app installs itself.",
        "",
        "## Architectures",
        "",
        f"Every version below is supported on {archs} (`x86_64` and `x86` cover desktop emulators).",
        "The bot reads the screen and does not depend on the CPU architecture, but the APK does:",
        "on the mirror, pick the variant matching `adb shell getprop ro.product.cpu.abi`.",
        "A mirror may not publish every architecture for every build.",
        "",
    ]
    for support in supported.apps:
        lines += [
            f"## {support.name} (`{support.package}`)",
            "",
            f"Reference build: `{support.reference}`.",
            "",
            "| Version | Status | Overrides applied | Desktop app | Architectures | Download |",
            "|---|---|---|---|---|---|",
        ]
        for row in compatibility_rows(support):
            applied = ", ".join(f"`{k}`" for k in row.overrides_applied) or "none"
            lines.append(
                f"| `{row.display}` | {row.status} | {applied} | {row.desktop_app} | {archs} "
                f"| [Search on APKMirror]({row.download_url}) |"
            )
        lines.append("")
    return "\n".join(lines)


def compatibility_file_drift(path: Path = COMPATIBILITY_PATH) -> Optional[str]:
    """None when the published file matches the sources, else what is wrong."""
    expected = render_compatibility_markdown(load_supported_versions())
    if not path.exists():
        return f"{path.name} is missing"
    actual = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if actual != expected:
        return f"{path.name} does not match its sources"
    return None


def as_json(supported: SupportedVersions) -> Dict[str, Any]:
    """The payload the desktop app generates its version list from."""
    return {
        "architectures": list(supported.architectures),
        "apps": {
            s.app: {
                "name": s.name,
                "package": s.package,
                "reference": s.reference,
                "override_versions": list(s.override_versions),
                "builds": [
                    {"version": b.version, "status": b.status, "recommended": b.recommended} for b in s.builds
                ],
            }
            for s in supported.apps
        },
    }
