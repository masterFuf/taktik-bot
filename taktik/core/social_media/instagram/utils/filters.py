"""
Module contenant les filtres pour les interactions Instagram.
"""
from typing import Optional, List, Dict, Any, Union
from loguru import logger
import json
import os
from pathlib import Path


class InstagramFilters:
    """
    Classe pour filtrer les comptes Instagram selon divers critères.
    """
    
    def __init__(self, filters_config: Optional[Union[Dict[str, Any], str]] = None):
        """
        Initialise les filtres Instagram.
        
        Args:
            filters_config: Configuration des filtres sous forme de dictionnaire ou chemin vers un fichier JSON
        """
        self.logger = logger.bind(module="instagram-filters")
        self.filters = {}
        
        if filters_config:
            if isinstance(filters_config, str):
                # Charger depuis un fichier
                self.load_from_file(filters_config)
            else:
                # Utiliser le dictionnaire directement
                self.filters = filters_config
    
    def load_from_file(self, file_path: str) -> bool:
        """
        Charge les filtres depuis un fichier JSON.
        
        Args:
            file_path: Chemin vers le fichier JSON
            
        Returns:
            bool: True si le chargement a réussi, False sinon
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.filters = json.load(f)
            self.logger.info(f"Filtres chargés depuis {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement des filtres: {e}")
            return False
    
    def save_to_file(self, file_path: str) -> bool:
        """
        Sauvegarde les filtres dans un fichier JSON.
        
        Args:
            file_path: Chemin vers le fichier JSON
            
        Returns:
            bool: True si la sauvegarde a réussi, False sinon
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.filters, f, indent=2)
            self.logger.info(f"Filtres sauvegardés dans {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des filtres: {e}")
            return False
    
    def get_rejection_reason(self, profile_data: Dict[str, Any]) -> str:
        """
        Retourne la raison pour laquelle un profil a été rejeté par les filtres.
        
        Args:
            profile_data: Données du profil à vérifier
            
        Returns:
            str: Message expliquant la raison du rejet, ou chaîne vide si le profil passe les filtres
        """
        # Vérifier les filtres de followers
        if 'min_followers' in self.filters and profile_data.get('followers_count', 0) < self.filters['min_followers']:
            return f"Trop peu de followers ({profile_data.get('followers_count', 0)} < {self.filters['min_followers']})"
        
        if 'max_followers' in self.filters and profile_data.get('followers_count', 0) > self.filters['max_followers']:
            return f"Trop de followers ({profile_data.get('followers_count', 0)} > {self.filters['max_followers']})"
        
        # Vérifier les filtres de following
        if 'min_followings' in self.filters and profile_data.get('following_count', 0) < self.filters['min_followings']:
            return f"Trop peu de followings ({profile_data.get('following_count', 0)} < {self.filters['min_followings']})"
        
        if 'max_followings' in self.filters and profile_data.get('following_count', 0) > self.filters['max_followings']:
            return f"Trop de followings ({profile_data.get('following_count', 0)} > {self.filters['max_followings']})"
        
        # Vérifier le ratio potentiel (followers/following)
        if 'min_potency_ratio' in self.filters or 'max_potency_ratio' in self.filters:
            following_count = profile_data.get('following_count', 0)
            if following_count > 0:
                ratio = profile_data.get('followers_count', 0) / following_count
                
                if 'min_potency_ratio' in self.filters and ratio < self.filters['min_potency_ratio']:
                    return f"Ratio followers/suivis trop faible ({ratio:.2f} < {self.filters['min_potency_ratio']})"
                
                if 'max_potency_ratio' in self.filters and ratio > self.filters['max_potency_ratio']:
                    return f"Ratio followers/suivis trop élevé ({ratio:.2f} > {self.filters['max_potency_ratio']})"
        
        # Vérifier le nombre de posts
        if 'min_posts' in self.filters and profile_data.get('posts_count', 0) < self.filters['min_posts']:
            return f"Trop peu de publications ({profile_data.get('posts_count', 0)} < {self.filters['min_posts']})"
        
        # Vérifier le type de compte (business/personnel)
        if 'skip_business' in self.filters and self.filters['skip_business'] and profile_data.get('is_business', False):
            return "Compte business ignoré (configuration)"
        
        if 'skip_non_business' in self.filters and self.filters['skip_non_business'] and not profile_data.get('is_business', False):
            return "Compte non-business ignoré (configuration)"
        
        # Vérifier la confidentialité du compte
        if 'privacy_relation' in self.filters:
            is_private = profile_data.get('is_private', False)
            
            if self.filters['privacy_relation'] == 'only_public' and is_private:
                return "Compte privé (configuration: only_public)"
            
            if self.filters['privacy_relation'] == 'only_private' and not is_private:
                return "Compte public (configuration: only_private)"
        
        # Vérifier les mots-clés dans la bio
        if 'blacklist_words' in self.filters and self.filters['blacklist_words']:
            bio = (profile_data.get('biography') or '').lower()
            for word in self.filters['blacklist_words']:
                if word.lower() in bio:
                    return f"Mot-clé interdit trouvé dans la bio: {word}"
        
        # Vérifier les mots obligatoires dans la bio
        if 'mandatory_words' in self.filters and self.filters['mandatory_words']:
            bio = (profile_data.get('biography') or '').lower()
            found = False
            for word in self.filters['mandatory_words']:
                if word.lower() in bio:
                    found = True
                    break
            
            if not found:
                return "Aucun mot-clé obligatoire trouvé dans la bio"
        
        # Aucun motif de rejet trouvé
        return ""

    def should_interact(self, profile_data: Dict[str, Any]) -> bool:
        """
        Détermine si un profil correspond aux critères de filtrage.
        
        Args:
            profile_data: Données du profil à vérifier
            
        Returns:
            bool: True si le profil passe les filtres, False sinon
        """
        # Vérifier les filtres de followers
        if 'min_followers' in self.filters and profile_data.get('followers_count', 0) < self.filters['min_followers']:
            self.logger.info(f"Profil ignoré: trop peu de followers ({profile_data.get('followers_count', 0)} < {self.filters['min_followers']})")
            return False
        
        if 'max_followers' in self.filters and profile_data.get('followers_count', 0) > self.filters['max_followers']:
            self.logger.info(f"Profil ignoré: trop de followers ({profile_data.get('followers_count', 0)} > {self.filters['max_followers']})")
            return False
        
        # Vérifier les filtres de following
        if 'min_followings' in self.filters and profile_data.get('following_count', 0) < self.filters['min_followings']:
            self.logger.info(f"Profil ignoré: trop peu de followings ({profile_data.get('following_count', 0)} < {self.filters['min_followings']})")
            return False
        
        if 'max_followings' in self.filters and profile_data.get('following_count', 0) > self.filters['max_followings']:
            self.logger.info(f"Profil ignoré: trop de followings ({profile_data.get('following_count', 0)} > {self.filters['max_followings']})")
            return False
        
        # Vérifier le ratio potentiel (followers/following)
        if 'min_potency_ratio' in self.filters or 'max_potency_ratio' in self.filters:
            following_count = profile_data.get('following_count', 0)
            if following_count > 0:
                ratio = profile_data.get('followers_count', 0) / following_count
                
                if 'min_potency_ratio' in self.filters and ratio < self.filters['min_potency_ratio']:
                    self.logger.info(f"Profil ignoré: ratio trop faible ({ratio:.2f} < {self.filters['min_potency_ratio']})")
                    return False
                
                if 'max_potency_ratio' in self.filters and ratio > self.filters['max_potency_ratio']:
                    self.logger.info(f"Profil ignoré: ratio trop élevé ({ratio:.2f} > {self.filters['max_potency_ratio']})")
                    return False
        
        # Vérifier le nombre de posts
        if 'min_posts' in self.filters and profile_data.get('posts_count', 0) < self.filters['min_posts']:
            self.logger.info(f"Profil ignoré: trop peu de posts ({profile_data.get('posts_count', 0)} < {self.filters['min_posts']})")
            return False
        
        # Vérifier le type de compte (business/personnel)
        if 'skip_business' in self.filters and self.filters['skip_business'] and profile_data.get('is_business', False):
            self.logger.info("Profil ignoré: compte business")
            return False
        
        if 'skip_non_business' in self.filters and self.filters['skip_non_business'] and not profile_data.get('is_business', False):
            self.logger.info("Profil ignoré: compte non-business")
            return False
        
        # Vérifier la confidentialité du compte
        if 'privacy_relation' in self.filters:
            is_private = profile_data.get('is_private', False)
            
            if self.filters['privacy_relation'] == 'only_public' and is_private:
                self.logger.info("Profil ignoré: compte privé")
                return False
            
            if self.filters['privacy_relation'] == 'only_private' and not is_private:
                self.logger.info("Profil ignoré: compte public")
                return False
        
        # Vérifier les mots-clés dans la bio
        if 'blacklist_words' in self.filters and self.filters['blacklist_words']:
            bio = (profile_data.get('biography') or '').lower()
            for word in self.filters['blacklist_words']:
                if word.lower() in bio:
                    self.logger.info(f"Profil ignoré: mot-clé interdit trouvé ({word})")
                    return False
        
        # Vérifier les mots obligatoires dans la bio
        if 'mandatory_words' in self.filters and self.filters['mandatory_words']:
            bio = (profile_data.get('biography') or '').lower()
            found = False
            for word in self.filters['mandatory_words']:
                if word.lower() in bio:
                    found = True
                    break
            
            if not found:
                self.logger.info("Profil ignoré: aucun mot-clé obligatoire trouvé")
                return False
        
        # Tous les filtres ont été passés
        return True


