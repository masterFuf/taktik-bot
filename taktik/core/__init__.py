"""Top-level compatibility exports for ``taktik.core``."""


def get_direction():
    """Return the shared ``Direction`` enum lazily."""
    from .shared.device.facade import Direction

    return Direction


def get_device_manager():
    """Return the shared ``DeviceManager`` lazily."""
    from .shared.device.manager import DeviceManager

    return DeviceManager


def __getattr__(name: str):
    if name == "Direction":
        return get_direction()
    if name == "DeviceManager":
        return get_device_manager()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["Direction", "DeviceManager"]
