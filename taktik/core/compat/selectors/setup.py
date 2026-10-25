"""Selector compatibility setup owners: the version overrides, applied to the catalogues a host
registered (`platforms.py`); compat names no platform."""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from loguru import logger

from .platforms import platform_selectors, registered_platforms
from .registry import VersionedSelectorRegistry, build_full_selector_map
from .supported_versions import CompatibilitySourceError


def create_registry(overrides_dir: Optional[str] = None) -> VersionedSelectorRegistry:
    """Create and return a VersionedSelectorRegistry holding every registered platform."""
    registry = VersionedSelectorRegistry(overrides_dir=overrides_dir)
    sizes = []
    for app in registered_platforms():
        selector_map = build_full_selector_map(platform_selectors(app).domains)
        registry.register_app(app, selector_map, baseline_version(app, overrides_dir))
        sizes.append(f"{app}={len(selector_map)} selectors")
    logger.info(f"[Compat] Registry ready: {', '.join(sizes)}")
    return registry


def build_xpath_to_selector_id_index(
    app: str, overrides_dir: Optional[str] = None
) -> Dict[str, str]:
    """Reverse index raw XPath -> logical selectorId for one app.

    Only XPaths that resolve to exactly one logical selectorId (namespaced
    ``domain.field``) are kept. XPaths shared by several selectors are dropped so
    callers never receive an ambiguous id. Dynamically generated XPaths (built
    from runtime parameters) are not in the catalogs and simply do not match.
    """
    registry = create_registry(overrides_dir=overrides_dir)
    version = registry.get_current_version(app) or ""
    copies = platform_selectors(app).copies
    candidates: Dict[str, set] = {}
    for selector_id, entry in registry.get_all(app, version).items():
        for xpath in entry.xpaths:
            candidates.setdefault(xpath, set()).add(selector_id)
    resolved = {xpath: _without_copies(ids, copies) for xpath, ids in candidates.items()}
    return {
        xpath: next(iter(ids))
        for xpath, ids in resolved.items()
        if len(ids) == 1
    }


def _without_copies(ids: set, copies: Mapping[str, str]) -> set:
    """The same xpath under the same field of a domain and of a domain that copies it at import
    (Instagram's post sub-catalogues copy `post`) is the source's entry."""
    present = {tuple(sid.split(".", 1)) for sid in ids}  # (domain, field) pairs
    kept = set()
    for sid in ids:
        domain, field = sid.split(".", 1)
        if (copies.get(domain), field) not in present:
            kept.add(sid)
    return kept


def baseline_version(app: str, overrides_dir: Optional[str] = None) -> str:
    """The version the platform's Python catalogues describe: `meta.baseline_version` of its YAML."""
    data = _load_yaml_overrides(app, Path(overrides_dir) if overrides_dir else None)
    version = (data.get("meta") or {}).get("baseline_version")
    if not version:
        raise CompatibilitySourceError(f"{app}: {app}.yaml declares no meta.baseline_version")
    return str(version)


