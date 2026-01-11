import time
import random
import os
import re
import math
import base64
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union
from loguru import logger

from .device_facade import DeviceFacade
from .utils import ActionUtils
from ...utils.taktik_keyboard import run_adb_shell, TAKTIK_KEYBOARD_IME, IME_MESSAGE_B64, IME_CLEAR_TEXT


class HumanBehavior:
    """Simule un comportement humain réaliste pour éviter la détection."""
    
    # Singleton pour partager l'état entre toutes les actions
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.session_start = time.time()
        self.actions_count = 0  # Toutes les actions (pour fatigue)
        self.interactions_count = 0  # Seulement les vraies interactions (like, follow, comment)
        self.last_action_time = time.time()
        self.last_break_at = 0
        
        # Configuration des pauses (basées sur les VRAIES interactions uniquement)
        self.interactions_before_short_break = random.randint(8, 15)
        self.interactions_before_long_break = random.randint(30, 50)
        
    def reset_session(self):
        """Reset pour une nouvelle session."""
        self.session_start = time.time()
        self.actions_count = 0
        self.interactions_count = 0
        self.last_action_time = time.time()
        self.last_break_at = 0
        self.interactions_before_short_break = random.randint(8, 15)
        self.interactions_before_long_break = random.randint(30, 50)
    
    def get_fatigue_multiplier(self) -> float:
        """Retourne un multiplicateur basé sur la durée de session.
        Plus la session dure, plus les delays augmentent."""
        minutes_elapsed = (time.time() - self.session_start) / 60
        # Après 30 min: x1.3, après 60 min: x1.6
        return 1.0 + (minutes_elapsed / 60) * 0.6
    
    def should_take_break(self) -> Tuple[bool, str, float]:
        """Vérifie si une pause est nécessaire.
        Returns: (should_break, break_type, duration)
        
        Les pauses sont basées sur les VRAIES interactions (like, follow, comment)
        pas sur les simples visites de profils ou scrolls.
        """
        interactions_since_break = self.interactions_count - self.last_break_at
        
        # Pause longue (1-3 min) toutes les 30-50 interactions
        if interactions_since_break >= self.interactions_before_long_break:
            self.last_break_at = self.interactions_count
            self.interactions_before_long_break = random.randint(30, 50)
            return (True, 'long', random.uniform(60, 180))  # 1-3 min
        
        # Pause courte (5-15s) toutes les 8-15 interactions
        if interactions_since_break >= self.interactions_before_short_break:
            self.last_break_at = self.interactions_count
            self.interactions_before_short_break = random.randint(8, 15)
            return (True, 'short', random.uniform(5, 15))  # 5-15s
        
        return (False, None, 0)
    
    def record_action(self):
        """Enregistre une action effectuée (pour le calcul de fatigue)."""
        self.actions_count += 1
        self.last_action_time = time.time()
    
    def record_interaction(self):
        """Enregistre une vraie interaction (like, follow, comment, story view).
        C'est ce compteur qui déclenche les pauses."""
        self.interactions_count += 1
        self.last_action_time = time.time()
    
    def gaussian_delay(self, base_min: float, base_max: float) -> float:
        """Génère un délai avec distribution gaussienne (plus naturel)."""
        mean = (base_min + base_max) / 2
        std = (base_max - base_min) / 4
        
        # Distribution gaussienne
        delay = random.gauss(mean, std)
        
        # Clamp entre min et max avec une petite marge
        delay = max(base_min * 0.8, min(base_max * 1.2, delay))
        
        # Appliquer le multiplicateur de fatigue (capped at x1.5 to avoid excessive delays)
        fatigue = min(self.get_fatigue_multiplier(), 1.5)
        delay *= fatigue
        
        return delay
    
    def get_random_offset(self, variance: int = 15) -> Tuple[int, int]:
        """Retourne un offset aléatoire pour les coordonnées (simule imprécision du doigt)."""
        return (
            random.randint(-variance, variance),
            random.randint(-variance, variance)
        )


