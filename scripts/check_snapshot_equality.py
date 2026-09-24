"""Does the screen photo find exactly what production finds? Every selector, every captured dump.

Step 1 of the one-photo spec. For each dump of a corpus (the `debug_ui` captures, never in this
repository) and each selector of the Instagram and TikTok catalogues, the photo is compared with
the production path on the same screen, node by node (their path in the tree), both ways:

- Instagram's: `CloneAwareDeviceProxy.xpath()` (every Instagram bridge mounts it; it rewrites
  `@resource-id` equalities) then uiautomator2's `d.xpath()`, against a photo taken with the
  proxy's rewrite;
- the plain `d.xpath()` (TikTok's bridges mount no proxy), against a plain photo.

A selector uiautomator2 rejects must be rejected by the photo too. The number of evaluations the
proxy's rewrite changes is printed: it proves the check sees that path at all (a first version
of this proof compared the photo with a raw engine and was blind to it). Exit 1 on any difference.

Selectors: every string of the selector catalogues (dataclass fields, properties, dict and list
values, locale tables, all languages) that is an xpath or a uiautomator2 shorthand (`@id`,
`^regex`, `%text%`); plain labels are left out. Modules that fail to import are named.

Usage: python scripts/check_snapshot_equality.py [--corpus DIR] [--limit N] [--every K]
The corpus defaults to $TAKTIK_DEBUG_UI, else ./debug_ui.
"""

from __future__ import annotations

import argparse
import importlib
import os
import pkgutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import uiautomator2  # noqa: E402
from uiautomator2.xpath import PageSource, XPathEntry  # noqa: E402

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy  # noqa: E402
from taktik.core.shared.device.snapshot import ScreenSnapshot  # noqa: E402

PLATFORM_PACKAGES = (
    "taktik.core.social_media.instagram.ui.selectors",
    "taktik.core.social_media.tiktok.ui.selectors",
)


def _selector_like(value) -> bool:
    if not isinstance(value, str):
        return False
    head = value.strip()[:1]
    return head in ("/", "(", "@", "^") or (value.startswith("%") and len(value) > 1)


def _collect_from(value, out: set, depth: int = 0) -> None:
    if depth > 4:
        return
    if _selector_like(value):
        out.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_from(item, out, depth + 1)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _collect_from(item, out, depth + 1)


def catalogue_selectors():
    """(selectors, modules that failed to import). No locale is active, so the localized
    properties return every language."""
    found: set = set()
    skipped = []
    for package_name in PLATFORM_PACKAGES:
        locales = importlib.import_module(package_name + ".locales")
        if hasattr(locales, "set_active_locale"):
            locales.set_active_locale(None)
        for table in getattr(locales, "_LOCALES", {}).values():
            _collect_from(dict(table), found)
        package = importlib.import_module(package_name)
        for info in pkgutil.walk_packages(package.__path__, package_name + "."):
            try:
                module = importlib.import_module(info.name)
            except Exception as exc:
                skipped.append(f"{info.name}: {type(exc).__name__}")
                continue
            for obj in list(vars(module).values()):
                if not hasattr(type(obj), "__dataclass_fields__"):
                    continue
                for name in dir(obj):
                    if name.startswith("_"):
                        continue
                    try:
                        value = getattr(obj, name)
                    except Exception:
                        continue
                    if callable(value):
                        continue
                    _collect_from(value, found)
    return sorted(found), skipped


class _U2Device:
    """What uiautomator2's `d.xpath` needs to run; the screen is passed as `source`."""

    wait_timeout = 1.0

    def __init__(self):
        self.xpath = XPathEntry(self)


class DumpCheck:
    """One dump, parsed once per side: the production path and the photo."""

    def __init__(self, xml: str):
        self.source = PageSource(xml)
        self.source.root
        device = _U2Device()
        self.plain = device.xpath
        self.proxy = CloneAwareDeviceProxy(device, "com.instagram.android")
        self.photo = ScreenSnapshot(xml)
        self.photo_rewritten = ScreenSnapshot(xml, rewrite=self.proxy.rewrite_xpath)

    @staticmethod
    def _paths(elements):
        return [el.elem.getroottree().getpath(el.elem) for el in elements]

    def production(self, selector: str, rewrite: bool):
        entry = self.proxy.xpath if rewrite else self.plain
        try:
            return self._paths(entry(selector, self.source).all()), None
        except Exception as exc:
            return None, type(exc).__name__

    def photographed(self, selector: str, rewrite: bool):
        photo = self.photo_rewritten if rewrite else self.photo
        try:
            return self._paths(photo.elements(selector)), None
        except Exception as exc:
            return None, type(exc).__name__

    def compare(self, selector: str, rewrite: bool, production=None) -> str:
        """'same', 'both_raise' or 'different'. `production`: its result, when already known."""
        expected, expected_error = production or self.production(selector, rewrite)
        got, got_error = self.photographed(selector, rewrite)
        if expected_error or got_error:
            return "both_raise" if expected_error == got_error else "different"
        return "same" if expected == got else "different"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default=os.environ.get("TAKTIK_DEBUG_UI") or str(ROOT / "debug_ui"))
    parser.add_argument("--limit", type=int, default=0, help="at most N dumps (0: all)")
    parser.add_argument("--every", type=int, default=1, help="one dump in K (sampling)")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    dumps = sorted(corpus.rglob("*.xml")) if corpus.is_dir() else []
    dumps = dumps[:: max(1, args.every)]
    if args.limit:
        dumps = dumps[: args.limit]
    if not dumps:
        print(f"No dump under {corpus}: nothing to check")
        return 0
    selectors, skipped = catalogue_selectors()
    version = getattr(uiautomator2, "__version__", None)
    if version is None:
        try:
            from importlib.metadata import version as _version
            version = _version("uiautomator2")
        except Exception:
            version = "unknown"
    print(f"uiautomator2 {version}; {len(dumps)} dumps x {len(selectors)} selectors x 2 paths")
    for line in skipped:
        print(f"  module not imported: {line}")

    started = time.perf_counter()
    counts = {"same": 0, "both_raise": 0, "different": 0}
    rewrite_changes = unreadable = 0
    examples = []
    for dump in dumps:
        try:
            check = DumpCheck(dump.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            unreadable += 1
            continue
        for selector in selectors:
            production = {rewrite: check.production(selector, rewrite) for rewrite in (True, False)}
            for rewrite in (True, False):
                verdict = check.compare(selector, rewrite, production[rewrite])
                counts[verdict] += 1
                if verdict == "different" and len(examples) < 10:
                    examples.append((dump.name, rewrite, selector[:120]))
            if production[True] != production[False]:
                rewrite_changes += 1
    elapsed = time.perf_counter() - started
    print(f"evaluations: {sum(counts.values())}, same: {counts['same']}, rejected on both sides: "
          f"{counts['both_raise']}, differences: {counts['different']}, evaluations the proxy "
          f"rewrite changes: {rewrite_changes}, unreadable dumps: {unreadable}, {elapsed:.0f} s")
    for name, rewrite, selector in examples:
        print(f"  DIFF {name} ({'proxy' if rewrite else 'plain'}): {selector}")
    return 1 if counts["different"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
