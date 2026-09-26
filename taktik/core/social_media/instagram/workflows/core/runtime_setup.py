"""Runtime setup helpers for Instagram workflows.

`prepare_instagram_selectors` is the part every Instagram launcher shares: the selector catalogs
matched to the installed version, to a clone's package, then to the app language read from the
screen. `prepare_instagram_automation_runtime` adds what only the automation carries.
"""

from typing import Any, Callable, Optional

from taktik.core.clone import patch_selectors_for_package, set_active_package
from taktik.core.clone.packages import get_original_package
from taktik.core.social_media.instagram.ui.language import detect_and_optimize

# NB: `apply_version_overrides` is imported lazily inside the function below.
# `compat.selectors.setup` imports the Instagram selector catalogs, which forces
# this package (`social_media.instagram`) to initialize; a module-level import here
# would re-enter the still-initializing compat module and raise a circular ImportError.

LogCallback = Callable[[str, str], None]
VersionProvider = Callable[[], Optional[str]]


def _noop_log(_level: str, _message: str) -> None:
    return None


def prepare_instagram_selectors(
    *,
    device: Any,
    package_name: Optional[str] = None,
    installed_version_provider: Optional[VersionProvider] = None,
    log: LogCallback = _noop_log,
) -> None:
    """Match the selector catalogs to the run's app, before any localized selector is read.

    In this order: the installed version's overrides, the clone package's ids (only when a
    package is named), then the app language detected on the current screen.
    """
    try:
        from taktik.core.compat.selectors.setup import apply_version_overrides

        detected_version = installed_version_provider() if installed_version_provider else None
        if detected_version:
            patched = apply_version_overrides("instagram", detected_version)
            if patched > 0:
                log("info", f"Applied {patched} selector override(s) for Instagram v{detected_version}")
            else:
                log("info", f"Instagram v{detected_version}: no selector overrides needed")
    except Exception as exc:
        log("warning", f"Version override failed (non-fatal): {exc}")

    if package_name:
        try:
            patched_clone = patch_selectors_for_package("instagram", package_name)
            if patched_clone > 0:
                log("info", f"Patched {patched_clone} selector(s) for clone: {package_name}")
        except Exception as exc:
            log("warning", f"Clone selector patching failed (non-fatal): {exc}")

    try:
        detected_lang = detect_and_optimize(device)
        log("info", f"App language detected: {detected_lang.upper()}")
    except Exception as exc:
        log("warning", f"Language detection failed (non-fatal): {exc}")


def prepare_instagram_automation_runtime(
    *,
    automation: Any,
    workflow_config: dict,
    package_name: Optional[str] = None,
    installed_version_provider: Optional[VersionProvider] = None,
    log: LogCallback = _noop_log,
) -> None:
    """Apply package, selector and language runtime setup to an automation instance."""
    effective_package = package_name or get_original_package("instagram")

    automation.config = workflow_config
    automation.package_name = effective_package
    set_active_package(effective_package)
    log("info", "Dynamic config applied")

    prepare_instagram_selectors(
        device=automation.device,
        package_name=package_name,
        installed_version_provider=installed_version_provider,
        log=log,
    )
