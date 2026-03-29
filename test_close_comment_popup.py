"""
Quick test script to close the comment popup on a connected device.
Run this when you have a comment popup open to test the new close logic.

Usage:
    python test_close_comment_popup.py
"""

import sys
import time
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

def main():
    logger.info("🧪 Testing comment popup close logic...")
    
    # Import device manager
    try:
        from taktik.core.device.device import DeviceManager
        from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction
        from taktik.core.social_media.instagram.ui.selectors import POPUP_SELECTORS
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        logger.error("Make sure you're running from the bot directory")
        return
    
    # Connect to device
    logger.info("📱 Connecting to device...")
    try:
        device_manager = DeviceManager()
        device_manager.connect()
        
        if not device_manager.device:
            logger.error("❌ No device connected")
            logger.info("Connect a device via USB or WiFi first")
            return
        
        device_id = device_manager.device_id
        logger.info(f"✅ Connected to device: {device_id}")
        
    except Exception as e:
        logger.error(f"❌ Device connection failed: {e}")
        return
    
    # Create comment action instance
    logger.info("🔧 Initializing comment action...")
    try:
        comment_action = CommentAction(device_manager)
        comment_action.popup_selectors = POPUP_SELECTORS
    except Exception as e:
        logger.error(f"❌ Failed to initialize: {e}")
        return
    
    # Check if comment popup is open
    logger.info("🔍 Checking if comment popup is open...")
    try:
        is_open = comment_action._is_comments_view_open()
        if not is_open:
            logger.warning("⚠️  Comment popup doesn't appear to be open")
            logger.info("Open a comment popup manually and run this script again")
            return
        
        logger.info("✅ Comment popup detected - proceeding with close test")
    except Exception as e:
        logger.warning(f"Could not verify popup state: {e}")
        logger.info("Proceeding anyway...")
    
    # Test the close logic
    logger.info("🧪 Testing _close_comment_popup() method...")
    logger.info("=" * 60)
    
    try:
        success = comment_action._close_comment_popup()
        
        logger.info("=" * 60)
        if success:
            logger.success("✅ Close method completed")
        else:
            logger.warning("⚠️  Close method returned False")
        
        # Verify closure
        time.sleep(1)
        still_open = comment_action._is_comments_view_open()
        
        if not still_open:
            logger.success("🎉 SUCCESS - Comment popup is now closed!")
        else:
            logger.error("❌ FAILED - Comment popup is still open")
            logger.info("Check the logs above to see which strategies were attempted")
            
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
    
    logger.info("🏁 Test complete")

if __name__ == "__main__":
    main()
