"""
The Instagram and TikTok versions TAKTIK supports, from the files the bot already runs on.

Three sources, none of them written twice:

- the selector reference: ``meta.baseline_version`` of ``compat/data/overrides/<app>.yaml``, the
  build the Python catalogues of ``ui/selectors/**`` describe;
- the version adjustments: the version keys of that same YAML, read by the bot's own registry;
- the installable builds: ``compat/data/app_builds.json`` (version, status, the one recommended
  build, the CPU architectures builds are installed for), and in the same file the status of the
  version adjustments (``override_status``).

A build is ``validated`` with its evidence, the ``validation`` block: the date, the commit of the core
it holds for, the Lab runs that prove it (phone model, versionCode, ABI, app language, SHA-256 of the
report, the exception a run was played under), who decided, and the known limits in French and in
English. The block is never written by hand: the desktop app's ``npm run lab:exit -- --promote``
hands this module the verdict of a green, up-to-date run (``promote_file``), and the whole file is
rewritten only if it stays valid.

``COMPATIBILITY.md`` at the repository root and the desktop app's version list are both generated
from here. ``scripts/audits/audit_compatibility_file.py`` fails when the published file and these sources
disagree.
"""

import copy
import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import quote_plus

import yaml

from .registry import VersionedSelectorRegistry

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUILDS_PATH = DATA_DIR / "app_builds.json"
OVERRIDES_DIR = DATA_DIR / "overrides"
REPO_ROOT = Path(__file__).resolve().parents[4]
COMPATIBILITY_PATH = REPO_ROOT / "COMPATIBILITY.md"

BUILD_STATUSES = ("validated", "testing")
#: ``adjusted``: the bot keeps adjustments for that version, no phone of ours runs it and no
#: validation is planned (two versions per app, 2026-09-30).
OVERRIDE_STATUSES = ("validated", "testing", "adjusted")
#: The row an adjusted version gets in COMPATIBILITY.md, by its status.
OVERRIDE_ROW_STATUS = {"validated": "Supported", "testing": "Under validation", "adjusted": "Adjusted, not validated"}
#: Every CPU ABI an Android build can be declared for; ``architectures`` names some of them.
ANDROID_ABIS = ("arm64-v8a", "armeabi-v7a", "x86_64", "x86")
# A search, never a guessed release page: the mirror's page slugs are not derivable from a version.
APKMIRROR_SEARCH = "https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s={query}"
REGENERATE_COMMAND = "python scripts/audits/audit_compatibility_file.py --write"
PROMOTE_COMMAND = "npm run lab:exit -- --promote <platform> <version>"

VALIDATION_KEYS = ("date", "core_commit", "decided_by", "runs", "notes")
RUN_KEYS = ("device", "version_code", "abi", "language", "report_sha256", "core_commit", "exception")
EXCEPTION_KEYS = ("reason", "skipped_actions")
NOTE_LANGUAGES = ("fr", "en")
PROMOTION_KEYS = ("app", "version", "validation")


class CompatibilitySourceError(ValueError):
    """The sources contradict themselves; nothing can be generated from them."""


@dataclass(frozen=True)
class RunException:
    """What a run left out, as the exception declared for its phone and version says."""

    reason: str
    skipped_actions: Tuple[str, ...]


@dataclass(frozen=True)
class ValidationRun:
    """One Lab run that proves a build: the bytes it ran and the report that says so."""

    device: str
    version_code: int
    abi: str
    language: str
    report_sha256: str
    core_commit: str
    exception: Optional[RunException] = None


@dataclass(frozen=True)
class Validation:
    date: str
    core_commit: str
    decided_by: str
    runs: Tuple[ValidationRun, ...]
    notes: Mapping[str, str]


@dataclass(frozen=True)
class AppBuild:
    version: str
    status: str
    recommended: bool = False
    validation: Optional[Validation] = None


@dataclass(frozen=True)
class AppSupport:
    app: str
    name: str
    package: str
    reference: str
    override_versions: Tuple[str, ...]
    builds: Tuple[AppBuild, ...]
    #: Every override version and its status: ``validated`` (a validated build of that version runs on
    #: one of our phones: "Supported"), ``testing`` ("Under validation") or ``adjusted`` (adjusted,
    #: run on none of our phones, not planned for validation: "Adjusted, not validated").
    override_status: Mapping[str, str] = field(default_factory=dict)


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


