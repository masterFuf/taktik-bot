"""Does the screen photo find exactly what `d.xpath()` finds? Every selector, every captured dump.

Step 1 of the one-photo spec. For each dump of a corpus (the `debug_ui` captures, never in this
repository) and each selector of the Instagram and TikTok catalogues (every selector instance,
every language), the elements found by `ScreenSnapshot` are compared, node by node (their path in
the tree), with those uiautomator2's own engine finds (`PageSource.find_elements` after
`strict_xpath`, what `d.xpath()` runs). Exit 1 on any difference.

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

from uiautomator2.xpath import PageSource, strict_xpath  # noqa: E402

from taktik.core.shared.device.snapshot import ScreenSnapshot  # noqa: E402

PLATFORM_PACKAGES = (
    "taktik.core.social_media.instagram.ui.selectors",
    "taktik.core.social_media.tiktok.ui.selectors",
)


def _xpath_like(value) -> bool:
    return isinstance(value, str) and value.strip()[:1] in ("/", "(")


def _collect_from(value, out: set) -> None:
    if _xpath_like(value):
        out.add(value)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            if _xpath_like(item):
                out.add(item)


def catalogue_selectors() -> list:
    """Every xpath of both catalogues: the selector instances (all languages: no locale active,
    so the localized properties return the union) and the locale string tables themselves."""
    found: set = set()
    for package_name in PLATFORM_PACKAGES:
        locales = importlib.import_module(package_name + ".locales")
        if hasattr(locales, "set_active_locale"):
            locales.set_active_locale(None)
        for table in getattr(locales, "_LOCALES", {}).values():
            for value in table.values():
                _collect_from(value, found)
        package = importlib.import_module(package_name)
        for info in pkgutil.walk_packages(package.__path__, package_name + "."):
            try:
                module = importlib.import_module(info.name)
            except Exception:
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
    return sorted(found)


def _paths_u2(source: PageSource, selector: str):
    try:
        root = source.root
        tree = root.getroottree()
        return [tree.getpath(el.elem) for el in source.find_elements(strict_xpath(selector))], None
    except Exception as exc:
        return None, type(exc).__name__


def _paths_snapshot(snap: ScreenSnapshot, selector: str):
    elements = snap.elements(selector)
    if snap._root is None:  # noqa: SLF001 — the proof reads the tree it evaluated on
        return []
    tree = snap._root.getroottree()  # noqa: SLF001
    return [tree.getpath(el) for el in elements if hasattr(el, "tag")]


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
    selectors = catalogue_selectors()
    print(f"{len(dumps)} dumps x {len(selectors)} selectors")

    started = time.perf_counter()
    evaluations = mismatches = u2_errors = unreadable = 0
    examples = []
    for dump in dumps:
        try:
            xml = dump.read_text(encoding="utf-8", errors="replace")
            source = PageSource.parse(xml)
            _ = source.root
        except Exception:
            unreadable += 1
            continue
        snap = ScreenSnapshot(xml)
        for selector in selectors:
            evaluations += 1
            expected, error = _paths_u2(source, selector)
            if error:
                u2_errors += 1
                continue  # uiautomator2 itself raises on it: nothing the photo must reproduce
            if _paths_snapshot(snap, selector) != expected:
                mismatches += 1
                if len(examples) < 10:
                    examples.append((dump.name, selector[:120]))
    elapsed = time.perf_counter() - started
    print(f"evaluations: {evaluations}, differences: {mismatches}, selectors uiautomator2 rejects: "
          f"{u2_errors}, unreadable dumps: {unreadable}, {elapsed:.0f} s")
    for name, selector in examples:
        print(f"  DIFF {name}: {selector}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
