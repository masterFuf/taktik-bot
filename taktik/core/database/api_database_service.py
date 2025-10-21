#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Database service using exclusively REST API."""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from .api_client import TaktikAPIClient
from .models import InstagramProfile, DatabaseSession, DatabaseQuery

logger = logging.getLogger(__name__)

class APIBasedDatabaseSession(DatabaseSession):
    
    def __init__(self, api_service):
        self.api_service = api_service
        self.logger = logger
        self.pending_instances = []
        
    def query(self, model_class):
        return APIBasedDatabaseQuery(self, model_class)
        
    def add(self, instance):
        if isinstance(instance, InstagramProfile):
            try:
                profile_data = self.api_service.save_profile_via_api(instance)
                if profile_data and 'profile_id' in profile_data:
                    instance.id = profile_data['profile_id']
                    self.logger.info(f"Profil {instance.username} ajouté via API avec ID: {profile_data['profile_id']}")
                else:
                    self.logger.warning(f"Profil {instance.username} ajouté via API mais impossible de récupérer l'ID")
            except Exception as e:
                self.logger.error(f"Erreur lors de l'ajout du profil {instance.username} via API: {e}")
        else:
            self.pending_instances.append(instance)
            self.logger.info(f"Instance ajoutée à la liste en attente: {instance}")
        return self
        
    def commit(self):
        try:
            self.logger.info("Exécution de commit() pour sauvegarder via API")
            
            for instance in self.pending_instances:
                if isinstance(instance, InstagramProfile):
                    try:
                        profile_data = self.api_service.save_profile_via_api(instance)
                        if profile_data and 'profile_id' in profile_data:
                            instance.id = profile_data['profile_id']
                            self.logger.info(f"Profil {instance.username} mis à jour via API avec ID: {profile_data['profile_id']}")
                    except Exception as e:
                        self.logger.error(f"Erreur lors de la mise à jour du profil {instance.username} via API: {e}")
            
            self.pending_instances.clear()
        except Exception as e:
            self.logger.error(f"Erreur lors du commit via API: {e}")

class APIBasedDatabaseQuery(DatabaseQuery):
    
    def __init__(self, session, model_class):
        self.session = session
        self.model_class = model_class
        self.filters = []
        
    def filter(self, *args):
        self.filters.extend(args)
        return self
        
    def first(self):
        username = None
        for f in self.filters:
            if isinstance(f, tuple) and f[0] == 'username':
                username = f[1]
                break
        
        self.session.logger.info(f"Requête API: first() avec filtres {self.filters}")
        
        if username and self.model_class == InstagramProfile:
            try:
                profile_data = self.session.api_service.get_profile_via_api(username)
                if profile_data:
                    profile = self.model_class(
                        id=profile_data.get('profile_id'),
                        username=profile_data.get('username'),
                        full_name=profile_data.get('full_name', ''),
                        followers_count=profile_data.get('followers_count', 0),
                        following_count=profile_data.get('following_count', 0),
                        posts_count=profile_data.get('posts_count', 0),
                        is_private=profile_data.get('is_private', False)
                    )
                    return profile
                else:
                    # Si le profil n'existe pas dans l'API, créer un profil par défaut
                    profile = self.model_class(
                        username=username,
                        full_name=f"User {username}",
                        followers_count=0,
                        following_count=0,
                        posts_count=0,
                        is_private=False,
                        id=1
                    )
                    return profile
            except Exception as e:
                self.session.logger.error(f"Erreur lors de la récupération du profil {username} via API: {e}")
                # En cas d'erreur, créer un profil par défaut
                profile = self.model_class(
                    username=username,
                    full_name=f"User {username}",
                    followers_count=0,
                    following_count=0,
                    posts_count=0,
                    is_private=False,
                    id=1
                )
                return profile
        return None

