"""Replay the TikTok screen decisions of two states of the code on captured dumps. Read-only.

For each TikTok capture, under each version the overrides know (the baseline and every version of
`compat/data/overrides/tiktok.yaml`), in the language the capture shows, the production reads run
on a fake phone: its `xpath` is uiautomator2's own `XPathEntry` (the code `d.xpath()` runs), its
dump is the capture, its clock jumps when the code sleeps. The reads: the popup scan, the comment
sheet, the suggestion page, `get_video_info` as the feed loops call it and in full, the For You and
inbox checks, `is_user_followed`, the Lab's screen name. Their answers, and the gestures they would
make, are compared between a base revision (`git archive`) and the working tree. Exit 1 on any
difference. The dumps each state asks for are printed, with the fake cost of `--dump-ms` per dump.

    python scripts/replay_screen_decisions.py --corpus DIR [--corpus DIR ...] [--base HEAD]
    python scripts/replay_screen_decisions.py --list FILE [--save-list FILE] [--report FILE]

The corpus defaults to $TAKTIK_DEBUG_UI, else ./debug_ui (captures are personal data: never in
this repository). A read that exists in one state only is listed, not compared.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import subprocess
import sys
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIKTOK_PACKAGES = ("com.zhiliaoapp.musically", "com.ss.android.ugc.trill", "com.ss.android.ugc.aweme",
                   "com.taktik.tt")
PROBES = ("popups", "comments", "suggestion", "video_info_feed", "video_info_full", "for_you",
          "inbox", "followed", "lab_screen", "read_screen")


# ── Child: runs inside one state of the code (PYTHONPATH), never imports the other ─────────────

def _plain(value):
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(v) for v in value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)


def _child_languages(files):
    from loguru import logger
    logger.remove()
    from taktik.core.social_media.tiktok.ui.language import _DETECTION

    class Screen:
        def __init__(self, xml):
            self.xml = xml

        def dump_hierarchy(self, *_a, **_k):
            return self.xml

    languages = {}
    for path in files:
        _DETECTION.reset()
        try:
            languages[path] = _DETECTION.detect_language(Screen(Path(path).read_text(encoding="utf-8", errors="replace")))
        except Exception:
            languages[path] = "unknown"
    return languages


def _child_decisions(files, version, language, dump_ms):
    import time

    from loguru import logger
    logger.remove()

    now = [1000.0]
    time.time = lambda: now[0]
    time.monotonic = lambda: now[0]
    time.sleep = lambda seconds: now.__setitem__(0, now[0] + max(float(seconds), 0.0))

    from uiautomator2.xpath import XPathEntry

    class Phone:
        wait_timeout = 1.0

        def __init__(self):
            self.xml, self.dumps, self.gestures = "", 0, []
            self.xpath = XPathEntry(self)
            self.info = {"displayWidth": 1080, "displayHeight": 2400}

        def dump_hierarchy(self, *_a, **_k):
            self.dumps += 1
            now[0] += dump_ms / 1000.0
            return self.xml

        def click(self, *args):
            self.gestures.append("click")

        def long_click(self, *args):
            self.gestures.append("long_click")

        def double_click(self, *args):
            self.gestures.append("double_click")

        def swipe(self, *args, **kwargs):
            self.gestures.append("swipe")

        def swipe_ext(self, *args, **kwargs):
            self.gestures.append("swipe")

        def press(self, key):
            self.gestures.append(f"press:{key}")

        def window_size(self):
            return 1080, 2400

        def app_current(self):
            return {"package": "com.zhiliaoapp.musically", "activity": "unknown"}

    from taktik.core.compat.selectors.setup import apply_version_overrides
    from taktik.core.social_media.tiktok.ui.language import detect_and_optimize

    apply_version_overrides("tiktok", version)
    phone = Phone()
    phone.xml = Path(files[0]).read_text(encoding="utf-8", errors="replace")
    detect_and_optimize(phone, override=language if language in ("fr", "en") else None)

    from types import SimpleNamespace

    from bridges.compat.diagnostics.runtime.action_test.runner import _detect_screen
    from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import DetectionActions
    from taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler import PopupHandler

    detection = DetectionActions(phone)
    handler = PopupHandler(None, detection)
    bundle = SimpleNamespace(detection=detection, device=detection.device)
    probes = {
        "popups": handler._fast_detect,
        "comments": detection.has_comments_section_open,
        "suggestion": detection.has_suggestion_page,
        "video_info_feed": lambda: detection.get_video_info(light_if_ad=True),
        "video_info_full": detection.get_video_info,
        "for_you": detection.is_on_for_you_page,
        "inbox": detection.is_on_inbox_page,
        "followed": detection.is_user_followed,
        "lab_screen": lambda: _detect_screen(bundle),
    }
    if hasattr(detection, "read_screen"):
        probes["read_screen"] = lambda: getattr(detection.read_screen(), "kind", None)

    out = {}
    for path in files:
        phone.xml = Path(path).read_text(encoding="utf-8", errors="replace")
        answers = {}
        for name, probe in probes.items():
            dumps_before, gestures_before = phone.dumps, len(phone.gestures)
            try:
                answer = _plain(probe())
            except Exception as exc:
                answer = f"error: {type(exc).__name__}"
            answers[name] = {"answer": answer, "gestures": phone.gestures[gestures_before:],
                             "dumps": phone.dumps - dumps_before}
        out[path] = answers
    return out


def child_main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", required=True, choices=("languages", "decisions"))
    parser.add_argument("--files", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--version", default="")
    parser.add_argument("--language", default="unknown")
    parser.add_argument("--dump-ms", type=float, default=250.0)
    args = parser.parse_args(argv)
    files = [line for line in Path(args.files).read_text(encoding="utf-8").splitlines() if line]
    if args.child == "languages":
        result = _child_languages(files)
    else:
        result = _child_decisions(files, args.version, args.language, args.dump_ms)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


# ── Parent ─────────────────────────────────────────────────────────────────────

def _run_child(code_root: Path, workdir: Path, tag: str, files, **options) -> dict:
    list_file = workdir / f"{tag}.files"
    out_file = workdir / f"{tag}.json"
    list_file.write_text("\n".join(files), encoding="utf-8")
    command = [sys.executable, str(Path(__file__).resolve()), "--files", str(list_file), "--out", str(out_file)]
    for key, value in options.items():
        command += [f"--{key.replace('_', '-')}", str(value)]
    env = {**os.environ, "PYTHONPATH": str(code_root), "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run(command, cwd=str(code_root), env=env, capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise RuntimeError(f"{tag} failed:\n{done.stderr[-2000:]}")
    return json.loads(out_file.read_text(encoding="utf-8"))


def _extract(revision: str, workdir: Path) -> Path:
    archive = subprocess.run(["git", "archive", "--format=tar", revision, "taktik", "bridges"],
                             cwd=ROOT, check=True, capture_output=True).stdout
    target = workdir / "base"
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(target)
    return target


def _versions() -> list:
    import yaml

    data = yaml.safe_load((ROOT / "taktik/core/compat/data/overrides/tiktok.yaml").read_text(encoding="utf-8")) or {}
    baseline = str((data.get("meta") or {}).get("baseline_version") or "43.1.4")
    return [baseline] + [str(v) for v in (data.get("versions") or {}) if str(v) != baseline]


def _dumps(args) -> list:
    if args.list:
        return [line.strip() for line in Path(args.list).read_text(encoding="utf-8").splitlines() if line.strip()]
    corpora = args.corpus or [os.environ.get("TAKTIK_DEBUG_UI") or str(ROOT / "debug_ui")]
    found = []
    for corpus in corpora:
        base = Path(corpus)
        for path in sorted(base.rglob("*.xml")) if base.is_dir() else []:
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(f'package="{package}' in text for package in TIKTOK_PACKAGES):
                found.append(str(path))
    return found


def _decide(root: Path, workdir: Path, label: str, groups: dict, dump_ms: float, jobs: int) -> dict:
    tasks = []
    for (version, language), files in groups.items():
        for index in range(0, len(files), 60):
            tag = f"{label}-{version}-{language}-{index}"
            tasks.append((tag, version, language, files[index:index + 60]))

    def run(task):
        tag, version, language, files = task
        answers = _run_child(root, workdir, tag, files, child="decisions", version=version,
                             language=language, dump_ms=dump_ms)
        return {(path, version): value for path, value in answers.items()}

    merged = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for part in pool.map(run, tasks):
            merged.update(part)
    return merged


FEED_TURN = ("popups", "comments", "suggestion", "video_info_feed")


def compare(before: dict, after: dict) -> dict:
    """Answers and gestures of each read, base against now, per (capture, version).

    A read present in one state only is listed, not compared; a capture missing from `after`
    counts as a difference for each of its reads."""
    compared = differences = 0
    examples, only_one_side = [], set()
    dumps_before, dumps_after = [], []
    for key in sorted(before):
        old, new = before[key], after.get(key)
        if new is None:
            differences += len(old)
            examples.append((Path(key[0]).name, key[1], "(missing)", {"answer": None, "gestures": []},
                             {"answer": "missing now", "gestures": []}))
            continue
        for probe in PROBES:
            if (probe in old) != (probe in new):
                only_one_side.add(probe)
                continue
            if probe not in old:
                continue
            compared += 1
            if (old[probe]["answer"], old[probe]["gestures"]) != (new[probe]["answer"], new[probe]["gestures"]):
                differences += 1
                if len(examples) < 20:
                    examples.append((Path(key[0]).name, key[1], probe, old[probe], new[probe]))
        dumps_before.append(sum(old[p]["dumps"] for p in FEED_TURN if p in old))
        dumps_after.append(sum(new[p]["dumps"] for p in FEED_TURN if p in new))
    return {"compared": compared, "differences": differences, "examples": examples,
            "only_one_side": sorted(only_one_side), "dumps_before": dumps_before or [0],
            "dumps_after": dumps_after or [0]}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--child" in argv:
        return child_main(argv)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", action="append", help="a capture folder (repeatable)")
    parser.add_argument("--list", help="read the captures from this file, one path per line")
    parser.add_argument("--save-list", help="write the captures replayed to this file")
    parser.add_argument("--base", default="HEAD", help="revision to compare the working tree with")
    parser.add_argument("--dump-ms", type=float, default=250.0, help="fake cost of one dump")
    parser.add_argument("--report", help="write every answer of both states to this JSON file")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args(argv)

    dumps = _dumps(args)
    if not dumps:
        print("No TikTok capture found: nothing to replay.")
        return 0
    if args.save_list:
        Path(args.save_list).write_text("\n".join(dumps) + "\n", encoding="utf-8")
    versions = _versions()

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        languages = _run_child(ROOT, workdir, "languages", dumps, child="languages")
        groups = {}
        for path in dumps:
            for version in versions:
                groups.setdefault((version, languages.get(path, "unknown")), []).append(path)
        base_root = _extract(args.base, workdir)
        before = _decide(base_root, workdir, "base", groups, args.dump_ms, args.jobs)
        after = _decide(ROOT, workdir, "now", groups, args.dump_ms, args.jobs)

    outcome = compare(before, after)
    dumps_before, dumps_after = outcome["dumps_before"], outcome["dumps_after"]
    counts = {language: sum(1 for v in languages.values() if v == language) for language in set(languages.values())}
    print(f"{len(dumps)} TikTok captures (languages {counts}) x versions {versions}; base {args.base}.")
    print(f"Decisions compared: {outcome['compared']}, differences: {outcome['differences']}.")
    if outcome["only_one_side"]:
        print(f"Reads present in one state only (not compared): {outcome['only_one_side']}")
    print(f"Dumps of a feed turn (popups, comments, suggestion, video info) at {args.dump_ms:.0f} ms each: "
          f"base median {statistics.median(dumps_before):.0f} (max {max(dumps_before)}), "
          f"now median {statistics.median(dumps_after):.0f} (max {max(dumps_after)}).")
    for name, version, probe, old, new in outcome["examples"]:
        print(f"  DIFF {name} {version} {probe}: {json.dumps(old['answer'], ensure_ascii=False)[:160]} "
              f"{old['gestures']} -> {json.dumps(new['answer'], ensure_ascii=False)[:160]} {new['gestures']}")
    if args.report:
        report = {f"{path} @ {version}": {"base": before[(path, version)], "now": after.get((path, version))}
                  for path, version in sorted(before)}
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if outcome["differences"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
