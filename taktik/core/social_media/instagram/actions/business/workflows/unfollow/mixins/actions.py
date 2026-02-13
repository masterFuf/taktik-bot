"""Unfollow actions, list extraction, scrolling, and sorting."""

import time
import random
from typing import Dict, List, Any, Optional


class UnfollowActionsMixin:
    """Mixin: perform unfollow, extract accounts, scroll & sort the following list."""
    
    def _unfollow_account(self, username: str) -> bool:
        """
        Effectuer l'unfollow d'un compte.
        
        Args:
            username: Nom d'utilisateur à unfollow
            
        Returns:
            True si l'unfollow a réussi
        """
        try:
            # S'assurer qu'on est sur le profil
            if not self.detection_actions.is_on_profile_screen():
                if not self.nav_actions.navigate_to_profile(username):
                    return False
                time.sleep(1.5)
            
            # Cliquer sur le bouton "Abonné" / "Following"
            clicked = False
            for selector in self._unfollow_selectors['following_button']:
                if self._find_and_click(selector, timeout=3):
                    clicked = True
                    self._human_like_delay('click')
                    break
            
            if not clicked:
                self.logger.warning(f"Cannot find Following button for @{username}")
                return False
            
            time.sleep(1)
            
            # Confirmer l'unfollow
            for selector in self._unfollow_selectors['unfollow_confirm']:
                if self._find_and_click(selector, timeout=3):
                    self._human_like_delay('click')
                    self.logger.debug(f"✅ Unfollow confirmed for @{username}")
                    
                    # Retourner à la liste
                    self._go_back_to_following_list()
                    return True
            
            # Si pas de confirmation trouvée, peut-être que l'unfollow est direct
            # Vérifier si le bouton est maintenant "Follow" / "Suivre"
            follow_button_indicators = self._unfollow_sel.follow_button_after_unfollow
            
            if self._is_element_present(follow_button_indicators):
                self.logger.debug(f"✅ Unfollow successful for @{username} (no confirmation needed)")
                self._go_back_to_following_list()
                return True
            
            self.logger.warning(f"Cannot confirm unfollow for @{username}")
            self._go_back_to_following_list()
            return False
            
        except Exception as e:
            self.logger.error(f"Error unfollowing @{username}: {e}")
            return False
    
    def _go_back_to_following_list(self):
        """Retourner à la liste des abonnements."""
        try:
            # Appuyer sur back plusieurs fois si nécessaire
            for _ in range(3):
                if self.detection_actions.is_following_list_open():
                    return
                self.device.press('back')
                time.sleep(0.5)
        except Exception as e:
            self.logger.debug(f"Error going back to following list: {e}")
    
    def _extract_following_accounts(self, max_accounts: int = 100) -> List[str]:
        """
        Extraire les comptes de la liste des abonnements.
        
        Args:
            max_accounts: Nombre max de comptes à extraire
            
        Returns:
            Liste de usernames
        """
        accounts = []
        seen_accounts = set()
        scroll_attempts = 0
        max_scroll_attempts = 15
        
        self.logger.info(f"📋 Extracting following accounts (max: {max_accounts})")
        
        while len(accounts) < max_accounts and scroll_attempts < max_scroll_attempts:
            # Extraire les comptes visibles
            new_accounts = self._get_visible_following_accounts()
            
            for username in new_accounts:
                if username not in seen_accounts and len(accounts) < max_accounts:
                    seen_accounts.add(username)
                    accounts.append(username)
            
            if len(accounts) >= max_accounts:
                break
            
            # Scroll pour voir plus de comptes
            previous_count = len(accounts)
            self.scroll_actions.scroll_down()
            time.sleep(1.5)
            scroll_attempts += 1
            
            # Si pas de nouveaux comptes après scroll
            if len(accounts) == previous_count:
                self.logger.debug("No new accounts found after scroll")
                break
        
        self.logger.info(f"✅ Extracted {len(accounts)} following accounts")
        return accounts
    
    def _get_visible_following_accounts(self) -> List[str]:
        """Récupérer les usernames visibles dans la liste following."""
        accounts = []
        
        try:
            for selector in self._unfollow_selectors['following_list_item']:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        try:
                            username = element.text
                            if username and self._is_valid_username(username):
                                accounts.append(self._clean_username(username))
                        except Exception:
                            continue
                    break
        except Exception as e:
            self.logger.debug(f"Error extracting following accounts: {e}")
        
        return accounts
    
    def _scroll_following_list(self):
        """Scroll dans la liste des following."""
        try:
            d = self.device.device
            screen_width = d.info.get('displayWidth', 576)
            screen_height = d.info.get('displayHeight', 1280)
            
            # Scroll du milieu vers le haut
            start_y = int(screen_height * 0.7)
            end_y = int(screen_height * 0.3)
            x = screen_width // 2
            
            d.swipe(x, start_y, x, end_y, duration=0.3)
        except Exception as e:
            self.logger.debug(f"Error scrolling: {e}")
    
    def _set_following_list_sort(self, sort_order: str = 'default') -> bool:
        """
        Set the sorting order for the following list.
        
        Args:
            sort_order: 'default', 'latest', or 'earliest'
            
        Returns:
            True if sorting was changed successfully, False otherwise
        """
        try:
            self.logger.info(f"📊 Setting following list sort order to: {sort_order}")
            
            # Click on the sort button to open the sort modal
            sort_button_clicked = False
            for selector in self._unfollow_selectors['sort_button']:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    sort_button_clicked = True
                    self.logger.debug("Clicked sort button")
                    break
            
            if not sort_button_clicked:
                self.logger.warning("Could not find sort button")
                return False
            
            time.sleep(1)  # Wait for modal to appear
            
            # Select the appropriate sort option
            sort_selector_key = f'sort_option_{sort_order}'
            if sort_selector_key not in self._unfollow_selectors:
                self.logger.warning(f"Unknown sort order: {sort_order}")
                return False
            
            for selector in self._unfollow_selectors[sort_selector_key]:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    self.logger.info(f"✅ Selected sort option: {sort_order}")
                    time.sleep(0.5)
                    return True
            
            self.logger.warning(f"Could not find sort option: {sort_order}")
            # Press back to close the modal if we couldn't select an option
            self.device.press('back')
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting sort order: {e}")
            return False