def family_covers(key: str, version: str) -> bool:
    """Is ``version`` a build of the family ``key`` stands for (``447.0.0.0`` covers
    ``447.0.0.55.81``, ``46.9.3`` covers ``46.9.3`` only)? The rule of the app's ``isAdjustedVersion``."""
    family = version_family(key).split(".")
    return version.split(".")[: len(family)] == family


def search_query(key: str) -> str:
    """What to search on the mirror: the exact build, or a family key down to three segments
    (``447.0.0.0`` -> ``447.0.0``), which is how released builds are numbered."""
    parts = key.split(".")
    while len(parts) > 3 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)


def apkmirror_search_url(app_name: str, version: str) -> str:
    return APKMIRROR_SEARCH.format(query=quote_plus(f"{app_name} {search_query(version)}"))


def _is_hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(c in "0123456789abcdef" for c in value)


def _text(raw: Dict[str, Any], key: str, where: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CompatibilitySourceError(f"{where}: {key} must be a non-empty text")
    return value


def _refuse_unknown_keys(raw: Dict[str, Any], known: Sequence[str], where: str) -> None:
    unknown = sorted(set(raw) - set(known))
    if unknown:
        raise CompatibilitySourceError(f"{where}: unknown key {', '.join(unknown)} (known: {', '.join(known)})")


def _read_exception(raw: Any, where: str) -> RunException:
    if not isinstance(raw, dict):
        raise CompatibilitySourceError(f"{where}: exception must be an object with reason and skipped_actions")
    _refuse_unknown_keys(raw, EXCEPTION_KEYS, where)
    actions = raw.get("skipped_actions")
    if not isinstance(actions, list) or not actions or not all(isinstance(a, str) and a for a in actions):
        raise CompatibilitySourceError(f"{where}: exception.skipped_actions must list the Lab actions the run left out")
    return RunException(reason=_text(raw, "reason", f"{where}: exception"), skipped_actions=tuple(actions))


def _read_run(raw: Any, where: str, architectures: Tuple[str, ...]) -> ValidationRun:
    if not isinstance(raw, dict):
        raise CompatibilitySourceError(f"{where}: a run is an object")
    _refuse_unknown_keys(raw, RUN_KEYS, where)
    version_code = raw.get("version_code")
    if not isinstance(version_code, int) or isinstance(version_code, bool) or version_code <= 0:
        raise CompatibilitySourceError(f"{where}: version_code must be the positive integer the phone reports")
    abi = raw.get("abi")
    if abi not in ANDROID_ABIS:
        raise CompatibilitySourceError(f"{where}: abi {abi!r} is not an Android ABI ({', '.join(ANDROID_ABIS)})")
    if abi not in architectures:
        raise CompatibilitySourceError(f"{where}: abi {abi} is not an announced architecture")
    language = raw.get("language")
    if not isinstance(language, str) or len(language) != 2 or not language.isalpha() or not language.islower():
        raise CompatibilitySourceError(f"{where}: language must be the app's two-letter language code")
    if not _is_hex(raw.get("report_sha256"), 64):
        raise CompatibilitySourceError(f"{where}: report_sha256 must be the lowercase SHA-256 of the run's report")
    if not _is_hex(raw.get("core_commit"), 40):
        raise CompatibilitySourceError(f"{where}: core_commit must be the full commit the run was made on")
    exception = raw.get("exception")
    return ValidationRun(
        device=_text(raw, "device", where),
        version_code=version_code,
        abi=abi,
        language=language,
        report_sha256=raw["report_sha256"],
        core_commit=raw["core_commit"],
        exception=None if exception is None else _read_exception(exception, where),
    )


def _read_validation(raw: Any, where: str, architectures: Tuple[str, ...]) -> Validation:
    """The evidence of a validated build: refused as soon as one part is missing or malformed."""
    if not isinstance(raw, dict):
        raise CompatibilitySourceError(f"{where}: validation must be an object")
    _refuse_unknown_keys(raw, VALIDATION_KEYS, where)
    try:
        datetime.date.fromisoformat(str(raw.get("date")))
    except ValueError:
        raise CompatibilitySourceError(f"{where}: date must be a day written YYYY-MM-DD") from None
    if not _is_hex(raw.get("core_commit"), 40):
        raise CompatibilitySourceError(f"{where}: core_commit must be the full commit of the core the validation holds for")
    runs = raw.get("runs")
    if not isinstance(runs, list) or not runs:
        raise CompatibilitySourceError(f"{where}: runs must list at least one Lab run")
    notes = raw.get("notes")
    if not isinstance(notes, dict) or set(notes) != set(NOTE_LANGUAGES) or not all(
        isinstance(notes[language], str) and notes[language].strip() for language in NOTE_LANGUAGES
    ):
        raise CompatibilitySourceError(f"{where}: notes must give the known limits in fr and en, and nothing else")
    return Validation(
        date=raw["date"],
        core_commit=raw["core_commit"],
        decided_by=_text(raw, "decided_by", where),
        runs=tuple(_read_run(run, f"{where}, run {n}", architectures) for n, run in enumerate(runs, start=1)),
        notes=dict(notes),
    )


def _read_builds(data: Dict[str, Any], app: str, architectures: Tuple[str, ...]) -> Tuple[AppBuild, ...]:
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
        # A validated build says which runs prove it, next to the rule that the recommended build is
        # validated: without the block, "validated" was a word anyone could write.
        validation = None
        if status == "validated":
            if "validation" not in entry:
                raise CompatibilitySourceError(
                    f"{app}: {version} is validated without its validation block (date, core commit, runs, "
                    f"decision, notes): record it with {PROMOTE_COMMAND}"
                )
            validation = _read_validation(entry["validation"], f"{app} {version}", architectures)
        elif "validation" in entry:
            raise CompatibilitySourceError(f"{app}: {version} carries a validation block but is {status}")
        seen.add(version)
        builds.append(AppBuild(version=version, status=status, recommended=bool(entry.get("recommended")),
                               validation=validation))

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


def _read_override_status(
    data: Dict[str, Any], app: str, overrides: Tuple[str, ...], builds: Tuple[AppBuild, ...]
) -> Dict[str, str]:
    """The status of each override version: ``validated`` unless `app_builds.json` declares it
    ``testing`` or ``adjusted``. A key that is not an override version, or an unknown status, is
    refused: a status must never stand for a version the bot does not adjust. A ``validated`` key needs
    a validated build of its version, which carries the runs that prove it."""
    declared = data.get("override_status") or {}
    if not isinstance(declared, dict):
        raise CompatibilitySourceError(f"{app}: override_status must map an override version to a status")
    for version, status in declared.items():
        if version not in overrides:
            raise CompatibilitySourceError(f"{app}: override_status names {version}, not a version the bot adjusts for")
        if status not in OVERRIDE_STATUSES:
            raise CompatibilitySourceError(f"{app}: override_status gives {version} an unknown status {status!r}")
    statuses = {version: declared.get(version, "validated") for version in overrides}
    for key, status in statuses.items():
        proven = any(b.status == "validated" and family_covers(key, b.version) for b in builds)
        if status == "validated" and not proven:
            shown = f"{version_family(key)}.x" if is_family_key(key) else key
            raise CompatibilitySourceError(
                f"{app}: the adjustments of {shown} are validated (the default) but no validated build of that "
                f"version carries the evidence: declare them testing or adjusted in override_status, or validate a "
                f"build of that version"
            )
    return statuses


def _read_meta(app: str, overrides_dir: Path) -> Dict[str, Any]:
    path = overrides_dir / f"{app}.yaml"
    if not path.exists():
        raise CompatibilitySourceError(f"{app}: {path.name} is missing")
    meta = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("meta") or {}
    if not meta.get("baseline_version") or not meta.get("package"):
        raise CompatibilitySourceError(f"{app}: {path.name} declares no meta.baseline_version or meta.package")
    return meta


def _read_architectures(data: Dict[str, Any]) -> Tuple[str, ...]:
    architectures = data.get("architectures")
    if not isinstance(architectures, list) or not architectures or len(set(architectures)) != len(architectures):
        raise CompatibilitySourceError("architectures: a non-empty list without duplicates is expected")
    for abi in architectures:
        if abi not in ANDROID_ABIS:
            raise CompatibilitySourceError(f"architectures: {abi} is not an Android ABI ({', '.join(ANDROID_ABIS)})")
    return tuple(architectures)


def supported_versions_from(data: Dict[str, Any], overrides_dir: Path = OVERRIDES_DIR) -> SupportedVersions:
    """The sources read from the content of `app_builds.json` (a promotion checks its result here
    before writing it)."""
    architectures = _read_architectures(data)
    registry = VersionedSelectorRegistry(overrides_dir=str(overrides_dir))
    apps = []
    for app, entry in (data.get("apps") or {}).items():
        meta = _read_meta(app, Path(overrides_dir))
        registry.register_app(app, {}, "")
        overrides = tuple(registry.get_override_versions(app))
        for key in overrides:
            if version_tuple(key) is None:
                raise CompatibilitySourceError(f"{app}: override key {key!r} is not a version")
        builds = _read_builds(entry, app, architectures)
        apps.append(
            AppSupport(
                app=app,
                name=str(entry.get("name") or app),
                package=str(meta["package"]),
                reference=str(meta["baseline_version"]),
                override_versions=overrides,
                builds=builds,
                override_status=_read_override_status(entry, app, overrides, builds),
            )
        )
    if not apps:
        raise CompatibilitySourceError("no app declared")
    # Announce exactly what is tested (2026-09-27): an architecture no validated run played is not one.
    played = {run.abi for support in apps for build in support.builds if build.validation for run in build.validation.runs}
    for abi in architectures:
        if abi not in played:
            raise CompatibilitySourceError(f"architectures: {abi} is announced but no validated run played it")
    return SupportedVersions(architectures=architectures, apps=tuple(apps))


def load_supported_versions(
    builds_path: Path = BUILDS_PATH, overrides_dir: Path = OVERRIDES_DIR
) -> SupportedVersions:
    return supported_versions_from(json.loads(Path(builds_path).read_text(encoding="utf-8")), overrides_dir)


# ─── Promotion: the verdict of the Lab's exit gate, recorded ────────────────────


def render_builds_json(data: Dict[str, Any]) -> str:
    """`app_builds.json` as every promotion writes it: the whole file, two-space indent, UTF-8."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def promote_builds(data: Dict[str, Any], promotions: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """A copy of `app_builds.json` where each promoted build is ``validated`` with the validation block
    its promotion carries (a build already validated gets the new evidence). A promotion names a build
    the file declares: a new build is declared first, ``testing``, and promoted once a run proves it.
    The block itself is checked by the reader, on the whole result (`promote_file`)."""
    promoted = copy.deepcopy(data)
    apps = promoted.get("apps") or {}
    for promotion in promotions:
        if not isinstance(promotion, dict) or "validation" not in promotion:
            raise CompatibilitySourceError("each promotion names an app, a version and a validation block")
        _refuse_unknown_keys(promotion, PROMOTION_KEYS, "promotion")
        app, version = promotion.get("app"), promotion.get("version")
        if app not in apps:
            raise CompatibilitySourceError(f"promotion: {app} is not an app of app_builds.json")
        build = next((b for b in apps[app].get("builds") or [] if b.get("version") == version), None)
        if build is None:
            raise CompatibilitySourceError(
                f"promotion: {app} {version} is not a declared build: declare it first in app_builds.json (testing)"
            )
        build["status"] = "validated"
        build["validation"] = copy.deepcopy(promotion["validation"])
    return promoted


def promote_file(verdict_path: Path, builds_path: Path = BUILDS_PATH, overrides_dir: Path = OVERRIDES_DIR) -> List[Tuple[str, str]]:
    """Record the promotions of a verdict file (a JSON list of ``{app, version, validation}``) in
    `app_builds.json`. The file is rewritten only when the whole result reads without an error; the
    promoted builds are returned."""
    try:
        promotions = json.loads(Path(verdict_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CompatibilitySourceError(f"{Path(verdict_path).name} is not JSON: {error}") from error
    if not isinstance(promotions, list) or not promotions:
        raise CompatibilitySourceError(f"{Path(verdict_path).name}: a non-empty list of promotions is expected")
    promoted = promote_builds(json.loads(Path(builds_path).read_text(encoding="utf-8")), promotions)
    supported_versions_from(promoted, overrides_dir)
    Path(builds_path).write_text(render_builds_json(promoted), encoding="utf-8", newline="\n")
    return [(p["app"], p["version"]) for p in promotions]


# ─── The public file ────────────────────────────────────────────────────────────


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
        elif build is not None and build.status == "validated":
            status = "Validated"
        elif version in support.override_versions:
            status = OVERRIDE_ROW_STATUS[support.override_status.get(version, "validated")]
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


def _evidence_line(version: str, validation: Validation) -> str:
    """One line per validated build: its runs grouped by phone and bytes, and its known limits."""
    groups: Dict[Tuple[str, str, int, str, int], int] = {}
    for run in validation.runs:
        left_out = len(run.exception.skipped_actions) if run.exception else 0
        key = (run.device, run.abi, run.version_code, run.language, left_out)
        groups[key] = groups.get(key, 0) + 1
    parts = []
    for (device, abi, version_code, language, left_out), count in groups.items():
        runs = f"{count} Lab run{'s' if count > 1 else ''}"
        skipped = f", {left_out} actions left out" if left_out else ""
        parts.append(f"{runs} on {device} ({abi}, versionCode {version_code}, {language}{skipped})")
    return f"- `{version}`, validated on {validation.date}: {'; '.join(parts)}. Notes: {validation.notes['en']}"


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
        "- **Validated**: a build proven by runs of the bot's test bench on one of our phones; the runs",
        "  and the known limits are listed under each table.",
        "- **Supported**: the bot carries selector adjustments for this version",
        "  (`taktik/core/compat/data/overrides/<app>.yaml`) and a validated build of it runs on one of our",
        "  phones. A version written `447.x` covers every build of that family.",
        "- **Under validation**: being tested end to end; expect gaps.",
        "- **Adjusted, not validated**: the bot carries selector adjustments for this version, but none of",
        "  our phones runs it and no validation is planned; expect gaps.",
        "",
        "Overrides applied: the adjustment sets the bot loads on that version (every key at or below",
        "it). \"Desktop app\" tells what the TAKTIK desktop app installs itself.",
        "",
        "## Architectures",
        "",
        f"Every version below is listed for {archs}: the architectures a validated run played.",
        "The bot reads the screen and does not depend on the CPU architecture, but the APK does:",
        "on the mirror, pick the variant matching `adb shell getprop ro.product.cpu.abi`.",
        "A mirror may not publish every architecture for every build.",
        "",
        "Tested on real arm64 phones only: the phones, Android versions, app versions and languages",
        "are in the README, section \"Tested on\". Emulators (`x86_64`, `x86`) are not tested.",
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
        evidence = []
        for build in support.builds:
            if build.validation is not None:
                evidence.append(_evidence_line(build.version, build.validation))
        if evidence:
            lines += ["", "Validated builds, with the runs that prove them and their known limits (notes):", "", *evidence]
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
    """The payload the desktop app generates its version lists from. `rows` are the rows of
    COMPATIBILITY.md, status included: the Lab's exit gate asks for a green run on each of them.
    `override_status` tells, for each adjusted version, whether a validated build of it runs on one of
    our phones (`validated`), it is under validation (`testing`) or adjusted only (`adjusted`): the app
    says the same of a phone on it. `abis` is every ABI a build can be declared for."""
    return {
        "architectures": list(supported.architectures),
        "abis": list(ANDROID_ABIS),
        "apps": {
            s.app: {
                "name": s.name,
                "package": s.package,
                "reference": s.reference,
                "override_versions": list(s.override_versions),
                "override_status": dict(s.override_status),
                "builds": [
                    {"version": b.version, "status": b.status, "recommended": b.recommended} for b in s.builds
                ],
                "rows": [
                    {"version": r.version, "display": r.display, "status": r.status} for r in compatibility_rows(s)
                ],
            }
            for s in supported.apps
        },
    }
