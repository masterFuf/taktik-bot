import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from taktik.core.shared.device.manager import DeviceManager
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.utils.ui_dump import dump_ui_hierarchy, capture_screenshot


def _connected_device_ids():
    return [
        entry["id"]
        for entry in DeviceManager.list_devices()
        if entry.get("status") == "device"
    ]


def _connect_raw_device(device_id):
    device_manager = DeviceManager(device_id=device_id)
    if not device_manager.connect(verify_atx=False):
        return None
    return device_manager.device


def test_problematic_page_detector(device_id=None):
    logger.info("🧪 Testing problematic page detector")
    
    try:
        import uiautomator2 as u2
        
        if device_id:
            devices = [device_id]
            logger.info(f"Using specified device: {device_id}")
        else:
            devices = _connected_device_ids()
            if not devices:
                logger.error("No Android device connected")
                return False
            device_id = devices[0]
            logger.info(f"No device specified, using first available: {device_id}")
        
        device = _connect_raw_device(device_id)
        if not device:
            logger.error(f"Failed to connect to device {device_id}")
            return False
        
        logger.info(f"Connected to device {device_id}")
        
        detector = ProblematicPageDetector(device, debug_mode=True)
        
        logger.info("📱 Capturing current screen state...")
        
        screenshot_path = capture_screenshot(device, "debug_ui/test_detector")
        dump_path = dump_ui_hierarchy(device, "debug_ui/test_detector")
        
        if screenshot_path:
            logger.info(f"📸 Initial screenshot: {screenshot_path}")
        if dump_path:
            logger.info(f"📄 Initial UI dump: {dump_path}")
        
        logger.info("🔍 Detecting problematic pages...")
        
        detected = detector.detect_and_handle_problematic_pages()
        
        if detected:
            logger.success("✅ Problematic page detected and handled!")
            
            time.sleep(2)
            screenshot_after = capture_screenshot(device, "debug_ui/test_detector")
            dump_after = dump_ui_hierarchy(device, "debug_ui/test_detector")
            
            if screenshot_after:
                logger.info(f"📸 Post-treatment screenshot: {screenshot_after}")
            if dump_after:
                logger.info(f"📄 Post-treatment UI dump: {dump_after}")
                
        else:
            logger.info("ℹ️ No problematic pages detected")
        
        return detected
        
    except Exception as e:
        logger.error(f"Test error: {e}")
        logger.debug("Details:", exc_info=True)
        return False


def test_continuous_monitoring(device_id=None):
    logger.info("🔄 Starting continuous monitoring (Ctrl+C to stop)")
    
    try:
        import uiautomator2 as u2
        
        if device_id:
            devices = [device_id]
            logger.info(f"Using specified device: {device_id}")
        else:
            devices = _connected_device_ids()
            if not devices:
                logger.error("No Android device connected")
                return False
            device_id = devices[0]
            logger.info(f"No device specified, using first available: {device_id}")
        
        device = _connect_raw_device(device_id)
        if not device:
            logger.error(f"Failed to connect to device {device_id}")
            return False
        
        logger.info(f"Connected to device {device_id}")
        detector = ProblematicPageDetector(device, debug_mode=True)
        
        detector.monitor_and_handle_continuously(check_interval=3)
        
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Monitoring error: {e}")
        logger.debug("Details:", exc_info=True)


def analyze_current_screen(device_id=None):
    logger.info("🔍 Analyzing current screen...")
    
    try:
        import uiautomator2 as u2
        
        if device_id:
            devices = [device_id]
            logger.info(f"Using specified device: {device_id}")
        else:
            devices = _connected_device_ids()
            if not devices:
                logger.error("No Android device connected")
                return
            device_id = devices[0]
            logger.info(f"No device specified, using first available: {device_id}")
        
        device = _connect_raw_device(device_id)
        if not device:
            logger.error(f"Failed to connect to device {device_id}")
            return
        
        logger.info(f"Connected to device {device_id}")
        
        screenshot_path = capture_screenshot(device, "debug_ui/analysis")
        dump_path = dump_ui_hierarchy(device, "debug_ui/analysis")
        
        if dump_path:
            logger.info(f"📄 Analyzing UI dump: {dump_path}")
            
            with open(dump_path, 'r', encoding='utf-8') as f:
                ui_content = f.read()
            
            keywords = [
                'Share', 'QR code', 'Copy link', 'WhatsApp', 
                'Add to story', 'Message', 'Threads', 'Close', 'Dismiss',
                'Cancel', '×', '✕', 'Back'
            ]
            
            found_keywords = []
            for keyword in keywords:
                if keyword.lower() in ui_content.lower():
                    found_keywords.append(keyword)
            
            if found_keywords:
                logger.info(f"🔍 Found keywords: {', '.join(found_keywords)}")
            else:
                logger.info("ℹ️ No problematic keywords found")
            
            close_patterns = [
                'close', 'dismiss', 'cancel', 'back', '×', '✕'
            ]
            
            close_elements = []
            for pattern in close_patterns:
                if pattern in ui_content.lower():
                    close_elements.append(pattern)
            
            if close_elements:
                logger.info(f"🔘 Close elements detected: {', '.join(close_elements)}")
            
        if screenshot_path:
            logger.info(f"📸 Screenshot saved: {screenshot_path}")
            
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        logger.debug("Details:", exc_info=True)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test problematic page detector")
    parser.add_argument("--mode", choices=["detect", "monitor", "analyze"], 
                       default="detect", help="Test mode")
    parser.add_argument("--device", type=str, help="Device ID to use (e.g., emulator-5556)")
    
    args = parser.parse_args()
    
    if args.mode == "detect":
        success = test_problematic_page_detector(device_id=args.device)
        sys.exit(0 if success else 1)
    elif args.mode == "monitor":
        test_continuous_monitoring(device_id=args.device)
    elif args.mode == "analyze":
        analyze_current_screen(device_id=args.device)
