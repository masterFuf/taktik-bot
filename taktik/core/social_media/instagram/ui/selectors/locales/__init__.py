"""Per-language UI string overlay for Instagram selectors.

ONE module per language (``fr.py``, ``en.py``, … ``es.py`` later). Each holds
ONLY the language-specific selector fragments (``@text`` / ``@content-desc`` /
``@hint`` / bare labels) in a flat ``STRINGS`` dict keyed by
``"<surface>.<field>"``.

Language-neutral selectors (resource-id / class / position) stay in the selector
dataclasses under ``ui/selectors/**`` ; a migrated field is exposed as a property
``base_neutre + L("surface.field")``.

The active locale is chosen once per session by
``ui.language.detect_and_optimize(device, override=...)`` which calls
``set_active_locale()``. ``L(key)`` then returns the fragments of the active
language — or, when the language is unknown, the union of all languages so we
never match fewer selectors than the legacy "keep-all" behaviour.

Adding a language = add ``<lang>.py`` with a ``STRINGS`` dict (same keys) and
register it in ``_LOCALES`` below. No change to the selector dataclasses.

Note: per-process module-global state. Bots run one bridge process per device,
so parallel devices in different languages do not share this global.
"""
from typing import Dict, List, Optional, Set

from . import en as _en
from . import fr as _fr

# lang code -> { "<surface>.<field>": [xpath fragment, ...] }
_LOCALES: Dict[str, Dict[str, List[str]]] = {
    "en": _en.STRINGS,
    "fr": _fr.STRINGS,
}

_active: Optional[str] = None  # active language code, or None when unknown


def available_locales() -> List[str]:
    """Registered language codes (e.g. ``['en', 'fr']``)."""
    return list(_LOCALES.keys())


def set_active_locale(lang: Optional[str]) -> None:
    """Set the active language for selector string injection.

    ``None`` (or an unregistered code) selects the keep-all union fallback.
    """
    global _active
    _active = lang if lang in _LOCALES else None


def active_locale() -> Optional[str]:
    """Currently active language code, or ``None`` when unknown / union mode."""
    return _active


def L(key: str) -> List[str]:
    """Language-specific selector fragments for ``key`` in the active locale.

    - active locale known  -> that language's fragments (``[]`` if key absent)
    - active locale unknown -> union of every language (dedup, stable order)
    """
    if _active is not None:
        return list(_LOCALES[_active].get(key, []))
    return L_all(key)


def L_all(key: str) -> List[str]:
    """Union of ``key`` fragments across EVERY registered locale, regardless of
    the active locale (dedup, stable order).

    Use this when a consumer must match against ALL locales at once — e.g. the
    notifications classifier, which reads activity-feed rows whose visible text
    can be in any language the device runs, independently of the locale the
    selector layer has been optimized for.
    """
    seen: Set[str] = set()
    union: List[str] = []
    for strings in _LOCALES.values():
        for sel in strings.get(key, []):
            if sel not in seen:
                seen.add(sel)
                union.append(sel)
    return union
