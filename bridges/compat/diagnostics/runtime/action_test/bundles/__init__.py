"""Public facade for compat action-test bundle factories."""

from bridges.compat.diagnostics.runtime.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from bridges.compat.diagnostics.runtime.action_test.bundles.tiktok import (
    build_tiktok_action_bundle,
    create_tiktok_device_facade,
)


__all__ = [
    "build_instagram_action_bundle",
    "build_tiktok_action_bundle",
    "create_instagram_device_facade",
    "create_tiktok_device_facade",
]