def _load_yaml_overrides(app: str, overrides_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Load and return the raw YAML data for an app override file."""
    base_dir = overrides_dir or (Path(__file__).resolve().parent.parent / "data" / "overrides")
    override_path = base_dir / f"{app}.yaml"
    if not override_path.exists():
        return {}
    try:
        with open(override_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"[Compat] Failed to load {override_path}: {e}")
        return {}


def _resolve_overrides_for_version(
    data: Dict[str, Any], target_version: str
) -> Dict[str, List[str]]:
    """Resolve which overrides apply for *target_version*."""
    versions = data.get("versions", {})
    if not versions or isinstance(versions, str):
        return {}

    # NUMERIC comparison, segment by segment — not string order. Lexicographically
    # "442.0.0.5" sorts AFTER "442.0.0.46" ('5' > '4'), so an override keyed on a
    # two-digit build would silently stop applying to later one-digit ones. Version
    # keys we cannot parse fall back to never-applicable rather than to string luck.
    def _vtuple(version: str):
        try:
            return tuple(int(part) for part in str(version).split("."))
        except ValueError:
            return None

    target_tuple = _vtuple(target_version)
    if target_tuple is None:
        return {}
    applicable = sorted(
        (v for v in versions if _vtuple(v) is not None and _vtuple(v) <= target_tuple),
        key=_vtuple,
    )

    merged: Dict[str, List[str]] = {}
    for version in applicable:
        entries = versions[version]
        if not isinstance(entries, dict):
            continue
        for action_key, xpaths in entries.items():
            if isinstance(xpaths, list):
                merged[action_key] = xpaths
            elif isinstance(xpaths, str):
                merged[action_key] = [xpaths]
    return merged


# Value of every field an override replaced, as it was before the first override touched it,
# keyed by catalogue. The catalogues are process-globals: a process that meets a second phone
# (the CLI loop, a clone after the official app) must start again from the baseline.
_ORIGINALS: Dict[int, Dict[str, Any]] = {}


def _restore_baseline(domains: Mapping[str, Any]) -> int:
    """Put back every field a previous override replaced. Returns how many were restored."""
    restored = 0
    for singleton in domains.values():
        for field_name, value in _ORIGINALS.get(id(singleton), {}).items():
            setattr(singleton, field_name, list(value) if isinstance(value, list) else value)
            restored += 1
    return restored


def _patch_singleton(
    domain_name: str,
    singleton: Any,
    overrides: Dict[str, List[str]],
) -> int:
    """Patch a dataclass singleton's fields in place."""
    prefix = f"{domain_name}."
    patched = 0

    for action_key, xpaths in overrides.items():
        if not action_key.startswith(prefix):
            continue
        field_name = action_key[len(prefix):]

        if not hasattr(singleton, field_name):
            logger.warning(
                f"[Compat] Override {action_key}: field '{field_name}' "
                f"not found on {type(singleton).__name__}, skipping"
            )
            continue

        current = getattr(singleton, field_name)
        # Field by field, never all-or-nothing: the locale refactor turned some list
        # fields into read-only @property (a locale-aware getter), and one such field
        # in an override used to raise AttributeError and abort the WHOLE apply — every
        # override after it, other domains included, silently never landed. A property
        # cannot be patched this way; say so and keep going.
        # Remembered only once the field took the override: a refused field would otherwise be
        # restored on every later apply, and that restore raises the same error.
        original = list(current) if isinstance(current, list) else current
        try:
            if isinstance(current, list):
                setattr(singleton, field_name, xpaths)
            elif isinstance(current, str):
                setattr(singleton, field_name, xpaths[0] if xpaths else current)
            else:
                logger.warning(
                    f"[Compat] Override {action_key}: unexpected type "
                    f"{type(current).__name__}, skipping"
                )
                continue
        except AttributeError:
            logger.warning(
                f"[Compat] Override {action_key}: field is a read-only property "
                f"on {type(singleton).__name__}, skipping (override the *_base "
                f"field instead)"
            )
            continue

        _ORIGINALS.setdefault(id(singleton), {}).setdefault(field_name, original)
        patched += 1
        logger.debug(f"[Compat] Patched {action_key} ({len(xpaths)} xpath(s))")

    return patched


def apply_overrides_for_device(device_id: str) -> Dict[str, int]:
    """Patch every registered platform's selector catalog to match what is installed on THIS phone.

    The catalog is a process-global. The Instagram device base patches it in
    `InstagramDeviceBase.connect()`, which is why a desktop run has always faced the right
    selectors -- but the standalone CLI did not go through that base for every run, and an audit
    found the patch reached only two of its entry points.
    Everywhere else, an open-source user on a phone that auto-updated to IG 442 was running the
    v410 baseline: the overrides existed, were correct, and were simply never applied.

    Called at CONNECT time on purpose: that is the moment a process learns which phone it is
    on, and it is the one funnel every caller already goes through. Every registered platform is
    patched because the phone is chosen before the workflow is, and they touch disjoint singletons.
    TikTok is looked up across its known package variants -- a phone carrying the `trill` or
    `aweme` build has TikTok installed even though the canonical package is absent.

    Reading a version is best-effort: a phone that does not answer keeps the baseline, said in the
    log, because failing to read a version must not stop a run from starting. A host that
    registered no platform, or a platform whose catalogue does not load, is no such case: its
    `SelectorRegistryError` (or the loader's error) goes up to the connection.
    """
    from taktik.core.clone.packages.package_map import get_package_variants
    from taktik.core.shared.device.app_inspection import get_installed_app_version

    applied: Dict[str, int] = {}
    for platform in registered_platforms():
        platform_selectors(platform)  # loaded outside the best-effort: a catalogue that fails says it
        try:
            for package in get_package_variants(platform):
                version = get_installed_app_version(device_id, package, platform)
                if version:
                    applied[platform] = apply_version_overrides(platform, version)
                    break
        except Exception as exc:
            logger.warning(f"[Compat] Could not apply {platform} overrides for {device_id}, baseline kept: {exc}")
    return applied


def apply_version_overrides(
    app: str,
    detected_version: str,
    overrides_dir: Optional[str] = None,
) -> int:
    """Patch selector singletons in place for the detected app version, starting again from the
    baseline: what an earlier call replaced is restored first. Raises `PlatformNotRegistered` for
    an app no host registered."""
    domains = platform_selectors(app).domains

    restored = _restore_baseline(domains)
    if restored:
        logger.info(f"[Compat] {app}: {restored} field(s) back to the baseline before applying v{detected_version}")

    base_dir = Path(overrides_dir) if overrides_dir else None
    data = _load_yaml_overrides(app, base_dir)
    if not data:
        logger.info(f"[Compat] No override file for {app}, using baseline selectors")
        return 0

    baseline = baseline_version(app, overrides_dir)
    if detected_version == baseline:
        logger.info(
            f"[Compat] {app} v{detected_version} matches baseline "
            f"v{baseline}, no overrides needed"
        )
        return 0

    overrides = _resolve_overrides_for_version(data, detected_version)
    if not overrides:
        logger.info(f"[Compat] No applicable overrides for {app} v{detected_version}")
        return 0

    total_patched = 0
    for domain_name, singleton in domains.items():
        total_patched += _patch_singleton(domain_name, singleton, overrides)

    logger.info(
        f"[Compat] Applied {total_patched} selector override(s) "
        f"for {app} v{detected_version} (baseline: v{baseline})"
    )
    return total_patched
