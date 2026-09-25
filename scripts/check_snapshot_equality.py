"""Does the screen photo find exactly what production finds? Every selector, every captured dump.

Step 1 of the one-photo spec. For each dump of a corpus (the `debug_ui` captures, never in this
repository) and each selector of the Instagram and TikTok catalogues, the photo is compared with
the production path on the same screen, node by node (their path in the tree), both ways:

- Instagram's: `CloneAwareDeviceProxy.xpath()` (every Instagram bridge mounts it; it rewrites
  `@resource-id` equalities) then uiautomator2's `d.xpath()`, against a photo taken with the
  proxy's rewrite;
- the plain `d.xpath()` (TikTok's bridges mount no proxy), against a plain photo.

A selector uiautomator2 rejects must be rejected by the photo's raw call too (its `find`/`exists`
then skip it, as the production loops behind `facade.xpath()` do). The number of evaluations the
proxy's rewrite changes is printed: it proves the check sees that path at all (a first version
of this proof compared the photo with a raw engine and was blind to it). Exit 1 on any difference.

What it proves, honestly: equality for the uiautomator2 INSTALLED. Under 3.3, `d.xpath()` and the
photo run the same selector class, so the check mostly proves the proxy rewrite and the tree; from
3.5, `d.xpath()` goes through `DeviceXPathSelector`, a different path. Run it with the version of
`requirements.lock`.

Selectors: every string of the selector catalogues (dataclass fields, properties, dict and list
values, locale tables, all languages) and of the version overrides (`compat/data/overrides/*.yaml`,
every version: they replace catalogue fields on the phones that run that version) that is an
xpath or a uiautomator2 shorthand (`@id`, `^regex`, `%text%`); plain labels are left out. Modules
that fail to import are named.

`--lxml` also compares, for information, the photo with plain lxml on `parse_ui_dump`: the engine
of the dump readers that do not go through `d.xpath()` (TikTok's popup scan, the author photo...).
A difference there is what such a reader would answer differently once it reads a photo.

Usage: python scripts/check_snapshot_equality.py [--corpus DIR ...] [--platform all|instagram|tiktok]
       [--list FILE] [--save-list FILE] [--limit N] [--every K] [--lxml] [--jobs N]
The corpus defaults to $TAKTIK_DEBUG_UI, else ./debug_ui. `--platform` keeps that platform's dumps
and catalogue (TikTok: the plain path only). `--list` reads the dumps from a file (one path per
line); `--save-list` writes the dumps checked, so a later run checks the same ones.
"""

from __future__ import annotations

import argparse
import importlib
import multiprocessing
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

PLATFORM_PACKAGES = {
    "instagram": "taktik.core.social_media.instagram.ui.selectors",
    "tiktok": "taktik.core.social_media.tiktok.ui.selectors",
}
APP_PACKAGES = {
    "instagram": ("com.instagram.",),
    "tiktok": ("com.zhiliaoapp.musically", "com.ss.android.ugc.trill", "com.ss.android.ugc.aweme",
               "com.taktik.tt"),
}
OVERRIDES_DIR = ROOT / "taktik" / "core" / "compat" / "data" / "overrides"


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


def override_selectors(platforms=tuple(PLATFORM_PACKAGES)) -> set:
    """Every selector of the version overrides, all versions of the given platforms."""
    import yaml

    found: set = set()
    for platform in platforms:
        path = OVERRIDES_DIR / f"{platform}.yaml"
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for entries in (data.get("versions") or {}).values():
            if isinstance(entries, dict):
                _collect_from(list(entries.values()), found)
    return found


def catalogue_selectors(platforms=tuple(PLATFORM_PACKAGES)):
    """(selectors, modules that failed to import). No locale is active, so the localized
    properties return every language. The version overrides are included."""
    found, skipped = _catalogue_only(platforms)
    return sorted(found | override_selectors(platforms)), skipped


def _catalogue_only(platforms):
    found: set = set()
    skipped = []
    for platform in platforms:
        package_name = PLATFORM_PACKAGES[platform]
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
    return found, skipped


class _U2Device:
    """What uiautomator2's `d.xpath` needs to run; the screen is passed as `source`."""

    wait_timeout = 1.0

    def __init__(self):
        self.xpath = XPathEntry(self)


class DumpCheck:
    """One dump, parsed once per side: the production path and the photo."""

    def __init__(self, xml: str):
        self.xml = xml
        self.source = PageSource(xml)
        self.source.root
        device = _U2Device()
        self.plain = device.xpath
        self.proxy = CloneAwareDeviceProxy(device, "com.instagram.android")
        self.photo = ScreenSnapshot(xml)
        self.photo_rewritten = ScreenSnapshot(xml, rewrite=self.proxy.rewrite_xpath)
        self._lxml_tree = None

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

    def lxml_agrees(self, selector: str) -> bool:
        """Does plain lxml on `parse_ui_dump` find something exactly when the photo does?"""
        from taktik.core.shared.device.ui_dump import parse_ui_dump

        if self._lxml_tree is None:
            self._lxml_tree = parse_ui_dump(self.xml)
        try:
            by_lxml = bool(self._lxml_tree.xpath(selector)) if self._lxml_tree is not None else False
        except Exception:
            by_lxml = False  # the readers skip a selector lxml rejects
        by_photo = bool(self.photographed(selector, False)[0])
        return by_lxml == by_photo


def dump_platform(text: str) -> str | None:
    for platform, prefixes in APP_PACKAGES.items():
        if any(f'package="{prefix}' in text for prefix in prefixes):
            return platform
    return None


