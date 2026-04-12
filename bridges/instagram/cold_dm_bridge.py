#!/usr/bin/env python3
"""
Cold DM Bridge - Interface between Electron and Cold DM Workflow
Sends DMs to a list of recipients (cold outreach)
Supports AI-generated personalized messages via OpenRouter.
"""

import sys
import json
import time
import random
import os
import urllib.request
import urllib.error

# Bootstrap: UTF-8 + loguru + sys.path in one call
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from bridges.common.bootstrap import setup_environment
setup_environment(log_level="INFO")

from bridges.common.keyboard import KeyboardService
from bridges.common.database import SentDMService
from bridges.instagram.base import logger, InstagramBridgeBase



def check_dm_already_sent(account_id: int, recipient_username: str) -> bool:
    """Check if a DM was already sent to this recipient (Instagram)."""
    return SentDMService.check_already_sent(account_id, recipient_username, platform='instagram')


def record_sent_dm(account_id: int, recipient_username: str, message: str, success: bool, error_message: str = None, session_id: str = None):
    """Record a sent DM in the database (Instagram)."""
    SentDMService.record(account_id, recipient_username, message, success, error_message, session_id, platform='instagram')


class ColdDMWorkflow(InstagramBridgeBase):
    """Cold DM workflow - sends DMs to new users (cold outreach)."""
    
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    def __init__(self, device_id: str):
        super().__init__(device_id)
        self._keyboard = KeyboardService(device_id)
        # Stats
        self.dms_sent = 0
        self.dms_success = 0
        self.dms_failed = 0
        self.private_profiles = 0
    
    def generate_ai_message(self, username: str, ai_prompt: str, openrouter_api_key: str) -> str:
        """Generate a personalized DM message for a user via OpenRouter."""
        try:
            system_prompt = """Tu es un expert en cold outreach Instagram. Tu génères des messages directs personnalisés, naturels et engageants.

Règles:
- Message court (1-3 phrases max)
- Ton amical et professionnel
- Pas de spam, pas de messages génériques
- Adapte le message au contexte donné
- Ne mentionne jamais que tu es une IA
- Réponds UNIQUEMENT avec le texte du message, rien d'autre"""

            user_prompt = f"""Génère un message de prospection Instagram pour @{username}.

Instructions spécifiques:
{ai_prompt}

Le message doit être unique et personnalisé. Réponds uniquement avec le texte du message."""

            headers = {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://taktik-bot.com",
                "X-Title": "TAKTIK Bot",
            }
            body = json.dumps({
                "model": "anthropic/claude-3.5-haiku",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.8,
                "max_tokens": 200,
            }).encode("utf-8")

            req = urllib.request.Request(self.OPENROUTER_API_URL, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {}).get("content", "").strip()
                # Remove surrounding quotes if present
                if message.startswith('"') and message.endswith('"'):
                    message = message[1:-1]
                logger.info(f"AI generated message for @{username}: {message[:50]}...")
                return message
        except Exception as e:
            logger.error(f"AI message generation failed for @{username}: {e}")
            return ""
    
    def navigate_to_search(self) -> bool:
        """Navigate to the search/explore tab."""
        logger.info("Navigating to search...")
        
        # Try search icon in bottom nav
        search_btn = self.device(resourceId="com.instagram.android:id/search_tab")
        if search_btn.exists:
            search_btn.click()
            time.sleep(2)
            return True
        
        # Try by description
        search_btn = self.device(description="Search and explore")
        if search_btn.exists:
            search_btn.click()
            time.sleep(2)
            return True
        
        search_btn = self.device(descriptionContains="Search")
        if search_btn.exists:
            search_btn.click()
            time.sleep(2)
            return True
        
        logger.error("Could not find search button")
        return False
    
    def search_user(self, username: str) -> bool:
        """Search for a user by username."""
        logger.info(f"Searching for user: {username}")
        username_lower = username.lower().strip()
        
        # Click on search bar
        search_bar = self.device(resourceId="com.instagram.android:id/action_bar_search_edit_text")
        if not search_bar.exists:
            search_bar = self.device(text="Search")
        if not search_bar.exists:
            search_bar = self.device(className="android.widget.EditText")
        
        if not search_bar.exists:
            logger.error("Search bar not found")
            return False
        
        search_bar.click()
        time.sleep(0.5)
        search_bar.set_text(username)
        time.sleep(2)
        
        # Click on Accounts tab to filter results
        accounts_tab = self.device(text="Accounts")
        if accounts_tab.exists:
            logger.info("Clicking Accounts tab")
            accounts_tab.click()
            time.sleep(1.5)
        
        # Method 1: Find user containers and match by username text inside
        # The clickable container is row_search_user_container, username is inside row_search_user_username
        user_containers = self.device(resourceId="com.instagram.android:id/row_search_user_container")
        if user_containers.exists:
            logger.info(f"Found {user_containers.count} user containers")
            for i in range(min(user_containers.count, 10)):
                try:
                    container = user_containers[i]
                    # Find username text inside this container
                    username_elem = container.child(resourceId="com.instagram.android:id/row_search_user_username")
                    if username_elem.exists:
                        found_username = username_elem.get_text()
                        if found_username:
                            found_lower = found_username.lower().strip()
                            logger.info(f"Checking user {i}: '{found_username}'")
                            # Exact match or close match
                            if found_lower == username_lower or username_lower in found_lower or found_lower in username_lower:
                                logger.info(f"Found matching user: {found_username}, clicking container")
                                container.click()
                                time.sleep(2)
                                return True
                except Exception as e:
                    logger.warning(f"Error checking container {i}: {e}")
                    continue
        
        # Method 2: Try clicking first result if username matches closely
        first_username = self.device(resourceId="com.instagram.android:id/row_search_user_username")
        if first_username.exists:
            first_text = first_username.get_text()
            if first_text and username_lower in first_text.lower():
                logger.info(f"Clicking first matching result: {first_text}")
                # Click the parent container
                first_username.click()
                time.sleep(2)
                return True
        
        logger.error(f"User {username} not found in search results")
        return False
    
    def is_private_profile(self) -> bool:
        """Check if the current profile is private."""
        # Check for private profile indicator
        private_state = self.device(resourceId="com.instagram.android:id/private_profile_empty_state")
        if private_state.exists:
            logger.info("Detected private profile (empty state)")
            return True
        
        # Check for "This account is private" text
        private_text = self.device(textContains="account is private")
        if private_text.exists:
            logger.info("Detected private profile (text)")
            return True
        
        # Check for French version
        private_text_fr = self.device(textContains="compte est privé")
        if private_text_fr.exists:
            logger.info("Detected private profile (text FR)")
            return True
        
        return False
    
    def open_dm_from_profile(self) -> bool:
        """Open DM conversation from a user's profile."""
        logger.info("Opening DM from profile...")
        
        # First check if profile is private
        if self.is_private_profile():
            logger.warning("Cannot send DM - profile is private")
            return "private"  # Special return value
        
        # Find Message button on profile
        msg_btn = self.device(text="Message")
        if not msg_btn.exists:
            msg_btn = self.device(description="Message")
        if not msg_btn.exists:
            msg_btn = self.device(resourceId="com.instagram.android:id/profile_header_message_button")
        
        if msg_btn.exists:
            msg_btn.click()
            time.sleep(2)
            return True
        
        logger.error("Message button not found on profile")
        return False
    
    def send_message(self, message: str) -> bool:
        """Send a message in the current conversation."""
        logger.info("Sending message...")
        
        # Find message input
        msg_input = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
        if not msg_input.exists:
            msg_input = self.device(className="android.widget.EditText")
        if not msg_input.exists:
            msg_input = self.device(textContains="Message")
        
        if not msg_input.exists:
            # Check if invite was already sent
            if self.check_invite_already_sent():
                return "invite_sent"  # Special return value
            logger.error("Message input not found")
            return False
        
        msg_input.click()
        time.sleep(0.5)
        
        # Simulate typing delay
        typing_time = min(len(message) * random.uniform(0.03, 0.05) + random.uniform(0.5, 1.5), 5.0)
        time.sleep(typing_time)
        
        # Use Taktik Keyboard for reliable input (supports emojis, special chars, etc.)
        if self._keyboard.type_text(message):
            logger.info("Text set via Taktik Keyboard")
        else:
            # Fallback to set_text or send_keys
            logger.warning("Taktik Keyboard failed, trying fallback methods...")
            try:
                msg_input.set_text(message)
            except Exception as e:
                logger.warning(f"set_text failed: {e}, trying send_keys...")
                try:
                    msg_input.send_keys(message)
                except Exception as e2:
                    logger.error(f"send_keys also failed: {e2}")
                    return False
        
        time.sleep(0.5)
        
        # Find and click send button
        send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button_container")
        if not send_btn.exists:
            send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button")
        if not send_btn.exists:
            send_btn = self.device(description="Send")
        if not send_btn.exists:
            send_btn = self.device(description="Envoyer")
        
        if send_btn.exists:
            send_btn.click()
            time.sleep(1)
            logger.info("Message sent!")
            return True
        
        logger.error("Send button not found")
        return False
    
    def go_back(self):
        """Go back to previous screen."""
        back_btn = self.device(resourceId="com.instagram.android:id/action_bar_button_back")
        if back_btn.exists:
            back_btn.click()
        else:
            self.device.press("back")
        time.sleep(1)
    
    def go_home(self):
        """Navigate to Instagram home screen."""
        logger.info("Navigating to home...")
        
        # First, press back to exit any conversation/profile we might be in
        # This ensures the bottom nav is visible
        self.device.press("back")
        time.sleep(1)
        
        # Try home tab in bottom nav
        home_btn = self.device(resourceId="com.instagram.android:id/feed_tab")
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True
        
        # Try by description
        home_btn = self.device(description="Home")
        if not home_btn.exists:
            home_btn = self.device(descriptionContains="Home")
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True
        
        # Still not found? Press back again and retry
        self.device.press("back")
        time.sleep(1)
        
        home_btn = self.device(resourceId="com.instagram.android:id/feed_tab")
        if home_btn.exists:
            home_btn.click()
            time.sleep(2)
            return True
        
        # Fallback: press back multiple times to get to home
        for _ in range(2):
            self.device.press("back")
            time.sleep(0.5)
        time.sleep(1)
        return True
    
    def check_invite_already_sent(self) -> bool:
        """Check if we're on the 'Invite sent' screen."""
        invite_sent = self.device(textContains="Invite sent")
        if invite_sent.exists:
            logger.info("Invite already sent to this user")
            return True
        
        # Also check for "You can send more messages after your invite is accepted"
        invite_msg = self.device(textContains="invite is accepted")
        if invite_msg.exists:
            logger.info("Invite already sent (waiting for acceptance)")
            return True
        
        return False
    
    def run(self, recipients: list, messages: list, delay_min: int = 30, delay_max: int = 60, max_dms: int = 50, account_id: int = 1, session_id: str = None, ai_prompt: str = '', openrouter_api_key: str = '') -> dict:
        """Run the cold DM workflow."""
        use_ai = bool(ai_prompt and openrouter_api_key)
        logger.info(f"Starting Cold DM workflow: {len(recipients)} recipients, {len(messages)} messages, AI mode: {use_ai}")
        
        if not messages and not use_ai:
            return {'success': False, 'error': 'No messages provided and AI mode not configured'}
        
        if not recipients:
            return {'success': False, 'error': 'No recipients provided'}
        
        # Filter out recipients who already received a DM
        filtered_recipients = []
        skipped_count = 0
        for recipient in recipients:
            if check_dm_already_sent(account_id, recipient):
                logger.info(f"Skipping {recipient} - DM already sent")
                skipped_count += 1
            else:
                filtered_recipients.append(recipient)
        
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} recipients (DM already sent)")
        
        if not filtered_recipients:
            return {'success': True, 'dms_sent': 0, 'dms_success': 0, 'dms_failed': 0, 'error': 'All recipients already received a DM'}
        
        # Restart Instagram for clean state
        self.restart_instagram()
        
        for i, recipient in enumerate(filtered_recipients[:max_dms]):
            if self.dms_sent >= max_dms:
                logger.info(f"Reached max DMs limit: {max_dms}")
                break
            
            logger.info(f"[{i+1}/{min(len(filtered_recipients), max_dms)}] Sending DM to: {recipient}")
            
            # Emit progress to Electron
            print(json.dumps({
                "type": "progress",
                "current": i + 1,
                "total": min(len(filtered_recipients), max_dms),
                "username": recipient
            }), flush=True)
            
            try:
                # Navigate to search
                if not self.navigate_to_search():
                    logger.warning(f"Could not navigate to search for {recipient}")
                    self.dms_failed += 1
                    # DON'T record - this is a temporary error, we can retry later
                    self.go_home()  # Reset to home before next attempt
                    continue
                
                # Search for user
                if not self.search_user(recipient):
                    logger.warning(f"Could not find user: {recipient}")
                    self.dms_failed += 1
                    # DON'T record - user might exist, just search failed
                    self.go_home()  # Reset to home
                    continue
                
                # Open DM from profile
                open_result = self.open_dm_from_profile()
                if open_result == "private":
                    logger.warning(f"Skipping {recipient} - private profile")
                    # Only count as private, NOT as failed (avoid double counting)
                    self.private_profiles += 1
                    # DON'T record - we might want to retry if they become public
                    self.go_home()
                    continue
                elif not open_result:
                    logger.warning(f"Could not open DM for: {recipient}")
                    self.dms_failed += 1
                    # DON'T record - could be temporary UI issue
                    self.go_home()  # Reset to home
                    continue
                
                # Pick a message (AI-generated or random from list)
                if use_ai:
                    message = self.generate_ai_message(recipient, ai_prompt, openrouter_api_key)
                    if not message:
                        logger.warning(f"AI generation failed for @{recipient}, skipping")
                        self.dms_failed += 1
                        self.go_home()
                        continue
                else:
                    message = random.choice(messages)
                
                # Send message
                send_result = self.send_message(message)
                
                if send_result == "invite_sent":
                    # Invite was already sent - record as success to avoid retry
                    logger.info(f"Invite already sent to {recipient} - marking as done")
                    record_sent_dm(account_id, recipient, "", True, "Invite already sent", session_id)
                    self.dms_sent += 1
                elif send_result:
                    self.dms_success += 1
                    logger.info(f"Successfully sent DM to {recipient}")
                    # ONLY record successful DMs - these should not be retried
                    record_sent_dm(account_id, recipient, message, True, None, session_id)
                    self.dms_sent += 1
                else:
                    self.dms_failed += 1
                    logger.warning(f"Failed to send DM to {recipient}")
                    # DON'T record failed sends - we can retry later
                
                # Go back to home before next user (more reliable than go_back twice)
                self.go_home()
                
                # Delay between DMs
                if i < len(filtered_recipients) - 1:
                    delay = random.uniform(delay_min, delay_max)
                    logger.info(f"Waiting {delay:.1f}s before next DM...")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error sending DM to {recipient}: {e}")
                self.dms_failed += 1
                self.go_home()  # Go home to reset state
        
        return {
            'success': True,
            'dms_sent': self.dms_sent,
            'dms_success': self.dms_success,
            'dms_failed': self.dms_failed,
            'private_profiles': self.private_profiles
        }


