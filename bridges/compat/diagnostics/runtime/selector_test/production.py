"""The selectors of the bench: those production runs on the connected phone.

Production, once connected: the overrides of the installed version (`apply_version_overrides`,
every YAML version <= the installed one, compared numerically), then the language detected on
the app's screen (`detect_and_optimize`), which picks the locale of the `L(...)` properties and
filters the other language out of the fields. The bench takes the same steps, then reads the
catalogues as the workflows read them: public fields AND properties.

Only what production hands `d.xpath()` is evaluated: an xpath or a uiautomator2 shorthand. A
label, a bare resource-id or a class name is compared elsewhere; it is counted, not tested. A
selector the language filter emptied is kept with no xpath, so it fails.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from loguru import logger

from bridges.compat.diagnostics.runtime.selector_test.runner import take_screen
from taktik.core.compat.selectors.registry import SelectorEntry, build_full_selector_map


@dataclass(frozen=True)
class PlatformCatalogue:
    """What production patches and reads for one app."""

    domains: Dict[str, Any]
    baseline_version: str
    apply_overrides: Callable[[str, str], int]
    detect_language: Callable[[Any], str]


@dataclass(frozen=True)
class ProductionSelectors:
    entries: Dict[str, SelectorEntry]
    version: str
    baseline_version: str
    overrides_applied: int
    language: str
    skipped_not_xpath: int
    skipped_empty: int


@dataclass(frozen=True)
class SelectorTestPlan:
    device: Any
    rewrite: Optional[Callable[[str], str]]
    xml: Optional[str]
    dump_error: Optional[str]
    selectors: ProductionSelectors


class _TakenScreen:
    """The dump already taken, so the language is detected on the screen being tested."""

    def __init__(self, xml: str):
        self._xml = xml

    def get_xml_dump(self) -> str:
        return self._xml


def platform_catalogue(app: str) -> PlatformCatalogue:
    from taktik.core.compat.selectors import setup

    if app == "instagram":
        from taktik.core.social_media.instagram.ui.language import detect_and_optimize

        return PlatformCatalogue(
            setup.INSTAGRAM_SELECTOR_DOMAINS, setup.INSTAGRAM_TARGET_VERSION,
            setup.apply_version_overrides, detect_and_optimize,
        )
    if app == "tiktok":
        from taktik.core.social_media.tiktok.ui.language import detect_and_optimize

        return PlatformCatalogue(
            setup.TIKTOK_SELECTOR_DOMAINS, setup.TIKTOK_TARGET_VERSION,
            setup.apply_version_overrides, detect_and_optimize,
        )
    raise ValueError(f"Unknown app: {app}")


def is_xpath_selector(value: str) -> bool:
    """An xpath or a uiautomator2 shorthand (`@id`, `^regex`, `%text%`)."""
    head = value.strip()
    return (
        head.lstrip("(").startswith("/")
        or head[:1] in ("@", "^")
        or (head.startswith("%") and len(head) > 1)
    )


def resolve_production_selectors(
    app: str,
    version: str,
    screen: Any,
    catalogue: Optional[PlatformCatalogue] = None,
) -> ProductionSelectors:
    """Patch the catalogues for `version`, detect the language on `screen`, read them back.

    `source` is "yaml" for a selector whose value differs from the baseline once patched, a
    property included when a `_x_base` it reads was overridden.
    """
    catalogue = catalogue or platform_catalogue(app)

    catalogue.apply_overrides(app, catalogue.baseline_version)
    baseline = build_full_selector_map(catalogue.domains, include_properties=True)
    applied = catalogue.apply_overrides(app, version) if version else 0
    patched = build_full_selector_map(catalogue.domains, include_properties=True)

    try:
        language = catalogue.detect_language(screen) or "unknown"
    except Exception as exc:  # noqa: BLE001 - production goes on with every locale
        logger.warning(f"[SelectorTest] Language detection failed: {exc}")
        language = "unknown"
    live = build_full_selector_map(catalogue.domains, include_properties=True)

    entries: Dict[str, SelectorEntry] = {}
    not_xpath = empty = 0
    for key, values in patched.items():
        xpaths = [value for value in live.get(key, []) if is_xpath_selector(value)]
        # A selector the language emptied stays, with no xpath: production has nothing left
        # to find it with in this language.
        if xpaths or any(is_xpath_selector(value) for value in values):
            source = "yaml" if values != baseline.get(key) else "python"
            entries[key] = SelectorEntry(xpaths=xpaths, source=source)
        elif values:
            not_xpath += 1
        else:
            empty += 1

    return ProductionSelectors(
        entries=entries,
        version=version,
        baseline_version=catalogue.baseline_version,
        overrides_applied=applied,
        language=language,
        skipped_not_xpath=not_xpath,
        skipped_empty=empty,
    )


def production_device(app: str, raw_device) -> tuple[Any, Optional[Callable[[str], str]]]:
    """What production calls `xpath()` on, and its rewrite: every Instagram bridge mounts the
    clone-aware proxy (`InstagramBridgeBase._after_connect`), TikTok mounts none."""
    if app != "instagram":
        return raw_device, None

    from taktik.core.clone import get_active_package
    from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
    from taktik.core.clone.packages.package_map import OFFICIAL_PACKAGE

    if isinstance(raw_device, CloneAwareDeviceProxy):
        proxy = raw_device
    else:
        proxy = CloneAwareDeviceProxy(raw_device, get_active_package() or OFFICIAL_PACKAGE)
    return proxy, proxy.rewrite_xpath


def installed_version(device_id: str, app: str) -> str:
    """The version the connection patcher reads (`apply_overrides_for_device`), or ""."""
    from taktik.core.clone.packages.package_map import get_package_variants
    from taktik.core.shared.device.app_inspection import get_installed_app_version

    for package in get_package_variants(app):
        version = get_installed_app_version(device_id, package, app)
        if version:
            return version
    return ""


def prepare_selector_test(
    app: str,
    requested_version: str,
    device_id: str,
    raw_device,
    *,
    catalogue: Optional[PlatformCatalogue] = None,
    read_installed_version: Callable[[str, str], str] = installed_version,
) -> SelectorTestPlan:
    """Device, version, screen and selectors, in production's order. The version asked by the
    app is the one it read on this phone; without it, the phone is asked."""
    device, rewrite = production_device(app, raw_device)
    version = requested_version or read_installed_version(device_id, app)
    xml, dump_error = take_screen(device)
    screen = _TakenScreen(xml) if xml else device
    selectors = resolve_production_selectors(app, version, screen, catalogue)
    return SelectorTestPlan(device, rewrite, xml, dump_error, selectors)


__all__ = [
    "PlatformCatalogue",
    "ProductionSelectors",
    "SelectorTestPlan",
    "installed_version",
    "is_xpath_selector",
    "platform_catalogue",
    "prepare_selector_test",
    "production_device",
    "resolve_production_selectors",
]
