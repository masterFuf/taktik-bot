"""Navigation and recovery methods for the followers workflow."""

import time
from typing import Dict, Any


class FollowerNavigationMixin:
    """Mixin: back-to-list navigation and recovery logic."""
    
    def _go_back_to_list(self) -> bool:
        """
        Clique sur le bouton retour de l'app Instagram pour revenir à la liste.
        Plus fiable que device.press('back') qui peut causer des scrolls indésirables.
        """
        try:
            # Essayer de cliquer sur le bouton retour de l'app
            clicked = False
            for selector in self._back_button_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element.click()
                        self.logger.debug("⬅️ Clicked Instagram back button")
                        self._human_like_delay('navigation')
                        clicked = True
                        break
                except Exception:
                    continue
            
            if not clicked:
                # Fallback: utiliser le bouton système
                self.logger.debug("⬅️ Using system back button (fallback)")
                self.device.press('back')
                self._human_like_delay('click')
            
            # Vérifier qu'on est bien revenu sur la liste des followers
            if self.detection_actions.is_followers_list_open():
                self.logger.debug("✅ Back to followers list confirmed")
                return True
            else:
                self.logger.warning("⚠️ Back clicked but not on followers list")
                return False
            
        except Exception as e:
            self.logger.error(f"Error going back: {e}")
            self.device.press('back')
            self._human_like_delay('click')
            return False
    
    def _ensure_on_followers_list(self, target_username: str = None, force_back: bool = False) -> bool:
        """
        S'assure qu'on est sur la liste des followers.
        Essaie plusieurs fois de revenir avec back, puis en dernier recours navigue vers la target.
        
        Args:
            target_username: Username de la target pour recovery en dernier recours
            force_back: Si True, fait toujours un back d'abord (à utiliser après avoir visité un profil)
        
        Retourne True si on est sur la liste, False sinon.
        """
        # Si force_back=False, vérifier si on est déjà sur la liste
        if not force_back and self.detection_actions.is_followers_list_open():
            return True
        
        # Sélecteurs UNIQUES à la liste des followers (depuis selectors.py)
        quick_check_selectors = self._followers_list_selectors.list_indicators
        
        # Fonction helper pour vérifier si on est sur la liste
        def is_on_followers_list() -> bool:
            for selector in quick_check_selectors:
                try:
                    exists = self.device.xpath(selector).exists
                    self.logger.debug(f"🔍 Checking selector: {selector[:50]}... = {exists}")
                    if exists:
                        return True
                except Exception as e:
                    self.logger.debug(f"❌ Selector error: {e}")
                    continue
            return False

        # Conditional wait: poll for the list instead of a fixed 2-2.5s sleep after a
        # back press. The list usually reappears in <1s, so this returns as soon as it's
        # there (no robotic systematic pause, no surfaced "Pause 2.5s") and only falls
        # back to the full timeout when the screen genuinely lags.
        def wait_for_followers_list(timeout: float = 2.5, interval: float = 0.25) -> bool:
            deadline = time.monotonic() + timeout
            while True:
                if is_on_followers_list():
                    return True
                if time.monotonic() >= deadline:
                    return False
                time.sleep(interval)
        
        # Sélecteurs pour le bouton back UI d'Instagram (depuis selectors.py)
        back_button_selectors = self.navigation_selectors.back_buttons_action_bar
        
        # Fonction helper pour cliquer sur le bouton back UI
        def click_ui_back_button() -> bool:
            for selector in back_button_selectors:
                try:
                    elem = self.device.xpath(selector)
                    if elem.exists:
                        elem.click()
                        self.logger.info(f"✅ Clicked UI back button")
                        return True
                except Exception as e:
                    self.logger.debug(f"❌ Back button error: {e}")
                    continue
            # Fallback: device.press('back') si le bouton UI n'est pas trouvé
            self.logger.warning(f"⚠️ UI back button not found, using device.press('back')")
            self.device.press('back')
            return True
        
        # Premier back (on vient d'un profil)
        self.logger.info(f"🔄 Recovery - clicking back button (1st) to return to followers list")
        click_ui_back_button()
        if wait_for_followers_list():
            self.logger.info(f"✅ Recovered to followers list (1st back)")
            return True

        # Si le premier back n'a pas suffi, on est peut-être sur le profil
        # (cas: post → profil après back, il faut un 2ème back pour la liste)
        self.logger.info(f"🔄 First back didn't reach list, trying 2nd back...")
        click_ui_back_button()
        if wait_for_followers_list():
            self.logger.info(f"✅ Recovered to followers list (2nd back)")
            return True

        # Dernier coup de pouce: laisser un peu plus de temps à l'écran et re-détecter
        self.logger.info(f"🔄 Detection failed, waiting a bit more and retrying...")
        if wait_for_followers_list(timeout=1.5):
            self.logger.info(f"✅ Recovered to followers list (after wait)")
            return True
        
        # Dernier recours: naviguer vers la target (on perd la position)
        if target_username:
            self.logger.warning(f"⚠️ Could not recover via back, navigating to @{target_username}")
            if self.nav_actions.navigate_to_profile(target_username):
                self._random_sleep(0.5, 1.0)  # Short delay after navigation
                if self.nav_actions.open_followers_list():
                    self._random_sleep(0.5, 1.0)  # Short delay
                    self.logger.warning("⚠️ Recovered but position in list is lost")
                    return True
        
        self.logger.error("❌ Could not recover to followers list")
        return False