class APIBasedDatabaseService:
    
    def __init__(self, api_client: Optional[TaktikAPIClient] = None):
        self.api_client = api_client or TaktikAPIClient()
        self.logger = logger
        self.session = APIBasedDatabaseSession(self)
        
        # Vérifier que l'API est accessible
        try:
            if self.api_client.health_check():
                self.logger.info("Connexion à l'API établie avec succès")
            else:
                self.logger.warning("L'API n'est pas accessible, certaines fonctionnalités peuvent ne pas fonctionner")
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification de l'API: {e}")
    
    def get_profile_via_api(self, username: str) -> Optional[Dict[str, Any]]:
        try:
            return self.api_client.get_profile(username)
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du profil {username} via API: {e}")
            return None
    
    def save_profile_via_api(self, profile: InstagramProfile) -> Optional[Dict[str, Any]]:
        try:
            # Nettoyer les données pour éviter les valeurs None
            full_name = getattr(profile, 'full_name', None)
            if full_name is None:
                full_name = ''
            
            biography = getattr(profile, 'biography', None)
            if biography is None:
                biography = ''
                
            notes = getattr(profile, 'notes', None)
            if notes is None:
                notes = ''
            
            profile_data = {
                'username': profile.username,
                'full_name': full_name,
                'followers_count': getattr(profile, 'followers_count', 0),
                'following_count': getattr(profile, 'following_count', 0),
                'posts_count': getattr(profile, 'posts_count', 0),
                'is_private': getattr(profile, 'is_private', False),
                'biography': biography,
                'notes': notes,
                'profile_pic_path': getattr(profile, 'profile_pic_path', None)
            }
            
            # Detailed log of data sent to API
            self.logger.info(f"💾 API save for @{profile.username}:")
            self.logger.debug(f"  • Name: {profile_data.get('full_name', 'N/A')}")
            self.logger.debug(f"  • Bio: {profile_data.get('biography', 'N/A')}")
            self.logger.debug(f"  • Stats: {profile_data.get('posts_count', 0)} posts, "
                            f"{profile_data.get('followers_count', 0)} followers, "
                            f"{profile_data.get('following_count', 0)} following")
            self.logger.debug(f"  • Private: {profile_data.get('is_private', False)}")
            self.logger.debug(f"  • Profile pic: {profile_data.get('profile_pic_path', 'N/A')}")
            
            return self.api_client.create_profile(profile_data)
        except Exception as e:
            self.logger.error(f"Error saving profile {profile.username} via API: {e}")
            return None
    
    def get_or_create_account_via_api(self, username: str, is_bot: bool = True) -> Tuple[int, bool]:
        try:
            account_data = self.api_client.get_or_create_account(username, is_bot)
            if account_data:
                return account_data.get('account_id', 1), account_data.get('created', False)
            return 1, False
        except Exception as e:
            self.logger.error(f"Error getting/creating account {username} via API: {e}")
            return 1, False
    
    def save_profile(self, profile: InstagramProfile, account_id: Optional[int] = None) -> bool:
        try:
            result = self.save_profile_via_api(profile)
            if result and account_id:
                # Record interaction if necessary
                self.logger.info(f"Profile {profile.username} saved via API for account {account_id}")
            return result is not None
        except Exception as e:
            self.logger.error(f"Error saving profile {profile.username}: {e}")
            return False
    
    def get_profile(self, username: str) -> Optional[InstagramProfile]:
        try:
            profile_data = self.get_profile_via_api(username)
            if profile_data:
                return InstagramProfile(
                    id=profile_data.get('profile_id'),
                    username=profile_data.get('username'),
                    full_name=profile_data.get('full_name', ''),
                    followers_count=profile_data.get('followers_count', 0),
                    following_count=profile_data.get('following_count', 0),
                    posts_count=profile_data.get('posts_count', 0),
                    is_private=profile_data.get('is_private', False),
                    notes=profile_data.get('notes', '')
                )
            return None
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du profil {username}: {e}")
            return None
    
    def profile_exists(self, username: str) -> bool:
        try:
            profile_data = self.get_profile_via_api(username)
            return profile_data is not None
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification de l'existence du profil {username}: {e}")
            return False
    
    def get_or_create_account(self, username: str, is_bot: bool = True) -> Tuple[int, bool]:
        return self.get_or_create_account_via_api(username, is_bot)
    
    def save_profile_and_get_id(self, profile: InstagramProfile) -> Optional[int]:
        try:
            result = self.save_profile_via_api(profile)
            if result and 'profile_id' in result:
                profile.id = result['profile_id']
                self.logger.info(f"Profil {profile.username} sauvegardé avec ID: {result['profile_id']}")
                return result['profile_id']
            else:
                self.logger.warning(f"Profil {profile.username} sauvegardé mais ID non récupéré")
                return 1  # ID par défaut
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde du profil {profile.username}: {e}")
            return 1  # ID par défaut en cas d'erreur
    
    def log_interaction(self, account_id: int, profile_id: int, interaction_type: str, 
                       success: bool = True, content: Optional[str] = None) -> bool:
        # Utiliser record_interaction avec un username générique car l'API attend target_username
        target_username = f"user_{profile_id}"
        return self.api_client.record_interaction(account_id, target_username, interaction_type, success, content)
    
    def record_interaction(self, account_id: int, username: str, interaction_type: str, success: bool = True, content: str = None, session_id: int = None) -> bool:
        try:
            # S'assurer que le profil existe avant d'enregistrer l'interaction
            profile = self.api_client.get_profile(username)
            if not profile:
                self.logger.warning(f"Profil {username} non trouvé, création automatique...")
                # Créer un profil minimal pour éviter l'erreur de contrainte FK
                profile_data = {
                    'username': username,
                    'full_name': '',
                    'followers_count': 0,
                    'following_count': 0,
                    'posts_count': 0,
                    'is_private': False,
                    'biography': '',
                    'notes': f'Profil créé automatiquement pour interaction {interaction_type}'
                }
                self.api_client.create_profile(profile_data)
            
            result = self.api_client.record_interaction(account_id, username, interaction_type, success, content, session_id)
            if result is None:
                # Timeout ou erreur réseau - ne pas considérer comme un échec critique
                self.logger.warning(f"Timeout API lors de l'enregistrement de l'interaction pour {username} - continuons")
                return True  # Considérer comme succès pour ne pas bloquer l'automation
            elif result:
                # Succès de l'enregistrement
                return True
            else:
                self.logger.error(f"Échec de l'enregistrement de l'interaction pour {username}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enregistrement de l'interaction: {e}")
            return False
    
    def mark_profile_as_processed(self, account_id: int, username: str, interaction_type: str = "PROFILE_VISIT", notes: str = None, session_id: int = None) -> bool:
        content = notes if notes else f"Profil {username} marqué comme traité"
        return self.record_interaction(account_id, username, interaction_type, success=True, content=content, session_id=session_id)
    
    def is_profile_processed(self, account_id: int, username: str, hours_limit: int = 24) -> bool:
        try:
            result = self.api_client.check_profile_processed(account_id, username, hours_limit)
            self.logger.info(f"🔍 API response for @{username} (account_id: {account_id}): {result}")
            if result is not None:
                processed = result.get('processed', False)
                if not processed:
                    reason = result.get('reason', 'Unknown')
                    self.logger.info(f"❌ @{username} not processed: {reason}")
                else:
                    self.logger.info(f"✅ @{username} already processed!")
                return processed
            return False
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification du profil {username}: {e}")
            return False
    
    def mark_as_filtered(self, account_id: int, username: str, reason: str, source_type: str = "GENERAL", source_name: str = "unknown", session_id: int = None) -> bool:
        try:
            return self.api_client.record_filtered_profile(account_id, username, reason, source_type, source_name, session_id)
        except Exception as e:
            self.logger.error(f"Erreur lors du marquage du profil filtré {username}: {e}")
            return False
    
    def get_interactions_by_type(self, interaction_type: str, limit: int = 1000) -> List[Dict[str, Any]]:
        try:
            # Cette méthode nécessiterait un nouvel endpoint API
            # Pour l'instant, retourner une liste vide
            self.logger.warning(f"get_interactions_by_type({interaction_type}) non implémenté dans l'API")
            return []
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des interactions de type {interaction_type}: {e}")
            return []
    
    def cleanup_old_interactions(self, interaction_type: str, before_timestamp: float) -> int:
        try:
            # Cette méthode nécessiterait un nouvel endpoint API
            # Pour l'instant, retourner 0
            self.logger.warning(f"cleanup_old_interactions({interaction_type}) non implémenté dans l'API")
            return 0
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage des interactions de type {interaction_type}: {e}")
            return 0
    
    def mark_as_processed(self, account_id: int, username: str, notes: str = None, session_id: int = None) -> bool:
        try:
            # Utiliser record_interaction pour marquer comme traité
            content = notes if notes else f"Profil {username} marqué comme traité"
            result = self.record_interaction(account_id, username, "PROFILE_VISIT", True, content, session_id)
            if result:
                self.logger.debug(f"Profil {username} marqué comme traité pour le compte {account_id}")
                return True
            else:
                self.logger.warning(f"Échec du marquage du profil {username} comme traité")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors du marquage du profil {username} comme traité: {e}")
            return False
    
    def is_profile_processed(self, account_id: int, username: str, hours_limit: int = 24) -> bool:
        try:
            result = self.api_client.check_profile_processed(account_id, username, hours_limit)
            if result:
                return result.get('processed', False)
            return False
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification du profil traité {username}: {e}")
            return False
    
    def record_filtered_profile(self, account_id: int, username: str, reason: str, source_type: str = "GENERAL", source_name: str = "unknown", session_id: int = None) -> bool:
        """Enregistre un profil filtré via l'API REST"""
        return self.mark_as_filtered(account_id, username, reason, source_type, source_name, session_id)
