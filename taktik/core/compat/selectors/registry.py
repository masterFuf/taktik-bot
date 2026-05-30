"""
Version-aware selector routing for compatibility tooling.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
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

    def get(self, app: str, version: str, action: str) -> SelectorEntry:
        if app not in self._apps:
            raise SelectorNotFound(app, version, action)

        app_data = self._apps[app]
        current_version = app_data["current_version"]
        current_selectors = app_data["selectors"]

        if app in self._overrides and version in self._overrides[app]:
            version_overrides = self._overrides[app][version]
            if action in version_overrides:
                return SelectorEntry(xpaths=version_overrides[action], source="yaml")

        if version == current_version:
            if action in current_selectors:
                return SelectorEntry(xpaths=current_selectors[action], source="python")
            raise SelectorNotFound(app, version, action)

        if app in self._overrides:
            closest = self._find_closest_version(self._overrides[app], version)
            if closest and action in self._overrides[app][closest]:
                return SelectorEntry(
                    xpaths=self._overrides[app][closest][action],
                    source="yaml",
                )

        if action in current_selectors:
            logger.warning(
                f"[Compat] No override for {app}/{version}/{action}, "
                f"falling back to current v{current_version} selectors"
            )
            return SelectorEntry(xpaths=current_selectors[action], source="python")

        raise SelectorNotFound(app, version, action)

    def get_all(self, app: str, version: str) -> Dict[str, SelectorEntry]:
        if app not in self._apps:
            return {}

        result: Dict[str, SelectorEntry] = {}
        current_selectors = self._apps[app]["selectors"]

        for action, xpaths in current_selectors.items():
            result[action] = SelectorEntry(xpaths=xpaths, source="python")

        if app in self._overrides and version in self._overrides[app]:
            for action, xpaths in self._overrides[app][version].items():
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
        if app not in self._overrides:
            return []
        return sorted(self._overrides[app].keys())

    def _find_closest_version(
        self, versions: Dict[str, Any], target: str
    ) -> Optional[str]:
        candidates = sorted(versions.keys(), reverse=True)
        for version in candidates:
            if version <= target:
                return version
        return None

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


def build_selector_map_from_dataclass(instance: Any) -> Dict[str, List[str]]:
    """Extract a flat selector map from an existing dataclass selector instance."""
    result = {}
    for field_name in vars(instance):
        if field_name.startswith("_"):
            continue
        value = getattr(instance, field_name)
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            result[field_name] = value
        elif isinstance(value, str):
            result[field_name] = [value]
    return result


def build_full_selector_map(
    selector_instances: Dict[str, Any],
) -> Dict[str, List[str]]:
    """Build a namespaced selector map from multiple dataclass instances."""
    result = {}
    for domain, instance in selector_instances.items():
        domain_map = build_selector_map_from_dataclass(instance)
        for action, xpaths in domain_map.items():
            result[f"{domain}.{action}"] = xpaths
    return result
