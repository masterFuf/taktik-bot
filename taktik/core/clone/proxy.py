"""
Clone-aware device proxy.

Transparently wraps a uiautomator2 device so that code written against the
official Instagram package name (``com.instagram.android``) keeps working
unchanged on cloned packages (e.g. ``com.taktik.ig1``, ``com.nomix.ig.c1``).

The proxy rewrites the package prefix in three places:

1. ``device(resourceId="com.instagram.android:id/…")``
2. ``device.xpath("…com.instagram.android:id/…")``
3. UiObjects returned by ``device(...)`` are themselves wrapped so calls like
   ``item.child(resourceId="com.instagram.android:id/…")`` and
   ``item.sibling(...)`` also rewrite their kwargs.

Everything else (``device.press``, ``device.swipe``, ``device.info``,
``device.screenshot``, attribute writes, etc.) is forwarded unchanged.

The proxy is a no-op when the active package equals the official one, so
installing it is always safe — there is no overhead on stock Instagram.

Usage:
    from taktik.core.clone.proxy import CloneAwareDeviceProxy
    proxy = CloneAwareDeviceProxy(raw_device, "com.taktik.ig1")
    proxy(resourceId="com.instagram.android:id/search_tab").click()
    # → internally: device(resourceId="com.taktik.ig1:id/search_tab").click()
"""

from typing import Any, Optional
from .package_map import OFFICIAL_PACKAGE

# UiObject methods that return another UiObject — these must be wrapped
# recursively so subsequent .child(resourceId=...) calls are also rewritten.
_UI_OBJECT_RETURNING = frozenset({"child", "sibling", "left", "right", "up", "down"})


def _rewrite_kwargs(kwargs: dict, official: str, clone: str) -> dict:
    """Rewrite ``resourceId`` in *kwargs* if it contains the official package."""
    rid = kwargs.get("resourceId")
    if rid and isinstance(rid, str) and official in rid:
        kwargs = dict(kwargs)
        kwargs["resourceId"] = rid.replace(official, clone)
    return kwargs


def _rewrite_str(value: Any, official: str, clone: str) -> Any:
    """Rewrite a string if it contains the official package; pass-through otherwise."""
    if isinstance(value, str) and official in value:
        return value.replace(official, clone)
    return value


class _UiObjectProxy:
    """Wrapper around a uiautomator2 UiObject that rewrites ``resourceId``
    in ``.child()`` / ``.sibling()`` / ``.left()`` / ``.right()`` / etc."""

    __slots__ = ("_obj", "_official", "_clone")

    def __init__(self, obj, official: str, clone: str):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_official", official)
        object.__setattr__(self, "_clone", clone)

    def __getattr__(self, name):
        attr = getattr(self._obj, name)
        if name in _UI_OBJECT_RETURNING and callable(attr):
            official, clone = self._official, self._clone

            def wrapper(*args, **kwargs):
                kwargs = _rewrite_kwargs(kwargs, official, clone)
                result = attr(*args, **kwargs)
                return _UiObjectProxy(result, official, clone)

            return wrapper
        return attr

    def __setattr__(self, name, value):
        setattr(self._obj, name, value)

    def __call__(self, *args, **kwargs):
        # Some flows index/call into UiObject — forward transparently.
        return self._obj(*args, **kwargs)

    def __getitem__(self, idx):
        result = self._obj[idx]
        return _UiObjectProxy(result, self._official, self._clone)

    def __iter__(self):
        for item in self._obj:
            yield _UiObjectProxy(item, self._official, self._clone)

    def __len__(self):
        return len(self._obj)

    def __bool__(self):
        return bool(self._obj)


class _XPathSelectorProxy:
    """Transparent wrapper for ``device.xpath(...)`` selectors.

    The hardcoded-package rewrite already happens at the entry call
    (``CloneAwareDeviceProxy.xpath``). This proxy mostly exists so that any
    chained call that itself takes a raw XPath string (e.g. ``.child(...)``)
    also benefits from the rewrite.
    """

    __slots__ = ("_sel", "_official", "_clone")

    def __init__(self, sel, official: str, clone: str):
        object.__setattr__(self, "_sel", sel)
        object.__setattr__(self, "_official", official)
        object.__setattr__(self, "_clone", clone)

    def __getattr__(self, name):
        return getattr(self._sel, name)

    def __setattr__(self, name, value):
        setattr(self._sel, name, value)

    def __call__(self, *args, **kwargs):
        return self._sel(*args, **kwargs)


class CloneAwareDeviceProxy:
    """Transparent proxy around a uiautomator2 device that rewrites
    ``resourceId`` and XPath strings on-the-fly for cloned packages.

    Forwards every other attribute / method to the underlying device.
    """

    __slots__ = ("_device", "_official", "_clone")

    def __init__(self, device, clone_package: str, official: str = OFFICIAL_PACKAGE):
        object.__setattr__(self, "_device", device)
        object.__setattr__(self, "_official", official)
        object.__setattr__(self, "_clone", clone_package)

    # ── Introspection helpers ────────────────────────────────────────
    @property
    def clone_package(self) -> str:
        return self._clone

    @property
    def raw(self):
        """Return the underlying (un-proxied) uiautomator2 device."""
        return self._device

    # ── Forwarding / interception ────────────────────────────────────
    def __getattr__(self, name):
        if name == "xpath":
            xpath_fn = getattr(self._device, "xpath")
            official, clone = self._official, self._clone

            def patched_xpath(arg=None, *args, **kwargs):
                if arg is None:
                    sel = xpath_fn(*args, **kwargs)
                else:
                    arg = _rewrite_str(arg, official, clone)
                    sel = xpath_fn(arg, *args, **kwargs)
                return _XPathSelectorProxy(sel, official, clone)

            return patched_xpath
        return getattr(self._device, name)

    def __setattr__(self, name, value):
        # Forward attribute writes (e.g. device.click_post_delay = 0.5).
        setattr(self._device, name, value)

    def __call__(self, *args, **kwargs):
        kwargs = _rewrite_kwargs(kwargs, self._official, self._clone)
        result = self._device(*args, **kwargs)
        return _UiObjectProxy(result, self._official, self._clone)


def rewrite_selector(
    resource_id: str,
    *,
    target_package: Optional[str] = None,
    official: str = OFFICIAL_PACKAGE,
) -> str:
    """Rewrite a resource-id (or any string containing the official package).

    If *target_package* is omitted, uses the globally active package
    (see ``taktik.core.clone.get_active_package``).

    No-op when *target_package* equals the official package — safe to call
    everywhere unconditionally.
    """
    if target_package is None:
        # Local import to avoid circular dependency at module load.
        from . import get_active_package
        target_package = get_active_package()
    if not target_package or target_package == official:
        return resource_id
    if official not in resource_id:
        return resource_id
    return resource_id.replace(official, target_package)


__all__ = [
    "CloneAwareDeviceProxy",
    "rewrite_selector",
    "OFFICIAL_PACKAGE",
]
