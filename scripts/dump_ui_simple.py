import os
import sys
import time
import argparse
import subprocess
from datetime import datetime

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from loguru import logger
logger.remove()
logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}")

emulator_id = "emulator-5564"

def main():
    parser = argparse.ArgumentParser(description="Dump current Instagram UI")
    parser.add_argument("-p", "--prefix", default="ui_dump", help="Prefix for dump file names")
    parser.add_argument("-d", "--device", default=emulator_id, help="ADB device ID to use")
    args = parser.parse_args()
    
    logger.info(f"Checking device {args.device}")
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        if args.device in result.stdout:
            logger.success(f"Device {args.device} found and connected")
        else:
            logger.error(f"Device {args.device} not found. Connected devices:\n{result.stdout}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error checking devices: {e}")
        sys.exit(1)
    
    output_dir = os.path.join(root_dir, "ui_dumps")
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    dump_file = os.path.join(output_dir, f"{args.prefix}_{timestamp}.xml")
    screenshot_file = os.path.join(output_dir, f"{args.prefix}_{timestamp}.png")
    
    logger.info("Capturing current UI...")
    try:
        subprocess.run(["adb", "-s", args.device, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], check=True)
        subprocess.run(["adb", "-s", args.device, "pull", "/sdcard/window_dump.xml", dump_file], check=True)
        
        subprocess.run(["adb", "-s", args.device, "shell", "screencap", "-p", "/sdcard/screenshot.png"], check=True)
        subprocess.run(["adb", "-s", args.device, "pull", "/sdcard/screenshot.png", screenshot_file], check=True)
        
        logger.success(f"UI dump saved to: {dump_file}")
        logger.success(f"Screenshot saved to: {screenshot_file}")
        
        try:
            with open(dump_file, 'r', encoding='utf-8') as f:
                xml_content = f.read()
                
            reel_indicators = ["Reel", "réel", "vidéo", "video", "play"]
            like_indicators = ["like", "aime", "j'aime", "heart"]
            
            for indicator in reel_indicators:
                if indicator.lower() in xml_content.lower():
                    logger.info(f"Detection: Possible reel (indicator: '{indicator}')")
                    break
            
            for indicator in like_indicators:
                if indicator.lower() in xml_content.lower():
                    logger.info(f"Detection: Possible like button (indicator: '{indicator}')")
                    break
                    
            logger.info(f"XML dump size: {len(xml_content)} characters")
            
        except Exception as e:
            logger.warning(f"Error analyzing XML dump: {e}")
            
    except Exception as e:
        logger.error(f"Error capturing UI: {e}")
        return


if __name__ == "__main__":
    main()
