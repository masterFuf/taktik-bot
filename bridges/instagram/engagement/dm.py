#!/usr/bin/env python3
"""
DM Bridge for TAKTIK Desktop
Unified bridge for reading and sending Instagram DM messages.

Usage:
    python dm_bridge.py read <device_id> <limit>
    python dm_bridge.py send <device_id> <username> <message>
"""

import sys
import json
import os
import time
import random
import re

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.base import logger, InstagramBridgeBase
from bridges.instagram.engagement.runtime.dm_navigation import DMInboxNavigationMixin



class DMBridge(DMInboxNavigationMixin, InstagramBridgeBase):
    """Bridge for DM operations between TAKTIK Desktop and Instagram."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self._keyboard = KeyboardService(device_id)

    def _simulate_typing_delay(self, text: str):
        """
        Simulate human typing time without actually typing char by char.
        This avoids issues with emojis and special characters while still
        appearing natural (not instant).
        """
        # Calculate realistic typing time: ~40-80ms per character for a fast typer
        # But cap it to avoid very long waits
        char_count = len(text)

        # Base time: 30-50ms per character
        base_time = char_count * random.uniform(0.03, 0.05)

        # Add some "thinking" time at the start (0.5-1.5s)
        thinking_time = random.uniform(0.5, 1.5)

        # Cap total time at 5 seconds max
        total_time = min(base_time + thinking_time, 5.0)

        logger.info(f"Simulating typing for {total_time:.1f}s ({char_count} chars)...")
        time.sleep(total_time)

    def send_message(self, message: str) -> bool:
        """Send a message in the current conversation with human-like timing."""
        logger.info("Sending message...")

        # Find message input - try multiple selectors
        msg_input = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
        if not msg_input.exists:
            logger.info("Trying alternative input selector...")
            msg_input = self.device(resourceId="com.instagram.android:id/message_content")
        if not msg_input.exists:
            logger.info("Trying EditText class...")
            msg_input = self.device(className="android.widget.EditText")
        if not msg_input.exists:
            logger.info("Trying hint text...")
            msg_input = self.device(textContains="Message")

        if not msg_input.exists:
            logger.error("Message input not found")
            return False

        logger.info(f"Found message input: {msg_input.info}")

        # Click on input field
        msg_input.click()
        time.sleep(random.uniform(0.5, 0.8))

        # Simulate typing delay (looks like we're typing)
        self._simulate_typing_delay(message)

        # Use Taktik Keyboard for reliable input (supports emojis, special chars, etc.)
        if self._keyboard.type_text(message):
            logger.info("Text set via Taktik Keyboard")
        else:
            # Fallback to set_text or send_keys
            logger.warning("Taktik Keyboard failed, trying fallback methods...")
            try:
                msg_input.set_text(message)
                logger.info("Text set via set_text")
            except Exception as e:
                logger.warning(f"set_text failed: {e}, trying send_keys...")
                try:
                    msg_input.send_keys(message)
                    logger.info("Text set via send_keys")
                except Exception as e2:
                    logger.error(f"send_keys also failed: {e2}")
                    return False

        time.sleep(random.uniform(0.3, 0.5))  # Brief pause before sending

        # Find send button - try multiple selectors
        send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button_container")
        logger.info(f"Send button (container): exists={send_btn.exists}")

        if not send_btn.exists:
            send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button")
            logger.info(f"Send button (direct): exists={send_btn.exists}")

        if not send_btn.exists:
            send_btn = self.device(description="Envoyer")
            logger.info(f"Send button (Envoyer): exists={send_btn.exists}")

        if not send_btn.exists:
            send_btn = self.device(description="Send")
            logger.info(f"Send button (Send): exists={send_btn.exists}")

        if not send_btn.exists:
            send_btn = self.device(description="Send message")
            logger.info(f"Send button (Send message): exists={send_btn.exists}")

        if not send_btn.exists:
            # Try to find any clickable element near the input that could be send
            send_btn = self.device(resourceId="com.instagram.android:id/send_button")
            logger.info(f"Send button (send_button): exists={send_btn.exists}")

        if send_btn.exists:
            logger.info(f"Clicking send button: {send_btn.info}")
            send_btn.click()
            time.sleep(1)
            logger.info("Message sent!")
            return True

        logger.error("Send button not found - dumping UI elements for debugging")
        # Log all clickable elements for debugging
        try:
            clickables = self.device(clickable=True)
            for i in range(min(clickables.count, 20)):
                elem = clickables[i]
                info = elem.info
                logger.info(f"Clickable {i}: {info.get('resourceId', '')} - {info.get('contentDescription', '')} - {info.get('className', '')}")
        except Exception:
            pass

        return False

    def read_conversations(self, limit: int) -> list:
        """Read DM conversations."""
        conversations = []
        processed_usernames = set()  # Track by inbox_username (lowercase)
        processed_real_usernames = set()  # Track by real_username (lowercase) to catch duplicates
        conversations_read = 0
        scroll_count = 0
        max_scrolls = 10

        while conversations_read < limit and scroll_count < max_scrolls:
            threads = self.device.xpath(DM_SELECTORS.thread_container).all()

            if not threads:
                logger.warning("No threads found")
                break

            # Trier les threads par position verticale (top) pour les traiter dans l'ordre
            threads_with_pos = []
            for thread in threads:
                try:
                    bounds = thread.info.get('bounds', {})
                    top = bounds.get('top', 0)
                    threads_with_pos.append((top, thread))
                except Exception:
                    continue
            threads_with_pos.sort(key=lambda x: x[0])

            new_conversations_in_scroll = 0  # Track if we found new conversations in this scroll

            for thread_top, thread in threads_with_pos:
                if conversations_read >= limit:
                    break

                try:
                    thread_info = thread.info
                    content_desc = thread_info.get('contentDescription', '')

                    # Extract username
                    username = "Unknown"
                    if content_desc:
                        parts = content_desc.split(',')
                        if parts:
                            username = parts[0].strip()

                    # Try via resource-id
                    try:
                        username_elem = self.device(resourceId="com.instagram.android:id/row_inbox_username")
                        if username_elem.exists:
                            for idx in range(username_elem.count):
                                elem = username_elem[idx]
                                bounds = elem.info.get('bounds', {})
                                thread_bounds = thread_info.get('bounds', {})
                                if bounds and thread_bounds:
                                    if (bounds.get('top', 0) >= thread_bounds.get('top', 0) and
                                        bounds.get('bottom', 0) <= thread_bounds.get('bottom', 0)):
                                        username = elem.get_text() or username
                                        break
                    except Exception:
                        pass

                    # Check if already processed (case-insensitive)
                    # Gérer les noms tronqués: "Here come the Grannies! ...." vs "Here come the Grannies! 💙🧡"
                    username_lower = username.lower().strip()
                    username_base = username_lower.rstrip('.').strip()  # Enlever les "..." de troncature

                    already_processed = False
                    for processed in processed_usernames:
                        processed_base = processed.rstrip('.').strip()
                        # Match exact ou l'un est préfixe de l'autre (troncature)
                        if (username_base == processed_base or
                            username_base.startswith(processed_base) or
                            processed_base.startswith(username_base)):
                            already_processed = True
                            break

                    if already_processed:
                        logger.debug(f"Skipping already processed: {username}")
                        continue

                    logger.info(f"Opening conversation: {username}")
                    thread.click()
                    time.sleep(2)

                    header_title = self.device(resourceId="com.instagram.android:id/header_title")
                    if not header_title.exists(timeout=3):
                        logger.warning(f"Could not open conversation with {username}")
                        # Vérifier si on est toujours dans l'inbox (pas besoin de back)
                        inbox_list = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
                        if not inbox_list.exists:
                            # On est quelque part d'autre, revenir à l'inbox
                            back_btn = self.device(resourceId="com.instagram.android:id/header_left_button")
                            if back_btn.exists:
                                back_btn.click()
                            else:
                                self.device.press("back")
                            time.sleep(1)
                        continue

                    real_username = header_title.get_text() or username
                    real_username_lower = real_username.lower().strip()

                    # Double-check: if real_username was already processed, skip
                    if real_username_lower in processed_real_usernames:
                        logger.info(f"Skipping duplicate (real_username already seen): {real_username}")
                        back_btn = self.device(resourceId="com.instagram.android:id/header_left_button")
                        if back_btn.exists:
                            back_btn.click()
                        else:
                            self.device.press("back")
                        time.sleep(1)
                        continue

                    # Mark both as processed
                    processed_usernames.add(username_lower)
                    processed_real_usernames.add(real_username_lower)

                    # Check if group or broadcast channel
                    is_group = False
                    can_reply = True
                    header_subtitle = self.device(resourceId="com.instagram.android:id/header_subtitle")
                    if header_subtitle.exists:
                        try:
                            subtitle_text = header_subtitle.get_text() or ''
                            # Récupérer aussi le contentDescription (content-desc dans le XML)
                            subtitle_info = header_subtitle.info
                            subtitle_desc = subtitle_info.get('contentDescription', '') or ''
                            combined = (subtitle_text + ' ' + subtitle_desc).lower()

                            # Détecter les groupes: "X membres", "X members", "X.XK members", etc.
                            is_group_pattern = bool(re.search(r'\d+\.?\d*k?\s*(membres|members)', combined))

                            if is_group_pattern or 'membres' in combined or 'members' in combined:
                                is_group = True
                                logger.info(f"Groupe détecté via subtitle: {combined[:50]}")
                        except Exception as e:
                            logger.debug(f"Erreur détection groupe via subtitle: {e}")

                    # Vérifier si on peut répondre (composer présent)
                    composer = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
                    if not composer.exists:
                        # Pas de composer = on ne peut pas répondre (groupe broadcast, channel, etc.)
                        can_reply = False
                        if not is_group:
                            # Si pas détecté comme groupe mais pas de composer, c'est probablement un broadcast channel
                            is_group = True
                            logger.info(f"Broadcast channel détecté (pas de composer): {real_username}")

                    # Collect messages
                    messages = self._collect_messages()

                    # Vérifier si le dernier message vient de nous
                    # Si oui, on ne peut pas répondre (on se répondrait à nous-mêmes)
                    last_message_is_ours = False
                    if messages:
                        last_msg = messages[-1]  # Dernier message (le plus récent)
                        if last_msg.get('is_sent', False):
                            last_message_is_ours = True
                            logger.info(f"Dernier message de @{real_username} est de NOUS -> can_reply=False")

                    # can_reply = False si:
                    # - C'est un groupe sans composer
                    # - Le dernier message vient de nous (on ne se répond pas)
                    if last_message_is_ours:
                        can_reply = False

                    conv = {
                        'username': real_username,
                        'inbox_username': username,  # Original name from inbox for reliable matching
                        'messages': messages,
                        'is_group': is_group,
                        'can_reply': can_reply,
                        'last_message_is_ours': last_message_is_ours  # Info supplémentaire pour le front
                    }
                    conversations.append(conv)
                    conversations_read += 1
                    new_conversations_in_scroll += 1

                    # Send real-time update
                    print(json.dumps({
                        "type": "conversation",
                        "current": conversations_read,
                        "total": limit,
                        "conversation": conv
                    }), flush=True)

                    # Go back
                    back_btn = self.device(resourceId="com.instagram.android:id/header_left_button")
                    if back_btn.exists:
                        back_btn.click()
                    else:
                        self.device.press("back")
                    time.sleep(1.5)

                except Exception as e:
                    logger.error(f"Error reading conversation: {e}")
                    # Vérifier si on est dans une conversation avant de faire back
                    inbox_list = self.device(resourceId="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview")
                    if not inbox_list.exists:
                        back_btn = self.device(resourceId="com.instagram.android:id/header_left_button")
                        if back_btn.exists:
                            back_btn.click()
                        else:
                            self.device.press("back")
                        time.sleep(1)
                    continue

            if conversations_read >= limit:
                break

            if self._is_accounts_to_follow_visible():
                logger.info("Reached bottom of DM inbox (Accounts to follow visible), stopping read")
                break

            if new_conversations_in_scroll == 0:
                logger.info("No new conversations found in current inbox viewport, stopping read")
                break

            # Scroll to load more
            scroll_count += 1
            self.device.swipe(
                self.screen_width // 2, int(self.screen_height * 0.7),
                self.screen_width // 2, int(self.screen_height * 0.3),
                duration=0.3
            )
            time.sleep(1.5)

        return conversations

    def _collect_messages(self) -> list:
        """Collect messages from current conversation."""
        all_items = []

        # Text messages
        msg_elements = self.device(resourceId="com.instagram.android:id/direct_text_message_text_view")
        for j in range(msg_elements.count):
            try:
                msg_elem = msg_elements[j]
                msg_bounds = msg_elem.info.get('bounds', {})
                text = msg_elem.get_text()
                if not text:
                    continue
                msg_left = msg_bounds.get('left', 0)
                msg_top = msg_bounds.get('top', 0)
                # Détection envoyé/reçu: les messages reçus sont à gauche (left < 25% de l'écran)
                # Les messages envoyés sont à droite (left >= 25% de l'écran)
                # Seuil de 25% car sur un écran de 576px: messages reçus ont left~84, envoyés ont left~172+
                is_received = msg_left < self.screen_width * 0.25
                all_items.append({
                    'type': 'text',
                    'text': text,
                    'is_sent': not is_received,
                    'top': msg_top
                })
            except Exception:
                continue

        # Reels
        reel_shares = self.device(resourceId="com.instagram.android:id/reel_share_item_view")
        for j in range(reel_shares.count):
            try:
                reel = reel_shares[j]
                reel_bounds = reel.info.get('bounds', {})
                reel_left = reel_bounds.get('left', 0)
                reel_top = reel_bounds.get('top', 0)
                # Même logique pour les reels: 25% de l'écran comme seuil
                is_received = reel_left < self.screen_width * 0.25

                title_elem = self.device(resourceId="com.instagram.android:id/title_text")
                reel_author = ""
                for k in range(title_elem.count):
                    try:
                        t = title_elem[k]
                        t_bounds = t.info.get('bounds', {})
                        if (t_bounds.get('top', 0) >= reel_bounds.get('top', 0) and
                            t_bounds.get('bottom', 0) <= reel_bounds.get('bottom', 0)):
                            reel_author = t.get_text() or ""
                            break
                    except Exception:
                        continue

                all_items.append({
                    'type': 'reel',
                    'text': f"[Reel de @{reel_author}]" if reel_author else "[Reel partagé]",
                    'is_sent': not is_received,
                    'top': reel_top
                })
            except Exception:
                continue

        # Sort all messages by position (top to bottom = chronological order)
        all_items.sort(key=lambda x: x['top'])

        # Pas de déduplication - garder TOUS les messages
        # Un même texte peut apparaître plusieurs fois (ex: smileys, réponses courtes)
        messages = []
        for msg in all_items:
            messages.append({
                'type': msg['type'],
                'text': msg['text'],
                'is_sent': msg['is_sent']
            })

        return messages


def main():
    from bridges.instagram.engagement.runtime.dm_commands import run_dm_cli

    run_dm_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
