"""Runtime config resolution for bridge-managed mobile apps."""

from typing import Any, Optional

from loguru import logger

from bridges.common.device.apps import (
    alternatives_for_platform,
    get_app_config,
    known_platforms,
)


def resolve_app_config(connection: Any, platform: str, package_override: Optional[str] = None) -> dict:
    """Resolve the effective app config for a platform and connected device."""
    app_config = get_app_config(platform)
    if not app_config:
        raise ValueError(f"Unknown platform '{platform}'. Must be one of: {known_platforms()}")

    if package_override and package_override != app_config["package"]:
        logger.info(f"[AppService] Using clone package: {package_override}")
        app_config["package"] = package_override
        # Taktik-cloner packages (com.taktik.ig*, com.taktik.tk*) do not share
        # the same internal activity class, so skip explicit activity launch.
        if package_override.startswith("com.taktik."):
            app_config["activity"] = None
        return app_config

    if package_override:
        return app_config

    device_manager = connection.device_manager
    alternatives = alternatives_for_platform(platform)
    if device_manager is None or not alternatives:
        return app_config

    for alternative_package in alternatives:
        if device_manager.is_app_installed(alternative_package):
            if alternative_package != app_config["package"]:
                logger.info(
                    f"[AppService] Default package '{app_config['package']}' "
                    f"not installed - using '{alternative_package}' for {platform}"
                )
                app_config["package"] = alternative_package
            return app_config

    logger.warning(
        f"[AppService] No known {platform} package found on device. "
        f"Tried: {alternatives}"
    )
    return app_config
