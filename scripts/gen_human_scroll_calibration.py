#!/usr/bin/env python3
"""Generate the human-scroll calibration from recorded human Instagram sessions.

Reads the JSONL session recordings (real swipes captured from associates browsing
Instagram for days) and emits a normalised calibration consumed by the human gesture
engine (`taktik/core/shared/behavior/gesture.py`).

Why normalised: the recording device(s) differ in resolution from target devices, so
every gesture is stored as ratios of screen size (nx,ny = start point / (W,H); ndy,ndx
= displacement / (H,W); ndy < 0 means moving up = scrolling the feed forward). The engine
bootstrap-samples these real tuples and denormalises them onto the target screen, which
reproduces the *real joint distribution* (distance/duration/curvature correlations) instead
of hand-tuned heuristics.

Usage:
    python scripts/gen_human_scroll_calibration.py [SESSIONS_DIR] [OUT_JSON]

Defaults:
    SESSIONS_DIR = ../human-session   (relative to repo root)
    OUT_JSON     = taktik/core/shared/behavior/human_scroll_calibration.json
"""

from __future__ import annotations

import glob
import json
import os
import sys

# Resolution inferred from the recordings (max observed x≈714, y≈1553 → 720x1600).
RECORD_W, RECORD_H = 720.0, 1600.0
# Drop sub-80ms / >1.6s swipes: the recorder logged some flings with ~0ms duration
# (artefacts) and the occasional very long drag that is not a feed scroll.
MIN_DUR_MS, MAX_DUR_MS = 80, 1600
MIN_DWELL_MS = 800  # ignore sub-second screen flickers when sampling reading pauses
# An inter-swipe gap in [3s, 60s] is a "stopped to read" pause between scroll bursts.
MIN_READ_MS, MAX_READ_MS = 3000, 60000
# A gap in [0.3s, 3s] is the pause BETWEEN two flicks of the same burst (median ~1.15s) —
# long enough that the previous fling's coast dies before the next flick (no abrupt catch).
MIN_BURST_GAP_MS, MAX_BURST_GAP_MS = 300, 3000


def build(sessions_dir: str) -> dict:
    ups: list[dict] = []
    downs: list[dict] = []
    dwell: list[int] = []
    idle: list[int] = []
    # Reading pauses BETWEEN scroll bursts: the time gap between two consecutive swipes when
    # it is long enough to be "stopped to read" (3-60s). This is the right distribution for a
    # feed-browsing rhythm (median ~6.2s) — distinct from SCREEN_CHANGE dwell (~13s, time spent
    # on a screen before navigating). Tracked per session (reset between files).
    read_pause: list[int] = []
    burst_gap: list[int] = []   # inter-flick gaps within a burst (median ~1.15s)

    for path in sorted(glob.glob(os.path.join(sessions_dir, "*.jsonl"))):
        prev_swipe_ts = None
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = o.get("event")
                if event == "SWIPE_ACTION":
                    # Inter-swipe reading gap (any direction, independent of the duration filter).
                    ts = o.get("ts")
                    if ts is not None and prev_swipe_ts is not None:
                        gap_ms = int((ts - prev_swipe_ts) * 1000)
                        if MIN_READ_MS <= gap_ms <= MAX_READ_MS:
                            read_pause.append(gap_ms)
                        elif MIN_BURST_GAP_MS <= gap_ms < MAX_BURST_GAP_MS:
                            burst_gap.append(gap_ms)
                    if ts is not None:
                        prev_swipe_ts = ts
                    if o.get("duration_ms") and o.get("direction") in ("UP", "DOWN"):
                        dur = int(o["duration_ms"])
                        if not (MIN_DUR_MS <= dur <= MAX_DUR_MS):
                            continue
                        tup = {
                            "nx": round(o["from_x"] / RECORD_W, 4),
                            "ny": round(o["from_y"] / RECORD_H, 4),
                            "ndy": round((o["to_y"] - o["from_y"]) / RECORD_H, 4),
                            "ndx": round((o["to_x"] - o["from_x"]) / RECORD_W, 4),
                            "dur": dur,
                        }
                        (ups if o["direction"] == "UP" else downs).append(tup)
                elif event == "SCREEN_CHANGE" and o.get("dwell_ms") and o["dwell_ms"] >= MIN_DWELL_MS:
                    dwell.append(int(o["dwell_ms"]))
                elif event == "IDLE" and o.get("duration_s"):
                    idle.append(int(o["duration_s"] * 1000))

    return {
        "_comment": (
            "Human gesture calibration derived from real Instagram sessions (2 devices). "
            "Tuples are normalised screen ratios: nx,ny = start point / (W,H); ndy,ndx = "
            "displacement / (H,W) (ndy<0 = upward = feed forward); dur = duration ms. "
            "Bootstrap-sample then denormalise onto the target screen. Do NOT hand-edit: "
            "regenerate via scripts/gen_human_scroll_calibration.py."
        ),
        "record_resolution": {"w": int(RECORD_W), "h": int(RECORD_H)},
        "n": {"up": len(ups), "down": len(downs), "dwell": len(dwell), "idle": len(idle),
              "read_pause": len(read_pause), "burst_gap": len(burst_gap)},
        "up": ups,
        "down": downs,
        "dwell_ms": dwell,
        "idle_ms": idle,
        "read_pause_ms": read_pause,   # reading pauses between scroll bursts (feed browsing)
        "burst_gap_ms": burst_gap,     # inter-flick gaps within a burst (median ~1.15s)
    }


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)  # bot/
    sessions_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(repo_root, "..", "human-session")
    out_json = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        repo_root, "taktik", "core", "shared", "behavior", "human_scroll_calibration.json",
    )
    if not os.path.isdir(sessions_dir):
        print(f"sessions dir not found: {sessions_dir}", file=sys.stderr)
        return 1
    data = build(sessions_dir)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=0)
    print(f"wrote {out_json} ({os.path.getsize(out_json)} bytes) — {data['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
