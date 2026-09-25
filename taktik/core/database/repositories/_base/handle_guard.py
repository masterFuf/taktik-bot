"""A pseudo becomes a profile row only if it can be a handle on its platform."""

from taktik.core.shared.text import is_platform_handle


class InvalidHandleError(ValueError):
    """A profile write carried text that the platform would not register as a handle."""


def require_handle(username, platform: str) -> str:
    """Return `username` unchanged, or raise before anything is read or written under it.

    Refused before the lookup too: a label stored earlier ("Send message") would otherwise be
    found and updated with the data of whichever profile was on screen.
    """
    if not is_platform_handle(username, platform):
        raise InvalidHandleError(f"Not a {platform} handle, profile not written: {username!r}")
    return username


__all__ = ["InvalidHandleError", "require_handle"]
