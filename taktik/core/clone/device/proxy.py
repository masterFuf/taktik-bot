"""
Package-agnostic device proxy (historically "clone-aware").

Transparently wraps a uiautomator2 device so that code written against the
official Instagram package name (``com.instagram.android``) keeps working
unchanged whatever prefix the id ACTUALLY has on screen:

  - ``com.instagram.android:id/X`` — stock Instagram;
  - ``com.taktik.ig1:id/X`` / ``com.nomix.ig.c1:id/X`` — a cloned package;
  - ``X`` — NO package prefix at all, which is what Instagram's Jetpack Compose
    screens (v442+) expose for their content ids.

It does this by turning an EXACT ``resourceId``/``@resource-id`` into a
``resourceIdMatches``/``substring-after`` form — ``^(.*:id/)?X$`` — that spans all
three. It used to only swap one prefix for another, which could not handle the
bare form, so a phone that auto-updated to a Compose build stopped finding its
rows even on the stock app. Same idiom TikTok DM already used
(``DMActions._resource_id_pattern``), generalised to any prefix.

Three interception points:

1. ``device(resourceId="…")``            → agnostic ``resourceIdMatches`` kwarg
2. ``device.xpath("…@resource-id=…")``   → agnostic ``substring-after`` predicate
3. UiObjects returned by ``device(...)`` are wrapped so ``item.child(resourceId=…)``
   and ``item.sibling(…)`` convert their kwargs too.

Everything else (``device.press``, ``device.swipe``, ``device.info``,
``device.screenshot``, attribute writes, etc.) is forwarded unchanged.

NOT a no-op on stock any more: it is mounted for EVERY Instagram bridge, because
the stock 442 app is exactly the one that needs the bare-id match. The overhead is
one regex build per selector, matched device-side by uiautomator.

Usage:
    from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
    proxy = CloneAwareDeviceProxy(raw_device, "com.taktik.ig1")
    proxy(resourceId="com.instagram.android:id/search_tab").click()
    # → internally: device(resourceIdMatches=r"^(.*:id/)?search_tab$").click()
"""

import re
from typing import Any, Optional

from taktik.core.clone.packages.package_map import OFFICIAL_PACKAGE

# UiObject methods that return another UiObject — these must be wrapped
# recursively so subsequent .child(resourceId=...) calls are also rewritten.
_UI_OBJECT_RETURNING = frozenset({"child", "sibling", "left", "right", "up", "down"})


def _agnostic_pattern(resource_id: str) -> str:
    """A `resourceIdMatches` regex that matches an id under ANY package prefix, or none.

    `^(.*:id/)?<token>$` matches all three forms the same node can take:
      - `com.instagram.android:id/<token>` — the official package;
      - `com.nomix.ig.c1:id/<token>`       — a clone package;
      - `<token>`                          — no prefix at all, which is what Instagram's
        Jetpack Compose screens (442+) expose for their content ids.

    The token is the id after the last `:id/` (or the whole string when there is none),
    escaped so an id is never read as a regex. This is the same idiom TikTok DM already
    uses (`DMActions._resource_id_pattern`) — extended here to be package-agnostic.
    """
    token = resource_id.rsplit(":id/", 1)[-1]
    return f"^(.*:id/)?{re.escape(token)}$"


def _rewrite_kwargs(kwargs: dict, official: str, clone: str) -> dict:
    """Turn an exact ``resourceId`` into a package-agnostic ``resourceIdMatches``.

    Why not the old prefix swap (`com.instagram.android` -> clone package)? Because it
    only ever handled ONE alternative prefix and could not handle the ABSENCE of a prefix.
    On Instagram 442 the official app exposes its Compose content ids with no package at
    all (`activity_feed_newsfeed_story_row`, not `com.instagram.android:id/…`), so an exact
    match found nothing. The agnostic regex covers the clone case AND the bare case AND the
    stock case in one shape — verified on a live 442 device against a 410 baseline: it
    recovers the bare ids and never regresses the prefixed native ones.

    `official`/`clone` are no longer needed for the match (the regex spans every prefix) but
    stay in the signature so the two call sites keep one contract. A caller that already
    passes `resourceIdMatches` is left untouched — it knows what it is doing.
    """
    rid = kwargs.get("resourceId")
    if rid and isinstance(rid, str):
        kwargs = dict(kwargs)
        del kwargs["resourceId"]
        kwargs["resourceIdMatches"] = _agnostic_pattern(rid)
    return kwargs


# A `@resource-id="…"` EQUALITY test inside an xpath predicate. Only equality is rewritten;
# a `contains(@resource-id, …)` form is already partial and left as-is.
_XPATH_RID_EQ = re.compile(r'@resource-id\s*=\s*"([^"]+)"')


def _rewrite_str(value: Any, official: str, clone: str) -> Any:
    """Make every ``@resource-id="pkg:id/X"`` equality in an xpath package-agnostic.

    Same reasoning as the kwarg path: an exact `@resource-id="com.instagram.android:id/X"`
    misses the bare `X` that Compose exposes on IG 442 (and misses a clone's prefix too).
    Each equality becomes `(substring-after(@resource-id,":id/")="X" or @resource-id="X")`,
    which matches the id under ANY prefix or none. `official`/`clone` are unused now (the
    form is prefix-free) but kept for one signature across both call sites.
    """
    if not (isinstance(value, str) and "@resource-id" in value):
        return value

    def _repl(match: "re.Match") -> str:
        token = match.group(1).rsplit(":id/", 1)[-1]
        return f'(substring-after(@resource-id,":id/")="{token}" or @resource-id="{token}")'

    return _XPATH_RID_EQ.sub(_repl, value)


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
        from taktik.core.clone import get_active_package
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
