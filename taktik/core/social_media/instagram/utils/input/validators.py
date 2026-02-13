"""
Validateurs pour les entrées utilisateur et les données Instagram.

Ce module contient des fonctions pour valider les noms d'utilisateur, les hashtags,
les URLs et autres données liées à Instagram.
"""

import re
from typing import Optional, List, Tuple, Dict, Any, Union
from urllib.parse import urlparse

# Expression régulière pour les noms d'utilisateur Instagram (entre 1 et 30 caractères, lettres, chiffres, points, tirets bas)
USERNAME_REGEX = r'^[A-Za-z0-9._]{1,30}$'

# Expression régulière pour les hashtags (entre 2 et 30 caractères, lettres, chiffres, underscore)
HASHTAG_REGEX = r'^[A-Za-z0-9_]{2,30}$'

# Expression régulière pour les IDs de post Instagram
POST_ID_REGEX = r'^[A-Za-z0-9_-]{10,}$'

def validate_username(username: str) -> Tuple[bool, str]:
    """
    Valide un nom d'utilisateur Instagram.
    
    Args:
        username: Le nom d'utilisateur à valider
        
    Returns:
        Tuple[bool, str]: (est_valide, message_erreur)
    """
    if not username:
        return False, "Le nom d'utilisateur ne peut pas être vide"
    
    if len(username) > 30:
        return False, "Le nom d'utilisateur ne peut pas dépasser 30 caractères"
    
    if not re.match(USERNAME_REGEX, username):
        return False, "Le nom d'utilisateur contient des caractères non autorisés"
    
    return True, ""

def validate_hashtag(hashtag: str) -> Tuple[bool, str]:
    """
    Valide un hashtag Instagram (sans le #).
    
    Args:
        hashtag: Le hashtag à valider (sans le #)
        
    Returns:
        Tuple[bool, str]: (est_valide, message_erreur)
    """
    if not hashtag:
        return False, "Le hashtag ne peut pas être vide"
    
    # Supprimer le # s'il est présent
    if hashtag.startswith('#'):
        hashtag = hashtag[1:]
    
    if len(hashtag) < 2:
        return False, "Le hashtag doit contenir au moins 2 caractères"
    
    if len(hashtag) > 30:
        return False, "Le hashtag ne peut pas dépasser 30 caractères"
    
    if not re.match(HASHTAG_REGEX, hashtag):
        return False, "Le hashtag contient des caractères non autorisés"
    
    return True, ""

def validate_url(url: str) -> Tuple[bool, str]:
    """
    Valide une URL Instagram.
    
    Args:
        url: L'URL à valider
        
    Returns:
        Tuple[bool, str]: (est_valide, message_erreur)
    """
    if not url:
        return False, "L'URL ne peut pas être vide"
    
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "L'URL n'est pas valide"
        
        # Vérifier que c'est bien une URL Instagram
        if 'instagram.com' not in result.netloc:
            return False, "L'URL doit être une URL Instagram valide"
            
        return True, ""
    except Exception:
        return False, "Format d'URL invalide"

def validate_post_id(post_id: str) -> Tuple[bool, str]:
    """
    Valide un ID de post Instagram.
    
    Args:
        post_id: L'ID du post à valider
        
    Returns:
        Tuple[bool, str]: (est_valide, message_erreur)
    """
    if not post_id:
        return False, "L'ID du post ne peut pas être vide"
    
    if not re.match(POST_ID_REGEX, post_id):
        return False, "Format d'ID de post invalide"
    
    return True, ""

def validate_comment(comment: str) -> Tuple[bool, str]:
    """
    Valide un commentaire Instagram.
    
    Args:
        comment: Le commentaire à valider
        
    Returns:
        Tuple[bool, str]: (est_valide, message_erreur)
    """
    if not comment:
        return False, "Le commentaire ne peut pas être vide"
    
    if len(comment) > 2200:
        return False, "Le commentaire ne peut pas dépasser 2200 caractères"
    
    # Vérifier les caractères non autorisés
    if '\x00' in comment:
        return False, "Le commentaire contient des caractères non autorisés"
    
    return True, ""
