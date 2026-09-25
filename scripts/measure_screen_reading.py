"""What reading a TikTok screen costs on a phone: before and after the one-photo change.

Measure (read-only), on the screen the phone shows:

    python scripts/measure_screen_reading.py --device SERIAL --label ad --lang fr --repeat 5 --out FILE.jsonl

Connects through `DeviceManager` (the device io meter, M1, counts every dump), then runs `--repeat`
times what production reads at the top of a feed turn (popups, comment sheet, suggestion page,
video info) and what the Lab runs to name the screen, and appends one JSON line per step. Nothing
touches the screen: once connected, the device refuses every server call that is not a read and
every adb command that moves the screen or starts an app (`ReadOnlyGuard`); a refused call makes
the run exit with code 2. The caption is read as displayed (`full_description=False`): production
taps a cut English caption open, a measurement does not. `--breakdown` also measures each read of
the video info on its own.

Summarize measurement files, or the stdout (JSON lines) and log of a bridge run:

    python scripts/measure_screen_reading.py --summarize FILE [FILE ...]

For a run: the `device_io` step `tiktok.feed.decision` the For You and search loops emit per turn,
by kind of screen; the gestures its telemetry reports; the stuck and skip lines of its log.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DECISION_STEP = "tiktok.feed.decision"
GESTURE_CATEGORIES = frozenset({
    "tap", "double_tap", "button_click", "scroll", "hswipe", "drag", "keystroke",
    "like", "follow", "favorite", "comment", "repost",
})
LOG_MARKERS = ("Same video detected", "Skipping a LIVE preview", "Skipping advertisement",
               "Stuck on same video", "Popup closed")


# ── Read-only guard ────────────────────────────────────────────────────────────

class ReadOnlyViolation(RuntimeError):
    """A measurement tried to act on the phone."""


# Adb commands that move the screen, start or stop an app, or change a setting.
_SCREEN_OR_APP_COMMANDS = frozenset({"input", "am", "monkey", "cmd", "svc", "ime", "reboot", "setprop"})
_WRITING_SUBCOMMANDS = {
    "pm": frozenset({"clear", "install", "uninstall", "disable", "disable-user", "enable", "grant",
                     "revoke", "hide", "unhide", "suspend"}),
    "settings": frozenset({"put", "delete", "reset"}),
}


def is_refused_command(command: Any) -> bool:
    """True for an adb shell command a read-only measurement must not run."""
    words = [str(word) for word in command] if isinstance(command, (list, tuple)) else str(command).split()
    while words and "=" in words[0] and not words[0].startswith("-"):
        words = words[1:]  # leading environment assignments (CLASSPATH=... app_process)
    if not words:
        return False
    name = words[0].rsplit("/", 1)[-1]
    if name in _SCREEN_OR_APP_COMMANDS:
        return True
    if name in _WRITING_SUBCOMMANDS and len(words) > 1:
        return words[1] in _WRITING_SUBCOMMANDS[name]
    return name == "wm" and len(words) > 2  # `wm size` reads, `wm size 1080x2400` writes


class ReadOnlyGuard:
    """Refuses, on one uiautomator2 device, what is not a read. Production code swallows
    exceptions, so a refused call is also kept in `refused`: raising alone could go unseen."""

    def __init__(self) -> None:
        from taktik.core.shared.device.server_restart import READ_ONLY_METHODS

        self.reads = READ_ONLY_METHODS | {"waitForWindowUpdate"}
        self.refused: List[str] = []
        self._restore: List[Tuple[Any, str, Any]] = []

    def _refuse(self, what: str) -> None:
        self.refused.append(what)
        raise ReadOnlyViolation(f"refused during a read-only measurement: {what}")

    def _wrap(self, owner: Any, name: str, make: Callable[[Callable], Callable]) -> None:
        original = getattr(owner, name, None)
        if callable(original):
            self._restore.append((owner, name, original))
            setattr(owner, name, make(original))

    def install(self, device: Any) -> "ReadOnlyGuard":
        def guard_rpc(original):
            def jsonrpc_call(method, params=None, timeout=10, *args, **kwargs):
                if method not in self.reads:
                    self._refuse(f"server call {method}")
                return original(method, params, timeout, *args, **kwargs)
            return jsonrpc_call

        def guard_shell(original):
            def shell(command, *args, **kwargs):
                if is_refused_command(command):
                    self._refuse(f"adb shell {command}")
                return original(command, *args, **kwargs)
            return shell

        self._wrap(device, "jsonrpc_call", guard_rpc)
        self._wrap(device, "shell", guard_shell)
        adb_device = getattr(device, "_dev", None)
        for name in ("shell", "shell2"):
            self._wrap(adb_device, name, guard_shell)

        from taktik.core.shared.device import adb as adb_module

        def guard_bot_shell(original):
            def _run_adb_shell(device_id, command):
                if is_refused_command(command):
                    self._refuse(f"adb shell {command}")
                return original(device_id, command)
            return _run_adb_shell

        self._wrap(adb_module, "_run_adb_shell", guard_bot_shell)
        return self

    def uninstall(self) -> None:
        for owner, name, original in reversed(self._restore):
            setattr(owner, name, original)
        self._restore.clear()


# ── Measurement ────────────────────────────────────────────────────────────────

def feed_reads(detection, popup_handler) -> List[Tuple[str, Callable[[], Any]]]:
    """What the For You loop reads at the top of a turn, without its gestures: the popup scan
    (closing one is a gesture), the comment sheet, the suggestion page, the video info."""
    return [
        ("feed.popups", popup_handler._fast_detect),
        ("feed.comments", detection.has_comments_section_open),
        ("feed.suggestion", detection.has_suggestion_page),
        ("feed.video_info", lambda: detection.get_video_info(light_if_ad=True, full_description=False)),
    ]


def breakdown_reads(detection) -> List[Tuple[str, Callable[[], Any]]]:
    return [
        ("video.is_ad", detection.is_ad_video),
        ("video.author", detection.get_video_author),
        ("video.description", detection.get_video_description),
        ("video.sound", detection.get_video_sound),
        ("video.like_count", detection.get_video_like_count),
        ("video.is_liked", detection.is_video_liked),
        ("video.is_favorited", detection.is_video_favorited),
        ("video.is_live", detection.is_live_preview),
    ]


def screen_kind(results: Dict[str, Any]) -> str:
    """The kind of screen the reads found, in the loop's vocabulary."""
    from taktik.core.social_media.tiktok.actions.business.workflows._internal import BaseVideoWorkflow

    popups = results.get("feed.popups")
    if isinstance(popups, set) and popups and "_fallback" not in popups:
        return "popup"
    if results.get("feed.comments") is True:
        return "comments"
    if results.get("feed.suggestion") is True:
        return "suggestion"
    info = results.get("feed.video_info")
    return BaseVideoWorkflow._screen_kind(info) if isinstance(info, dict) else "unknown"


