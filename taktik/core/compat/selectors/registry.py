"""
Version-aware selector routing for compatibility tooling.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger


class SelectorNotFound(Exception):
    """Raised when no selector is found for the given (app, version, action)."""

    def __init__(self, app: str, version: str, action: str):
        self.app = app
        self.version = version
        self.action = action
        super().__init__(f"No selector for {app}/{version}/{action}")


@dataclass
class SelectorEntry:
    """A single selector entry with its XPath fallback list."""

    xpaths: List[str]
    source: str = "python"

    def first(self) -> str:
        if not self.xpaths:
            raise ValueError("Empty selector entry")
        return self.xpaths[0]

    def all(self) -> List[str]:
        return list(self.xpaths)


class VersionedSelectorRegistry:
    """Version-aware selector registry wrapping current selector catalogs."""

    def __init__(self, overrides_dir: Optional[str] = None):
        self._overrides_dir = Path(overrides_dir) if overrides_dir else (
            Path(__file__).resolve().parent.parent / "data" / "overrides"
        )
        self._apps: Dict[str, Dict[str, Any]] = {}
        self._overrides: Dict[str, Dict[str, Dict[str, List[str]]]] = {}

    def register_app(
        self,
        app: str,
        selector_map: Dict[str, List[str]],
        current_version: str,
    ) -> None:
        self._apps[app] = {
            "current_version": current_version,
            "selectors": selector_map,
        }
        logger.info(
            f"[Compat] Registered {app} v{current_version} "
            f"with {len(selector_map)} selectors"
        )
        self._load_overrides(app)

    def _load_overrides(self, app: str) -> None:
        override_path = self._overrides_dir / f"{app}.yaml"
        if not override_path.exists():
            logger.debug(f"[Compat] No overrides file for {app}")
            self._overrides[app] = {}
            return

        try:
            with open(override_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            versions = data.get("versions", {})
            self._overrides[app] = {}

            for version, actions in versions.items():
                version_str = str(version)
                self._overrides[app][version_str] = {}
                for action_key, xpaths in actions.items():
                    if isinstance(xpaths, list):
                        self._overrides[app][version_str][action_key] = xpaths
                    elif isinstance(xpaths, str):
                        self._overrides[app][version_str][action_key] = [xpaths]

            override_count = sum(len(v) for v in self._overrides[app].values())
            logger.info(
                f"[Compat] Loaded {len(versions)} version overrides "
                f"for {app} ({override_count} selector overrides total)"
            )
        except Exception as e:
            logger.error(f"[Compat] Failed to load overrides for {app}: {e}")
            self._overrides[app] = {}

    def _overrides_for(self, app: str, version: str) -> Dict[str, List[str]]:
        """The overrides the patcher applies for *version*: every version <= it, compared
        numerically, the later one winning per key."""
        from .setup import _resolve_overrides_for_version

        return _resolve_overrides_for_version({"versions": self._overrides.get(app, {})}, version)

    def get(self, app: str, version: str, action: str) -> SelectorEntry:
        if app not in self._apps:
            raise SelectorNotFound(app, version, action)

        overrides = self._overrides_for(app, version)
        if action in overrides:
            return SelectorEntry(xpaths=overrides[action], source="yaml")

        current_selectors = self._apps[app]["selectors"]
        if action in current_selectors:
            return SelectorEntry(xpaths=current_selectors[action], source="python")

        raise SelectorNotFound(app, version, action)

    def get_all(self, app: str, version: str) -> Dict[str, SelectorEntry]:
        """The map with the overrides of *version* on top. A static view: an override of a
        `_x_base` field shows under its own key, not in the property that reads it; the live
        catalogues, once patched, are the view production runs."""
        if app not in self._apps:
            return {}

        result: Dict[str, SelectorEntry] = {}
        current_selectors = self._apps[app]["selectors"]

        for action, xpaths in current_selectors.items():
            result[action] = SelectorEntry(xpaths=xpaths, source="python")

        for action, xpaths in self._overrides_for(app, version).items():
            result[action] = SelectorEntry(xpaths=xpaths, source="yaml")

        return result

    def list_actions(self, app: str) -> List[str]:
        if app not in self._apps:
            return []
        actions = set(self._apps[app]["selectors"].keys())
        if app in self._overrides:
            for version_overrides in self._overrides[app].values():
                actions.update(version_overrides.keys())
        return sorted(actions)

    def get_current_version(self, app: str) -> Optional[str]:
        if app not in self._apps:
            return None
        return self._apps[app]["current_version"]

    def get_override_versions(self, app: str) -> List[str]:
        """Override versions in numeric order; keys that are not a version come last."""
        if app not in self._overrides:
            return []
        return sorted(self._overrides[app].keys(), key=_version_order)

    def to_dict(self, app: str, version: str) -> Dict[str, Any]:
        all_selectors = self.get_all(app, version)
        return {
            "app": app,
            "version": version,
            "current_version": self.get_current_version(app),
            "selector_count": len(all_selectors),
            "selectors": {
                action: {
                    "xpaths": entry.xpaths,
                    "source": entry.source,
                }
                for action, entry in all_selectors.items()
            },
        }


def _version_order(version: Any) -> Tuple[int, Tuple[int, ...], str]:
    try:
        return (0, tuple(int(part) for part in str(version).split(".")), "")
    except ValueError:
        return (1, (), str(version))


def _public_selector_names(instance: Any, include_properties: bool) -> List[str]:
    """Public fields, then public properties when asked: a property (`_x_base + L(...)`) is
    what the workflows read, and `vars()` does not list it."""
    names = [name for name in getattr(instance, "__dict__", {}) if not name.startswith("_")]
    if not include_properties:
        return names
    seen = set(names)
    for klass in type(instance).__mro__:
        for name, attr in vars(klass).items():
            if isinstance(attr, property) and not name.startswith("_") and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def build_selector_map_from_dataclass(
    instance: Any, include_properties: bool = False
) -> Dict[str, List[str]]:
    """Flat selector map of one catalogue, as it reads NOW (overrides already applied, active
    locale). Without the properties by default: the xpath -> selectorId index would lose, as
    ambiguous, every xpath a property repeats from a public field."""
    result = {}
    for name in _public_selector_names(instance, include_properties):
        try:
            value = getattr(instance, name)
        except Exception as exc:
            logger.debug(f"[Compat] {type(instance).__name__}.{name} unreadable: {exc}")
            continue
        if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
            result[name] = list(value)
        elif isinstance(value, str):
            result[name] = [value]
    return result


def build_full_selector_map(
    selector_instances: Dict[str, Any],
    include_properties: bool = False,
) -> Dict[str, List[str]]:
    """Build a namespaced selector map from multiple dataclass instances."""
    result = {}
    for domain, instance in selector_instances.items():
        domain_map = build_selector_map_from_dataclass(instance, include_properties)
        for action, xpaths in domain_map.items():
            result[f"{domain}.{action}"] = xpaths
    return result
