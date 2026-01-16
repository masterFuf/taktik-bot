"""Business logic for Instagram profiles."""

import time
from typing import Dict, Any, List, Optional
from loguru import logger
from ...core.base_business_action import BaseBusinessAction
from taktik.core.database import get_db_service


class ProfileBusiness(BaseBusinessAction):

    
    def __init__(self, device, session_manager=None):
        super().__init__(device, session_manager, automation=None, module_name="profile")
    
    def get_complete_profile_info(self, username: str = None, 
                                 navigate_if_needed: bool = True,
                                 enrich: bool = False) -> Optional[Dict[str, Any]]:
        try:
            if navigate_if_needed:
                if username:
                    if not self.nav_actions.navigate_to_profile(username):
                        self.logger.error(f"Failed to navigate to @{username}")
                        return None
                else:
                    if not self.nav_actions.navigate_to_profile_tab():
                        self.logger.error("Failed to navigate to own profile")
                        return None
            
            # Quick profile screen check (skip if navigate_if_needed=False, we trust the caller)
            if navigate_if_needed:
                if not self.detection_actions.is_on_profile_screen():
                    self.logger.error("Not on a profile screen")
                    return None
            
            # Short delay for profile to load
            self._random_sleep(0.3, 0.6)
            
            # Use batch detection for boolean flags (1 ADB call instead of 3)
            profile_flags = self.detection_actions.get_profile_flags_batch()
            
            # Use enriched extraction if requested (gets more data: business_category, website, linked_accounts)
            if enrich:
                profile_text = self.detection_actions.get_enriched_profile_data()
                original_username = profile_text.get('username')
                
                # If bio is truncated, click "more" to expand and re-extract
                if profile_text.get('bio_truncated'):
                    if self.detection_actions.click_bio_more_button():
                        self._random_sleep(0.3, 0.5)
                        # Re-extract with full bio
                        new_profile_text = self.detection_actions.get_enriched_profile_data()
                        
                        # IMPORTANT: Verify we're still on the same profile
                        # Clicking "more" might have navigated to a @username link in the bio
                        new_username = new_profile_text.get('username')
                        if new_username and original_username and new_username.lower() != original_username.lower():
                            self.logger.warning(f"⚠️ Profile changed after 'more' click: {original_username} → {new_username}. Going back.")
                            self.device.press("back")
                            self._random_sleep(0.3, 0.5)
                            # Keep original profile_text (truncated bio is better than wrong profile)
                        else:
                            profile_text = new_profile_text
            else:
                profile_text = self.detection_actions.get_profile_text_batch()
            
            # Get counts (these are fast, ~300ms each)
            followers_count = self._get_followers_count_robust()
            following_count = self._get_following_count_robust()
            posts_count = self._get_posts_count_robust()
            
            # Get visible posts count (skip is_post_grid_visible - redundant)
            visible_posts = self.detection_actions.count_visible_posts()
            
            # Fallback to individual call if batch didn't get username (critical field)
            extracted_username = profile_text.get('username')
            if not extracted_username:
                extracted_username = self.detection_actions.get_username_from_profile()
            
            profile_info = {
                'username': extracted_username,
                'full_name': profile_text.get('full_name'),
                'biography': profile_text.get('biography'),
                'followers_count': followers_count,
                'following_count': following_count,
                'posts_count': posts_count,
                'is_private': profile_flags.get('is_private', False),
                'is_verified': profile_flags.get('is_verified', False),
                'is_business': profile_flags.get('is_business', False),
                'follow_button_state': self.click_actions.get_follow_button_state(),
                'has_posts': visible_posts > 0,
                'visible_posts_count': visible_posts,
                'visible_stories_count': self.detection_actions.count_visible_stories()
            }
            
            # Add enriched fields if available
            if enrich:
                profile_info['business_category'] = profile_text.get('business_category')
                profile_info['website'] = profile_text.get('website')
                profile_info['linked_accounts'] = profile_text.get('linked_accounts', [])
            
            # Clean username if necessary
            if profile_info['username']:
                profile_info['username'] = self._clean_username(profile_info['username'])
            
            # Add metadata
            profile_info['extraction_timestamp'] = self.utils.format_duration(0)  # Current time
            # NOTE: get_screen_state_summary() removed for performance - it added ~30s of unnecessary detections
            
            # Detailed log with all profile information
            self.logger.info(f"✅ Profile extracted: @{profile_info['username']} ({profile_info['followers_count']} followers)")
            self.logger.debug(f"📊 Complete profile data @{profile_info['username']}:")
            self.logger.debug(f"  • Full name: {profile_info.get('full_name', 'N/A')}")
            self.logger.debug(f"  • Bio: {profile_info.get('biography', 'N/A')}")
            self.logger.debug(f"  • Posts: {profile_info.get('posts_count', 0)} | "
                            f"Followers: {profile_info.get('followers_count', 0)} | "
                            f"Following: {profile_info.get('following_count', 0)}")
            self.logger.debug(f"  • Private: {profile_info.get('is_private', False)} | "
                            f"Verified: {profile_info.get('is_verified', False)} | "
                            f"Business: {profile_info.get('is_business', False)}")
            self.logger.debug(f"  • Visible posts: {profile_info.get('visible_posts_count', 0)} | "
                            f"Visible stories: {profile_info.get('visible_stories_count', 0)}")
            self.logger.debug(f"  • Follow button state: {profile_info.get('follow_button_state', 'unknown')}")
            
            # Save profile to database with actual information
            self._save_profile_to_database(profile_info)
            
            return profile_info
            
        except Exception as e:
            self.logger.error(f"Profile extraction error: {e}")
            return None
    
    def _save_profile_to_database(self, profile_info: Dict[str, Any]):
        try:
            if not profile_info or not profile_info.get('username'):
                return
            
            # Prepare data for API
            profile_data = {
                'username': profile_info['username'],
                'full_name': profile_info.get('full_name', ''),
                'biography': profile_info.get('biography', ''),
                'followers_count': profile_info.get('followers_count', 0),
                'following_count': profile_info.get('following_count', 0),
                'posts_count': profile_info.get('posts_count', 0),
                'is_private': profile_info.get('is_private', False),
                'notes': ''  # Don't auto-populate notes
            }
            
            # Use API to save/update profile
            try:
                db_service = get_db_service()
                from taktik.core.database.models import InstagramProfile
                profile = InstagramProfile(
                    username=profile_data['username'],
                    full_name=profile_data['full_name'],
                    biography=profile_data['biography'],
                    followers_count=profile_data['followers_count'],
                    following_count=profile_data['following_count'],
                    posts_count=profile_data['posts_count'],
                    is_private=profile_data['is_private'],
                    notes=profile_data['notes']
                )
                
                success = db_service.save_profile(profile)
                if success:
                    self.logger.debug(f"Profile @{profile_info['username']} saved to DB with actual data")
                    self.logger.debug(f"  DB: {profile_data['posts_count']} posts, "
                                    f"{profile_data['followers_count']} followers, "
                                    f"{profile_data['following_count']} following")
                else:
                    self.logger.warning(f"Failed to save profile @{profile_info['username']}")
            except Exception as db_error:
                self.logger.error(f"Database access error: {db_error}")
                
        except Exception as e:
            self.logger.error(f"Error saving profile: {e}")
    
    def is_profile_suitable_for_interaction(self, profile_info: Dict[str, Any], 
                                          criteria: Dict[str, Any] = None) -> Dict[str, Any]:
        if not criteria:
            criteria = self._get_default_criteria()
        
        result = {
            'suitable': True,
            'reasons': [],
            'score': 100,
            'category': 'suitable'
        }
        
        if not profile_info:
            result.update({'suitable': False, 'reasons': ['Profile info unavailable'], 'score': 0})
            return result
        
        if profile_info.get('is_private', False):
            if not criteria.get('allow_private', False):
                result.update({
                    'suitable': False,
                    'reasons': ['Private account'],
                    'category': 'private',
                    'score': 0
                })
                return result
        
        # Vérifications des compteurs
        followers = profile_info.get('followers_count', 0)
        following = profile_info.get('following_count', 0)
        posts = profile_info.get('posts_count', 0)
        
        # Nombre minimum de followers
        min_followers = criteria.get('min_followers', 0)
        if followers < min_followers:
            result['suitable'] = False
            result['reasons'].append(f'Too few followers ({followers} < {min_followers})')
            result['score'] -= 30
        
        # Nombre maximum de followers
        max_followers = criteria.get('max_followers', float('inf'))
        if followers > max_followers:
            result['suitable'] = False
            result['reasons'].append(f'Too many followers ({followers} > {max_followers})')
            result['score'] -= 20
        
        # Nombre minimum de posts
        min_posts = criteria.get('min_posts', 3)
        if posts < min_posts:
            result['suitable'] = False
            result['reasons'].append(f'Too few posts ({posts} < {min_posts})')
            result['score'] -= 25
        
        # Ratio followers/following
        max_following_ratio = criteria.get('max_following_ratio', 10.0)
        if following > 0:
            ratio = followers / following
            if ratio > max_following_ratio:
                result['reasons'].append(f'High follower ratio ({ratio:.1f})')
                result['score'] -= 10
        
        # Comptes vérifiés
        if profile_info.get('is_verified', False):
            if not criteria.get('allow_verified', True):
                result['suitable'] = False
                result['reasons'].append('Verified account')
                result['score'] -= 40
        
        # Comptes business
        if profile_info.get('is_business', False):
            if not criteria.get('allow_business', True):
                result['reasons'].append('Business account')
                result['score'] -= 15
        
        # DISABLED: Bot username detection - too many false positives
        # username = profile_info.get('username', '')
        # if self.utils.is_likely_bot_username(username):
        #     result['suitable'] = False
        #     result['reasons'].append('Likely bot username')
        #     result['category'] = 'bot'
        #     result['score'] -= 50
        
        # Déterminer la catégorie finale
        if result['suitable']:
            if result['score'] >= 90:
                result['category'] = 'excellent'
            elif result['score'] >= 70:
                result['category'] = 'good'
            else:
                result['category'] = 'acceptable'
        else:
            if 'Private account' in result['reasons']:
                result['category'] = 'private'
            elif 'bot' in result['category']:
                result['category'] = 'bot'
            else:
                result['category'] = 'filtered'
        
        return result
    
    def extract_profile_metrics(self, profile_info: Dict[str, Any]) -> Dict[str, Any]:
        metrics = {}
        
        followers = profile_info.get('followers_count', 0)
        following = profile_info.get('following_count', 0)
        posts = profile_info.get('posts_count', 0)
        
        # Ratios de base
        metrics['followers_following_ratio'] = followers / following if following > 0 else float('inf')
        metrics['posts_followers_ratio'] = posts / followers if followers > 0 else 0
        metrics['avg_followers_per_post'] = followers / posts if posts > 0 else 0
        
        # Score d'engagement estimé (basé sur les ratios)
        engagement_score = 0
        if followers > 0 and posts > 0:
            # Plus de posts par rapport aux followers = plus actif
            if metrics['posts_followers_ratio'] > 0.01:  # Plus de 1 post pour 100 followers
                engagement_score += 30
            
            # Ratio followers/following équilibré
            if 0.5 <= metrics['followers_following_ratio'] <= 5:
                engagement_score += 40
            
            # Compte avec activité récente (basé sur la présence de stories)
            if profile_info.get('visible_stories_count', 0) > 0:
                engagement_score += 30
        
        metrics['estimated_engagement_score'] = min(engagement_score, 100)
        
        # Catégorie de compte
        if followers < 100:
            metrics['account_category'] = 'micro'
        elif followers < 1000:
            metrics['account_category'] = 'small'
        elif followers < 10000:
            metrics['account_category'] = 'medium'
        elif followers < 100000:
            metrics['account_category'] = 'large'
        else:
            metrics['account_category'] = 'mega'
        
        # Score de qualité global
        quality_score = 50  # Base
        
        # Bonus pour profil complet
        if profile_info.get('full_name'):
            quality_score += 10
        if profile_info.get('biography'):
            quality_score += 15
        if profile_info.get('is_verified'):
            quality_score += 20
        
        # Malus pour signaux négatifs
        if profile_info.get('is_private'):
            quality_score -= 20
        # DISABLED: Bot username detection - too many false positives
        # if self.utils.is_likely_bot_username(profile_info.get('username', '')):
        #     quality_score -= 40
        
        metrics['quality_score'] = max(0, min(100, quality_score))
        
        return metrics
    
    def navigate_and_extract_profile(self, username: str, 
                                   max_retries: int = 3) -> Optional[Dict[str, Any]]:
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Attempt {attempt + 1}/{max_retries} for @{username}")
                
                if not self.nav_actions.navigate_to_profile(username):
                    if attempt < max_retries - 1:
                        self._human_like_delay('navigation')
                        continue
                    else:
                        return None
                
                profile_info = self.get_complete_profile_info(navigate_if_needed=False)
                if profile_info:
                    return profile_info
                
                if attempt < max_retries - 1:
                    self._human_like_delay('navigation')
                
            except Exception as e:
                self.logger.debug(f"Error attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    self._human_like_delay('navigation')
        
        return None
    
    def batch_extract_profiles(self, usernames: List[str], 
                             max_profiles: int = None) -> List[Dict[str, Any]]:
        profiles = []
        processed_count = 0
        
        if max_profiles:
            usernames = usernames[:max_profiles]
        
        self.logger.info(f"Batch extraction of {len(usernames)} profiles")
        
        for i, username in enumerate(usernames):
            try:
                self.logger.debug(f"[{i+1}/{len(usernames)}] Extraction @{username}")
                
                profile_info = self.navigate_and_extract_profile(username)
                if profile_info:
                    profiles.append(profile_info)
                    processed_count += 1
                    
                    # Log de progression
                    if processed_count % 10 == 0:
                        self.logger.info(f"📊 {processed_count} profils extraits")
                
                # Délai entre les profils
                self._human_like_delay('navigation')
                
            except Exception as e:
                self.logger.error(f"Erreur extraction @{username}: {e}")
                continue
        
        self.logger.info(f"✅ Extraction terminée: {len(profiles)} profils extraits")
        return profiles
    
    def _get_default_criteria(self) -> Dict[str, Any]:
        return {
            'min_followers': 10,
            'max_followers': 50000,
            'min_posts': 3,
            'max_following_ratio': 10.0,
            'allow_private': False,
            'allow_verified': True,
            'allow_business': True
        }
    
    def _get_followers_count_robust(self, swipe_up_if_needed: bool = False) -> int:
        self.logger.debug("Attempting to get followers count (robust method)...")
        
        try:
            from ....ui.extractors import parse_number_from_text
            
            # Méthode 1: Essayer avec l'ID de ressource spécifique
            element = self.device.find(resourceId=f"{self.device.app_id}:id/profile_header_familiar_followers_value")
            if element and hasattr(element, 'exists') and element.exists:
                count_text = element.get_text()
                if count_text:
                    # Utiliser parse_number_from_text pour gérer tous les formats (166K, 166 K, 1.2M, etc.)
                    parsed = parse_number_from_text(count_text)
                    if parsed > 0:
                        return parsed
            
            followers = self._get_count_from_element_robust(
                element_type='id',
                resource_id='row_profile_header_textview_followers_count'
            )
            
            if followers is not None:
                self.logger.debug(f"Followers count found via resource ID: {followers}")
                return followers
            
            followers = self._get_count_from_element_robust(
                element_type='text',
                text='followers'
            )
            
            if followers is not None:
                self.logger.debug(f"Followers count found via text: {followers}")
                return followers
            
            followers = self._get_count_from_element_robust(
                element_type='description',
                description='followers'
            )
            
            if followers is not None:
                self.logger.debug(f"Followers count found via description: {followers}")
                return followers
            
            if swipe_up_if_needed:
                self.logger.debug("Followers count not found, attempting to scroll...")
                self.device.swipe_up()
                time.sleep(1)
                return self._get_followers_count_robust(swipe_up_if_needed=False)
            
            self.logger.warning("Unable to find followers count")
            return 0
            
        except Exception as e:
            self.logger.error(f"Error retrieving followers count: {e}")
            return 0
    
    def _get_following_count_robust(self, swipe_up_if_needed: bool = False) -> int:
        self.logger.debug("Attempting to get following count (robust method)...")
        
        try:
            from ....ui.extractors import parse_number_from_text
            
            element = self.device.find(resourceId=f"{self.device.app_id}:id/profile_header_familiar_following_value")
            if element and hasattr(element, 'exists') and element.exists:
                count_text = element.get_text()
                if count_text:
                    parsed = parse_number_from_text(count_text)
                    if parsed > 0:
                        return parsed
            
            following = self._get_count_from_element_robust(
                element_type='id',
                resource_id='row_profile_header_textview_following_count'
            )
            
            if following is not None:
                self.logger.debug(f"Following count found via resource ID: {following}")
                return following
            
            following = self._get_count_from_element_robust(
                element_type='text',
                text='following'
            )
            
            if following is not None:
                self.logger.debug(f"Following count found via text: {following}")
                return following
            
            self.logger.warning("Unable to find following count")
            return 0
            
        except Exception as e:
            self.logger.error(f"Error retrieving following count: {e}")
            return 0
    
    def _get_posts_count_robust(self, swipe_up_if_needed: bool = False) -> int:
        self.logger.debug("Attempting to get posts count (robust method)...")
        
        try:
            from ....ui.extractors import parse_number_from_text
            
            element = self.device.find(resourceId=f"{self.device.app_id}:id/profile_header_familiar_post_count_value")
            if element and hasattr(element, 'exists') and element.exists:
                count_text = element.get_text()
                if count_text:
                    parsed = parse_number_from_text(count_text)
                    if parsed > 0:
                        return parsed
            
            posts = self._get_count_from_element_robust(
                element_type='id',
                resource_id='profile_header_familiar_post_count_value'
            )
            
            if posts is not None:
                self.logger.debug(f"Posts count found via resource ID: {posts}")
                return posts
            
            posts = self._get_count_from_element_robust(
                element_type='id',
                resource_id='row_profile_header_textview_post_count'
            )
            
            if posts is not None:
                self.logger.debug(f"Posts count found via old ID: {posts}")
                return posts
            
            posts = self._get_count_from_element_robust(
                element_type='text',
                text='posts'
            )
            
            if posts is not None:
                self.logger.debug(f"Posts count found via text: {posts}")
                return posts
            
            self.logger.warning("Unable to find posts count")
            return 0
            
        except Exception as e:
            self.logger.error(f"Error retrieving posts count: {e}")
            return 0
    
    def _get_count_from_element_robust(self, element_type: str, resource_id: str = None, text: str = None, description: str = None) -> Optional[int]:
        try:
            from ....ui.extractors import parse_number_from_text
            
            if element_type == 'id' and resource_id:
                element = self.device.xpath(f'//*[@resource-id="{self.device.app_id}:id/{resource_id}"]')
            elif element_type == 'text' and text:
                element = self.device.xpath(f'//*[contains(@text, "{text}")]')
            elif element_type == 'description' and description:
                element = self.device.xpath(f'//*[contains(@content-desc, "{description}")]')
            else:
                return None
                
            if element.exists:
                text = element.get_text()
                if text:
                    return parse_number_from_text(text)
        except Exception as e:
            self.logger.debug(f"Error extracting count: {e}")
            
        return None