def _plain(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def measure_once(reads: List[Tuple[str, Callable[[], Any]]], screen_name: Callable[[], str],
                 costs: List[Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Each read under the device io meter: (one record per step, what the reads answered).
    `costs` is where the telemetry sink puts the `device_io` steps."""
    from taktik.core.shared.telemetry.device_io import measure_device_io

    records, results = [], {}
    for name, read in reads + [("lab.screen", screen_name)]:
        before = len(costs)
        with measure_device_io(name, source="measure"):
            try:
                results[name] = read()
            except ReadOnlyViolation:
                raise
            except Exception as exc:  # the read failed: its cost still counts
                results[name] = f"error: {type(exc).__name__}: {exc}"
        for step in costs[before:]:
            records.append({"record": "step", "step": step.action, **step.detail})
    feed = [r for r in records if r["step"].startswith("feed.")]
    decision = {"record": "step", "step": DECISION_STEP, "source": "measure"}
    for key in ("total_ms", "other_ms", "dumps", "dump_ms", "rpc", "rpc_ms", "waits", "wait_ms",
                "shells", "shell_ms", "errors"):
        decision[key] = round(sum(r.get(key, 0) for r in feed), 1)
    records.append(decision)
    return records, results


def _revision() -> str:
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "taktik", "bridges"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return rev + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def run_measure(args) -> int:
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    from importlib.metadata import version as package_version
    from types import SimpleNamespace

    from bridges.compat.diagnostics.runtime.action_test.runner import _detect_screen
    from bridges.compat.diagnostics.runtime.selector_test.production import installed_version
    from taktik.core.shared.device.manager import DeviceManager
    from taktik.core.shared.telemetry import clear_telemetry_sink, configure_telemetry_sink
    from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import DetectionActions
    from taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler import PopupHandler
    from taktik.core.social_media.tiktok.ui.language import detect_and_optimize

    manager = DeviceManager(args.device)
    if not manager.connect(verify_atx=False):
        print(f"Could not connect to {args.device}", file=sys.stderr)
        return 1
    device = manager.device
    guard = ReadOnlyGuard().install(device)
    costs: List[Any] = []
    configure_telemetry_sink(lambda metric: costs.append(metric) if metric.category == "device_io" else None)
    out = open(args.out, "a", encoding="utf-8", newline="") if args.out else sys.stdout
    try:
        language = detect_and_optimize(device, override=None if args.lang == "detect" else args.lang)
        detection = DetectionActions(device)
        popup_handler = PopupHandler(None, detection)
        bundle = SimpleNamespace(detection=detection, device=detection.device)
        reads = feed_reads(detection, popup_handler) + (breakdown_reads(detection) if args.breakdown else [])
        context = {"device": args.device, "label": args.label}
        header = {"record": "context", **context, "app_version": installed_version(args.device, "tiktok"),
                  "language": language, "uiautomator2": package_version("uiautomator2"),
                  "revision": _revision(), "full_description": False, "repeat": args.repeat}
        out.write(json.dumps(header, ensure_ascii=False) + "\n")
        for sample in range(1, args.repeat + 1):
            records, results = measure_once(reads, lambda: _detect_screen(bundle), costs)
            for record in records:
                out.write(json.dumps({**context, "sample": sample, **record}, ensure_ascii=False) + "\n")
            info = results.get("feed.video_info")
            summary = {"record": "sample", **context, "sample": sample, "kind": screen_kind(results),
                       "lab_screen": results.get("lab.screen"), "popups": _plain(results.get("feed.popups")),
                       "comments": results.get("feed.comments"), "suggestion": results.get("feed.suggestion"),
                       "is_ad": info.get("is_ad") if isinstance(info, dict) else None,
                       "is_live": info.get("is_live") if isinstance(info, dict) else None,
                       "author_found": bool(info.get("author")) if isinstance(info, dict) else None,
                       "refused": len(guard.refused)}
            out.write(json.dumps(summary, ensure_ascii=False) + "\n")
            out.flush()
            decision = records[-1]
            print(f"sample {sample}/{args.repeat}: {summary['kind']}, lab {summary['lab_screen']}, "
                  f"decision {decision['total_ms'] / 1000:.1f} s, {decision['dumps']:.0f} dumps",
                  file=sys.stderr)
    except ReadOnlyViolation as exc:
        print(f"STOPPED: {exc}", file=sys.stderr)
    finally:
        clear_telemetry_sink()
        guard.uninstall()
        if out is not sys.stdout:
            out.close()
    if guard.refused:
        print(f"READ-ONLY VIOLATED, {len(guard.refused)} call(s) refused: {guard.refused[:5]}", file=sys.stderr)
        return 2
    return 0


# ── Summary ────────────────────────────────────────────────────────────────────

def _p90(values: List[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]


def _cost_line(label: str, rows: List[Dict[str, Any]]) -> str:
    totals = [float(r.get("total_ms", 0)) for r in rows]
    dumps = [float(r.get("dumps", 0)) for r in rows]
    per_dump = [float(r.get("dump_ms", 0)) / r["dumps"] for r in rows if r.get("dumps")]
    d = f"{statistics.median(per_dump):.0f} ms" if per_dump else "-"
    return (f"  {label:34s} n={len(rows):4d}  total median {statistics.median(totals) / 1000:6.2f} s  "
            f"p90 {_p90(totals) / 1000:6.2f} s  dumps median {statistics.median(dumps):5.1f}  D {d}")


def summarize(paths: Iterable[str]) -> str:
    steps: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    kinds: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    decisions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    gestures: Counter = Counter()
    markers: Counter = Counter()
    refused = 0
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            for marker in LOG_MARKERS:
                if marker in line:
                    markers[marker] += 1
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if not isinstance(item, dict):
                continue
            if item.get("record") == "step":
                steps[(item.get("device", "?"), item.get("label", "?"), item["step"])].append(item)
            elif item.get("record") == "sample":
                kinds[(item.get("device", "?"), item.get("label", "?"))][item.get("kind")] += 1
                refused = max(refused, int(item.get("refused") or 0))
            elif item.get("type") == "step_metric":
                detail = item.get("detail") or {}
                if item.get("category") == "device_io" and item.get("action") == DECISION_STEP:
                    decisions[str(detail.get("kind"))].append(detail)
                elif item.get("category") in GESTURE_CATEGORIES:
                    gestures[f"{item.get('category')}/{item.get('action')}"] += 1
    lines = []
    if steps:
        lines.append("Measurements (read-only), per device / label / step:")
        for key in sorted(steps):
            lines.append(_cost_line("/".join(key), steps[key]))
        for key, counter in sorted(kinds.items()):
            lines.append(f"  kinds read on {'/'.join(key)}: {dict(counter)}")
        lines.append(f"  calls refused by the read-only guard: {refused}")
    if decisions:
        count = sum(len(rows) for rows in decisions.values())
        lines.append(f"Run: {count} feed turns ({DECISION_STEP}), by kind of screen:")
        for kind in sorted(decisions):
            share = 100.0 * len(decisions[kind]) / count
            lines.append(_cost_line(f"{kind} ({share:.1f} per 100 turns)", decisions[kind]))
        lines.append(f"  gestures reported by the telemetry: {dict(sorted(gestures.items())) or 'none'}")
    if markers:
        lines.append(f"Log lines: {dict(markers)}")
    return "\n".join(lines) if lines else "Nothing to summarize."


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", help="serial of the phone to measure (read-only)")
    parser.add_argument("--label", default="", help="what is on screen: video, ad, live, profile...")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--lang", default="detect", choices=("detect", "fr", "en"),
                        help="the app language (production detects it on the feed at startup)")
    parser.add_argument("--breakdown", action="store_true", help="also each read of the video info")
    parser.add_argument("--out", help="JSON lines file to append to (default: stdout)")
    parser.add_argument("--summarize", nargs="+", metavar="FILE")
    args = parser.parse_args(argv)
    if args.summarize:
        print(summarize(args.summarize))
        return 0
    if not args.device:
        parser.error("--device or --summarize is required")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    return run_measure(args)


if __name__ == "__main__":
    raise SystemExit(main())
