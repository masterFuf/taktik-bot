"""
VersionedSelectorRegistry — Version-aware selector routing.

Wraps the existing ui/selectors dataclass modules (Instagram & TikTok) and adds
version-based override support via YAML files.

Architecture:
  1. Current version → returns existing Python dataclass selectors (no change)
  2. Different version → checks YAML overrides for that version
  3. No override found → falls back to closest known version

The existing selectors in ui/selectors/ remain the source of truth for the
current app version. YAML overrides only contain DIFFS for other versions.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
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
    source: str = "python"  # "python" (from dataclass) or "yaml" (from override)

    def first(self) -> str:
        """Return the primary XPath selector."""
        if not self.xpaths:
            raise ValueError("Empty selector entry")
        return self.xpaths[0]

    def all(self) -> List[str]:
        """Return all XPath fallbacks."""
        return list(self.xpaths)


class VersionedSelectorRegistry:
    """
    Version-aware selector registry that wraps existing ui/selectors modules.

    Usage:
        registry = VersionedSelectorRegistry()
        registry.register_app("instagram", current_selectors_map, "410.0.0.53.71")
        registry.register_app("tiktok", current_selectors_map, "43.1.4")

        # Get selectors for detected version
        selectors = registry.get("instagram", "410.0.0.53.71", "feed.like_button")
        # Returns SelectorEntry with xpaths list
    """

    def __init__(self, overrides_dir: Optional[str] = None):
        self._overrides_dir = Path(overrides_dir) if overrides_dir else (
            Path(__file__).parent / "data" / "overrides"
        )
        # app -> { "current_version": str, "selectors": { domain.action -> List[str] } }
        self._apps: Dict[str, Dict[str, Any]] = {}
        # app -> { version -> { domain.action -> List[str] } }
        self._overrides: Dict[str, Dict[str, Dict[str, List[str]]]] = {}

    def register_app(
        self,
        app: str,
        selector_map: Dict[str, List[str]],
        current_version: str,
    ) -> None:
        """
        Register an app's current selectors from the existing dataclass modules.

        Args:
            app: "instagram" or "tiktok"
            selector_map: Flat dict of "domain.action" -> List[str] (XPaths)
                          Built from the existing dataclass instances.
            current_version: The app version these selectors are known to work with.
        """
        self._apps[app] = {
            "current_version": current_version,
            "selectors": selector_map,
        }
        logger.info(
            f"[Compat] Registered {app} v{current_version} "
            f"with {len(selector_map)} selectors"
        )
        # Load YAML overrides if they exist
        self._load_overrides(app)

    def _load_overrides(self, app: str) -> None:
        """Load YAML override file for an app if it exists."""
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

            override_count = sum(
                len(v) for v in self._overrides[app].values()
            )
            logger.info(
                f"[Compat] Loaded {len(versions)} version overrides "
                f"for {app} ({override_count} selector overrides total)"
            )
        except Exception as e:
            logger.error(f"[Compat] Failed to load overrides for {app}: {e}")
            self._overrides[app] = {}

    def get(self, app: str, version: str, action: str) -> SelectorEntry:
        """
        Get selector for (app, version, action).

        Resolution order:
          1. Exact version match in YAML overrides
          2. Current Python selectors (if version matches current)
          3. Closest version override (newest version <= requested)
          4. Fall back to current Python selectors
          5. Raise SelectorNotFound
        """
        if app not in self._apps:
            raise SelectorNotFound(app, version, action)

        app_data = self._apps[app]
        current_version = app_data["current_version"]
        current_selectors = app_data["selectors"]

        # 1. Check YAML overrides for exact version match
        if app in self._overrides and version in self._overrides[app]:
            version_overrides = self._overrides[app][version]
            if action in version_overrides:
                return SelectorEntry(
                    xpaths=version_overrides[action],
                    source="yaml",
                )

        # 2. If requesting current version, use Python selectors
        if version == current_version:
            if action in current_selectors:
                return SelectorEntry(
                    xpaths=current_selectors[action],
                    source="python",
                )
            raise SelectorNotFound(app, version, action)

        # 3. Check closest version in overrides
        if app in self._overrides:
            closest = self._find_closest_version(
                self._overrides[app], version
            )
            if closest and action in self._overrides[app][closest]:
                return SelectorEntry(
                    xpaths=self._overrides[app][closest][action],
                    source="yaml",
                )

        # 4. Fall back to current Python selectors
        if action in current_selectors:
            logger.warning(
                f"[Compat] No override for {app}/{version}/{action}, "
                f"falling back to current v{current_version} selectors"
            )
            return SelectorEntry(
                xpaths=current_selectors[action],
                source="python",
            )

        raise SelectorNotFound(app, version, action)

    def get_all(self, app: str, version: str) -> Dict[str, SelectorEntry]:
        """Get all selectors for an app/version combination."""
        if app not in self._apps:
            return {}

        result: Dict[str, SelectorEntry] = {}
        current_selectors = self._apps[app]["selectors"]

        # Start with current Python selectors as base
        for action, xpaths in current_selectors.items():
            result[action] = SelectorEntry(xpaths=xpaths, source="python")

        # Override with version-specific YAML if available
        if app in self._overrides and version in self._overrides[app]:
            for action, xpaths in self._overrides[app][version].items():
                result[action] = SelectorEntry(xpaths=xpaths, source="yaml")

        return result

    def list_actions(self, app: str) -> List[str]:
        """List all known action names for an app."""
        if app not in self._apps:
            return []
        actions = set(self._apps[app]["selectors"].keys())
        if app in self._overrides:
            for version_overrides in self._overrides[app].values():
                actions.update(version_overrides.keys())
        return sorted(actions)

    def get_current_version(self, app: str) -> Optional[str]:
        """Get the current (baseline) version for an app."""
        if app not in self._apps:
            return None
        return self._apps[app]["current_version"]

    def get_override_versions(self, app: str) -> List[str]:
        """List all versions that have YAML overrides."""
        if app not in self._overrides:
            return []
        return sorted(self._overrides[app].keys())

    def _find_closest_version(
        self, versions: Dict[str, Any], target: str
    ) -> Optional[str]:
        """Find the closest version <= target using string comparison."""
        candidates = sorted(versions.keys(), reverse=True)
        for v in candidates:
            if v <= target:
                return v
        return None

    def to_dict(self, app: str, version: str) -> Dict[str, Any]:
        """Export selectors as a JSON-serializable dict (for Electron IPC)."""
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
    """
    Extract a flat selector map from an existing dataclass selector instance.

    Converts e.g. FEED_SELECTORS.like_button = ['//*[@resource-id=...']', ...]
    into {"like_button": ['//*[@resource-id=...']', ...]}

    Args:
        instance: A dataclass instance (e.g., FeedSelectors(), NavigationSelectors())

    Returns:
        Dict mapping field_name -> List[str] of XPath selectors
    """
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
    """
    Build a namespaced selector map from multiple dataclass instances.

    Args:
        selector_instances: Dict of domain_name -> dataclass instance
            e.g. {"feed": FEED_SELECTORS, "navigation": NAVIGATION_SELECTORS}

    Returns:
        Flat dict with "domain.action" keys
        e.g. {"feed.like_button": [...], "navigation.home_tab": [...]}
    """
    result = {}
    for domain, instance in selector_instances.items():
        domain_map = build_selector_map_from_dataclass(instance)
        for action, xpaths in domain_map.items():
            result[f"{domain}.{action}"] = xpaths
    return result