def main():
    if len(sys.argv) < 2:
        logger.error("Usage: cold_dm_bridge.py <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        # Load configuration
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        device_id = config['deviceId']
        logger.info(f"Starting Cold DM workflow for device: {device_id}")
        
        # Initialize workflow
        workflow = ColdDMWorkflow(device_id)
        
        if not workflow.connect():
            logger.error(f"Failed to connect to device {device_id}")
            print(json.dumps({"success": False, "error": "Failed to connect to device"}))
            sys.exit(1)
        
        # Get config
        recipients = config.get('recipients', [])
        messages = config.get('messages', [])
        delay_min = config.get('delayMin', 30)
        delay_max = config.get('delayMax', 60)
        max_dms = config.get('maxDmsPerSession', 50)
        account_id = config.get('accountId', 1)  # Default to account 1
        session_id = config.get('sessionId', device_id)  # Use device_id as session identifier
        ai_prompt = config.get('aiPrompt', '')
        openrouter_api_key = config.get('openrouterApiKey', '')
        
        message_mode = config.get('messageMode', 'manual')
        if message_mode == 'ai' and not openrouter_api_key:
            logger.warning("AI mode requested but no OpenRouter API key provided, falling back to manual messages")
        
        logger.info(f"Cold DM config: {len(recipients)} recipients, {len(messages)} messages, mode: {message_mode}")
        
        # Run workflow with duplicate checking
        result = workflow.run(recipients, messages, delay_min, delay_max, max_dms, account_id, session_id, ai_prompt, openrouter_api_key)
        
        # Output result as JSON for Electron to parse
        print(json.dumps({
            "success": result.get('success', False),
            "dmsSent": result.get('dms_sent', 0),
            "dmsSuccess": result.get('dms_success', 0),
            "dmsFailed": result.get('dms_failed', 0),
            "error": result.get('error')
        }))
        
    except Exception as e:
        logger.error(f"Cold DM workflow error: {e}", exc_info=True)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