class BaseAction:
    def __init__(self, device):
        self.device = device if isinstance(device, DeviceFacade) else DeviceFacade(device)
        self.logger = logger.bind(module=f"instagram.actions.{self.__class__.__name__.lower()}")
        self.utils = ActionUtils()
        self.human = HumanBehavior()  # Singleton partagé
        
        self._method_stats = {
            'clicks': 0,
            'waits': 0,
            'sleeps': 0,
            'errors': 0
        }
        
    def _random_sleep(self, min_delay: float = 0.3, max_delay: float = 0.8) -> None:
        """Sleep avec distribution gaussienne et fatigue de session."""
        delay = self.human.gaussian_delay(min_delay, max_delay)
        self.logger.debug(f"⏱️ Random sleep: {delay:.2f}s (fatigue: x{self.human.get_fatigue_multiplier():.2f})")
        time.sleep(delay)
    
    def _human_like_delay(self, action_type: str = 'general') -> None:
        """Délai humanisé selon le type d'action avec distribution gaussienne."""
        delays = {
            'click': (0.2, 0.5),
            'navigation': (0.7, 1.5),
            'scroll': (0.3, 0.7),
            'typing': (0.08, 0.15),
            'reading_bio': (2.0, 5.0),      # Temps de lecture réaliste
            'before_like': (0.5, 2.0),      # Hésitation avant like
            'after_like': (1.0, 3.0),       # Satisfaction après like
            'before_follow': (1.0, 3.0),    # Réflexion avant follow
            'story_view': (2.0, 5.0),       # Regarder une story
            'story_load': (1.0, 2.0),       # Chargement story
            'load_more': (2.0, 4.0),        # Après clic load more (Instagram needs time to load)
            'profile_view': (1.5, 4.0),     # Observer un profil
            'default': (0.3, 0.8)
        }
        
        min_delay, max_delay = delays.get(action_type, delays['default'])
        self._random_sleep(min_delay, max_delay)
        
        # Enregistrer l'action pour le système de pauses
        self.human.record_action()
    
    def _maybe_take_break(self) -> bool:
        """Vérifie et prend une pause si nécessaire. Retourne True si pause prise."""
        should_break, break_type, duration = self.human.should_take_break()
        
        if should_break:
            if break_type == 'long':
                self.logger.info(f"☕ Pause longue naturelle ({duration/60:.1f} min) - {self.human.interactions_count} interactions effectuées")
            else:
                self.logger.info(f"⏸️ Pause courte ({duration:.0f}s) - {self.human.interactions_count} interactions")
            
            time.sleep(duration)
            return True
        
        return False
    
    def _find_and_click(self, selectors: Union[List[str], str], timeout: float = 5.0, 
                       human_delay: bool = True) -> bool:
        if isinstance(selectors, str):
            selectors = [selectors]
        
        start_time = time.time()
        last_error = None
        
        self.logger.debug(f"🔍 Searching for elements with {len(selectors)} selectors")
        
        while time.time() - start_time < timeout:
            for i, selector in enumerate(selectors):
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        self.logger.debug(f"✅ Element found with selector #{i+1}: {selector[:50]}...")
                        element.click()
                        self._method_stats['clicks'] += 1
                        
                        if human_delay:
                            self._human_like_delay('click')
                        
                        return True
                except Exception as e:
                    last_error = e
                    self.logger.debug(f"❌ Selector #{i+1} failed: {str(e)[:100]}")
                    continue
            
            time.sleep(0.5)
        
        self.logger.warning(f"🚫 No element found after {timeout}s")
        if last_error:
            self.logger.debug(f"Last error: {last_error}")
        
        self._method_stats['errors'] += 1
        return False
    
    def _wait_for_element(self, selectors: Union[List[str], str], timeout: float = 10.0, 
                         check_interval: float = 0.5, silent: bool = False) -> bool:
        if isinstance(selectors, str):
            selectors = [selectors]
        
        start_time = time.time()
        if not silent:
            self.logger.debug(f"⏳ Waiting for element with {len(selectors)} selectors")
        
        while time.time() - start_time < timeout:
            for selector in selectors:
                try:
                    if self.device.xpath(selector).exists:
                        if not silent:
                            self.logger.debug(f"✅ Element appeared: {selector[:50]}...")
                        self._method_stats['waits'] += 1
                        return True
                except Exception:
                    continue
            
            time.sleep(check_interval)
        
        if not silent:
            self.logger.warning(f"⏰ Timeout: element not found after {timeout}s")
        self._method_stats['errors'] += 1
        return False
    
    def _is_element_present(self, selectors: Union[List[str], str]) -> bool:
        if isinstance(selectors, str):
            selectors = [selectors]
        
        for selector in selectors:
            try:
                if self.device.xpath(selector).exists:
                    return True
            except Exception:
                continue
        
        return False
    
    def _get_text_from_element(self, selectors: Union[List[str], str]) -> Optional[str]:    
        if isinstance(selectors, str):
            selectors = [selectors]
        
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    text = element.get_text()
                    if text:
                        return text.strip()
            except Exception as e:
                self.logger.debug(f"Error getting text: {e}")
                continue
        
        return None
    
    def _get_element_attribute(self, selectors: Union[List[str], str], 
                             attribute: str) -> Optional[str]:
        if isinstance(selectors, str):
            selectors = [selectors]
        
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element.attrib.get(attribute)
            except Exception:
                continue
        
        return None

    def _scroll_down(self, distance: int = 500) -> None:
        """Scroll vers le bas avec variance naturelle."""
        screen_info = self.device.info
        screen_height = screen_info['displayHeight']
        screen_width = screen_info['displayWidth']
        
        # Position X avec variance (pas toujours au centre)
        center_x = screen_width // 2
        offset_x, offset_y = self.human.get_random_offset(30)
        start_x = center_x + offset_x
        end_x = center_x + random.randint(-20, 20)  # Légère courbe
        
        start_y = int(screen_height * random.uniform(0.65, 0.75))
        end_y = int(screen_height * random.uniform(0.25, 0.35))
        
        # Durée variable du swipe
        duration = random.uniform(0.2, 0.4)
        
        self.device.swipe(start_x, start_y, end_x, end_y, duration=duration)
        self._human_like_delay('scroll')
    
    def _scroll_up(self, distance: int = 500) -> None:
        """Scroll vers le haut avec variance naturelle."""
        screen_info = self.device.info
        screen_height = screen_info['displayHeight']
        screen_width = screen_info['displayWidth']
        
        center_x = screen_width // 2
        offset_x, _ = self.human.get_random_offset(30)
        start_x = center_x + offset_x
        end_x = center_x + random.randint(-20, 20)
        
        start_y = int(screen_height * random.uniform(0.25, 0.35))
        end_y = int(screen_height * random.uniform(0.65, 0.75))
        
        duration = random.uniform(0.2, 0.4)
        
        self.device.swipe(start_x, start_y, end_x, end_y, duration=duration)
        self._human_like_delay('scroll')
    
    def _press_back(self, count: int = 1) -> None:
        for _ in range(count):
            self.device.press('back')
            self._human_like_delay('click')
    
    def _is_instagram_open(self) -> bool:
        try:
            current_app = self.device.app_current()
            return current_app.get('package') == 'com.instagram.android'
        except Exception:
            return False
    
    def _open_instagram(self) -> bool:
        try:
            self.device.app_start('com.instagram.android')
            self._human_like_delay('navigation')
            return self._is_instagram_open()
        except Exception as e:
            self.logger.error(f"Error opening Instagram: {e}")
            return False
    
    def _debug_current_screen(self, description: str = "") -> None:
        try:
            current_app = self.device.app_current()
            activity = current_app.get('activity', 'Unknown')
            
            self.logger.debug(f"🔍 Debug screen {description}")
            self.logger.debug(f"📱 Activity: {activity}")
            self.logger.debug(f"📊 Stats: {self._method_stats}")
        except Exception as e:
            self.logger.debug(f"Debug error: {e}")
    
    def get_method_stats(self) -> Dict[str, int]:
        return self._method_stats.copy()
    
    def reset_stats(self) -> None:
        self._method_stats = {key: 0 for key in self._method_stats}
        self.logger.debug("📊 Stats reset")
        
    def _extract_number_from_text(self, text: str) -> Optional[int]:
        return self.utils.parse_number_from_text(text)
    
    def _clean_username(self, username: str) -> str:
        return self.utils.clean_username(username)
    
    def _is_valid_username(self, username: str) -> bool:
        return self.utils.is_valid_username(username)
    
    def _type_like_human(self, text: str, min_delay: float = 0.05, max_delay: float = 0.15) -> None:
        """
        Tape du texte caractère par caractère avec des délais humains.
        Simule une frappe naturelle avec des variations de vitesse.
        
        Args:
            text: Le texte à taper
            min_delay: Délai minimum entre les caractères (en secondes)
            max_delay: Délai maximum entre les caractères (en secondes)
        """
        self.logger.debug(f"⌨️ Typing '{text}' with human-like delays")
        
        for i, char in enumerate(text):
            # Taper le caractère
            self.device.send_keys(char)
            
            # Délai variable entre les caractères
            # Plus rapide pour les caractères consécutifs similaires
            if i > 0 and text[i-1].lower() == char.lower():
                # Même touche = plus rapide
                delay = random.uniform(min_delay * 0.5, max_delay * 0.7)
            elif char in '._-':
                # Caractères spéciaux = légèrement plus lent (changement de zone clavier)
                delay = random.uniform(min_delay * 1.2, max_delay * 1.5)
            else:
                # Délai normal avec distribution gaussienne
                mean = (min_delay + max_delay) / 2
                std = (max_delay - min_delay) / 4
                delay = max(min_delay, min(max_delay, random.gauss(mean, std)))
            
            # Occasionnellement, une micro-pause (comme si on cherchait la touche)
            if random.random() < 0.08:  # 8% de chance
                delay += random.uniform(0.1, 0.3)
            
            time.sleep(delay)
        
        self.logger.debug(f"✅ Finished typing '{text}'")
    
    def _get_device_serial(self) -> str:
        """Get the device serial for ADB commands."""
        try:
            device_serial = getattr(self.device.device, 'serial', None)
            if not device_serial:
                device_info = getattr(self.device.device, '_device_info', {})
                device_serial = device_info.get('serial', 'emulator-5554')
            
            if not device_serial:
                self.logger.warning("⚠️ Device ID not found, using emulator-5554")
                device_serial = "emulator-5554"
                
        except Exception as e:
            self.logger.warning(f"⚠️ Device ID error: {e}, using emulator-5554")
            device_serial = "emulator-5554"
        
        return device_serial
    
    def _is_taktik_keyboard_active(self) -> bool:
        """Check if Taktik Keyboard (ADB Keyboard) is the active IME."""
        try:
            device_serial = self._get_device_serial()
            result = run_adb_shell(device_serial, 'settings get secure default_input_method')
            return TAKTIK_KEYBOARD_IME in result
        except Exception as e:
            self.logger.debug(f"Cannot check keyboard status: {e}")
            return False
    
    def _activate_taktik_keyboard(self) -> bool:
        """Activate Taktik Keyboard as the default IME."""
        try:
            device_serial = self._get_device_serial()
            
            # Enable the IME
            run_adb_shell(device_serial, f'ime enable {TAKTIK_KEYBOARD_IME}')
            
            # Set as default
            result = run_adb_shell(device_serial, f'ime set {TAKTIK_KEYBOARD_IME}')
            
            if 'selected' in result.lower():
                self.logger.debug("✅ Taktik Keyboard activated")
                return True
            else:
                self.logger.warning(f"⚠️ Failed to activate Taktik Keyboard: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error activating Taktik Keyboard: {e}")
            return False
    
    def _type_with_taktik_keyboard(self, text: str, delay_mean: int = 80, delay_deviation: int = 30) -> bool:
        """
        Type text using Taktik Keyboard (ADB Keyboard) via broadcast.
        This is more reliable than uiautomator2's send_keys for special characters.
        
        Args:
            text: Text to type
            delay_mean: Mean delay between characters in ms (default 80)
            delay_deviation: Delay deviation in ms (default 30)
            
        Returns:
            True if successful, False otherwise
        """
        if not text:
            return True
        
        try:
            device_serial = self._get_device_serial()
            
            # Check if Taktik Keyboard is active, activate if not
            if not self._is_taktik_keyboard_active():
                self.logger.debug("Taktik Keyboard not active, activating...")
                if not self._activate_taktik_keyboard():
                    self.logger.warning("⚠️ Could not activate Taktik Keyboard, falling back to send_keys")
                    self.device.send_keys(text)
                    return True
            
            # Encode text as base64
            text_b64 = base64.b64encode(text.encode('utf-8')).decode('utf-8')
            
            # Send broadcast with text
            broadcast_cmd = f'am broadcast -a {IME_MESSAGE_B64} --es msg {text_b64} --ei delay_mean {delay_mean} --ei delay_deviation {delay_deviation}'
            result = run_adb_shell(device_serial, broadcast_cmd)
            
            if result and 'error' not in result.lower():
                # Wait for typing to complete
                typing_time = (delay_mean * len(text) + delay_deviation) / 1000
                self.logger.debug(f"⌨️ Taktik Keyboard typing '{text[:20]}...' ({typing_time:.1f}s)")
                time.sleep(typing_time + 0.5)  # Add small buffer
                return True
            else:
                self.logger.warning(f"⚠️ Taktik Keyboard broadcast failed: {result}")
                # Fallback to send_keys
                self.device.send_keys(text)
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error using Taktik Keyboard: {e}")
            # Fallback to send_keys
            try:
                self.device.send_keys(text)
                return True
            except:
                return False
