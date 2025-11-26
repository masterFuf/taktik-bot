"""
Configuration Loader
====================

Charge et valide les configurations de session depuis JSON ou dictionnaire.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
from pydantic import BaseModel, Field, validator


class AccountConfig(BaseModel):
    """Configuration du compte à automatiser"""
    username: str = Field(..., description="Username Instagram/TikTok")
    password: str = Field(..., description="Mot de passe")
    save_session: bool = Field(True, description="Sauvegarder la session")
    save_login_info: bool = Field(False, description="Sauvegarder les infos de login")


class WorkflowLimits(BaseModel):
    """Limites du workflow"""
    max_interactions: int = Field(50, ge=1, le=1000, description="Max profiles à traiter")
    max_follows: int = Field(20, ge=0, le=500, description="Max follows total")
    max_likes: int = Field(50, ge=0, le=1000, description="Max likes total")
    max_likes_per_profile: int = Field(2, ge=1, le=20, description="Max likes par profil")
    max_comments: int = Field(10, ge=0, le=100, description="Max commentaires")
    max_unfollows: int = Field(50, ge=0, le=500, description="Max unfollows")


class WorkflowActions(BaseModel):
    """Actions à effectuer"""
    like: bool = Field(True)
    follow: bool = Field(True)
    comment: bool = Field(False)
    watch: bool = Field(False)
    unfollow: bool = Field(False)


class WorkflowProbabilities(BaseModel):
    """Probabilités des actions (en %)"""
    like: int = Field(80, ge=0, le=100, description="Probabilité de liker (%)")
    follow: int = Field(20, ge=0, le=100, description="Probabilité de suivre (%)")
    comment: int = Field(5, ge=0, le=100, description="Probabilité de commenter (%)")
    watch_stories: int = Field(15, ge=0, le=100, description="Probabilité de regarder les stories (%)")
    like_stories: int = Field(10, ge=0, le=100, description="Probabilité de liker les stories (%)")


class WorkflowFilters(BaseModel):
    """Filtres de ciblage"""
    min_followers: int = Field(50, ge=0, description="Minimum de followers")
    max_followers: int = Field(50000, ge=0, description="Maximum de followers")
    min_posts: int = Field(5, ge=0, description="Minimum de posts")
    max_followings: int = Field(7500, ge=0, description="Maximum de followings")


class SessionSettings(BaseModel):
    """Paramètres de session"""
    duration_minutes: int = Field(60, ge=1, le=480, description="Durée de session (minutes)")
    min_delay: int = Field(5, ge=1, le=60, description="Délai minimum entre actions (secondes)")
    max_delay: int = Field(15, ge=1, le=120, description="Délai maximum entre actions (secondes)")


class WorkflowConfig(BaseModel):
    """Configuration du workflow"""
    type: str = Field(..., description="Type: automation, management, advanced_actions")
    target_type: Optional[str] = Field(None, description="hashtag, followers, following, post_url")
    target_username: Optional[str] = Field(None, description="Username cible (pour followers/following)")
    hashtag: Optional[str] = Field(None, description="Hashtag à cibler")
    post_url: Optional[str] = Field(None, description="URL du post")
    actions: WorkflowActions = Field(default_factory=WorkflowActions)
    limits: WorkflowLimits = Field(default_factory=WorkflowLimits)
    probabilities: Optional[WorkflowProbabilities] = Field(default_factory=WorkflowProbabilities)
    filters: Optional[WorkflowFilters] = Field(default_factory=WorkflowFilters)
    session: Optional[SessionSettings] = Field(default_factory=SessionSettings)
    
    @validator('type')
    def validate_type(cls, v):
        valid_types = ['automation', 'management', 'advanced_actions']
        if v not in valid_types:
            raise ValueError(f"Type must be one of {valid_types}")
        return v
    
    @validator('target_type')
    def validate_target_type(cls, v, values):
        if values.get('type') == 'automation' and not v:
            raise ValueError("target_type is required for automation workflow")
        valid_targets = ['hashtag', 'followers', 'following', 'post_url']
        if v and v not in valid_targets:
            raise ValueError(f"target_type must be one of {valid_targets}")
        return v


class SessionConfig(BaseModel):
    """Configuration complète de session"""
    client_id: Optional[str] = Field(None, description="ID client (pour Taktik Social)")
    platform: str = Field(..., description="Platform: instagram ou tiktok")
    device_id: str = Field(..., description="Device ID (ex: emulator-5566)")
    api_key: Optional[str] = Field(None, description="Clé API Taktik")
    account: AccountConfig
    workflow: WorkflowConfig
    
    @validator('platform')
    def validate_platform(cls, v):
        valid_platforms = ['instagram', 'tiktok']
        if v not in valid_platforms:
            raise ValueError(f"Platform must be one of {valid_platforms}")
        return v


class ConfigLoader:
    """Charge et valide les configurations de session"""
    
    @staticmethod
    def from_json(config_path: str) -> SessionConfig:
        """
        Charge une configuration depuis un fichier JSON.
        
        Args:
            config_path: Chemin vers le fichier JSON
            
        Returns:
            SessionConfig validée
            
        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            ValueError: Si la configuration est invalide
        """
        path = Path(config_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        logger.info(f"📄 Loading config from: {config_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            config = SessionConfig(**data)
            logger.success(f"✅ Config loaded and validated: {config.platform} - {config.account.username}")
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON: {e}")
            raise ValueError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            logger.error(f"❌ Config validation failed: {e}")
            raise ValueError(f"Invalid configuration: {e}")
    
    @staticmethod
    def from_dict(config_dict: Dict[str, Any]) -> SessionConfig:
        """
        Charge une configuration depuis un dictionnaire.
        
        Args:
            config_dict: Dictionnaire de configuration
            
        Returns:
            SessionConfig validée
            
        Raises:
            ValueError: Si la configuration est invalide
        """
        logger.info("📄 Loading config from dictionary")
        
        try:
            config = SessionConfig(**config_dict)
            logger.success(f"✅ Config validated: {config.platform} - {config.account.username}")
            return config
            
        except Exception as e:
            logger.error(f"❌ Config validation failed: {e}")
            raise ValueError(f"Invalid configuration: {e}")
    
    @staticmethod
    def to_json(config: SessionConfig, output_path: str) -> None:
        """
        Sauvegarde une configuration dans un fichier JSON.
        
        Args:
            config: Configuration à sauvegarder
            output_path: Chemin du fichier de sortie
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"💾 Saving config to: {output_path}")
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config.dict(), f, indent=2, ensure_ascii=False)
        
        logger.success(f"✅ Config saved: {output_path}")
    
    @staticmethod
    def create_example_config(platform: str = "instagram") -> SessionConfig:
        """
        Crée une configuration d'exemple.
        
        Args:
            platform: Platform (instagram ou tiktok)
            
        Returns:
            SessionConfig d'exemple
        """
        return SessionConfig(
            client_id="example_client_123",
            platform=platform,
            device_id="emulator-5566",
            api_key="tk_live_your_api_key_here",
            account=AccountConfig(
                username="your_username",
                password="your_password",
                save_session=True,
                save_login_info=False
            ),
            workflow=WorkflowConfig(
                type="automation",
                target_type="hashtag",
                hashtag="travel",
                actions=WorkflowActions(
                    like=True,
                    follow=True,
                    comment=False
                ),
                limits=WorkflowLimits(
                    max_interactions=50,
                    max_follows=20,
                    max_likes=50,
                    max_comments=0
                )
            )
        )
