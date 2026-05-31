"""
record_human_session.py
=======================
Record a manual Instagram session for human behavior analysis.

Usage
-----
    python scripts/record_human_session.py -d <device_serial>

Examples
--------
    # USB device (find serial with: adb devices)
    python scripts/record_human_session.py -d R3CN50BXLPN

    # Emulator
    python scripts/record_human_session.py -d emulator-5554

    # Custom output file and faster polling
    python scripts/record_human_session.py -d R3CN50BXLPN -o my_session.jsonl --interval 0.3

Output
------
    recordings/session_YYYYMMDD_HHMMSS.jsonl  (one JSON object per line)

Each line is an event:
    {"ts":"2026-05-15T14:23:01.234Z","event":"content_change","screen":"feed","content_type":"post","author":"username123","dwell_ms":3420,"extra":{"prev_author":"username0"}}
    {"ts":"2026-05-15T14:23:07.234Z","event":"like","screen":"feed","content_type":"post","author":"username123"}
    ...

Use analyze_sessions.py (coming soon) to aggregate stats across multiple sessions.
"""

import os
import sys
import argparse
from datetime import datetime

# Make bot/ the root so taktik.* imports resolve
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, root_dir)

from loguru import logger

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level:<8}</level> | {message}",
)

from taktik.core.social_media.instagram.recorder import HumanBehaviorRecorder


def _list_adb_devices() -> list:
    """Return connected ADB device serials (best-effort)."""
    import subprocess
    try:
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().splitlines()[1:]  # skip header
        return [
            line.split()[0]
            for line in lines
            if line.strip() and "offline" not in line
        ]
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Record manual Instagram usage for human behavior analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-d", "--device",
        help="ADB device serial (run 'adb devices' to list). "
             "If omitted and only one device is connected, it will be used automatically.",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output JSONL file path. Default: recordings/session_YYYYMMDD_HHMMSS.jsonl",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        metavar="SEC",
        help="Poll interval in seconds (default: 0.5). Lower = more precise, higher CPU.",
    )
    args = parser.parse_args()

    # Auto-select device if not specified
    device_id = args.device
    if not device_id:
        devices = _list_adb_devices()
        if len(devices) == 1:
            device_id = devices[0]
            logger.info(f"Auto-selected device: {device_id}")
        elif len(devices) == 0:
            logger.error("No ADB devices found. Connect a device and try again.")
            sys.exit(1)
        else:
            logger.error(
                f"Multiple devices found: {devices}\n"
                "Specify one with -d <serial>"
            )
            sys.exit(1)

    # Build output path
    if args.output:
        output_path = args.output
    else:
        recordings_dir = os.path.join(root_dir, "..", "recordings")
        os.makedirs(recordings_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(recordings_dir, f"session_{ts}.jsonl")
        output_path = os.path.normpath(output_path)

    # Run
    recorder = HumanBehaviorRecorder(
        device_id=device_id,
        output_path=output_path,
        poll_interval=args.interval,
    )
    recorder.connect()
    recorder.run()


if __name__ == "__main__":
    main()
