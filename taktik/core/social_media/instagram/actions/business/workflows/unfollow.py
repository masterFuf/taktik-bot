"""Business logic for Instagram unfollow workflow.

Ce workflow permet de unfollow des comptes de manière automatisée.
Utilisations typiques:
- Nettoyer sa liste d'abonnements
- Unfollow les comptes qui ne follow pas en retour
- Unfollow les comptes inactifs
"""

import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ...core.base_business_action import BaseBusinessAction
from ..common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service


class UnfollowBusiness(BaseBusinessAction):
    """Business logic for unfollowing Instagram accounts."""
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "unfollow", init_business_modules=False)
        
        from ..common.workflow_defaults import UNFOLLOW_DEFAULTS
        from ....ui.selectors import UNFOLLOW_SELECTORS
        self.default_config = {**UNFOLLOW_DEFAULTS}
        
        # Sélecteurs centralisés (depuis selectors.py)
        self._unfollow_sel = UNFOLLOW_SELECTORS
        # Backward-compatible dict wrapper for existing code
        self._unfollow_selectors = {
            'following_button': self._unfollow_sel.following_button,
            'unfollow_confirm': self._unfollow_sel.unfollow_confirm,
            'following_list_item': self._unfollow_sel.following_list_item,
            'following_tab': self._unfollow_sel.following_tab,
            'sort_button': self._unfollow_sel.sort_button,
            'sort_option_default': self._unfollow_sel.sort_option_default,
            'sort_option_latest': self._unfollow_sel.sort_option_latest,
            'sort_option_earliest': self._unfollow_sel.sort_option_earliest,
        }
    
    def run_unfollow_workflow(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Exécuter le workflow d'unfollow.
        
        Args:
            config: Configuration du workflow
            
        Returns:
            Dict avec les statistiques
        """
        effective_config = {**self.default_config, **(config or {})}
        
        stats = {
            'accounts_checked': 0,
            'unfollows_made': 0,
            'skipped_verified': 0,
            'skipped_business': 0,
            'skipped_recent': 0,
            'skipped_followers': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            self.logger.info("🔄 Starting unfollow workflow")
            self.logger.info(f"Max unfollows: {effective_config['max_unfollows']}")
            self.logger.info(f"Unfollow non-followers only: {effective_config['unfollow_non_followers']}")
            
            # Naviguer vers son propre profil
            if not self.nav_actions.navigate_to_profile_tab():
                self.logger.error("Failed to navigate to own profile")
                stats['errors'] += 1
                return stats
            
            time.sleep(2)
            
            # Ouvrir la liste des abonnements (following)
            if not self.nav_actions.open_following_list():
                self.logger.error("Failed to open following list")
                stats['errors'] += 1
                return stats
            
            time.sleep(2)
            
            # Apply sorting based on unfollow mode
            unfollow_mode = effective_config.get('unfollow_mode', 'non-followers')
            if unfollow_mode == 'oldest':
                # Sort by "Date followed: Earliest" to unfollow oldest first
                self._set_following_list_sort('earliest')
                time.sleep(1.5)
            elif unfollow_mode == 'all':
                # Sort by "Date followed: Latest" for "all following" mode
                self._set_following_list_sort('latest')
                time.sleep(1.5)
            # For 'non-followers' mode, we keep default sorting
            
            # Extraire les comptes à potentiellement unfollow
            accounts_to_check = self._extract_following_accounts(
                max_accounts=effective_config['max_unfollows'] * 3
            )
            
            if not accounts_to_check:
                self.logger.warning("No accounts found in following list")
                return stats
            
            self.logger.info(f"📋 {len(accounts_to_check)} accounts to check")
            
            unfollows_done = 0
            
            for username in accounts_to_check:
                if unfollows_done >= effective_config['max_unfollows']:
                    self.logger.info(f"✅ Reached max unfollows ({effective_config['max_unfollows']})")
                    break
                
                stats['accounts_checked'] += 1
                self.logger.info(f"[{stats['accounts_checked']}] Checking @{username}")
                
                # Vérifier si on doit unfollow ce compte
                should_unfollow, reason = self._should_unfollow_account(username, effective_config)
                
                if not should_unfollow:
                    self.logger.debug(f"Skipping @{username}: {reason}")
                    if 'verified' in reason:
                        stats['skipped_verified'] += 1
                    elif 'business' in reason:
                        stats['skipped_business'] += 1
                    elif 'recent' in reason:
                        stats['skipped_recent'] += 1
                    elif 'follower' in reason:
                        stats['skipped_followers'] += 1
                    continue
                
                # Effectuer l'unfollow
                if self._unfollow_account(username):
                    stats['unfollows_made'] += 1
                    unfollows_done += 1
                    self.logger.info(f"✅ Unfollowed @{username} ({unfollows_done}/{effective_config['max_unfollows']})")
                    
                    # Enregistrer l'action
                    self._record_action(username, 'UNFOLLOW', 1)
                    
                    # Délai entre unfollows
                    delay = random.randint(*effective_config['unfollow_delay_range'])
                    self.logger.debug(f"⏳ Waiting {delay}s before next unfollow")
                    time.sleep(delay)
                else:
                    stats['errors'] += 1
            
            stats['success'] = True
            self.logger.info(f"✅ Unfollow workflow completed: {stats['unfollows_made']} unfollows")
            
        except Exception as e:
            self.logger.error(f"Error in unfollow workflow: {e}")
            stats['errors'] += 1
        
        return stats
    
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
    
    def _should_unfollow_account(self, username: str, config: Dict[str, Any]) -> tuple:
        """
        Déterminer si on doit unfollow un compte.
        
        Args:
            username: Nom d'utilisateur
            config: Configuration
            
        Returns:
            Tuple (should_unfollow: bool, reason: str)
        """
        try:
            # Naviguer vers le profil pour vérifier
            if not self.nav_actions.navigate_to_profile(username):
                return False, "cannot_navigate"
            
            time.sleep(1.5)
            
            # Vérifier si c'est un compte vérifié
            if config.get('skip_verified', True):
                if self.detection_actions.is_verified_account():
                    self._go_back_to_following_list()
                    return False, "verified_account"
            
            # Vérifier si c'est un compte business
            if config.get('skip_business', False):
                if self.detection_actions.is_business_account():
                    self._go_back_to_following_list()
                    return False, "business_account"
            
            # Vérifier si le compte nous follow en retour
            if config.get('unfollow_non_followers', True):
                if self._does_user_follow_back(username):
                    self._go_back_to_following_list()
                    return False, "is_follower"
            
            # Vérifier la date du follow (si disponible en BDD)
            if config.get('min_days_since_follow', 0) > 0:
                days_since_follow = self._get_days_since_follow(username)
                if days_since_follow is not None and days_since_follow < config['min_days_since_follow']:
                    self._go_back_to_following_list()
                    return False, f"recent_follow_{days_since_follow}d"
            
            return True, "should_unfollow"
            
        except Exception as e:
            self.logger.debug(f"Error checking if should unfollow @{username}: {e}")
            return False, f"error: {e}"
    
    def _does_user_follow_back(self, username: str) -> bool:
        """Vérifier si un utilisateur nous follow en retour."""
        try:
            return self._is_element_present(self._unfollow_sel.follows_back_indicators)
            
        except Exception as e:
            self.logger.debug(f"Error checking if @{username} follows back: {e}")
            return False  # En cas de doute, on considère qu'il ne follow pas
    
    def _get_days_since_follow(self, username: str) -> Optional[int]:
        """Récupérer le nombre de jours depuis le follow (depuis la BDD)."""
        try:
            account_id = self._get_account_id()
            if not account_id:
                return None
            
            # Chercher dans l'historique des interactions
            db_service = get_db_service()
            if db_service:
                # Cette méthode devrait être implémentée dans DatabaseHelpers
                return DatabaseHelpers.get_days_since_follow(username, account_id)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting days since follow for @{username}: {e}")
            return None
    
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
    
    def run_simple_unfollow_from_list(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Workflow d'unfollow SIMPLE: cliquer directement sur les boutons "Following" dans la liste.
        
        C'est beaucoup plus rapide que de visiter chaque profil.
        On doit déjà être sur la liste des "following" de notre propre compte.
        
        Args:
            config: Configuration du workflow
            
        Returns:
            Dict avec les statistiques
        """
        effective_config = {**self.default_config, **(config or {})}
        max_unfollows = effective_config.get('max_unfollows', 50)
        
        stats = {
            'unfollows_made': 0,
            'errors': 0,
            'scrolls': 0,
            'success': False
        }
        
        try:
            self.logger.info("🔄 Starting SIMPLE unfollow workflow (direct button clicks)")
            self.logger.info(f"Max unfollows: {max_unfollows}")
            
            # Accéder au device uiautomator2 sous-jacent
            d = self.device.device
            
            # Vérifier qu'on est sur la liste following (onglet "following" sélectionné)
            following_tab = d(resourceId="com.instagram.android:id/title", textContains="following")
            if not following_tab.exists:
                # Essayer de trouver n'importe quel onglet "following"
                following_tab = d(textContains="following")
            
            # Sélecteurs pour le bouton "Following" dans la liste
            following_button_selectors = [
                'com.instagram.android:id/follow_list_row_large_follow_button',  # resource-id
            ]
            
            # Sélecteur pour la modal de confirmation (compte privé)
            unfollow_confirm_selector = 'com.instagram.android:id/primary_button'
            
            unfollows_done = 0
            max_scrolls = 50
            scroll_count = 0
            no_button_count = 0
            
            while unfollows_done < max_unfollows and scroll_count < max_scrolls:
                # Chercher tous les boutons "Following" visibles
                following_buttons = d(
                    resourceId="com.instagram.android:id/follow_list_row_large_follow_button",
                    text="Following"
                )
                
                if not following_buttons.exists:
                    self.logger.debug("No 'Following' buttons found on screen")
                    no_button_count += 1
                    if no_button_count >= 3:
                        self.logger.info("No more Following buttons after 3 scrolls, stopping")
                        break
                    # Scroll pour voir plus
                    self._scroll_following_list()
                    scroll_count += 1
                    stats['scrolls'] += 1
                    time.sleep(1)
                    continue
                
                no_button_count = 0  # Reset counter
                
                # Cliquer sur le premier bouton "Following" trouvé
                # Récupérer le username associé pour le log
                username = "unknown"
                try:
                    # Le username est dans le même container parent
                    button_info = following_buttons[0].info
                    button_bounds = button_info.get('bounds', {})
                    # Chercher le username proche de ce bouton
                    usernames_on_screen = d(resourceId="com.instagram.android:id/follow_list_username")
                    if usernames_on_screen.exists:
                        for i in range(usernames_on_screen.count):
                            try:
                                u_elem = usernames_on_screen[i]
                                u_bounds = u_elem.info.get('bounds', {})
                                # Si le username est sur la même ligne (même top approximativement)
                                if abs(u_bounds.get('top', 0) - button_bounds.get('top', 0)) < 50:
                                    username = u_elem.get_text() or "unknown"
                                    break
                            except:
                                pass
                except:
                    pass
                
                # Essayer de cliquer sur le bouton
                try:
                    self.logger.info(f"[{unfollows_done + 1}/{max_unfollows}] Clicking 'Following' for @{username}")
                    following_buttons[0].click()
                    time.sleep(1)
                    
                    # Vérifier si une modal de confirmation apparaît (compte privé)
                    confirm_button = d(resourceId=unfollow_confirm_selector, text="Unfollow")
                    if confirm_button.exists(timeout=2):
                        self.logger.debug("Modal detected, clicking 'Unfollow' to confirm")
                        confirm_button.click()
                        time.sleep(0.5)
                    
                    unfollows_done += 1
                    stats['unfollows_made'] += 1
                    self.logger.info(f"✅ Unfollowed @{username} ({unfollows_done}/{max_unfollows})")
                    
                    # Enregistrer l'action
                    self._record_action(username, 'UNFOLLOW', 1)
                    
                    # Envoyer l'événement en temps réel au frontend (séparé pour éviter les erreurs I/O)
                    try:
                        from desktop_bridge import send_unfollow_event, send_stats
                        send_unfollow_event(username, success=True)
                        send_stats(unfollows=unfollows_done)
                    except:
                        pass  # Ignorer toutes les erreurs d'envoi
                    
                    # Petit délai entre les unfollows (plus court car on ne visite pas les profils)
                    delay = random.randint(2, 5)
                    self.logger.debug(f"⏳ Short delay: {delay}s")
                    time.sleep(delay)
                    
                except Exception as e:
                    self.logger.warning(f"Error clicking Following button: {e}")
                    stats['errors'] += 1
                    # Scroll pour passer à d'autres boutons
                    self._scroll_following_list()
                    scroll_count += 1
                    stats['scrolls'] += 1
                    time.sleep(1)
            
            stats['success'] = True
            self.logger.info(f"✅ Simple unfollow workflow completed: {stats['unfollows_made']} unfollows in {stats['scrolls']} scrolls")
            
        except Exception as e:
            self.logger.error(f"Error in simple unfollow workflow: {e}")
            stats['errors'] += 1
        
        return stats
    
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
    
    def unfollow_specific_accounts(self, usernames: List[str], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Unfollow une liste spécifique de comptes.
        
        Args:
            usernames: Liste des usernames à unfollow
            config: Configuration
            
        Returns:
            Dict avec les statistiques
        """
        effective_config = {**self.default_config, **(config or {})}
        
        stats = {
            'accounts_to_unfollow': len(usernames),
            'unfollows_made': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            self.logger.info(f"🔄 Unfollowing {len(usernames)} specific accounts")
            
            for i, username in enumerate(usernames, 1):
                self.logger.info(f"[{i}/{len(usernames)}] Unfollowing @{username}")
                
                if self._unfollow_account(username):
                    stats['unfollows_made'] += 1
                    self._record_action(username, 'UNFOLLOW', 1)
                    
                    # Délai entre unfollows
                    if i < len(usernames):
                        delay = random.randint(*effective_config['unfollow_delay_range'])
                        self.logger.debug(f"⏳ Waiting {delay}s before next unfollow")
                        time.sleep(delay)
                else:
                    stats['errors'] += 1
            
            stats['success'] = True
            self.logger.info(f"✅ Unfollowed {stats['unfollows_made']}/{len(usernames)} accounts")
            
        except Exception as e:
            self.logger.error(f"Error in specific unfollow: {e}")
            stats['errors'] += 1
        
        return stats
    
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
