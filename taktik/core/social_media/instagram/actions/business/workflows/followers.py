"""Business logic for Instagram follower interactions."""

from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
import time
import random
import json
import os
from pathlib import Path

from ...core.base_business_action import BaseBusinessAction
from taktik.core.database import get_db_service
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector

from ..common import DatabaseHelpers
from .followers_tracker import FollowersTracker


class FollowerBusiness(BaseBusinessAction):
    """Business logic for Instagram follower interactions."""
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "follower", init_business_modules=True)
        
        self.default_config = {
            'max_followers_to_extract': 50,
            'max_interactions_per_session': 20,
            'interaction_delay_range': (5, 12),
            'scroll_attempts': 5,
            'like_probability': 0.8,
            'follow_probability': 0.2,
            'story_probability': 0.15,
            'like_posts': True,
            'max_likes_per_profile': 4,
            'comment_probability': 0.05
        }
        # Use AppData folder for checkpoints to avoid permission issues
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        self.checkpoint_dir = Path(app_data) / 'taktik-desktop' / 'temp' / 'checkpoints'
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.current_checkpoint_file = None
        self.current_followers_list = []
        self.current_index = 0
        
        # Sélecteurs pour le bouton retour Instagram
        self._back_button_selectors = [
            '//*[@content-desc="Retour"]',
            '//*[@content-desc="Back"]',
            '//*[@content-desc="Précédent"]',
            '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
            '//android.widget.ImageView[@content-desc="Retour"]',
            '//android.widget.ImageView[@content-desc="Back"]'
        ]
    
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
        
        # Sélecteurs UNIQUES à la liste des followers (pas présents sur les profils)
        # unified_follow_list_tab_layout et unified_follow_list_view_pager n'existent QUE sur la liste
        quick_check_selectors = [
            '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]',
            '//*[@resource-id="com.instagram.android:id/unified_follow_list_view_pager"]',
            '//android.widget.Button[contains(@text, "mutual")]',
        ]
        
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
        
        # Sélecteurs pour le bouton back UI d'Instagram (flèche en haut à gauche)
        back_button_selectors = [
            '//*[@resource-id="com.instagram.android:id/left_action_bar_buttons"]//android.widget.ImageView[@clickable="true"]',
            '//*[@resource-id="com.instagram.android:id/left_action_bar_buttons"]/android.widget.ImageView',
            '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
        ]
        
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
        self.logger.info(f"⏳ Waiting 2s after 1st back...")
        self._random_sleep(2.0, 2.5)
        
        self.logger.info(f"🔍 Checking if on followers list after 1st back...")
        if is_on_followers_list():
            self.logger.info(f"✅ Recovered to followers list (1st back)")
            return True
        
        # Si le premier back n'a pas suffi, on est peut-être sur le profil
        # (cas: post → profil après back, il faut un 2ème back pour la liste)
        self.logger.info(f"🔄 First back didn't reach list, trying 2nd back...")
        click_ui_back_button()
        self.logger.info(f"⏳ Waiting 2s after 2nd back...")
        self._random_sleep(2.0, 2.5)
        
        self.logger.info(f"🔍 Checking if on followers list after 2nd back...")
        if is_on_followers_list():
            self.logger.info(f"✅ Recovered to followers list (2nd back)")
            return True
        
        # Attendre un peu plus et réessayer la détection
        self.logger.info(f"🔄 Detection failed, waiting 1s more and retrying...")
        self._random_sleep(1.0, 1.5)
        
        if is_on_followers_list():
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

    def extract_followers_from_profile(self, target_username: str, 
                                     max_followers: int = 50,
                                     filter_criteria: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        try:
            self.logger.info(f"Extracting followers from @{target_username} (max: {max_followers})")
            
            if not self.nav_actions.navigate_to_profile(target_username):
                self.logger.error(f"Failed to navigate to @{target_username}")
                return []
            
            # Vérifier que le profil est accessible
            if self.detection_actions.is_private_account():
                self.logger.warning(f"@{target_username} is a private account")
                return []
            
            if not self.nav_actions.open_followers_list():
                self.logger.error("Failed to open followers list")
                return []
            
            self._random_sleep()
            
            followers = self._extract_followers_with_scroll(max_followers)
            
            if not followers:
                self.logger.warning("No followers extracted")
                return []
            
            self.logger.info(f"{len(followers)} followers extracted from @{target_username}")
            
            if filter_criteria:
                filtered_followers = self._filter_followers(followers, filter_criteria)
                self.logger.info(f"{len(filtered_followers)}/{len(followers)} followers after filtering")
                return filtered_followers
            
            return followers
            
        except Exception as e:
            self.logger.error(f"Error extracting followers from @{target_username}: {e}")
            return []
    
    def _create_checkpoint(self, session_id: str, target_username: str, followers: List[Dict[str, Any]], current_index: int = 0) -> str:
        try:
            checkpoint_data = {
                'session_id': session_id,
                'target_username': target_username,
                'followers': followers,
                'current_index': current_index,
                'total_followers': len(followers),
                'created_at': time.time(),
                'status': 'active'
            }
            
            checkpoint_filename = f"checkpoint_{session_id}_{target_username}.json"
            checkpoint_path = self.checkpoint_dir / checkpoint_filename
            
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            
            self.current_checkpoint_file = str(checkpoint_path)
            self.current_followers_list = followers
            self.current_index = current_index
            
            self.logger.info(f"Checkpoint created: {checkpoint_filename} (index: {current_index}/{len(followers)})")
            return str(checkpoint_path)
            
        except Exception as e:
            self.logger.error(f"Error creating checkpoint: {e}")
            return None
    
    def _load_checkpoint(self, session_id: str, target_username: str) -> Dict[str, Any]:
        try:
            checkpoint_filename = f"checkpoint_{session_id}_{target_username}.json"
            checkpoint_path = self.checkpoint_dir / checkpoint_filename
            
            if not checkpoint_path.exists():
                return None
            
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            self.current_checkpoint_file = str(checkpoint_path)
            self.current_followers_list = checkpoint_data.get('followers', [])
            self.current_index = checkpoint_data.get('current_index', 0)
            
            self.logger.info(f"Checkpoint loaded: {checkpoint_filename} (index: {self.current_index}/{len(self.current_followers_list)})")
            return checkpoint_data
            
        except Exception as e:
            self.logger.error(f"Error loading checkpoint: {e}")
            return None
    
    def _update_checkpoint_index(self, new_index: int):
        try:
            if not self.current_checkpoint_file or not os.path.exists(self.current_checkpoint_file):
                return
            
            with open(self.current_checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            checkpoint_data['current_index'] = new_index
            checkpoint_data['updated_at'] = time.time()
            
            with open(self.current_checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            
            self.current_index = new_index
            self.logger.debug(f"Checkpoint updated: index {new_index}/{len(self.current_followers_list)}")
            
        except Exception as e:
            self.logger.error(f"Error updating checkpoint: {e}")
    
    def _cleanup_checkpoint(self):
        try:
            if self.current_checkpoint_file and os.path.exists(self.current_checkpoint_file):
                os.remove(self.current_checkpoint_file)
                self.logger.info(f"Checkpoint cleaned: {os.path.basename(self.current_checkpoint_file)}")
            
            self.current_checkpoint_file = None
            self.current_followers_list = []
            self.current_index = 0
            
        except Exception as e:
            self.logger.error(f"Error cleaning checkpoint: {e}")
    
    def interact_with_followers(self, followers: List[Dict[str, Any]], 
                              interaction_config: Dict[str, Any] = None,
                              session_id: str = None,
                              target_username: str = None) -> Dict[str, Any]:
        config = {**self.default_config, **(interaction_config or {})}
        
        stats = {
            'processed': 0,
            'liked': 0,
            'followed': 0,
            'stories_viewed': 0,
            'errors': 0,
            'skipped': 0,
            'resumed_from_checkpoint': False
        }
        
        max_interactions = min(len(followers), config['max_interactions_per_session'])
        start_index = 0
        
        self.logger.info(f"Probabilities: like={config.get('like_probability', 'N/A')}, follow={config.get('follow_probability', 'N/A')}")
        self.logger.info(f"Config: {config}")
        self.logger.info(f"Max interactions: {max_interactions} (followers: {len(followers)}, config: {config['max_interactions_per_session']})")
        if session_id and target_username:
            checkpoint_data = self._load_checkpoint(session_id, target_username)
            if checkpoint_data:
                followers = checkpoint_data.get('followers', followers)
                start_index = checkpoint_data.get('current_index', 0)
                stats['resumed_from_checkpoint'] = True
                self.logger.info(f"Resuming from checkpoint at index {start_index}/{len(followers)}")
            else:
                self._create_checkpoint(session_id, target_username, followers, 0)
        
        self.logger.info(f"Starting interactions with {max_interactions} followers (start index: {start_index})")
        
        try:
            for i in range(start_index, min(len(followers), max_interactions)):
                # Vérifier si la session doit continuer (durée, limites, etc.)
                if hasattr(self, 'session_manager') and self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        break
                
                follower = followers[i]
                username = follower.get('username', '')
                
                try:
                    if not username:
                        stats['skipped'] += 1
                        self._update_checkpoint_index(i + 1)
                        continue
                    
                    self.logger.info(f"[{i+1}/{max_interactions}] Interacting with @{username}")
                    if session_id and target_username:
                        self._update_checkpoint_index(i)
                    
                    account_id = follower.get('source_account_id')
                    if account_id:
                        try:
                            should_skip, skip_reason = DatabaseHelpers.is_profile_skippable(
                                username, account_id, hours_limit=24*60
                            )
                            if should_skip:
                                self.logger.info(f"Profile @{username} skipped ({skip_reason})")
                                stats['skipped'] += 1
                                self.stats_manager.increment('skipped')
                                continue
                        except Exception as e:
                            self.logger.warning(f"Error checking @{username}: {e}")
                    
                    try:
                        if not self.nav_actions.navigate_to_profile(username):
                            self.logger.warning(f"Failed to navigate to @{username}")
                            stats['errors'] += 1
                            self.stats_manager.add_error(f"Navigation failed to @{username}")
                            continue
                    except Exception as e:
                        self.logger.error(f"Error navigating to @{username}: {e}")
                        stats['errors'] += 1
                        self.stats_manager.add_error(f"Navigation error @{username}: {str(e)}")
                        continue
                    
                    self._random_sleep()
                    
                    # ✅ EXTRACTION UNIQUE DU PROFIL (évite les duplications)
                    profile_data = None
                    if hasattr(self, 'automation') and self.automation:
                        try:
                            profile_data = self.profile_business.get_complete_profile_info(username=username, navigate_if_needed=False)
                            if not profile_data:
                                self.logger.warning(f"Failed to get profile data for @{username}")
                                stats['errors'] += 1
                                self.stats_manager.increment('errors')
                                continue
                            
                            if profile_data.get('is_private', False):
                                self.logger.info(f"Private profile @{username} - skipped")
                                stats['skipped'] += 1
                                self.stats_manager.increment('private_profiles')
                                self.stats_manager.increment('skipped')
                                
                                # Enregistrer le profil privé dans filtered_profile
                                try:
                                    session_id = self._get_session_id()
                                    source_name = getattr(self.automation, 'target_username', 'unknown')
                                    DatabaseHelpers.record_filtered_profile(
                                        username=username,
                                        reason='Private profile',
                                        source_type='FOLLOWER',
                                        source_name=source_name,
                                        account_id=account_id,
                                        session_id=session_id
                                    )
                                    self.logger.debug(f"Private profile @{username} recorded in API")
                                except Exception as e:
                                    self.logger.error(f"Error recording private profile @{username}: {e}")
                                
                                continue
                                
                        except Exception as e:
                            self.logger.error(f"Error getting profile @{username}: {e}")
                            stats['errors'] += 1
                            self.stats_manager.increment('errors')
                            continue
                    
                    try:
                        # ✅ Passer profile_data pour éviter une 2ème extraction
                        interaction_result = self._perform_profile_interactions(username, config, profile_data=profile_data)
                        
                        # Track if we actually interacted
                        actually_interacted = False
                        
                        if interaction_result.get('liked'):
                            stats['liked'] += 1
                            actually_interacted = True
                        if interaction_result.get('followed'):
                            stats['followed'] += 1
                            actually_interacted = True
                        if interaction_result.get('story_viewed'):
                            stats['stories_viewed'] += 1
                            actually_interacted = True
                        if interaction_result.get('commented'):
                            if 'comments' not in stats:
                                stats['comments'] = 0
                            stats['comments'] += 1
                            actually_interacted = True
                        
                        # Only count as interacted if we actually did something
                        if actually_interacted:
                            stats['processed'] += 1
                            self.stats_manager.increment('profiles_interacted')
                            # Enregistrer l'interaction pour le système de pauses
                            self.human.record_interaction()
                        else:
                            self.logger.debug(f"@{username} visited but no interaction (probability)")
                            stats['skipped'] += 1
                        
                        # Mark as processed in DB (to avoid revisiting)
                        if account_id:
                            try:
                                visit_notes = "Profile interaction" if actually_interacted else "Visited but no interaction"
                                DatabaseHelpers.mark_profile_as_processed(
                                    username, visit_notes,
                                    account_id=account_id,
                                    session_id=self._get_session_id()
                                )
                            except Exception as e:
                                self.logger.warning(f"Error marking @{username}: {e}")
                        
                        if interaction_result.get('filtered', False):
                            self.stats_manager.increment('profiles_filtered')
                            

                            try:
                                filter_reasons = interaction_result.get('filter_reasons', [])
                                reasons_text = ', '.join(filter_reasons) if filter_reasons else 'filtered'
                                
                                account_id = self._get_account_id()
                                session_id = self._get_session_id()
                                source_name = getattr(self.automation, 'target_username', 'unknown')
                                
                                self.logger.debug(f"[FILTERED] Attempting to record @{username}: account_id={account_id}, session_id={session_id}, source={source_name}")
                                
                                if not account_id:
                                    self.logger.warning(f"[FILTERED] Cannot record @{username} - account_id is None")
                                else:
                                    DatabaseHelpers.record_filtered_profile(
                                        username=username,
                                        reason=reasons_text,
                                        source_type='FOLLOWER',
                                        source_name=source_name,
                                        account_id=account_id,
                                        session_id=session_id
                                    )
                                    self.logger.info(f"Filtered profile @{username} recorded (reasons: {reasons_text})")
                            except Exception as e:
                                self.logger.error(f"Error recording filtered profile @{username}: {e}")
                        else:
                            if interaction_result.get('liked'):
                                self.stats_manager.increment('likes', interaction_result.get('likes_count', 1))
                            if interaction_result.get('followed'):
                                self.stats_manager.increment('follows')
                            if interaction_result.get('story_viewed'):
                                self.stats_manager.increment('stories_watched')
                            if interaction_result.get('commented'):
                                self.stats_manager.increment('comments')
                        
                    except Exception as e:
                        self.logger.error(f"Error interacting with @{username}: {e}")
                        stats['errors'] += 1
                        self.stats_manager.add_error(f"Interaction error @{username}: {str(e)}")
                        continue
                    
                    self.stats_manager.display_stats(current_profile=username)
                    
                    if i < max_interactions - 1:
                        delay = random.randint(*config['interaction_delay_range'])
                        self.logger.debug(f"Delay {delay}s before next interaction")
                        time.sleep(delay)
                    
                except Exception as e:
                    self.logger.error(f"Critical error @{username}: {e}")
                    stats['errors'] += 1
                    self.stats_manager.add_error(f"Critical error @{username}: {str(e)}")
                    
                    if session_id and target_username:
                        self._update_checkpoint_index(i + 1)
                    
                    continue
        
        finally:
            if session_id and target_username:
                self._cleanup_checkpoint()
        
        self.logger.info(f"Interactions completed: {stats}")
        
        self.stats_manager.display_final_stats(workflow_name="FOLLOWERS")
        
        real_stats = self.stats_manager.to_dict()
        return {
            'processed': real_stats.get('profiles_visited', 0),
            'liked': real_stats.get('likes', 0),
            'followed': real_stats.get('follows', 0),
            'stories_viewed': real_stats.get('stories_watched', 0),
            'comments': real_stats.get('comments', 0),
            'errors': real_stats.get('errors', 0),
            'skipped': stats.get('skipped', 0),
            'resumed_from_checkpoint': stats.get('resumed_from_checkpoint', False)
        }
    
    def interact_with_followers_direct(self, target_username: str,
                                       max_interactions: int = 30,
                                       config: Dict[str, Any] = None,
                                       account_id: int = None) -> Dict[str, Any]:
        """
        🆕 NOUVEAU WORKFLOW: Interaction directe depuis la liste des followers.
        
        Au lieu de scraper puis naviguer via deep link, on:
        1. Ouvre la liste des followers
        2. Pour chaque follower visible: clic direct → interaction → retour
        3. Scroll seulement quand tous les visibles sont traités
        
        Avantages:
        - ❌ Plus de deep links (pattern suspect)
        - ✅ Navigation 100% naturelle par clics
        - ✅ Comportement humain réaliste
        """
        config = config or {}
        
        stats = {
            'interacted': 0,      # Profiles with actual interaction (like/follow/story/comment)
            'visited': 0,         # Total profiles visited (navigated to)
            'liked': 0,
            'followed': 0,
            'stories_viewed': 0,
            'story_likes': 0,     # Likes on stories
            'errors': 0,
            'skipped': 0,
            'filtered': 0,        # Profiles filtered by criteria
            'already_processed': 0,
            # Keep 'processed' as alias for 'interacted' for backward compatibility
            'processed': 0
        }
        
        interaction_config = {
            'like_probability': config.get('like_probability', 0.8),
            'follow_probability': config.get('follow_probability', 0.2),
            'comment_probability': config.get('comment_probability', 0.1),
            'story_probability': config.get('story_probability', 0.2),
            'max_likes_per_profile': config.get('max_likes_per_profile', 3),
            'filter_criteria': config.get('filter_criteria', config.get('filters', {}))
        }
        
        # Navigation configuration
        # deep_link_percentage: 0 = always search, 100 = always deep link
        # force_search_for_target: if True, always use search for target profile navigation
        deep_link_percentage = config.get('deep_link_percentage', 90)
        force_search_for_target = config.get('force_search_for_target', False)
        
        try:
            # 1. Naviguer vers le profil cible
            self.logger.info(f"🎯 Opening followers list of @{target_username}")
            
            if not self.nav_actions.navigate_to_profile(
                target_username, 
                deep_link_usage_percentage=deep_link_percentage,
                force_search=force_search_for_target
            ):
                self.logger.error(f"Failed to navigate to @{target_username}")
                return stats
            
            self._human_like_delay('profile_view')
            
            # Récupérer le profil complet (inclut is_private via batch check)
            profile_info = self.profile_business.get_complete_profile_info(target_username, navigate_if_needed=False)
            
            # Vérifier si le profil est privé (from profile_info, no extra ADB call)
            if profile_info and profile_info.get('is_private', False):
                self.logger.warning(f"@{target_username} is a private account")
                return stats
            
            target_followers_count = profile_info.get('followers_count', 0) if profile_info else 0
            
            if target_followers_count > 0:
                self.logger.info(f"📊 Target @{target_username} has {target_followers_count:,} followers")
            else:
                self.logger.warning(f"⚠️ Could not get followers count for @{target_username}")
            
            # 2. Ouvrir la liste des followers OU following selon interaction_type
            interaction_type = config.get('interaction_type', 'followers')
            
            if interaction_type == 'following':
                self.logger.info(f"📋 Opening FOLLOWING list of @{target_username}")
                if not self.nav_actions.open_following_list():
                    self.logger.error("Failed to open following list")
                    return stats
            else:
                self.logger.info(f"📋 Opening FOLLOWERS list of @{target_username}")
                if not self.nav_actions.open_followers_list():
                    self.logger.error("Failed to open followers list")
                    return stats
            
            self._human_like_delay('navigation')
            
            # Démarrer la phase d'interaction
            if self.session_manager:
                self.session_manager.start_interaction_phase()
            
            # 3. Boucle principale d'interaction
            processed_usernames = set()
            scroll_attempts = 0
            max_scroll_attempts = 100  # Augmenté pour les très gros comptes
            no_new_profiles_count = 0
            total_usernames_seen = 0  # Compteur total de usernames vus
            
            # Contexte de navigation pour savoir où on en est
            last_visited_username = None  # Dernier profil visité
            next_expected_username = None  # Prochain profil attendu après le retour
            
            # Initialiser le ScrollEndDetector pour gérer le bouton "Voir plus" et la fin de liste
            scroll_detector = ScrollEndDetector(repeats_to_end=5, device=self.device)
            
            # Initialiser le tracker pour diagnostiquer les problèmes de navigation
            # Récupérer le username du compte actif depuis automation ou utiliser "unknown"
            account_username = "unknown"
            if self.automation and hasattr(self.automation, 'active_username') and self.automation.active_username:
                account_username = self.automation.active_username
            tracker = FollowersTracker(account_username, target_username)
            self.logger.info(f"📝 Tracking log: {tracker.get_log_file_path()}")
            
            self.logger.info(f"🚀 Starting direct interactions (max: {max_interactions})")
            
            while stats['interacted'] < max_interactions and scroll_attempts < max_scroll_attempts:
                # Vérifier si on doit prendre une pause
                took_break = self._maybe_take_break()
                
                # Après une pause, vérifier qu'on est toujours sur la liste des followers
                if took_break:
                    if not self.detection_actions.is_followers_list_open():
                        self.logger.warning("⚠️ Not on followers list after break, trying to recover...")
                        
                        # IMPORTANT: Ne PAS naviguer vers la target car ça reset la liste!
                        # Essayer d'abord de revenir avec le bouton back (max 3 tentatives)
                        recovered = False
                        for back_attempt in range(3):
                            self.logger.debug(f"🔙 Back attempt {back_attempt + 1}/3")
                            if self._go_back_to_list():
                                self._human_like_delay('navigation')
                                if self.detection_actions.is_followers_list_open():
                                    self.logger.info("✅ Recovered to followers list via back button")
                                    recovered = True
                                    break
                        
                        if not recovered:
                            # En dernier recours seulement, naviguer vers la target
                            # Mais on sait qu'on va perdre notre position dans la liste
                            self.logger.warning("⚠️ Could not recover via back, navigating to target (will restart from beginning)")
                            if not self.nav_actions.navigate_to_profile(
                                target_username,
                                deep_link_usage_percentage=deep_link_percentage,
                                force_search=force_search_for_target
                            ):
                                self.logger.error("Could not navigate back to target profile")
                                break
                            if not self.nav_actions.open_followers_list():
                                self.logger.error("Could not reopen followers list")
                                break
                            self._human_like_delay('navigation')
                            # Reset le compteur car on recommence
                            self.logger.warning(f"⚠️ Position lost - restarting from beginning (was at {total_usernames_seen} usernames)")
                
                # Vérifier si la session doit continuer
                if self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        break
                
                # Récupérer les followers visibles (uniquement les vrais, pas les suggestions)
                visible_followers = self.detection_actions.get_visible_followers_with_elements()
                
                # Tracker: enregistrer les followers visibles
                if visible_followers:
                    visible_usernames_for_tracking = [f['username'] for f in visible_followers]
                    loop_detected = tracker.log_visible_followers(visible_usernames_for_tracking, "scan")
                    if loop_detected:
                        self.logger.warning("⚠️ LOOP DETECTED: Back to start of followers list!")
                        # Si on détecte une boucle, on a probablement perdu notre position
                        # On peut soit arrêter, soit essayer de scroller pour avancer
                        if tracker.loop_detected_count >= 3:
                            self.logger.error("🛑 Too many loops detected (3+), stopping to avoid infinite loop")
                            break
                        else:
                            # Essayer de scroller pour sortir de la boucle
                            self.logger.info("🔄 Trying to scroll past the loop...")
                            for _ in range(3):
                                self.scroll_actions.scroll_followers_list_down()
                                self._human_like_delay('scroll')
                            continue
                
                if not visible_followers:
                    self.logger.debug("No visible followers found on screen")
                    
                    # Vérifier si on est dans la section suggestions (fin des vrais followers)
                    if self.detection_actions.is_in_suggestions_section():
                        self.logger.info("📋 Reached suggestions section - checking for 'See more' button")
                        
                        # Essayer de cliquer sur "Voir plus" pour charger plus de vrais followers
                        if scroll_detector.click_load_more_if_present():
                            self._human_like_delay('load_more')
                            # Attendre un peu plus pour que la liste se recharge
                            time.sleep(1.5)
                            continue
                        else:
                            # Réessayer une fois de plus après un petit scroll
                            self.logger.debug("No 'See more' button found, trying a small scroll...")
                            self.scroll_actions.scroll_followers_list_down()
                            self._human_like_delay('scroll')
                            
                            # Re-vérifier le bouton après le scroll
                            if scroll_detector.click_load_more_if_present():
                                self._human_like_delay('load_more')
                                time.sleep(1.5)
                                continue
                            
                            self.logger.info("🏁 No more real followers to load - end of list")
                            break
                    
                    # Vérifier s'il y a un bouton "Voir plus" même sans section suggestions
                    if scroll_detector.click_load_more_if_present():
                        self._human_like_delay('load_more')
                        continue
                    
                    # Vérifier si on a atteint la fin de la liste
                    if scroll_detector.is_the_end():
                        self.logger.info("🏁 End of followers list detected")
                        break
                    
                    # PRIORITÉ: Vérifier le bouton "Voir plus" AVANT de scroller
                    load_more_result = self.scroll_actions.check_and_click_load_more()
                    if load_more_result is True:
                        self.logger.info("✅ 'Voir plus' clicked (no visible followers) - loading more real followers")
                        self._human_like_delay('load_more')
                        time.sleep(1.0)
                        scroll_attempts = 0
                        continue
                    elif load_more_result is False:
                        self.logger.info("🏁 End of followers list detected (suggestions section)")
                        break
                    
                    scroll_attempts += 1
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
                    continue
                
                new_usernames_found = 0  # Nouveaux usernames vus (pas encore dans processed_usernames)
                new_profiles_to_interact = 0  # Profils avec lesquels on va vraiment interagir
                did_interact_this_iteration = False  # A-t-on interagi avec un profil cette itération?
                
                # Extraire la liste ordonnée des usernames visibles
                visible_usernames_list = [f['username'] for f in visible_followers]
                
                # Vérifier si on est au bon endroit après un retour de profil
                if last_visited_username and next_expected_username:
                    position_ok = last_visited_username in visible_usernames_list or next_expected_username in visible_usernames_list
                    tracker.log_position_check(last_visited_username, next_expected_username, visible_usernames_list, position_ok)
                    
                    if position_ok:
                        self.logger.debug(f"✅ Position OK: found @{last_visited_username} or @{next_expected_username} in visible list")
                    else:
                        self.logger.warning(f"⚠️ Position lost: neither @{last_visited_username} nor @{next_expected_username} visible")
                        # On continue quand même, le scroll nous ramènera
                
                for idx, follower_data in enumerate(visible_followers):
                    username = follower_data['username']
                    
                    # Skip si déjà vu dans cette session (évite de re-traiter)
                    if username in processed_usernames:
                        continue
                    
                    # Skip our own account - never interact with ourselves!
                    if account_username and account_username != "unknown":
                        if username.lower() == account_username.lower():
                            self.logger.info(f"⏭️ Skipping own account @{username}")
                            processed_usernames.add(username)
                            # Don't count own account in filtered stats
                            continue
                    
                    # Skip target account - no need to interact with the source
                    if target_username and username.lower() == target_username.lower():
                        self.logger.info(f"⏭️ Skipping target account @{username}")
                        processed_usernames.add(username)
                        # Don't count target account in filtered stats
                        continue
                    
                    processed_usernames.add(username)
                    new_usernames_found += 1
                    total_usernames_seen += 1
                    
                    # Vérifier si déjà traité OU filtré via API (DB)
                    if account_id:
                        try:
                            should_skip, skip_reason = DatabaseHelpers.is_profile_skippable(
                                username, account_id, hours_limit=24*60
                            )
                            if should_skip:
                                if skip_reason == "already_processed":
                                    self.logger.debug(f"@{username} already processed in DB, skipping")
                                    stats['already_processed'] += 1
                                    tracker.log_skipped_from_db(username, "already_processed")
                                elif skip_reason == "already_filtered":
                                    self.logger.debug(f"@{username} already filtered in DB, skipping")
                                    stats['filtered'] += 1
                                    tracker.log_skipped_from_db(username, "already_filtered")
                                stats['skipped'] += 1
                                continue
                        except Exception as e:
                            self.logger.warning(f"Error checking @{username}: {e}")
                    
                    # Ce profil est nouveau et pas dans la DB → on va interagir
                    new_profiles_to_interact += 1
                    
                    # Mémoriser le contexte AVANT de cliquer
                    last_visited_username = username
                    # Trouver le prochain username dans la liste (s'il existe)
                    if idx + 1 < len(visible_followers):
                        next_expected_username = visible_followers[idx + 1]['username']
                    else:
                        next_expected_username = None
                    
                    # === INTERACTION DIRECTE ===
                    # Afficher les interactions réussies ET les profils visités pour plus de clarté
                    profiles_clicked = stats.get('profiles_clicked', 0) + 1
                    stats['profiles_clicked'] = profiles_clicked
                    progress_info = f"[{stats['interacted']}/{max_interactions} interactions, {profiles_clicked} visited]"
                    if target_followers_count > 0:
                        progress_pct = (total_usernames_seen / target_followers_count) * 100
                        progress_info += f" ({progress_pct:.1f}% of {target_followers_count:,} followers scanned)"
                    self.logger.info(f"{progress_info} 👆 Clicking on @{username}")
                    
                    # Cliquer sur le profil dans la liste
                    if not self.detection_actions.click_follower_in_list(username):
                        self.logger.warning(f"Could not click on @{username}")
                        stats['errors'] += 1
                        continue
                    
                    self._human_like_delay('navigation')
                    
                    # Vérifier qu'on est bien sur un profil
                    if not self.detection_actions.is_on_profile_screen():
                        self.logger.warning(f"Not on profile screen after clicking @{username}")
                        # S'assurer qu'on revient bien sur la liste avant de continuer
                        if not self._ensure_on_followers_list(target_username):
                            self.logger.error("Could not recover to followers list, stopping")
                            break
                        stats['errors'] += 1
                        continue
                    
                    # ✅ Profile successfully visited - increment counter
                    stats['visited'] += 1
                    self.stats_manager.increment('profiles_visited')
                    
                    # Tracker: enregistrer la visite
                    tracker.log_profile_visit(username, idx, already_in_db=False)
                    
                    # Extraire les infos du profil
                    try:
                        profile_data = self.profile_business.get_complete_profile_info(
                            username=username, 
                            navigate_if_needed=False
                        )
                        
                        if not profile_data:
                            self.logger.warning(f"Could not get profile data for @{username}")
                            # force_back=True car on vient de visiter un profil
                            if not self._ensure_on_followers_list(target_username, force_back=True):
                                self.logger.error("Could not recover to followers list, stopping")
                                break
                            stats['errors'] += 1
                            continue
                        
                        # Vérifier si profil privé
                        if profile_data.get('is_private', False):
                            self.logger.info(f"🔒 Private profile @{username} - skipped")
                            stats['skipped'] += 1
                            self.stats_manager.increment('private_profiles')
                            
                            # Tracker: profil filtré (privé)
                            tracker.log_profile_filtered(username, "Private profile", profile_data)
                            
                            # Enregistrer comme filtré
                            if account_id:
                                try:
                                    DatabaseHelpers.record_filtered_profile(
                                        username=username,
                                        reason='Private profile',
                                        source_type='FOLLOWER',
                                        source_name=target_username,
                                        account_id=account_id,
                                        session_id=self._get_session_id()
                                    )
                                except Exception:
                                    pass
                            
                            # force_back=True car on vient de visiter un profil privé
                            if not self._ensure_on_followers_list(target_username, force_back=True):
                                self.logger.error("Could not recover to followers list, stopping")
                                break
                            continue
                        
                        # Appliquer les filtres
                        filter_criteria = interaction_config.get('filter_criteria', {})
                        filter_result = self.filtering_business.apply_comprehensive_filter(
                            profile_data, filter_criteria
                        )
                        
                        if not filter_result.get('suitable', False):
                            reasons = filter_result.get('reasons', [])
                            self.logger.info(f"🚫 @{username} filtered: {', '.join(reasons)}")
                            stats['filtered'] += 1
                            self.stats_manager.increment('profiles_filtered')
                            
                            # Tracker: profil filtré (critères)
                            tracker.log_profile_filtered(username, ', '.join(reasons), profile_data)
                            
                            # IMPORTANT: Enregistrer le profil filtré dans la DB pour éviter de le revisiter
                            if account_id:
                                try:
                                    DatabaseHelpers.record_filtered_profile(
                                        username=username,
                                        reason=', '.join(reasons),
                                        source_type='FOLLOWER',
                                        source_name=target_username,
                                        account_id=account_id,
                                        session_id=self._get_session_id()
                                    )
                                except Exception as e:
                                    self.logger.debug(f"Error recording filtered profile @{username}: {e}")
                            
                            # force_back=True car on vient de visiter un profil filtré
                            if not self._ensure_on_followers_list(target_username, force_back=True):
                                self.logger.error("Could not recover to followers list, stopping")
                                break
                            continue
                        
                        # === EFFECTUER LES INTERACTIONS ===
                        interaction_result = self._perform_profile_interactions(
                            username, 
                            interaction_config, 
                            profile_data=profile_data
                        )
                        
                        # DEBUG: Log interaction result
                        self.logger.debug(f"🔍 interaction_result for @{username}: {interaction_result}")
                        
                        # Mettre à jour les stats locales ET le stats_manager
                        # Track if we actually interacted with this profile
                        actually_interacted = False
                        
                        if interaction_result.get('liked'):
                            likes_count = interaction_result.get('likes_count', 1)
                            stats['liked'] += likes_count
                            self.stats_manager.increment('likes', likes_count)
                            actually_interacted = True
                        if interaction_result.get('followed'):
                            stats['followed'] += 1
                            self.stats_manager.increment('follows')
                            actually_interacted = True
                        if interaction_result.get('story_viewed'):
                            stats['stories_viewed'] += 1
                            self.stats_manager.increment('stories_watched')
                            actually_interacted = True
                        if interaction_result.get('story_liked'):
                            stats['story_likes'] += 1
                            self.stats_manager.increment('story_likes')
                            actually_interacted = True
                        if interaction_result.get('commented'):
                            actually_interacted = True
                        
                        # Only count as "interacted" if we actually did something
                        # (like, follow, story view/like, comment - not just visited)
                        if actually_interacted:
                            stats['interacted'] += 1
                            stats['processed'] += 1  # Keep for backward compatibility
                            self.stats_manager.increment('profiles_interacted')
                            did_interact_this_iteration = True
                            # Enregistrer l'interaction pour le système de pauses
                            self.human.record_interaction()
                            # Tracker: interaction réussie
                            tracker.log_profile_interacted(username, {
                                'liked': interaction_result.get('liked', False),
                                'followed': interaction_result.get('followed', False),
                                'story_viewed': interaction_result.get('story_viewed', False),
                                'commented': interaction_result.get('commented', False)
                            })
                        else:
                            # Visited but no interaction (probability rolls failed)
                            self.logger.debug(f"@{username} visited but no interaction (probability)")
                            stats['skipped'] += 1
                        
                        # Marquer comme traité dans la DB (même si pas d'interaction, pour éviter de revisiter)
                        if account_id:
                            try:
                                DatabaseHelpers.mark_profile_as_processed(
                                    username, 
                                    "Direct interaction from followers list" if actually_interacted else "Visited but no interaction",
                                    account_id=account_id,
                                    session_id=self._get_session_id()
                                )
                            except Exception:
                                pass
                        
                        # Enregistrer dans session manager SEULEMENT si on a vraiment interagi
                        if actually_interacted and self.session_manager:
                            self.session_manager.record_profile_processed()
                        
                    except Exception as e:
                        self.logger.error(f"Error interacting with @{username}: {e}")
                        stats['errors'] += 1
                    
                    # Retour à la liste des followers avec vérification robuste
                    # force_back=True car on vient de visiter un profil et d'interagir
                    if not self._ensure_on_followers_list(target_username, force_back=True):
                        self.logger.error("Could not return to followers list, stopping")
                        break
                    
                    # === VÉRIFICATION DE POSITION APRÈS RETOUR (style Insomniac) ===
                    # Récupérer les followers visibles après le retour
                    visible_after_back = self.detection_actions.get_visible_followers_with_elements()
                    if visible_after_back:
                        visible_usernames_after = [f['username'] for f in visible_after_back]
                        
                        # Vérifier si on est revenu à la bonne position
                        position_ok = tracker.check_position_after_back(username, visible_usernames_after)
                        
                        if not position_ok:
                            self.logger.warning(f"⚠️ Position lost after visiting @{username} - may cause loop")
                            # Log pour diagnostic mais on continue
                            # Le système de processed_usernames évitera de revisiter les mêmes profils
                    
                    # Afficher les stats
                    self.stats_manager.display_stats(current_profile=username)
                    
                    # Vérifier si on a atteint le max
                    if stats['interacted'] >= max_interactions:
                        break
                    
                    # IMPORTANT: Après avoir interagi, on sort de la boucle for
                    # pour re-scanner la liste et trouver le prochain follower non traité
                    # Cela évite de rester bloqué sur les mêmes profils
                    break
                
                # Notifier le scroll detector des usernames vus
                visible_usernames = [f['username'] for f in visible_followers]
                scroll_detector.notify_new_page(visible_usernames, list(processed_usernames))
                
                # Vérifier si on a vu de nouveaux usernames (même s'ils sont déjà dans la DB)
                # C'est important pour savoir si on avance dans la liste ou si on est bloqué
                if new_usernames_found == 0:
                    # Aucun nouvel username = on revoit les mêmes profils
                    no_new_profiles_count += 1
                    
                    # Calculer combien de followers il reste potentiellement à parcourir
                    remaining_followers = target_followers_count - total_usernames_seen if target_followers_count > 0 else float('inf')
                    
                    self.logger.debug(f"⚠️ No new usernames found ({no_new_profiles_count}/15) - {total_usernames_seen} seen, ~{remaining_followers:,.0f} remaining")
                    
                    # Vérifier s'il y a un bouton "Voir plus" avant de conclure
                    if scroll_detector.click_load_more_if_present():
                        self._human_like_delay('load_more')
                        no_new_profiles_count = 0
                        continue
                    
                    # Conditions pour arrêter (alignées avec _extract_followers_with_scroll):
                    # 1. On a vu ~95% des followers de la target → fin de liste
                    # 2. OU le scroll detector dit qu'on est à la fin
                    # 3. OU le tracker détecte des pages identiques (style Insomniac)
                    # 4. OU on a essayé 20 fois sans nouveaux usernames (sécurité)
                    should_stop = False
                    
                    # Vérifier si on a parcouru ~95% des followers (comme dans l'ancienne fonction)
                    if target_followers_count > 0 and total_usernames_seen >= target_followers_count * 0.95:
                        self.logger.info(f"🏁 Reached end of list: seen {total_usernames_seen:,}/{target_followers_count:,} followers (~95%)")
                        should_stop = True
                    elif scroll_detector.is_the_end():
                        self.logger.info("🏁 ScrollEndDetector: end of list reached")
                        should_stop = True
                    elif tracker.is_end_of_list():
                        self.logger.info("🏁 Tracker: same followers seen multiple times - end of list")
                        should_stop = True
                    elif no_new_profiles_count >= 20:
                        self.logger.info(f"🏁 No new usernames found after 20 attempts (seen {total_usernames_seen:,} usernames)")
                        should_stop = True
                    elif no_new_profiles_count >= 10:
                        # Après 10 tentatives, log la progression pour debug
                        if target_followers_count > 0:
                            coverage = (total_usernames_seen / target_followers_count) * 100
                            self.logger.debug(f"📊 {coverage:.1f}% coverage ({total_usernames_seen:,}/{target_followers_count:,}), continuing...")
                    
                    if should_stop:
                        break
                    
                    # PRIORITÉ: Vérifier le bouton "Voir plus" AVANT de scroller
                    load_more_result = self.scroll_actions.check_and_click_load_more()
                    if load_more_result is True:
                        self.logger.info("✅ 'Voir plus' clicked (no new usernames) - loading more real followers")
                        self._human_like_delay('load_more')
                        time.sleep(1.0)
                        no_new_profiles_count = 0
                        continue
                    elif load_more_result is False:
                        self.logger.info("🏁 End of followers list detected (suggestions section)")
                        break
                    
                    # Forcer un scroll pour essayer d'avancer
                    tracker.log_scroll("down")
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
                    scroll_attempts += 1
                    continue  # Re-scanner après le scroll
                else:
                    # On a vu de nouveaux usernames, on continue
                    no_new_profiles_count = 0
                    
                    # Log pour debug avec progression
                    if target_followers_count > 0:
                        coverage = (total_usernames_seen / target_followers_count) * 100
                        self.logger.debug(f"📊 Progress: {total_usernames_seen:,}/{target_followers_count:,} ({coverage:.1f}%) - {new_usernames_found} new this page")
                    
                    if new_profiles_to_interact == 0 and new_usernames_found > 0:
                        self.logger.debug(f"📋 {new_usernames_found} new usernames seen, but all already in DB - continuing scroll")
                
                # Scroller pour voir plus de followers
                # On scroll seulement si:
                # 1. On n'a pas atteint le max
                # 2. On n'a PAS interagi cette itération (sinon on re-scanne d'abord pour voir si le suivant est visible)
                #    OU tous les nouveaux usernames étaient déjà dans la DB
                if stats['interacted'] < max_interactions:
                    if not did_interact_this_iteration or (new_usernames_found > 0 and new_profiles_to_interact == 0):
                        self.logger.debug(f"📜 Scrolling (interacted: {did_interact_this_iteration}, new_usernames: {new_usernames_found}, to_interact: {new_profiles_to_interact})")
                        
                        # PRIORITÉ: Vérifier le bouton "Voir plus" AVANT de scroller
                        # C'est crucial car le bouton apparaît après ~25 followers et doit être cliqué
                        # pour charger les vrais followers suivants (sinon on tombe dans les suggestions)
                        load_more_result = self.scroll_actions.check_and_click_load_more()
                        if load_more_result is True:
                            # Bouton trouvé et cliqué - attendre le chargement
                            self.logger.info("✅ 'Voir plus' clicked before scroll - loading more real followers")
                            self._human_like_delay('load_more')
                            time.sleep(1.0)  # Attendre que les nouveaux followers se chargent
                            scroll_attempts = 0  # Reset car on a chargé de nouveaux followers
                            continue  # Re-scanner sans scroller
                        elif load_more_result is False:
                            # Fin de liste détectée (suggestions section)
                            self.logger.info("🏁 End of followers list detected (suggestions section)")
                            break
                        # Si None, pas de bouton visible -> on peut scroller normalement
                        
                        tracker.log_scroll("down")
                        self.scroll_actions.scroll_followers_list_down()
                        self._human_like_delay('scroll')
                        scroll_attempts += 1
            
            # Tracker: enregistrer la fin de session
            tracker.log_session_end(stats)
            self.logger.info(f"✅ Direct interactions completed: {stats}")
            self.stats_manager.display_final_stats(workflow_name="FOLLOWERS_DIRECT")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error in direct followers workflow: {e}")
            return stats
    
    def interact_with_target_followers(self, target_username: str = None, target_usernames: List[str] = None,
                                     max_interactions: int = 10,
                                     like_posts: bool = True,
                                     max_likes_per_profile: int = 2,
                                     skip_processed: bool = True,
                                     automation=None,
                                     account_id: int = None,
                                     config: Dict[str, Any] = None) -> Dict[str, Any]:
        # Support both single and multi-target
        if target_usernames is None:
            target_usernames = [target_username] if target_username else []
        
        if not target_usernames:
            self.logger.error("No target username(s) provided")
            return {}
        
        if len(target_usernames) > 1:
            self.logger.info(f"🎯 Multi-target mode: {len(target_usernames)} targets configured")
        
        stats = {
            'interactions_performed': 0,
            'likes_performed': 0,
            'follows_performed': 0,
            'profiles_processed': 0,
            'profiles_visited': 0,
            'profiles_filtered': 0,
            'skipped': 0,
            'errors': 0
        }
        
        if config is None:
            config = {}
        
        interaction_config = {
            'max_interactions_per_session': max_interactions,
            'like_posts': like_posts,
            'max_likes_per_profile': max_likes_per_profile,
            'like_probability': config.get('like_probability', 0.8),
            'follow_probability': config.get('follow_probability', 0.2),
            'comment_probability': config.get('comment_probability', 0.1),
            'story_probability': config.get('story_probability', 0.2),
            'filter_criteria': config.get('filter_criteria', config.get('filters', {}))
        }
        
        # Démarrer la phase de scraping
        if self.session_manager:
            self.session_manager.start_scraping_phase()
        
        # Extract followers from multiple targets
        all_followers = []
        for target_idx, target_username in enumerate(target_usernames):
            try:
                self.logger.info(f"📥 [{target_idx + 1}/{len(target_usernames)}] Extracting followers from @{target_username}...")
                
                if not self.nav_actions.navigate_to_profile(target_username):
                    self.logger.error(f"Failed to navigate to @{target_username}, skipping")
                    continue
                
                if self.detection_actions.is_private_account():
                    self.logger.warning(f"@{target_username} is a private account, skipping")
                    continue
                
                # Get profile info to check follower count BEFORE opening list
                profile_info = self.profile_business.get_complete_profile_info(target_username, navigate_if_needed=False)
                total_followers_count = profile_info.get('followers_count', 0) if profile_info else 0
                
                if total_followers_count > 0:
                    self.logger.info(f"📊 @{target_username} has {total_followers_count} followers")
                
                if not self.nav_actions.open_followers_list():
                    self.logger.error(f"Failed to open followers list for @{target_username}, skipping")
                    continue
                
                self._random_sleep()
                
                # Calculate how many more followers we need
                remaining_needed = (max_interactions * 2) - len(all_followers)
                if remaining_needed <= 0:
                    self.logger.info(f"✅ Target reached: {len(all_followers)} followers collected")
                    break
                
                # Adjust extraction limit based on profile's actual follower count
                extraction_limit = remaining_needed
                if total_followers_count > 0:
                    # Don't try to extract more than what the profile has (with 10% margin for already processed)
                    max_available = int(total_followers_count * 0.9)
                    extraction_limit = min(remaining_needed, max_available)
                    self.logger.info(f"🎯 Extraction limit adjusted to {extraction_limit} (profile has ~{total_followers_count} followers)")
                
                followers = self._extract_followers_with_scroll(
                    extraction_limit, 
                    account_id, 
                    target_username,
                    max_followers_count=total_followers_count
                )
                
                if followers:
                    all_followers.extend(followers)
                    self.logger.info(f"✅ {len(followers)} followers extracted from @{target_username} (total: {len(all_followers)})")
                else:
                    self.logger.warning(f"⚠️ No followers extracted from @{target_username}")
                
                # Check if we have enough followers
                if len(all_followers) >= max_interactions * 2:
                    self.logger.info(f"🎯 Target reached: {len(all_followers)} followers collected")
                    break
                    
            except Exception as e:
                self.logger.error(f"Error extracting from @{target_username}: {e}")
                continue
        
        # Terminer le scraping et démarrer les interactions
        if self.session_manager:
            self.session_manager.end_scraping_phase()
            self.session_manager.start_interaction_phase()
        
        if not all_followers:
            self.logger.warning(f"❌ No followers extracted from any target")
            return stats
        
        self.logger.info(f"✅ Total: {len(all_followers)} followers extracted from {len(target_usernames)} target(s)")
        self.logger.info(f"🎯 Processing {min(len(all_followers), max_interactions)} followers...")
        
        try:
            session_id_str = str(getattr(automation, 'current_session_id', 'unknown')) if automation else 'unknown'
            return self.interact_with_followers(
                all_followers[:max_interactions], 
                interaction_config,
                session_id=session_id_str,
                target_username=target_usernames[0]  # Use first target for checkpoint naming
            )
            
        except Exception as e:
            self.logger.error(f"Error during interactions: {e}")
            return {
                'interactions_performed': 0,
                'likes_performed': 0,
                'follows_performed': 0,
                'profiles_processed': 0,
                'error': str(e)
            }
    
    def _extract_followers_with_scroll(self, max_followers: int, account_id: int = None, target_username: str = None, max_followers_count: int = 0) -> List[Dict[str, Any]]:
        followers_data = []
        processed_usernames = set()
        scroll_attempts = 0
        max_scroll_attempts = 10
        total_usernames_seen = 0  # Track total usernames seen (including filtered ones)
        
        def follower_callback(follower_username):
            if follower_username in processed_usernames:
                return True
            
            processed_usernames.add(follower_username)
            
            if account_id:
                try:
                    should_skip, skip_reason = DatabaseHelpers.is_profile_skippable(
                        follower_username, account_id, hours_limit=24*60
                    )
                    if should_skip:
                        self.logger.info(f"Profile @{follower_username} skipped ({skip_reason})")
                        return True
                except Exception as e:
                    self.logger.warning(f"Error checking @{follower_username}: {e}")
            
            follower_data = {
                'username': follower_username,
                'source_account_id': account_id,
                'source_username': target_username,
                'full_name': None,
                'is_verified': False,
                'is_private': False,
                'followers_count': None,
                'following_count': None,
                'timestamp': time.time()
            }
            followers_data.append(follower_data)
            
            if len(followers_data) >= max_followers:
                return False
            
            return True
        
        self.logger.info(f"Extracting with individual filtering (max: {max_followers})")
        
        while len(followers_data) < max_followers and scroll_attempts < max_scroll_attempts:
            current_usernames = self.content_business.extract_usernames_from_follow_list()
            
            if not current_usernames:
                self.logger.debug("No new followers found")
                scroll_attempts += 1
            else:
                new_found = 0
                for username in current_usernames:
                    if username:
                        total_usernames_seen += 1
                        continue_extraction = follower_callback(username)
                        if continue_extraction:
                            new_found += 1
                        else:
                            self.logger.info(f"{len(followers_data)} eligible followers collected")
                            return followers_data
                
                # Check if we've seen approximately all followers from this profile
                if max_followers_count > 0 and total_usernames_seen >= max_followers_count * 0.95:
                    self.logger.info(f"🏁 Reached end of list: seen {total_usernames_seen}/{max_followers_count} followers from @{target_username}")
                    break
                
                if new_found == 0:
                    scroll_attempts += 1
                    if scroll_attempts >= max_scroll_attempts:
                        self.logger.info(f"No new eligible followers found after {scroll_attempts} scrolls - end of list reached")
                        break
                else:
                    scroll_attempts = 0
                
                self.logger.debug(f"{new_found} new eligible, total: {len(followers_data)} (seen: {total_usernames_seen}/{max_followers_count if max_followers_count > 0 else '?'})")
            
            if len(followers_data) < max_followers:
                load_more_result = self.scroll_actions.check_and_click_load_more()
                if load_more_result:
                    self.logger.info("'Load more' button clicked, 25 new followers loaded")
                    self._human_like_delay('load_more')
                    scroll_attempts = 0
                elif load_more_result is False:
                    self.logger.info("End of followers list detected")
                    break
                elif load_more_result is None:
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
        
        self.logger.info(f"Extraction completed: {len(followers_data)} eligible followers")
        return followers_data
    
    def _filter_followers(self, followers: List[Dict[str, Any]], 
                         criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        filtered = []
        
        for follower in followers:
            username = follower.get('username', '')
            if not username:
                continue
            
            # DISABLED: Bot username detection - too many false positives
            # if criteria.get('exclude_bots', True):
            #     if self.utils.is_likely_bot_username(username):
            #         continue
            
            filtered.append(follower)
        
        return filtered
    
    def _perform_profile_interactions(self, username: str, 
                                    config: Dict[str, Any],
                                    profile_data: dict = None) -> Dict[str, bool]:
        result = {
            'liked': False,
            'followed': False,
            'story_viewed': False,
            'commented': False
        }
        
        try:
            # ✅ Utiliser profile_data si déjà fourni (évite extraction inutile)
            if profile_data:
                profile_info = profile_data
            else:
                profile_info = self.profile_business.get_complete_profile_info(username=username, navigate_if_needed=False)
            
            if not profile_info:
                return result
            
            if profile_info.get('is_private', False):
                self.logger.debug(f"@{username} is a private profile")
            
            filter_criteria = config.get('filter_criteria', config.get('filters', {}))
            
            self.logger.debug(f"Filter criteria for @{username}: {filter_criteria}")
            
            filter_result = self.filtering_business.apply_comprehensive_filter(
                profile_info, filter_criteria
            )
            
            if not filter_result.get('suitable', False):
                reasons = filter_result.get('reasons', [])
                self.logger.info(f"@{username} filtered: {', '.join(reasons)}")
                
                posts_count = profile_info.get('posts_count', 0)
                min_posts = filter_criteria.get('min_posts', 0)
                if posts_count < min_posts:
                    self.logger.warning(f"@{username} has {posts_count} posts (minimum required: {min_posts})")
                
                result['filtered'] = True
                result['filter_reasons'] = reasons
                self.stats_manager.increment('profiles_filtered')
                return result
            
            # 📊 Enregistrer que ce profil va être traité (après toutes les vérifications)
            if hasattr(self, 'session_manager') and self.session_manager:
                self.session_manager.record_profile_processed()
            
            like_probability = config.get('like_probability', 0.8)
            follow_probability = config.get('follow_probability', 0.2)
            comment_probability = config.get('comment_probability', 0.1)
            
            self.logger.debug(f"Probabilities: like={like_probability}, follow={follow_probability}, comment={comment_probability}")
            self.logger.debug(f"Config: {config}")
            
            like_roll = random.random()
            follow_roll = random.random()
            comment_roll = random.random()
            
            if follow_roll < follow_probability:
                self.logger.debug(f"Follow probability won ({follow_roll:.3f} < {follow_probability})")
                
                # Check if we already follow this user (button shows "Following" instead of "Follow")
                follow_button_state = profile_info.get('follow_button_state', 'unknown')
                if follow_button_state in ['following', 'unfollow', 'requested']:
                    self.logger.info(f"⏭️ Already following @{username} (button: {follow_button_state}) - skipping follow")
                    result['already_following'] = True
                else:
                    follow_result = self.click_actions.follow_user(username)
                    if follow_result:
                        result['followed'] = True
                        try:
                            self.stats_manager.increment('follows')
                        except Exception as e:
                            self.logger.error(f"Critical error: Follow of @{username} cancelled - {e}")
                            self.logger.error(f"Security: Follow of @{username} cancelled to avoid quota leak")
                            
                            result['followed'] = False
                            result['error'] = f"Follow cancelled - API quotas not updated: {e}"
                            return result
                        
                        # REMOVED: L'enregistrement des follows est déjà géré dans base_business_action.py (centralisé)
                        
                        self._handle_follow_suggestions_popup()
                    else:
                        self.logger.debug(f"Follow failed for @{username}")
            else:
                self.logger.debug(f"Follow probability lost ({follow_roll:.3f} >= {follow_probability})")
            
            should_comment = comment_roll < comment_probability and not profile_info.get('is_private', False)
            
            if like_roll < like_probability or should_comment:
                action_type = []
                if like_roll < like_probability:
                    action_type.append("like")
                if should_comment:
                    action_type.append("comment")
                
                self.logger.debug(f"Opening posts for: {', '.join(action_type)}")
                
                try:
                    custom_comments = config.get('custom_comments', [])
                    like_result = self.like_business.like_profile_posts(
                        username=username,
                        max_likes=3,
                        navigate_to_profile=False,
                        config=config,
                        profile_data=profile_info,
                        should_comment=should_comment,
                        custom_comments=custom_comments,
                        comment_template_category=config.get('comment_template_category', 'generic')
                    )
                    
                    likes_count = like_result.get('posts_liked', 0)
                    comments_count = like_result.get('posts_commented', 0)
                    
                    if likes_count > 0:
                        result['liked'] = True
                        result['likes_count'] = likes_count
                        self.logger.debug(f"Likes completed - {likes_count} posts liked")
                    
                    if comments_count > 0:
                        result['commented'] = True
                        self.logger.info(f"✅ {comments_count} comment(s) posted on @{username}'s posts")
                    
                    if likes_count == 0 and comments_count == 0:
                        self.logger.debug(f"No actions performed for @{username}")
                        
                except Exception as e:
                    self.logger.error(f"Error during post interactions for @{username}: {e}")
            else:
                if like_roll >= like_probability:
                    self.logger.debug(f"Like probability lost ({like_roll:.3f} >= {like_probability})")
                if comment_roll >= comment_probability:
                    self.logger.debug(f"Comment probability lost ({comment_roll:.3f} >= {comment_probability})")
            
            if random.random() < config.get('story_probability', 0.3):
                if self._view_stories(username):
                    result['story_viewed'] = True
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error interacting with @{username}: {e}")
            return result
    
    def _view_stories(self, username: str, like_stories: bool = False) -> Optional[Dict[str, int]]:
        try:
            if not self.detection_actions.has_stories():
                return None
            
            if self.click_actions.click_story_ring():
                self._human_like_delay('story_load')
                
                stories_viewed = 0
                stories_liked = 0
                
                for _ in range(3):
                    self._human_like_delay(2, 5)
                    stories_viewed += 1
                    
                    if like_stories:
                        try:
                            if self.click_actions.like_story():
                                stories_liked += 1
                                self.logger.debug(f"Story liked")
                        except Exception as e:
                            self.logger.debug(f"Error liking story: {e}")
                    
                    if not self.nav_actions.navigate_to_next_story():
                        break
                
                self.device.back()
                self._human_like_delay('navigation')
                
                if stories_viewed > 0:
                    self.logger.debug(f"{stories_viewed} stories viewed, {stories_liked} liked")
                    return {
                        'stories_viewed': stories_viewed,
                        'stories_liked': stories_liked
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error viewing stories @{username}: {e}")
            return None
    
    def get_session_stats(self) -> Dict[str, Any]:
        return self.stats_manager.get_summary()
    
    def _validate_follower_limits(self, profile_info: Dict[str, Any], requested_interactions: int) -> Dict[str, Any]:
        available_followers = profile_info.get('followers_count', 0)
        
        result = {
            'valid': True,
            'warning': None,
            'suggestion': None,
            'adjusted_max': None
        }
        
        if available_followers == 0:
            result['valid'] = False
            result['warning'] = "Profile has no followers, cannot extract followers"
            result['suggestion'] = "Choose a profile with followers"
            return result
        
        if requested_interactions > available_followers:
            result['valid'] = False
            result['warning'] = f"Requested {requested_interactions} interactions but only {available_followers} followers available"
            result['suggestion'] = f"Automatically adjusting to maximum {available_followers} interactions"
            result['adjusted_max'] = available_followers
        
        return result