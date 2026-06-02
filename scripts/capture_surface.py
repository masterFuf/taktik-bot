"""Capture appariee dump XML + screenshot pour une surface donnee.

Produit, pour un device + une surface (feed, stories, reels, ...), un couple
de fichiers nommes de facon coherente dans :

    bot/debug_ui/cartography/<platform>/<surface>/

    <surface>_<timestamp>.xml   (hierarchie UI)
    <surface>_<timestamp>.png   (capture ecran)

But : fournir la matiere premiere (dump + screenshot apparies) que l'agent IA
analyse pour enrichir `front/src/features/tools/cartography/data/cartography.json`
(elements observes, detections, actions).

Exemples :
    python scripts/capture_surface.py -d emulator-5564 -s feed
    python scripts/capture_surface.py -d emulator-5564 -s profile -p instagram
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

REMOTE_XML = "/sdcard/window_dump.xml"
REMOTE_PNG = "/sdcard/screenshot.png"


def adb(device: str, *args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["adb", "-s", device, *args], **kwargs)


def device_connected(device: str) -> bool:
    out = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    return device in out.stdout


def capture(device: str, platform: str, surface: str) -> int:
    if not device_connected(device):
        print(f"[ERREUR] Device '{device}' introuvable. Branchez-le ou verifiez l'id.")
        return 1

    out_dir = os.path.join(ROOT_DIR, "debug_ui", "cartography", platform, surface)
    os.makedirs(out_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xml_path = os.path.join(out_dir, f"{surface}_{timestamp}.xml")
    png_path = os.path.join(out_dir, f"{surface}_{timestamp}.png")

    try:
        # 1) Dump de la hierarchie UI
        adb(device, "shell", "uiautomator", "dump", REMOTE_XML, check=True,
            capture_output=True, text=True)
        adb(device, "pull", REMOTE_XML, xml_path, check=True,
            capture_output=True, text=True)

        # 2) Screenshot
        adb(device, "shell", "screencap", "-p", REMOTE_PNG, check=True,
            capture_output=True, text=True)
        adb(device, "pull", REMOTE_PNG, png_path, check=True,
            capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        print(f"[ERREUR] Capture echouee : {exc.stderr or exc}")
        return 1

    size = os.path.getsize(xml_path) if os.path.exists(xml_path) else 0
    print(f"[OK] Dump     : {xml_path} ({size} octets)")
    print(f"[OK] Screenshot : {png_path}")
    print(f"[INFO] Surface '{surface}' ({platform}) capturee dans {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture dump XML + screenshot apparies par surface.")
    parser.add_argument("-d", "--device", required=True, help="Id ADB du device (ex: emulator-5564).")
    parser.add_argument("-s", "--surface", required=True,
                        help="Nom de la surface (feed, stories, reels, search, messages, profile, system).")
    parser.add_argument("-p", "--platform", default="instagram", help="Plateforme (defaut: instagram).")
    args = parser.parse_args()
    return capture(args.device, args.platform, args.surface)


if __name__ == "__main__":
    sys.exit(main())