# ── One dump, in a worker process ─────────────────────────────────────────────

_WORKER: dict = {}


def _init_worker(selectors, rewrites, lxml):
    _WORKER.update(selectors=selectors, rewrites=rewrites, lxml=lxml)


def check_dump(path: str) -> dict:
    """Counts and a few examples for one dump."""
    selectors, rewrites, lxml = _WORKER["selectors"], _WORKER["rewrites"], _WORKER["lxml"]
    result = {"same": 0, "both_raise": 0, "different": 0, "rewrite_changes": 0, "unreadable": 0,
              "lxml_different": 0, "examples": [], "lxml_examples": []}
    try:
        check = DumpCheck(Path(path).read_text(encoding="utf-8", errors="replace"))
    except Exception:
        result["unreadable"] = 1
        return result
    name = Path(path).name
    for selector in selectors:
        production = {rewrite: check.production(selector, rewrite) for rewrite in rewrites}
        for rewrite in rewrites:
            verdict = check.compare(selector, rewrite, production[rewrite])
            result[verdict] += 1
            if verdict == "different" and len(result["examples"]) < 5:
                result["examples"].append((name, rewrite, selector[:120]))
        if len(rewrites) == 2 and production[True] != production[False]:
            result["rewrite_changes"] += 1
        if lxml and not check.lxml_agrees(selector):
            result["lxml_different"] += 1
            if len(result["lxml_examples"]) < 5:
                result["lxml_examples"].append((name, selector[:120]))
    return result


def _corpus_dumps(args) -> list:
    if args.list:
        lines = Path(args.list).read_text(encoding="utf-8").splitlines()
        return [Path(line.strip()) for line in lines if line.strip()]
    corpora = args.corpus or [os.environ.get("TAKTIK_DEBUG_UI") or str(ROOT / "debug_ui")]
    dumps = []
    for corpus in corpora:
        base = Path(corpus)
        dumps += sorted(base.rglob("*.xml")) if base.is_dir() else []
    if args.platform != "all":
        dumps = [d for d in dumps
                 if dump_platform(d.read_text(encoding="utf-8", errors="replace")) == args.platform]
    dumps = dumps[:: max(1, args.every)]
    return dumps[: args.limit] if args.limit else dumps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", action="append", help="a dump folder (repeatable)")
    parser.add_argument("--platform", choices=("all", "instagram", "tiktok"), default="all")
    parser.add_argument("--list", help="read the dumps from this file, one path per line")
    parser.add_argument("--save-list", help="write the dumps checked to this file")
    parser.add_argument("--limit", type=int, default=0, help="at most N dumps (0: all)")
    parser.add_argument("--every", type=int, default=1, help="one dump in K (sampling)")
    parser.add_argument("--lxml", action="store_true", help="also compare with plain lxml (information)")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()

    dumps = _corpus_dumps(args)
    if not dumps:
        print("No dump found: nothing to check")
        return 0
    if args.save_list:
        Path(args.save_list).write_text("\n".join(str(d) for d in dumps) + "\n", encoding="utf-8")
    platforms = tuple(PLATFORM_PACKAGES) if args.platform == "all" else (args.platform,)
    in_catalogue, skipped = _catalogue_only(platforms)
    in_overrides = override_selectors(platforms)
    selectors = sorted(in_catalogue | in_overrides)
    from_overrides = len(in_overrides - in_catalogue)
    rewrites = (False,) if args.platform == "tiktok" else (True, False)
    try:
        from importlib.metadata import version as _version
        version = _version("uiautomator2")
    except Exception:
        version = getattr(uiautomator2, "__version__", "unknown")
    print(f"uiautomator2 {version}; {len(dumps)} dumps x {len(selectors)} selectors "
          f"({from_overrides} from the version overrides) x {len(rewrites)} path(s)")
    for line in skipped:
        print(f"  module not imported: {line}")

    started = time.perf_counter()
    totals = {"same": 0, "both_raise": 0, "different": 0, "rewrite_changes": 0, "unreadable": 0,
              "lxml_different": 0}
    examples, lxml_examples = [], []
    paths = [str(d) for d in dumps]
    init = (selectors, rewrites, args.lxml)
    if args.jobs > 1 and len(paths) > 1:
        with multiprocessing.Pool(args.jobs, initializer=_init_worker, initargs=init) as pool:
            results = pool.imap_unordered(check_dump, paths, chunksize=4)
            results = list(results)
    else:
        _init_worker(*init)
        results = [check_dump(path) for path in paths]
    for result in results:
        for key in totals:
            totals[key] += result[key]
        examples += result["examples"]
        lxml_examples += result["lxml_examples"]
    elapsed = time.perf_counter() - started
    evaluations = totals["same"] + totals["both_raise"] + totals["different"]
    print(f"evaluations: {evaluations}, same: {totals['same']}, rejected on both sides: "
          f"{totals['both_raise']}, differences: {totals['different']}, evaluations the proxy "
          f"rewrite changes: {totals['rewrite_changes']}, unreadable dumps: {totals['unreadable']}, "
          f"{elapsed:.0f} s")
    for name, rewrite, selector in examples[:10]:
        print(f"  DIFF {name} ({'proxy' if rewrite else 'plain'}): {selector}")
    if args.lxml:
        print(f"plain lxml on parse_ui_dump answers otherwise than the photo (information): "
              f"{totals['lxml_different']} of {len(dumps) * len(selectors)} evaluations")
        for name, selector in lxml_examples[:10]:
            print(f"  LXML {name}: {selector}")
    return 1 if totals["different"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