class DefaultFilters:
    """
    Classe contenant des configurations de filtres prédéfinies.
    """
    
    @staticmethod
    def get_safe_filters() -> Dict[str, Any]:
        """
        Retourne une configuration de filtres sécurisée pour éviter les bots et les comptes suspects.
        
        Returns:
            Dict[str, Any]: Configuration de filtres
        """
        return {
            "min_followers": 30,
            "max_followers": 25000,
            "min_followings": 30,
            "max_followings": 5000,
            "min_potency_ratio": 0.05,  # Au moins 1 follower pour 20 following
            "max_potency_ratio": 20,   # Au plus 20 followers pour 1 following
            "min_posts": 5,
            "privacy_relation": "only_public",
            "blacklist_words": ["bot", "follow for follow", "f4f", "l4l", "like for like"]
        }
    
    @staticmethod
    def get_engagement_filters() -> Dict[str, Any]:
        """
        Retourne une configuration de filtres pour maximiser l'engagement.
        
        Returns:
            Dict[str, Any]: Configuration de filtres
        """
        return {
            "min_followers": 50,
            "max_followers": 50000,
            "min_followings": 50,
            "max_followings": 7500,
            "min_potency_ratio": 0.1,
            "max_potency_ratio": 15,
            "min_posts": 10,
            "privacy_relation": "only_public"
        }
    
    @staticmethod
    def get_influencer_filters() -> Dict[str, Any]:
        """
        Retourne une configuration de filtres pour cibler les micro-influenceurs.
        
        Returns:
            Dict[str, Any]: Configuration de filtres
        """
        return {
            "min_followers": 1000,
            "max_followers": 50000,
            "min_followings": 100,
            "max_followings": 5000,
            "min_potency_ratio": 1,  # Plus de followers que de following
            "min_posts": 30,
            "privacy_relation": "only_public"
        }
