#!/usr/bin/env python3

import fcntl
import json
import re
import subprocess
import tempfile
from pathlib import Path


# ============================================================
# CONFIG
# ============================================================

TARGET_ACCOUNT = "explainedsummary"

VIDEO_DIR = Path("/home/tospak/Downloads/Explained.Summary")
TAKTIK_DIR = Path("/home/tospak/taktik-bot")
PYTHON = TAKTIK_DIR / ".venv/bin/python"

POSTED_FILE = VIDEO_DIR / ".tiktok_posted_Explained.Summary.txt"
LOCK_FILE = VIDEO_DIR / ".tiktok_upload.lock"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}

FIXED_HASHTAGS = [
    "stickman",
    "animation",
    "explained",
]


# ============================================================
# COMMANDS
# ============================================================

def run(cmd, **kwargs):
    return subprocess.run(
        cmd,
        text=True,
        check=False,
        **kwargs,
    )


def get_output(cmd):
    result = run(
        cmd,
        capture_output=True,
    )

    return result.stdout.strip()


# ============================================================
# ADB DEVICE
# ============================================================

def get_device():
    devices = []

    for line in get_output(
        ["adb", "devices"]
    ).splitlines()[1:]:

        parts = line.split()

        if (
            len(parts) >= 2
            and parts[1] == "device"
        ):
            devices.append(parts[0])

    if not devices:
        raise RuntimeError(
            "No authorized ADB phone connected."
        )

    if len(devices) > 1:
        raise RuntimeError(
            "More than one ADB device connected."
        )

    return devices[0]


# ============================================================
# VIDEO SELECTION
# ============================================================

def load_posted():
    if not POSTED_FILE.exists():
        return set()

    return {
        line.strip()
        for line in POSTED_FILE.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    }


def get_next_video():
    posted = load_posted()

    videos = sorted(
        [
            path
            for path in VIDEO_DIR.rglob("*")
            if (
                path.is_file()
                and path.suffix.lower()
                in VIDEO_EXTENSIONS
            )
        ],
        key=lambda p: p.name.lower(),
    )

    for video in videos:
        relative = (
            video.relative_to(VIDEO_DIR)
            .as_posix()
        )

        if relative not in posted:
            return video

    return None


def mark_posted(video):
    relative = (
        video.relative_to(VIDEO_DIR)
        .as_posix()
    )

    with POSTED_FILE.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(relative + "\n")


# ============================================================
# CAPTION
# ============================================================

def clean(text):
    return re.sub(
        r"\s+",
        " ",
        text.replace("_", " "),
    ).strip()


def parse_video_name(video):
    match = re.match(
        r"^video_\d+_(.*?)_topic_\d+_(.*)$",
        video.stem,
        re.I,
    )

    if match:
        series = clean(match.group(1))
        topic = clean(match.group(2))

        return series, topic

    topic = re.sub(
        r"^video_\d+_",
        "",
        video.stem,
        flags=re.I,
    )

    return "", clean(topic)


def make_tag(text):
    words = re.findall(
        r"[A-Za-z0-9]+",
        text.lower(),
    )

    return "".join(words[:4])[:40]


def make_caption(video):
    series, topic = parse_video_name(video)

    caption = (
        f"{topic} — explained in under a minute."
    )

    tags = FIXED_HASHTAGS.copy()

    topic_tag = make_tag(topic)

    if topic_tag:
        tags.append(topic_tag)

    if series:
        series_tag = make_tag(series)

        if (
            series_tag
            and series_tag not in tags
        ):
            tags.append(series_tag)

    return caption, tags[:5]


# ============================================================
# ACCOUNT SWITCHING
# ============================================================

def account_switcher_available():
    checks = [
        TAKTIK_DIR
        / "taktik/core/social_media/tiktok/auth/switch.py",

        TAKTIK_DIR
        / "bridges/tiktok/account/runtime/account_switch.py",
    ]

    return any(path.exists() for path in checks)


def ensure_account(device):
    if not account_switcher_available():
        print()
        print("ERROR:")
        print(
            "This Taktik branch does not contain "
            "TikTok account switching."
        )
        print(
            "Upload cancelled to avoid posting "
            "to the wrong account."
        )

        return False

    config = {
        "deviceId": device,
        "workflowType": "switch_account",
        "targetUsername": TARGET_ACCOUNT,
        "androidUserId": 0,
    }

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as file:

        json.dump(config, file)

        config_path = Path(file.name)

    try:
        result = run(
            [
                str(PYTHON),
                "bridges/launcher.py",
                "tiktok_account_bridge",
                str(config_path),
            ],
            cwd=TAKTIK_DIR,
        )

        if result.returncode != 0:
            print(
                "Could not verify/switch to",
                f"@{TARGET_ACCOUNT}",
            )

            return False

        return True

    finally:
        config_path.unlink(
            missing_ok=True
        )


# ============================================================
# UPLOAD
# ============================================================

def upload(
    device,
    video,
    caption,
    hashtags,
):
    config = {
        "deviceId": device,
        "localPath": str(video),
        "caption": caption,
        "hashtags": hashtags,
        "postType": "video",
        "androidUserId": 0,
    }

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as file:

        json.dump(config, file)

        config_path = Path(file.name)

    try:
        result = run(
            [
                str(PYTHON),
                "bridges/launcher.py",
                "tiktok_publish_bridge",
                str(config_path),
            ],
            cwd=TAKTIK_DIR,
        )

        return result.returncode == 0

    finally:
        config_path.unlink(
            missing_ok=True
        )


# ============================================================
# MAIN
# ============================================================

def main():
    if not VIDEO_DIR.exists():
        raise RuntimeError(
            f"Video folder missing: {VIDEO_DIR}"
        )

    with LOCK_FILE.open("w") as lock:

        try:
            fcntl.flock(
                lock,
                fcntl.LOCK_EX
                | fcntl.LOCK_NB,
            )

        except BlockingIOError:
            print(
                "Another uploader is already running."
            )
            return 1

        device = get_device()

        video = get_next_video()

        if video is None:
            print("No videos left.")
            return 0

        caption, tags = make_caption(video)

        print()
        print("Account:", f"@{TARGET_ACCOUNT}")
        print("Video:", video.name)
        print("Caption:", caption)
        print(
            "Tags:",
            " ".join(
                "#" + tag
                for tag in tags
            ),
        )
        print()

        print(
            "Checking correct TikTok account..."
        )

        if not ensure_account(device):
            return 1

        print("Account verified.")
        print("Uploading...")

        if not upload(
            device,
            video,
            caption,
            tags,
        ):
            print("UPLOAD FAILED")
            return 1

        mark_posted(video)

        print()
        print("SUCCESS")
        print(
            f"Posted to @{TARGET_ACCOUNT}:"
        )
        print(video.name)

        return 0


if __name__ == "__main__":
    raise SystemExit(main())