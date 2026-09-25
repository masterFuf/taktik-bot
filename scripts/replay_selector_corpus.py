"""Replay the Instagram baseline dumps of the Lab corpus on two states of the selector catalogue.

Every xpath field of every `*_SELECTORS` catalogue (properties included, with the fr then the en
locale, union per dump) is evaluated on every baseline dump, in the base revision and in the
working tree. A field that matches FEWER dumps now than in the base is a baseline regression:
listed, and the exit code is 1.

    python scripts/replay_selector_corpus.py                 # working tree against HEAD
    python scripts/replay_selector_corpus.py --base origin/main

The corpus is `debug_ui/` (local only, never versioned: dumps are personal data). A field no dump
matches in either state says nothing: its screen is absent from the corpus.
"""

from __future__ import annotations

import argparse
import glob
import importlib
import io
import json
import multiprocessing
import os
import pkgutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = "410.0.0.53.71"
NS = {"re": "http://exslt.org/regular-expressions"}


def _is_xpath(value) -> bool:
    return isinstance(value, str) and value.lstrip().startswith(("/", "("))


def _xpaths(value):
    if _is_xpath(value):
        return [value]
    if isinstance(value, (list, tuple)):
        return [v for v in value if _is_xpath(v)]
    return []


def dump_fields(out_path: str) -> None:
    """Child mode: write {catalogue.field: [xpaths]} for the code on PYTHONPATH."""
    import taktik.core.social_media.instagram.ui.selectors as package
    from taktik.core.social_media.instagram.ui.selectors import locales

    catalogues = {}
    modules = [package] + [importlib.import_module(info.name)
                           for info in pkgutil.walk_packages(package.__path__, package.__name__ + ".")]
    for module in modules:
        for name, obj in vars(module).items():
            owner = type(obj).__module__
            if name.endswith("_SELECTORS") and owner.startswith(package.__name__):
                if id(obj) not in catalogues or module.__name__ == owner:
                    catalogues[id(obj)] = (name, obj)

    fields = {}
    for name, obj in catalogues.values():
        attrs = {n for n in vars(obj) if not n.startswith("_")}
        attrs |= {n for klass in type(obj).__mro__ for n, v in vars(klass).items()
                  if isinstance(v, property) and not n.startswith("_")}
        for attr in sorted(attrs):
            found = []
            for lang in ("fr", "en"):
                locales.set_active_locale(lang)
                try:
                    found += [x for x in _xpaths(getattr(obj, attr)) if x not in found]
                except Exception:
                    pass
            locales.set_active_locale(None)
            if found:
                fields[f"{name}.{attr}"] = found
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(fields, handle)


def _fields_of(code_root: str, workdir: str, label: str) -> dict:
    out = os.path.join(workdir, f"fields_{label}.json")
    env = {**os.environ, "PYTHONPATH": code_root, "PYTHONIOENCODING": "utf-8"}
    subprocess.run([sys.executable, os.path.abspath(__file__), "--dump-fields", out],
                   env=env, cwd=code_root, check=True, stdout=subprocess.DEVNULL)
    with open(out, encoding="utf-8") as handle:
        return json.load(handle)


def _extract(revision: str, workdir: str) -> str:
    archive = subprocess.run(["git", "archive", "--format=tar", revision, "taktik"],
                             cwd=ROOT, check=True, capture_output=True).stdout
    target = os.path.join(workdir, "base")
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(target)
    return target


def _match_chunk(args):
    # Here, not at import: the field dump runs this file against the BASE code on PYTHONPATH.
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from lxml import etree
    from taktik.core.shared.device.ui_dump import parse_ui_dump

    paths, xpaths = args
    compiled = {}
    for xpath in xpaths:
        try:
            compiled[xpath] = etree.XPath(xpath, namespaces=NS)
        except Exception:
            pass
    hits = {}
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as handle:
            root = parse_ui_dump(handle.read())
        if root is None:
            continue
        for xpath, finder in compiled.items():
            try:
                if finder(root):
                    hits.setdefault(xpath, []).append(path)
            except Exception:
                pass
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="HEAD", help="revision to compare the working tree with")
    parser.add_argument("--dump-fields", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.dump_fields:
        dump_fields(args.dump_fields)
        return 0

    dumps = sorted(glob.glob(os.path.join(ROOT, "debug_ui", "cartography", "*", "instagram", BASELINE,
                                          "**", "*.xml"), recursive=True))
    if not dumps:
        print(f"No {BASELINE} dump under debug_ui/: nothing to replay.")
        return 0

    with tempfile.TemporaryDirectory() as workdir:
        old = _fields_of(_extract(args.base, workdir), workdir, "base")
        new = _fields_of(ROOT, workdir, "now")

    xpaths = sorted({x for fields in (old, new) for values in fields.values() for x in values})
    workers = max(1, (os.cpu_count() or 2) - 1)
    chunks = [dumps[i::workers] for i in range(workers)]
    hits = {}
    with multiprocessing.Pool(workers) as pool:
        for part in pool.map(_match_chunk, [(chunk, xpaths) for chunk in chunks]):
            for xpath, paths in part.items():
                hits.setdefault(xpath, []).extend(paths)

    def matched(values):
        return {path for xpath in values for path in hits.get(xpath, [])}

    losses = []
    for field in sorted(set(old) | set(new)):
        before, after = matched(old.get(field, [])), matched(new.get(field, []))
        if len(after) < len(before):
            losses.append((field, len(before), len(after), sorted(before - after)[:3]))

    print(f"{len(dumps)} dumps {BASELINE}, {len(old)} fields in {args.base}, {len(new)} now.")
    if not losses:
        print("No field matches fewer baseline dumps than before.")
        return 0
    for field, before, after, examples in losses:
        print(f"LOSS {field}: {before} -> {after}")
        for path in examples:
            print(f"    {os.path.relpath(path, ROOT)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
