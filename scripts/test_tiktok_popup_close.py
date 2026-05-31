"""
Test script for TikTok popup closing.
Tests the close_system_popup and close_follow_friends_popup functions.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
import uiautomator2 as u2
from taktik.core.shared.device.manager import DeviceManager


def test_close_popup(device_id=None):
    """Test closing TikTok popups."""
    logger.info("🧪 Testing TikTok popup closing")
    
    try:
        if device_id:
            logger.info(f"Using specified device: {device_id}")
        else:
            devices = [
                entry["id"]
                for entry in DeviceManager.list_devices()
                if entry.get("status") == "device"
            ]
            if not devices:
                logger.error("No Android device connected")
                return False
            device_id = devices[0]
            logger.info(f"No device specified, using first available: {device_id}")
        
        device_manager = DeviceManager(device_id=device_id)
        if not device_manager.connect(verify_atx=False):
            logger.error(f"Failed to connect to device {device_id}")
            return False
        device = device_manager.device
        
        logger.info(f"✅ Connected to device {device_id}")
        
        # Import TikTok actions
        from taktik.core.social_media.tiktok.actions.atomic.click_actions import ClickActions
        from taktik.core.social_media.tiktok.actions.atomic.detection_actions import DetectionActions
        
        click = ClickActions(device)
        detection = DetectionActions(device)
        
        # Test 1: Check for system popups
        logger.info("🔍 Test 1: Checking for system popups...")
        if click.close_system_popup():
            logger.success("✅ System popup closed!")
            time.sleep(1)
        else:
            logger.info("ℹ️ No system popup detected")
        
        # Test 2: Check for "Follow your friends" popup
        logger.info("🔍 Test 2: Checking for 'Follow your friends' popup...")
        if detection.has_follow_friends_popup():
            logger.info("📱 'Follow your friends' popup detected!")
            if click.close_follow_friends_popup():
                logger.success("✅ 'Follow your friends' popup closed!")
            else:
                logger.warning("❌ Failed to close 'Follow your friends' popup")
                # Try manual click on Close button
                logger.info("🔧 Trying manual click on Close button...")
                try:
                    # Try different selectors
                    selectors_to_try = [
                        {'resourceId': 'com.zhiliaoapp.musically:id/dga'},
                        {'description': 'Close'},
                        {'className': 'android.widget.ImageView', 'description': 'Close'},
                    ]
                    for sel in selectors_to_try:
                        logger.info(f"Trying selector: {sel}")
                        elem = device(**sel)
                        if elem.exists:
                            logger.info(f"✅ Found element with {sel}")
                            elem.click()
                            logger.success("✅ Clicked!")
                            break
                        else:
                            logger.info(f"❌ Not found with {sel}")
                except Exception as e:
                    logger.error(f"Manual click failed: {e}")
        else:
            logger.info("ℹ️ No 'Follow your friends' popup detected")
        
        # Test 3: Check for generic popup
        logger.info("🔍 Test 3: Checking for any TikTok popup...")
        if detection.has_popup():
            logger.info("📱 Popup detected!")
            if click.close_popup():
                logger.success("✅ Popup closed!")
            else:
                logger.warning("❌ Failed to close popup")
        else:
            logger.info("ℹ️ No popup detected")
        
        # Test 4: Try generic close button
        logger.info("🔍 Test 4: Trying generic Close button...")
        try:
            close_elem = device(description='Close')
            if close_elem.exists:
                logger.info("✅ Found Close button by description")
                close_elem.click()
                logger.success("✅ Clicked Close button!")
            else:
                logger.info("ℹ️ No Close button found by description")
        except Exception as e:
            logger.error(f"Error: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Test error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test TikTok popup closing")
    parser.add_argument("--device", type=str, help="Device ID to use")
    
    args = parser.parse_args()
    
    success = test_close_popup(device_id=args.device)
    sys.exit(0 if success else 1)
