# Fichier de traduction française

BANNER = """
████████╗ █████╗ ██╗  ██╗████████╗██╗██╗  ██╗
╚══██╔══╝██╔══██╗██║ ██╔╝╚══██╔══╝██║██║ ██╔╝
   ██║   ███████║█████╔╝    ██║   ██║█████╔╝ 
   ██║   ██╔══██║██╔═██╗    ██║   ██║██╔═██╗ 
   ██║   ██║  ██║██║  ██╗   ██║   ██║██║  ██╗
   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝╚═╝  ╚═╝
"""

TRANSLATIONS = {
    "app_title": "Outil d'automatisation pour les réseaux sociaux",
    "menu_title": "Menu Principal",
    "option_instagram": "Instagram",
    "option_tiktok": "TikTok",
    "option_quit": "Quitter",
    "prompt_choice": "Votre choix",
    "goodbye": "Merci d'avoir utilisé TAKTIK. À bientôt !",
    "website": "Site web",
    "github": "GitHub",
    
    # Device management
    "no_device_connected": "Aucun appareil connecté.",
    "select_device": "Sélectionnez un appareil :",
    "device_selected": "Appareil sélectionné : {}",
    "instagram_not_installed": "Instagram n'est pas installé sur cet appareil.",
    "launching_instagram": "Lancement d'Instagram...",
    "instagram_launched_success": "Instagram a été lancé avec succès !",
    "instagram_launch_failed": "Échec du lancement d'Instagram.",
    
    # Workflow management
    "launch_workflow_question": "Voulez-vous lancer un workflow d'automatisation sur cet appareil ?",
    "config_path_prompt": "Chemin du fichier de configuration JSON (laisser vide pour défaut)",
    "no_target_selected": "Aucune cible sélectionnée. Arrêt du workflow.",
    "workflow_generation_error": "Erreur lors de la génération du workflow dynamique.",
    "cannot_connect_device": "Impossible de se connecter à l'appareil {}",
    "device_init_error": "Erreur: L'appareil n'a pas pu être initialisé correctement",
    "initializing_automation": "Initialisation de l'automatisation Instagram...",
    "config_loaded": "Configuration chargée depuis {}",
    "config_load_error": "Erreur lors du chargement de la configuration",
    "dynamic_config_applied": "Configuration dynamique appliquée",
    "no_config_default": "Aucune configuration fournie, utilisation des paramètres par défaut.",
    
    # Workflow results
    "workflow_summary": "Résumé du workflow Instagram",
    "likes": "Likes",
    "follows": "Follows",
    "unfollows": "Unfollows",
    "comments": "Commentaires",
    "total_interactions": "Interactions totales",
    "duration": "Durée",
    "result": "Résultat",
    
    # Target selection
    "target_selection_title": "Sélection du type de cible",
    "target_option_target": "Target (nom d'utilisateur/profil)",
    "target_option_hashtags": "Hashtags",
    "choose_target_type": "Choisissez le type de cible",
    "hashtags_dev_message": "Module Hashtags en cours de développement...",
    
    # Target workflow configuration
    "target_workflow_title": "🎯 Configuration du workflow Target/Followers",
    "target_username_prompt": "Nom d'utilisateur cible (sans @)",
    "username_required": "Nom d'utilisateur requis !",
    "interaction_types_available": "Types d'interaction disponibles :",
    "followers_interaction": "Followers - Interagir avec les abonnés du compte cible",
    "following_interaction": "Following - Interagir avec les comptes suivis par la cible",
    "recent_posts_likers": "Recent Posts Likers - Interagir avec ceux qui ont liké les posts récents",
    "choose_interaction_type": "Choisissez le type d'interaction",
    "limits_configuration": "📊 Configuration des limites :",
    "max_profiles_prompt": "Nombre maximum de profils à traiter",
    "max_likes_per_profile": "Nombre maximum de likes par profil",
    "probabilities_configuration": "🎲 Configuration des probabilités d'interaction (en %) :",
    "like_probability": "Probabilité de liker des posts",
    "follow_probability": "Probabilité de follow",
    "comment_probability": "Probabilité de commenter",
    "story_probability": "Probabilité de regarder les stories",
    "story_like_probability": "Probabilité de liker les stories",
    "advanced_filters": "🔍 Filtres avancés de ciblage :",
    "min_followers_required": "Nombre minimum de followers requis",
    "max_followers_accepted": "Nombre maximum de followers acceptés",
    "min_posts_required": "Nombre minimum de posts requis",
    "max_followings_accepted": "Nombre maximum de comptes suivis acceptés",
    "blacklist_optional": "🚫 Liste noire (optionnel) :",
    "blacklist_keywords": "Mots-clés à éviter (séparés par des virgules)",
    "session_configuration": "⏱️ Configuration de session :",
    "max_session_duration": "Durée maximale de session (minutes)",
    "min_delay_actions": "Délai minimum entre actions (secondes)",
    "max_delay_actions": "Délai maximum entre actions (secondes)",
    "target_workflow_summary": "📋 Résumé de la configuration Target/Followers :",
    "parameter": "Paramètre",
    "value": "Valeur",
    "target": "Cible",
    "interaction_type": "Type d'interaction",
    "max_interactions": "Max interactions",
    "probabilities": "Probabilités",
    "filters": "Filtres",
    "session": "Session",
    "blacklisted_words": "Mots blacklistés",
    "session_estimates": "📊 Estimations de session :",
    "estimated_likes": "Likes estimés :",
    "estimated_follows": "Follows estimés :",
    "estimated_comments": "Commentaires estimés :",
    "target_workflow_configured": "✅ Workflow Target configuré pour @{}",
    
    # Workflow hashtags
    "hashtag_workflow_config": "🔗 Configuration du workflow Hashtags",
    "enter_hashtag": "Entrez le hashtag à cibler (sans #)",
    "hashtag_required": "Hashtag requis !",
    "recent_likers": "Recent Likers - Utilisateurs qui ont récemment liké des posts",
    "top_likers": "Top Likers - Utilisateurs qui ont le plus liké des posts populaires",
    "recent_posts": "Recent Posts - Auteurs de posts récents (à développer)",
    "top_posts": "Top Posts - Auteurs de posts populaires (à développer)",
    "max_posts_check": "Nombre maximum de posts à vérifier",
    "hashtag_workflow_success": "✅ Workflow Hashtags configuré avec succès !",
    
    # Workflow URL de post
    "target_option_post_url": "URL de post spécifique",
    "post_url_workflow_config": "🔗 Configuration du workflow URL de post",
    "enter_post_url": "URL du post Instagram à cibler",
    "post_url_required": "URL du post requise !",
    "invalid_instagram_url": "URL Instagram invalide. Utilisez un format comme: https://www.instagram.com/p/ABC123/",
    "interaction_mode": "📱 Mode d'interaction: Utilisateurs qui ont liké ce post spécifique",
    "workflow_extract_likers": "Note: Le workflow va extraire les likers du post fourni",
    "post_url_workflow_summary": "📋 Résumé de la configuration URL de post :",
    "post_url": "URL du post",
    "post_id": "ID du post",
    "post_id_not_detected": "Non détecté",
    "interaction_type_likers": "post-likers",
    "post_url_workflow_success": "✅ Workflow URL de post configuré pour {}",

    # Instagram manager
    "launching_instagram_title": "Lancement d'Instagram",
    "instagram_not_installed_device": "Instagram n'est pas installé sur cet appareil.",
    "launching_instagram_progress": "Lancement d'Instagram...",
    "instagram_launched_successfully": "Instagram a été lancé avec succès !",
    "instagram_launch_failed": "Échec du lancement d'Instagram.",
    
    # Workflow initialization
    "starting_automation_session": "=== Démarrage de la session d'automatisation Instagram ===",
    "restarting_instagram_clean_state": "🔄 Redémarrage d'Instagram pour garantir un état initial propre...",
    "instagram_restarted_successfully": "✅ Instagram redémarré avec succès",
    "waiting_instagram_load": "⏳ Attente de {}s pour le chargement complet d'Instagram...",
    
    # API connection
    "api_connection_established": "Connexion à l'API établie avec succès"
}
