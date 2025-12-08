"""API client for communicating with Taktik Instagram API."""

import os
import requests
import json
from typing import Optional, Dict, Any, Tuple, List
from loguru import logger

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .models import InstagramProfile
else:
    InstagramProfile = None

class TaktikAPIClient:
    
    def __init__(self, api_url: str = None, api_key: str = None, config_mode: bool = False):
        if api_url:
            self.api_url = api_url.rstrip('/')
        else:
            from ..config.api_endpoints import get_api_url
            self.api_url = get_api_url()
        self.config_mode = config_mode
        
        if config_mode:
            self.api_key = None
            logger.info("Configuration mode enabled - API key not required")
        else:
            if not api_key:
                logger.error("API key required. Pass the API key retrieved from server as parameter.")
                raise ValueError("API key required. Use API key retrieved from server.")
            
            self.api_key = api_key
            logger.info("Using API key passed as parameter")
        
        self.headers = {
            'Content-Type': 'application/json'
        }
        if self.api_key:
            self.headers['Authorization'] = f'Bearer {self.api_key}'
            
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _get_license_api_key(self) -> Optional[str]:
        try:
            from ..license.integrated_license_manager import integrated_license_manager
            config = integrated_license_manager.load_config()
            if config and config.get('api_key'):
                return config['api_key']
        except Exception as e:
            logger.debug(f"Cannot retrieve license API key: {e}")
        return None
    
    def _make_request(self, method: str, endpoint: str, data: dict = None, timeout: int = 30, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        if not self.api_key and not self.config_mode:
            raise ValueError("API key missing for request")
            
        url = f"{self.api_url}{endpoint}"
        request_headers = {
            'Content-Type': 'application/json'
        }
        if self.api_key:
            request_headers['Authorization'] = f'Bearer {self.api_key}'
        
        if headers:
            request_headers.update(headers)
        
        # Timeout plus court pour les interactions (éviter les blocages)
        timeout = 10 if '/interactions' in endpoint else 30
        
        try:
            # Activer la vérification SSL maintenant que le certificat est valide
            import os
            verify_ssl = os.getenv('TAKTIK_DISABLE_SSL_VERIFY', '0').lower() not in ('1', 'true', 'yes')
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=request_headers, params=params, timeout=timeout, verify=verify_ssl)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=request_headers, json=data, timeout=timeout, verify=verify_ssl)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=request_headers, json=data, timeout=timeout, verify=verify_ssl)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=request_headers, timeout=timeout, verify=verify_ssl)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout ({timeout}s) sur {method} {url} - API probablement surchargée")
            return None
        except requests.exceptions.RequestException as e:
            # 404 sur GET est normal (ressource n'existe pas encore)
            if hasattr(e, 'response') and e.response.status_code == 404 and method == 'GET':
                logger.debug(f"Resource not found (404) for {method} {url} - normal if first time")
            else:
                logger.error(f"HTTP error during request {method} {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error during API request: {e}")
            return None
    
    def health_check(self) -> bool:
        try:
            result = self._make_request('GET', '/health')
            return result.get('status') == 'healthy'
        except:
            return False
    
    def verify_license(self, license_key: str) -> Dict[str, Any]:
        data = {'license_key': license_key}
        result = self._make_request('POST', '/auth/verify-license', data)
        return result
    
    def save_profile(self, profile: 'InstagramProfile') -> Optional[int]:
        try:
            data = {
                'username': profile.username,
                'followers_count': profile.followers_count,
                'following_count': profile.following_count,
                'posts_count': profile.posts_count,
                'is_private': profile.is_private,
                'full_name': profile.full_name,
                'biography': getattr(profile, 'biography', ''),
                'notes': profile.notes
            }
            
            result = self._make_request('POST', '/profiles', data)
            return result.get('profile_id')
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du profil {profile.username}: {e}")
            return None
    
    def get_profile(self, username: str) -> Optional['InstagramProfile']:
        try:
            result = self._make_request('GET', f'/profiles/{username}')
            
            if result:
                # Import dynamique pour éviter les références circulaires
                from .models import InstagramProfile
                return InstagramProfile(
                    id=result.get('profile_id'),
                    username=result.get('username'),
                    full_name=result.get('full_name', ''),
                    followers_count=result.get('followers_count', 0),
                    following_count=result.get('following_count', 0),
                    posts_count=result.get('posts_count', 0),
                    is_private=result.get('is_private', False),
                    biography=result.get('biography', ''),
                    notes=result.get('notes')
                )
            return None
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Error retrieving profile {username}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving profile {username}: {e}")
            return None
    
    def create_account(self, username: str, is_bot: bool = True) -> Tuple[int, bool]:
        try:
            data = {'username': username, 'is_bot': is_bot}
            result = self._make_request('POST', '/accounts', data)
            return result.get('account_id'), result.get('created', False)
            
        except Exception as e:
            logger.error(f"Error creating account {username}: {e}")
            return 1, False
    
    def log_interaction(self, account_id: int, profile_id: int, interaction_type: str, 
                       success: bool = True, content: Optional[str] = None) -> bool:
        try:
            # Cette méthode est dépréciée car elle utilise profile_id au lieu de target_username
            # Pour maintenir la compatibilité, on va essayer de récupérer le username
            logger.warning("log_interaction() est déprécié - utilisez record_interaction() avec target_username")
            
            # Fallback: utiliser un username générique basé sur le profile_id
            target_username = f"user_{profile_id}"
            return self.record_interaction(account_id, target_username, interaction_type, success, content)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'interaction: {e}")
            return False
    
    def get_account_stats(self, account_id: int) -> Dict[str, Any]:
        try:
            return self._make_request('GET', f'/stats/{account_id}')
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des stats pour le compte {account_id}: {e}")
            return {}
    
    def get_account_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        try:
            return self._make_request('GET', f'/accounts/{username}')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Erreur lors de la récupération du compte {username}: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du compte {username}: {e}")
            return None
    
    def get_interactions(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            result = self._make_request('GET', f'/interactions/{account_id}?limit={limit}')
            return result.get('interactions', [])
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des interactions pour le compte {account_id}: {e}")
            return []
    
    def create_profile(self, profile_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            result = self._make_request('POST', '/profiles', profile_data)
            return result
        except Exception as e:
            logger.error(f"Erreur lors de la création du profil {profile_data.get('username', 'inconnu')}: {e}")
            return None
    
    def get_or_create_account(self, username: str, is_bot: bool = True) -> Optional[Dict[str, Any]]:
        try:
            # D'abord essayer de récupérer le compte existant
            account = self.get_account_by_username(username)
            if account:
                return {'account_id': account.get('account_id'), 'created': False}
            
            data = {'username': username, 'is_bot': is_bot}
            result = self._make_request('POST', '/accounts', data)
            return {'account_id': result.get('account_id'), 'created': True}
        except Exception as e:
            logger.error(f"Error creating account {username}: {e}")
            return None
    
    def record_interaction(self, account_id: int, target_username: str, interaction_type: str, success: bool = True, content: str = None, session_id: int = None) -> bool:
        try:
            interaction_type_mapping = {
                'LIKE': 'LIKE',
                'FOLLOW': 'FOLLOW',
                'UNFOLLOW': 'UNFOLLOW',
                'COMMENT': 'COMMENT',
                'STORY_WATCH': 'STORY_WATCH',
                'STORY_LIKE': 'STORY_LIKE',
                'PROFILE_VISIT': 'PROFILE_VISIT'
            }
            
            mapped_interaction_type = interaction_type_mapping.get(interaction_type.upper() if interaction_type else '', 'LIKE')
            
            if interaction_type and interaction_type.upper() not in interaction_type_mapping:
                logger.debug(f"Interaction type mapped: '{interaction_type}' -> '{mapped_interaction_type}' (default)")
            
            data = {
                'account_id': account_id,
                'target_username': target_username,
                'interaction_type': mapped_interaction_type,
                'success': success,
                'content': content,
                'session_id': session_id
            }
            result = self._make_request('POST', '/interactions', data)
            
            # ⚠️ NE PAS appeler record_api_action ici car c'est déjà fait par SessionManager.record_action()
            # Sinon chaque action est comptée 2 fois dans license_usage !
            # Les actions sont enregistrées via session_manager.record_action() → record_action_usage()
            # 
            # AVANT (BUG - comptait 2x):
            # - session_manager.record_action('like_posts') → record_action_usage('LIKE') → +1
            # - record_interaction(..., 'LIKE') → record_api_action('LIKE') → +1
            # TOTAL: 2 actions pour 1 like !
            #
            # MAINTENANT (CORRIGÉ):
            # - session_manager.record_action('like_posts') → record_action_usage('LIKE') → +1
            # - record_interaction(..., 'LIKE') → enregistre juste dans la table interactions
            # TOTAL: 1 action pour 1 like ✅
            
            return result.get('success', False) if result else False
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'interaction: {e}")
            return False
    
    def record_api_action(self, action_type: str = 'UNKNOWN') -> bool:
        try:
            data = {'action_type': action_type}
            result = self._make_request('POST', '/usage/record-action', data)
            return result.get('success', False) if result else False
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement d'action: {e}")
            return False
    
    def check_action_limits(self) -> Dict[str, Any]:
        try:
            if self.api_key:
                result = self._make_request('GET', '/usage/remaining-actions-by-api-key')
                if result:
                    max_actions = result.get('max_actions_per_day', 0)
                    remaining = result.get('remaining_actions', max_actions)
                    logger.debug(f"Limites API récupérées: {remaining}/{max_actions}")
                    
                    return {
                        'can_perform_action': remaining > 0,
                        'remaining_actions': remaining,
                        'actions_used_today': max_actions - remaining,
                        'max_actions_per_day': max_actions
                    }
            
            from taktik.core.license.api_license_manager import APILicenseManager
            api_license_manager = APILicenseManager()
            config = api_license_manager.load_config()
            license_key = config.get('license_key') if config else None
            
            if not license_key:
                logger.warning("Clé de licence non trouvée pour la vérification des limites")
                return {'can_perform_action': False, 'remaining_actions': 0, 'max_actions_per_day': 0}
            
            data = {'license_key': license_key}
            result = self._make_request('POST', '/auth/verify-license', data)
            
            if result and result.get('valid'):
                limits = result.get('limits', {})
                max_actions = limits.get('max_actions_per_day', 0)
                remaining = limits.get('actions_remaining', max_actions)
                logger.debug(f"Limites API récupérées: {remaining}/{max_actions}")
                
                return {
                    'can_perform_action': remaining > 0,
                    'remaining_actions': remaining,
                    'actions_used_today': max_actions - remaining,
                    'max_actions_per_day': max_actions
                }
            
            logger.warning("Aucune réponse de l'API pour les limites")
            return {'can_perform_action': False, 'remaining_actions': 0, 'max_actions_per_day': 0}
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des limites: {e}")
            return {'can_perform_action': False, 'remaining_actions': 0, 'max_actions_per_day': 0}
    
    def check_recent_interaction(self, target_username: str, days: int = 7) -> bool:
        try:
            params = {'days': days}
            result = self._make_request('GET', f'/interactions/recent/{target_username}', params)
            return result.get('has_recent_interaction', False)
        except Exception as e:
            logger.error(f"Erreur lors de la vérification d'interaction récente pour {target_username}: {e}")
            return False
    
    def record_filtered_profile(self, account_id: int, username: str, reason: str, source_type: str, source_name: str, session_id: int = None) -> bool:
        try:
            logger.debug(f"[FILTERED_PROFILE] Début enregistrement profil filtré: {username}")
            
            profile = self.get_profile(username)
            if not profile:
                logger.debug(f"[FILTERED_PROFILE] Profil {username} non trouvé, création en cours...")
                profile_data = {
                    'username': username,
                    'followers_count': 0,
                    'following_count': 0,
                    'posts_count': 0,
                    'is_private': False,
                    'full_name': '',
                    'biography': '',
                    'notes': f'Profil créé automatiquement pour filtrage'
                }
                profile_result = self.create_profile(profile_data)
                if not profile_result:
                    logger.error(f"Impossible de créer le profil {username} pour filtrage")
                    return False
                profile_id = profile_result.get('profile_id')
                logger.debug(f"[FILTERED_PROFILE] Profil {username} créé avec ID: {profile_id}")
            else:
                profile_id = profile.id
                logger.debug(f"[FILTERED_PROFILE] Profil {username} existant avec ID: {profile_id}")
                
            if not profile_id:
                logger.error(f"[FILTERED_PROFILE] Impossible d'obtenir profile_id pour {username}")
                return False
                
            data = {
                'account_id': account_id,
                'profile_id': profile_id,
                'username': username,
                'reason': reason,
                'source_type': source_type,
                'source_name': source_name,
                'session_id': session_id
            }
            logger.debug(f"[FILTERED_PROFILE] Données à envoyer: {data}")
            result = self._make_request('POST', '/filtered-profiles', data)
            
            if result and result.get('success', False):
                logger.debug(f"[FILTERED_PROFILE] Succès enregistrement profil filtré: {username}")
                return True
            else:
                logger.error(f"[FILTERED_PROFILE] Échec enregistrement profil filtré: {username}, résultat: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du profil filtré {username}: {e}")
            return False
    
    def is_profile_filtered(self, username: str, account_id: int) -> bool:
        """Vérifie si un profil a été filtré pour un compte donné."""
        try:
            result = self._make_request('GET', f'/filtered-profiles/{username}/{account_id}')
            if result:
                return result.get('filtered', False)
            return False
        except Exception as e:
            logger.debug(f"Erreur lors de la vérification du profil filtré {username}: {e}")
            return False
    
    def check_filtered_profiles_batch(self, usernames: list, account_id: int) -> list:
        """
        Vérifie si plusieurs profils sont filtrés en une seule requête.
        Retourne la liste des usernames qui sont filtrés.
        """
        try:
            if not usernames:
                return []
            
            data = {
                'usernames': usernames,
                'account_id': account_id
            }
            result = self._make_request('POST', '/filtered-profiles/check-batch', data)
            
            if result:
                return result.get('filtered_usernames', [])
            return []
        except Exception as e:
            logger.debug(f"Erreur lors de la vérification batch des profils filtrés: {e}")
            return []
    
    def create_session(self, account_id: int, session_name: str, target_type: str, target: str, config_used: Dict[str, Any] = None) -> Optional[int]:
        try:
            truncated_target = target[:50] if target else 'unknown'
            
            truncated_session_name = session_name[:100] if session_name else 'unknown_session'
            
            if target and len(target) > 50:
                logger.debug(f"Session target truncated: '{target}' -> '{truncated_target}'")
            if session_name and len(session_name) > 100:
                logger.debug(f"Session name truncated: '{session_name}' -> '{truncated_session_name}'")
            
            data = {
                'account_id': account_id,
                'session_name': truncated_session_name,
                'target_type': target_type,
                'target': truncated_target,
                'config_used': config_used
            }
            result = self._make_request('POST', '/sessions', data)
            return result.get('session_id') if result.get('success') else None
        except Exception as e:
            logger.error(f"Erreur lors de la création de la session: {e}")
            return None
    
    def update_session(self, session_id: int, update_data: Dict[str, Any]) -> bool:
        try:
            result = self._make_request('PUT', f'/sessions/{session_id}', update_data)
            return result.get('success', False)
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la session {session_id}: {e}")
            return False
    
    def get_session_stats(self, session_id: int) -> Optional[Dict[str, int]]:
        try:
            result = self._make_request('GET', f'/sessions/{session_id}/stats')
            if result:
                return {
                    'total_interactions': result.get('total_interactions', 0),
                    'total_likes': result.get('total_likes', 0),
                    'total_follows': result.get('total_follows', 0),
                    'total_comments': result.get('total_comments', 0),
                    'total_story_views': result.get('total_story_views', 0),
                    'total_story_likes': result.get('total_story_likes', 0),
                    'successful_interactions': result.get('successful_interactions', 0)
                }
            return None
        except Exception as e:
            logger.error(f"Error retrieving session stats {session_id}: {e}")
            return None
    
    def record_action_usage(self, action_type: str) -> bool:
        try:
            data = {'action_type': action_type}
            result = self._make_request('POST', '/usage/record-action', data)
            return result.get('success', False) if result else False
        except Exception as e:
            logger.error(f"Error recording action {action_type}: {e}")
            return False
    
    def check_profile_processed(self, account_id: int, username: str, hours_limit: int = 24) -> Optional[Dict[str, Any]]:
        try:
            params = {'hours_limit': hours_limit}
            result = self._make_request('GET', f'/profiles/{username}/processed/{account_id}', params)
            return result
        except Exception as e:
            logger.error(f"Error checking profile {username}: {e}")
            return None
