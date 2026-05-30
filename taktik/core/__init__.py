"""Legacy top-level compatibility exports for ``taktik.core``."""


def get_device_facade():
    """Return the Instagram ``DeviceFacade`` lazily."""
    from .social_media.instagram.actions.core.device.facade import DeviceFacade

    return DeviceFacade


def get_direction():
    """Return the shared ``Direction`` enum lazily."""
    from .shared.device.facade import Direction

    return Direction


def get_device_manager():
    """Return the legacy-compatible ``DeviceManager`` lazily."""
    from .device import DeviceManager

    return DeviceManager


def __getattr__(name: str):
    if name == "DeviceFacade":
        return get_device_facade()
    if name == "Direction":
        return get_direction()
    if name == "DeviceManager":
        return get_device_manager()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["DeviceFacade", "Direction", "DeviceManager"]
