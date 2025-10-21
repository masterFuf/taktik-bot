"""
Logique métier pour la gestion de la configuration Instagram.

Ce module centralise la gestion des configurations, endpoints API,
et paramètres système.
"""

import os
import json
from typing import Dict, List, Any, Optional
from loguru import logger

from ...core.base_action import BaseAction


class ConfigBusiness(BaseAction):
    """Logique métier pour la gestion de la configuration Instagram."""
    
    def __init__(self, device, session_manager=None):
        """
        Initialise la logique métier de configuration.
        
        Args:
            device: Instance de l'appareil uiautomator2 ou DeviceFacade
            session_manager: Gestionnaire de session (optionnel)
        """
        super().__init__(device)
        self.session_manager = session_manager
        self.logger = logger.bind(module="instagram-config-business")
        
        # Configuration par défaut
        self.default_config = {
            'api': {
                'base_url': os.getenv('TAKTIK_API_URL', 'https://api.taktik-bot.com'),
                'timeout': 30,
                'retry_attempts': 3
            },
            'instagram': {
                'app_package': 'com.instagram.android',
                'deep_link_base': 'https://www.instagram.com',
                'default_delays': {
                    'navigation': (1, 3),
                    'scroll': (0.5, 1.5),
                    'interaction': (2, 5),
                    'post_load': (1, 2),
                    'story_load': (0.5, 1)
                }
            },
            'automation': {
                'max_retries': 3,
                'screenshot_on_error': True,
                'human_like_behavior': True,
                'random_delays': True
            }
        }
    
    def get_api_endpoints(self) -> Dict[str, str]:
        """
        Récupère les endpoints API configurés.
        
        Returns:
            Dictionnaire des endpoints API
        """
        try:
            # Import dynamique pour éviter les dépendances circulaires
            from taktik.core.config.api_endpoints import APIEndpointManager
            
            endpoint_manager = APIEndpointManager()
            base_url = endpoint_manager.get_primary_endpoint()
            
            if not base_url:
                base_url = self.default_config['api']['base_url']
                self.logger.warning(f"⚠️ Utilisation de l'endpoint par défaut: {base_url}")
            
            endpoints = {
                'base_url': base_url,
                'profiles': f"{base_url}/profiles",
                'interactions': f"{base_url}/interactions",
                'sessions': f"{base_url}/sessions",
                'usage': f"{base_url}/usage",
                'filtered_profiles': f"{base_url}/filtered-profiles",
                'remaining_actions': f"{base_url}/usage/remaining-actions-by-api-key"
            }
            
            self.logger.debug(f"🔗 Endpoints API configurés: {base_url}")
            return endpoints
            
        except Exception as e:
            self.logger.error(f"Erreur récupération endpoints: {e}")
            # Fallback vers la configuration par défaut
            base_url = self.default_config['api']['base_url']
            return {
                'base_url': base_url,
                'profiles': f"{base_url}/profiles",
                'interactions': f"{base_url}/interactions",
                'sessions': f"{base_url}/sessions",
                'usage': f"{base_url}/usage",
                'filtered_profiles': f"{base_url}/filtered-profiles",
                'remaining_actions': f"{base_url}/usage/remaining-actions-by-api-key"
            }
    
    
    def get_instagram_config(self) -> Dict[str, Any]:
        """
        Récupère la configuration spécifique à Instagram.
        
        Returns:
            Configuration Instagram
        """
        config = self.default_config['instagram'].copy()
        
        # Ajouter les configurations d'environnement
        config.update({
            'device_id': os.getenv('DEVICE_ID'),
            'emulator_name': os.getenv('EMULATOR_NAME'),
            'debug_mode': os.getenv('DEBUG', 'false').lower() == 'true',
            'screenshot_path': os.getenv('SCREENSHOT_PATH', './screenshots'),
            'log_level': os.getenv('LOG_LEVEL', 'INFO')
        })
        
        return config
    
    def get_automation_limits(self) -> Dict[str, int]:
        """
        Récupère les limites d'automatisation configurées.
        
        Returns:
            Limites d'automatisation
        """
        return {
            'max_likes_per_hour': int(os.getenv('MAX_LIKES_PER_HOUR', '60')),
            'max_follows_per_hour': int(os.getenv('MAX_FOLLOWS_PER_HOUR', '30')),
            'max_comments_per_hour': int(os.getenv('MAX_COMMENTS_PER_HOUR', '10')),
            'max_stories_per_hour': int(os.getenv('MAX_STORIES_PER_HOUR', '100')),
            'max_profiles_per_session': int(os.getenv('MAX_PROFILES_PER_SESSION', '50')),
            'min_delay_between_actions': int(os.getenv('MIN_DELAY_BETWEEN_ACTIONS', '5')),
            'max_delay_between_actions': int(os.getenv('MAX_DELAY_BETWEEN_ACTIONS', '15'))
        }
    
    def get_filtering_criteria(self) -> Dict[str, Any]:
        """
        Récupère les critères de filtrage par défaut.
        
        Returns:
            Critères de filtrage
        """
        return {
            'min_followers': int(os.getenv('MIN_FOLLOWERS', '10')),
            'max_followers': int(os.getenv('MAX_FOLLOWERS', '50000')),
            'min_posts': int(os.getenv('MIN_POSTS', '3')),
            'max_following_ratio': float(os.getenv('MAX_FOLLOWING_RATIO', '10.0')),
            'allow_private': os.getenv('ALLOW_PRIVATE', 'false').lower() == 'true',
            'allow_verified': os.getenv('ALLOW_VERIFIED', 'true').lower() == 'true',
            'allow_business': os.getenv('ALLOW_BUSINESS', 'true').lower() == 'true',
            'exclude_bots': os.getenv('EXCLUDE_BOTS', 'true').lower() == 'true'
        }
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Valide la configuration complète du système.
        
        Returns:
            Résultat de la validation
        """
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'components': {}
        }
        
        try:
            # Valider les endpoints API
            endpoints = self.get_api_endpoints()
            if endpoints['base_url']:
                validation_result['components']['api'] = 'OK'
            else:
                validation_result['errors'].append("Endpoints API non configurés")
                validation_result['valid'] = False
            
            # Architecture 100% API - pas de validation DB directe
            # La connexion DB est gérée côté serveur via l'API
            validation_result['components']['database'] = 'API'
            
            # Valider la configuration Instagram
            ig_config = self.get_instagram_config()
            if ig_config.get('device_id'):
                validation_result['components']['device'] = 'OK'
            else:
                validation_result['warnings'].append("Device ID non configuré")
            
            # Valider les limites
            limits = self.get_automation_limits()
            if all(v > 0 for v in limits.values()):
                validation_result['components']['limits'] = 'OK'
            else:
                validation_result['warnings'].append("Certaines limites sont à 0")
            
            self.logger.info(f"✅ Validation configuration: {len(validation_result['errors'])} erreurs, {len(validation_result['warnings'])} avertissements")
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Erreur validation: {e}")
            self.logger.error(f"Erreur validation configuration: {e}")
        
        return validation_result
    
    def get_complete_config(self) -> Dict[str, Any]:
        """
        Récupère la configuration complète du système.
        
        Returns:
            Configuration complète
        """
        try:
            return {
                'api': {
                    'endpoints': self.get_api_endpoints(),
                    'timeout': self.default_config['api']['timeout'],
                    'retry_attempts': self.default_config['api']['retry_attempts']
                },
                # Architecture 100% API - pas de config DB côté client
                'instagram': self.get_instagram_config(),
                'automation': {
                    **self.default_config['automation'],
                    'limits': self.get_automation_limits()
                },
                'filtering': self.get_filtering_criteria(),
                'validation': self.validate_configuration()
            }
            
        except Exception as e:
            self.logger.error(f"Erreur récupération configuration complète: {e}")
            return self.default_config
    
    def update_config_value(self, key_path: str, value: Any) -> bool:
        """
        Met à jour une valeur de configuration.
        
        Args:
            key_path: Chemin de la clé (ex: 'api.timeout')
            value: Nouvelle valeur
            
        Returns:
            True si la mise à jour a réussi
        """
        try:
            # Pour cette version, on met à jour les variables d'environnement
            env_mapping = {
                'api.base_url': 'TAKTIK_API_URL',
                'instagram.device_id': 'DEVICE_ID',
                'automation.limits.max_likes_per_hour': 'MAX_LIKES_PER_HOUR',
                'filtering.min_followers': 'MIN_FOLLOWERS',
                'filtering.max_followers': 'MAX_FOLLOWERS'
            }
            
            env_var = env_mapping.get(key_path)
            if env_var:
                os.environ[env_var] = str(value)
                self.logger.info(f"🔧 Configuration mise à jour: {key_path} = {value}")
                return True
            else:
                self.logger.warning(f"⚠️ Clé de configuration non mappée: {key_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur mise à jour configuration: {e}")
            return False
