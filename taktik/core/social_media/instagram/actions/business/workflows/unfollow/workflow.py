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

from ....core.base_business import BaseBusinessAction
from ...common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service

from .....ui.selectors import UNFOLLOW_SELECTORS
from .mixins.decision import UnfollowDecisionMixin
from .mixins.actions import UnfollowActionsMixin


class UnfollowBusiness(
    UnfollowDecisionMixin,
    UnfollowActionsMixin,
    BaseBusinessAction
):
    """Business logic for unfollowing Instagram accounts."""
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "unfollow", init_business_modules=False)
        
        from ...common.workflow_defaults import UNFOLLOW_DEFAULTS
        from .....ui.selectors import UNFOLLOW_SELECTORS
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
    
    # ─── Workflow 1: run_unfollow_workflow (profile-visit based) ──────────

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
            'skipped_whitelisted': 0,
            'skipped_blacklisted_forced': 0,
            'skipped_not_bot_follow': 0,
            'skipped_verified': 0,
            'skipped_business': 0,
            'skipped_recent': 0,
            'skipped_followers': 0,
            'skipped_not_mutual': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            unfollow_mode = effective_config.get('unfollow_mode', 'non-followers')
            self.logger.info("🔄 Starting unfollow workflow")
            self.logger.info(f"Mode: {unfollow_mode} | Max: {effective_config['max_unfollows']} | Cooldown: {effective_config.get('min_days_since_follow', 0)}d | Bot-only: {effective_config.get('bot_follows_only', False)}")
            self.logger.info(f"Whitelist: {len(effective_config.get('whitelist', []))} | Blacklist: {len(effective_config.get('blacklist', []))}")
            
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
                    if 'whitelisted' in reason:
                        stats['skipped_whitelisted'] += 1
                    elif 'not_followed_by_bot' in reason:
                        stats['skipped_not_bot_follow'] += 1
                    elif 'verified' in reason:
                        stats['skipped_verified'] += 1
                    elif 'business' in reason:
                        stats['skipped_business'] += 1
                    elif 'recent' in reason:
                        stats['skipped_recent'] += 1
                    elif 'not_mutual' in reason:
                        stats['skipped_not_mutual'] += 1
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
    
    # ─── Workflow 2: run_simple_unfollow_from_list (fast, no profile visit) ─

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
            following_tab = d(resourceId=UNFOLLOW_SELECTORS.following_tab_title_resource_id, textContains="following")
            if not following_tab.exists:
                # Essayer de trouver n'importe quel onglet "following"
                following_tab = d(textContains="following")
            
            # Sélecteurs pour le bouton "Following" dans la liste
            following_button_resource_id = UNFOLLOW_SELECTORS.following_list_button_resource_id
            unfollow_confirm_resource_id = UNFOLLOW_SELECTORS.unfollow_confirm_resource_id
            
            unfollows_done = 0
            max_scrolls = 50
            scroll_count = 0
            no_button_count = 0
            
            while unfollows_done < max_unfollows and scroll_count < max_scrolls:
                # Chercher tous les boutons "Following" visibles
                following_buttons = d(
                    resourceId=following_button_resource_id,
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
                    usernames_on_screen = d(resourceId=UNFOLLOW_SELECTORS.following_list_username_resource_id)
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
                    confirm_button = d(resourceId=unfollow_confirm_resource_id, text="Unfollow")
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
    
    # ─── Workflow 3: unfollow_specific_accounts ──────────────────────────

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
