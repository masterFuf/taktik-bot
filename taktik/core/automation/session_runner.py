"""
Session Runner
==============

Exécute des sessions d'automatisation Instagram/TikTok de manière programmatique.
Reproduit le flow de la CLI sans interaction utilisateur.
"""

import uuid
from typing import Optional, Dict, Any
from loguru import logger
from datetime import datetime

from .config_loader import ConfigLoader, SessionConfig
from .result_handler import SessionResult, SessionStats, SessionStatus
from .device_registry import DeviceRegistry


class SessionRunner:
    """
    Exécute une session d'automatisation de manière programmatique.
    
    Usage:
        # Depuis un fichier JSON
        runner = SessionRunner.from_config("config.json")
        result = runner.execute()
        
        # Depuis un dictionnaire
        config = {...}
        runner = SessionRunner.from_dict(config)
        result = runner.execute()
    """
    
    def __init__(self, config: SessionConfig, session_id: Optional[str] = None):
        """
        Initialise le runner.
        
        Args:
            config: Configuration de session validée
            session_id: ID de session (généré automatiquement si non fourni)
        """
        self.config = config
        self.session_id = session_id or str(uuid.uuid4())
        self.device_registry = DeviceRegistry()
        
        # Résultat
        self.result = SessionResult(
            session_id=self.session_id,
            client_id=config.client_id,
            platform=config.platform,
            username=config.account.username,
            device_id=config.device_id,
            workflow_type=config.workflow.type,
            target_type=config.workflow.target_type,
            target_value=self._get_target_value()
        )
        
        logger.info(f"🚀 Session initialized: {self.session_id}")
    
    def _get_target_value(self) -> Optional[str]:
        """Récupère la valeur de la cible (hashtag, post_url, etc.)"""
        if self.config.workflow.hashtag:
            return self.config.workflow.hashtag
        elif self.config.workflow.post_url:
            return self.config.workflow.post_url
        elif self.config.workflow.target_type:
            return self.config.workflow.target_type
        return None
    
    @classmethod
    def from_config(cls, config_path: str, session_id: Optional[str] = None) -> 'SessionRunner':
        """
        Crée un runner depuis un fichier de configuration JSON.
        
        Args:
            config_path: Chemin vers le fichier JSON
            session_id: ID de session (optionnel)
            
        Returns:
            SessionRunner initialisé
        """
        config = ConfigLoader.from_json(config_path)
        return cls(config, session_id)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any], session_id: Optional[str] = None) -> 'SessionRunner':
        """
        Crée un runner depuis un dictionnaire.
        
        Args:
            config_dict: Dictionnaire de configuration
            session_id: ID de session (optionnel)
            
        Returns:
            SessionRunner initialisé
        """
        config = ConfigLoader.from_dict(config_dict)
        return cls(config, session_id)
    
    def execute(self) -> SessionResult:
        """
        Exécute la session d'automatisation.
        
        Returns:
            SessionResult avec les résultats
        """
        self.result.mark_started()
        self.result.add_log(f"Starting {self.config.platform} session for @{self.config.account.username}")
        
        try:
            # 1. Vérifier/connecter le device
            self._connect_device()
            
            # 2. Lancer l'application
            self._launch_app()
            
            # 3. Se connecter au compte
            self._login()
            
            # 4. Exécuter le workflow
            self._execute_workflow()
            
            # 5. Marquer comme réussi
            self.result.mark_success()
            self.result.add_log("Session completed successfully", "success")
            
            logger.success(f"✅ Session completed: {self.session_id}")
            
        except Exception as e:
            error_msg = str(e)
            self.result.mark_failed(error_msg, {"exception": type(e).__name__})
            self.result.add_log(f"Session failed: {error_msg}", "error")
            logger.error(f"❌ Session failed: {error_msg}")
        
        finally:
            # Mettre à jour le registre
            self.device_registry.update_last_used(self.config.device_id)
        
        return self.result
    
    def _connect_device(self) -> None:
        """Connecte au device"""
        self.result.add_log(f"Connecting to device: {self.config.device_id}")
        logger.info(f"📱 Connecting to device: {self.config.device_id}")
        
        from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
        
        self.device_manager = DeviceManager()
        
        if not self.device_manager.connect(self.config.device_id):
            raise ConnectionError(f"Failed to connect to device: {self.config.device_id}")
        
        if not self.device_manager.device:
            raise ConnectionError("Device initialization failed")
        
        self.result.add_log("Device connected successfully", "success")
        logger.success(f"✅ Connected to device: {self.config.device_id}")
    
    def _launch_app(self) -> None:
        """Lance l'application Instagram/TikTok"""
        self.result.add_log(f"Launching {self.config.platform} app")
        logger.info(f"📱 Launching {self.config.platform}...")
        
        if self.config.platform == "instagram":
            from taktik.core.social_media.instagram.core.manager import InstagramManager
            manager = InstagramManager(self.device_manager)
            manager.launch()
        elif self.config.platform == "tiktok":
            from taktik.core.social_media.tiktok.core.manager import TikTokManager
            manager = TikTokManager(self.device_manager)
            manager.launch()
        else:
            raise ValueError(f"Unsupported platform: {self.config.platform}")
        
        self.result.add_log("App launched successfully", "success")
        logger.success(f"✅ {self.config.platform.capitalize()} launched")
    
    def _login(self) -> None:
        """Se connecte au compte"""
        self.result.add_log(f"Logging in as @{self.config.account.username}")
        logger.info(f"🔐 Logging in as @{self.config.account.username}...")
        
        if self.config.platform == "instagram":
            from taktik.core.social_media.instagram.workflows.management.login_workflow import LoginWorkflow
            
            # Initialiser le workflow avec device et device_id
            workflow = LoginWorkflow(
                device=self.device_manager.device,
                device_id=self.config.device_id
            )
            
            # Exécuter le login
            result = workflow.execute(
                username=self.config.account.username,
                password=self.config.account.password,
                save_session=self.config.account.save_session,
                save_login_info_instagram=self.config.account.save_login_info
            )
            
            if not result.get('success'):
                raise RuntimeError(f"Login failed: {result.get('message', 'Unknown error')}")
        
        elif self.config.platform == "tiktok":
            # TODO: Implémenter le login TikTok
            raise NotImplementedError("TikTok login not yet implemented")
        
        self.result.add_log("Login successful", "success")
        logger.success(f"✅ Logged in as @{self.config.account.username}")
    
    def _execute_workflow(self) -> None:
        """Exécute le workflow configuré"""
        workflow_type = self.config.workflow.type
        self.result.add_log(f"Executing workflow: {workflow_type}")
        logger.info(f"⚙️ Executing workflow: {workflow_type}")
        
        if self.config.platform == "instagram":
            if workflow_type == "automation":
                self._execute_instagram_automation()
            elif workflow_type == "management":
                self._execute_instagram_management()
            elif workflow_type == "advanced_actions":
                self._execute_instagram_advanced_actions()
            else:
                raise ValueError(f"Unknown workflow type: {workflow_type}")
        
        elif self.config.platform == "tiktok":
            # TODO: Implémenter les workflows TikTok
            raise NotImplementedError("TikTok workflows not yet implemented")
        
        self.result.add_log("Workflow completed", "success")
        logger.success(f"✅ Workflow completed")
    
    def _execute_instagram_automation(self) -> None:
        """Exécute un workflow d'automation Instagram"""
        from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
        from taktik.core.license.unified_license_manager import UnifiedLicenseManager
        
        # Créer la config dynamique
        dynamic_config = self._build_instagram_automation_config()
        
        # Initialiser l'automation
        automation = InstagramAutomation(self.device_manager)
        
        # Récupérer l'API key depuis la license si fournie
        api_key_to_use = None
        if self.config.api_key:
            # Si c'est une license key (format TAKTIK-...), récupérer l'API key
            if self.config.api_key.startswith('TAKTIK-'):
                logger.info("🔑 Retrieving API key from license...")
                license_manager = UnifiedLicenseManager()
                license_info = license_manager.verify_license(self.config.api_key)
                
                if license_info and license_info.get('valid'):
                    api_key = license_manager._get_api_key_from_server(self.config.api_key)
                    if api_key:
                        logger.success(f"✅ API key retrieved: {api_key[:15]}...")
                        api_key_to_use = api_key
                    else:
                        logger.warning("⚠️ Could not retrieve API key from license")
                else:
                    logger.warning("⚠️ Invalid license")
            else:
                # C'est déjà une API key (format tk_live_...)
                api_key_to_use = self.config.api_key
        
        # Configurer le database service et les limites de licence
        if api_key_to_use:
            # Configurer le database service globalement
            from taktik.core.database import configure_db_service
            configure_db_service(api_key_to_use)
            
            # Initialiser les limites de licence
            automation._initialize_license_limits(api_key_to_use)
            logger.success("✅ Database service configured")
        
        automation.config = dynamic_config
        
        # Exécuter
        automation.run_workflow()
        
        # Récupérer les stats
        if hasattr(automation, 'stats'):
            self._update_stats_from_automation(automation.stats)
    
    def _build_instagram_automation_config(self) -> Dict[str, Any]:
        """Construit la config pour InstagramAutomation"""
        wf = self.config.workflow
        
        # Construire l'action principale selon le target_type
        action = {
            "type": "interact_with_followers",  # Type par défaut
            "max_interactions": wf.limits.max_interactions,
            "like_posts": wf.actions.like,
            "follow_users": wf.actions.follow,
            "comment_on_posts": wf.actions.comment,
            "watch_stories": wf.actions.watch,
            "max_likes_per_profile": wf.limits.max_likes_per_profile,
            "max_follows": wf.limits.max_follows,
            "max_likes": wf.limits.max_likes,
            "max_comments": wf.limits.max_comments,
        }
        
        # Ajouter le target selon le type
        if wf.target_type in ["followers", "following"]:
            action["type"] = "interact_with_followers"
            action["target_username"] = wf.target_username
            action["interaction_type"] = wf.target_type  # followers ou following
        elif wf.target_type == "hashtag":
            action["type"] = "hashtag"
            action["hashtag"] = wf.hashtag
        elif wf.target_type == "post_url":
            action["type"] = "post_url"
            action["post_url"] = wf.post_url
        
        # Ajouter les probabilités si présentes
        if wf.probabilities:
            action["like_probability"] = wf.probabilities.like
            action["follow_probability"] = wf.probabilities.follow
            action["comment_probability"] = wf.probabilities.comment
            action["watch_stories_probability"] = wf.probabilities.watch_stories
            action["like_stories_probability"] = wf.probabilities.like_stories
        
        # Ajouter les filtres si présents
        if wf.filters:
            action["filters"] = {
                "min_followers": wf.filters.min_followers,
                "max_followers": wf.filters.max_followers,
                "min_posts": wf.filters.min_posts,
                "max_followings": wf.filters.max_followings,
            }
        
        # Config finale avec liste d'actions
        config = {
            "actions": [action]  # Liste d'actions, pas un dictionnaire
        }
        
        # Ajouter les paramètres de session si présents
        if wf.session:
            config["session_settings"] = {
                "session_duration_minutes": wf.session.duration_minutes,
                "delay_between_actions": {
                    "min": wf.session.min_delay,
                    "max": wf.session.max_delay
                }
            }
        
        return config
    
    def _execute_instagram_management(self) -> None:
        """Exécute un workflow de management Instagram"""
        # TODO: Implémenter (post content, story, etc.)
        raise NotImplementedError("Instagram management workflows not yet implemented in automation mode")
    
    def _execute_instagram_advanced_actions(self) -> None:
        """Exécute des actions avancées Instagram"""
        # TODO: Implémenter (mass DM, intelligent unfollow, etc.)
        raise NotImplementedError("Instagram advanced actions not yet implemented in automation mode")
    
    def _update_stats_from_automation(self, automation_stats: Any) -> None:
        """Met à jour les stats depuis l'automation"""
        if hasattr(automation_stats, 'likes'):
            self.result.stats.likes = automation_stats.likes
        if hasattr(automation_stats, 'follows'):
            self.result.stats.follows = automation_stats.follows
        if hasattr(automation_stats, 'comments'):
            self.result.stats.comments = automation_stats.comments
        if hasattr(automation_stats, 'watches'):
            self.result.stats.watches = automation_stats.watches
        if hasattr(automation_stats, 'errors'):
            self.result.stats.errors = automation_stats.errors
    
    def get_result(self) -> SessionResult:
        """
        Récupère le résultat de la session.
        
        Returns:
            SessionResult
        """
        return self.result
    
    def cancel(self) -> None:
        """Annule la session en cours"""
        self.result.mark_cancelled()
        self.result.add_log("Session cancelled by user", "warning")
        logger.warning(f"⚠️ Session cancelled: {self.session_id}")
