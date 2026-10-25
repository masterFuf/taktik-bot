"""The platforms whose selector catalogues compat patches, registered by the host that runs them.

compat names no platform: the version overrides, the clone patch, the Lab's tables read the
catalogues a host registered here. Each host (the bridges' entry, the CLI, the test harness, a
script that drives a phone) registers, at its start, every platform it serves: a name and a loader
that returns the platform's `PlatformSelectors`. Symfony would call it a compiler pass filling a
tagged registry; here the tag is a call at the start of the process.

The loader runs at the first read, not at registration: a platform's selectors import its whole
package (seconds for Instagram and TikTok together), and a bridge that never touches a phone (the
schema gate at every launch of the app) must not pay for them. The first read is at the latest the
phone's connection (`shared/device/manager.py`), so every registered catalogue is loaded, then
patched, before any workflow reads it, as it was when compat imported them itself.

A read of a platform no host registered, or a platform that hands an empty table, raises a
`SelectorRegistryError` that says so: a registry that answers nothing in silence would leave a run
on the baseline selectors of an app that moved on, with nothing in the log.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Tuple

from loguru import logger


class SelectorRegistryError(LookupError):
    """The selector tables a read asks for are not there: a host's start is missing something."""


class PlatformNotRegistered(SelectorRegistryError):
    """No host of this process registered the platform (or any platform) before the read."""

    def __init__(self, platform: str, registered: Tuple[str, ...]):
        self.platform = platform
        self.registered = registered
        known = ", ".join(registered) if registered else "none"
        super().__init__(
            f"No selector catalogue registered for {platform!r} (registered: {known}). The host "
            "registers its platforms at its start (`register_platform`), before any phone connects."
        )


class EmptySelectorTable(SelectorRegistryError):
    """A platform's loader handed no catalogue, or a domain without its catalogue object."""


@dataclass(frozen=True)
class PlatformSelectors:
    """What a platform hands compat: its catalogues by domain, the names the YAML overrides use.

    `copies`: a domain whose fields copy another domain's values at import (Instagram's post
    sub-catalogues copy `post`); the xpath -> selectorId index reads such an xpath as the source's.
    """

    domains: Mapping[str, Any]
    copies: Mapping[str, str] = field(default_factory=dict)


Loader = Callable[[], PlatformSelectors]

_LOADERS: Dict[str, Loader] = {}
_LOADED: Dict[str, PlatformSelectors] = {}


def register_platform(platform: str, load: Loader) -> None:
    """Declare a platform and how to load its selectors; the loader runs at the first read.

    A platform registered again keeps its first loader: two hosts of one process (the test
    harness and the CLI it drives) both point at the platform's one declaration.
    """
    if platform in _LOADERS:
        logger.debug(f"[Compat] {platform} already registered, first loader kept")
        return
    _LOADERS[platform] = load


def registered_platforms() -> Tuple[str, ...]:
    """The platforms registered so far, in registration order. Raises when there is none: a
    connection that patches 'every registered platform' would otherwise patch nothing, in silence."""
    if not _LOADERS:
        raise PlatformNotRegistered("any platform", ())
    return tuple(_LOADERS)


def platform_selectors(platform: str) -> PlatformSelectors:
    """The platform's catalogues by domain, loaded at the first call."""
    if platform not in _LOADERS:
        raise PlatformNotRegistered(platform, tuple(_LOADERS))
    if platform not in _LOADED:
        selectors = _LOADERS[platform]()
        empty = [name for name, catalogue in selectors.domains.items() if catalogue is None]
        if not selectors.domains or empty:
            raise EmptySelectorTable(
                f"The selector catalogue of {platform!r} is empty"
                + (f" (domains without a catalogue: {', '.join(empty)})" if empty else "")
            )
        _LOADED[platform] = selectors
    return _LOADED[platform]
