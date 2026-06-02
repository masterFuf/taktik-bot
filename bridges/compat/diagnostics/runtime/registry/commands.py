"""Registry command handlers for the compat diagnostics bridge."""


def handle_get_registry(ipc, registry, app_name: str, version: str) -> None:
    """Return the full selector registry as JSON."""
    try:
        data = registry.to_dict(app_name, version)
        ipc.send("registry_data", **data)
    except Exception as exc:
        ipc.send("error", error=str(exc), error_code="REGISTRY_ERROR")


def handle_list_actions(ipc, registry, app_name: str) -> None:
    """List all known action names for an app."""
    try:
        actions = registry.list_actions(app_name)
        ipc.send("actions_list", app=app_name, actions=actions, count=len(actions))
    except Exception as exc:
        ipc.send("error", error=str(exc), error_code="LIST_ERROR")


def handle_get_selector(ipc, registry, app_name: str, version: str, action: str) -> None:
    """Get a specific selector."""
    from taktik.core.compat.selectors import SelectorNotFound

    try:
        entry = registry.get(app_name, version, action)
        ipc.send(
            "selector",
            app=app_name,
            version=version,
            action=action,
            xpaths=entry.xpaths,
            source=entry.source,
        )
    except SelectorNotFound as exc:
        ipc.send(
            "selector_not_found",
            app=exc.app,
            version=exc.version,
            action=exc.action,
        )
    except Exception as exc:
        ipc.send("error", error=str(exc), error_code="SELECTOR_ERROR")


def handle_check_selectors(ipc, registry, app_name: str, version: str) -> None:
    """Validate all selectors exist for a version and report any missing."""
    try:
        all_selectors = registry.get_all(app_name, version)
        current_version = registry.get_current_version(app_name)
        override_versions = registry.get_override_versions(app_name)

        python_count = sum(1 for entry in all_selectors.values() if entry.source == "python")
        yaml_count = sum(1 for entry in all_selectors.values() if entry.source == "yaml")

        ipc.send(
            "check_result",
            app=app_name,
            version=version,
            current_version=current_version,
            override_versions=override_versions,
            total_selectors=len(all_selectors),
            python_selectors=python_count,
            yaml_selectors=yaml_count,
            is_current_version=(version == current_version),
            status="OK",
        )
    except Exception as exc:
        ipc.send("error", error=str(exc), error_code="CHECK_ERROR")


__all__ = [
    "handle_check_selectors",
    "handle_get_registry",
    "handle_get_selector",
    "handle_list_actions",
]

