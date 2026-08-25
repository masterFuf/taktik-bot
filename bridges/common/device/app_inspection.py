"""Compat re-export — the primitives moved to their AGENTS owner.

`taktik/core/shared/device/app_inspection.py` owns these now: they are ADB shell
primitives, and the standalone CLI needs `get_installed_app_version` without
importing a desktop bridge adapter. Existing bridge imports keep working here.
"""

from taktik.core.shared.device.app_inspection import (
    get_installed_app_version,
    is_app_running,
    is_package_installed,
)

__all__ = ["get_installed_app_version", "is_app_running", "is_package_installed"]
