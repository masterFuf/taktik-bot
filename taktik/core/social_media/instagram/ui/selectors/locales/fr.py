"""French (fr) UI string overlay for Instagram selectors.

ONE module per language. Holds ONLY the language-specific selector fragments
(``@text`` / ``@content-desc`` / ``@hint`` / bare labels) keyed by
``"<surface>.<field>"``. Language-neutral selectors (resource-id / class /
position) live in the selector dataclasses under ``ui/selectors/**`` and are
combined with these via ``L(key)`` (see ``locales/__init__.py``).

Provenance: fragments extracted from the historical EN/FR selector lists
(real device dumps, Instagram v410.0.0.53.71).
"""
from typing import Dict, List

STRINGS: Dict[str, List[str]] = {
    # --- auth ---
    "auth.contacts_sync_popup": [
        "//android.widget.Button[@content-desc=\"Autoriser\"]",
    ],
    "auth.create_account_button": [
        "//android.view.View[@content-desc=\"Créer un compte\"]",
        "//android.widget.Button[@content-desc=\"Créer un compte\"]",
        "//*[.//android.view.View[@content-desc=\"Créer un compte\"]]",
    ],
    "auth.error_message_selectors": [
        "//android.widget.TextView[contains(@text, \"incorrecte\")]",
        "//android.widget.TextView[contains(@text, \"Incorrecte\")]",
        "//android.widget.TextView[contains(@text, \"suspendu\")]",
        "//android.widget.TextView[contains(@text, \"bloqué\")]",
        "//android.widget.TextView[contains(@text, \"trop de\")]",
        "//android.widget.TextView[contains(@text, \"Réessayer\")]",
    ],
    "auth.forgot_password_button": [
        "//android.widget.Button[@content-desc=\"Mot de passe oublié ?\"]",
        "//android.widget.Button[.//android.view.View[@content-desc=\"Mot de passe oublié ?\"]]",
    ],
    "auth.google_autofill_dismiss_button": [
        "//android.widget.ImageView[@content-desc=\"Annuler\"]",
    ],
    "auth.home_logged_out_screen_indicators": [],
    "auth.location_permission_dialog": [],
    "auth.log_into_another_account_button": [
        "//android.widget.Button[@content-desc=\"Se connecter avec un autre compte\"]",
        "//*[contains(@content-desc, \"Se connecter avec un autre compte\")]",
    ],
    "auth.login_button": [
        "//android.widget.Button[@content-desc=\"Se connecter\"]",
        "//android.widget.Button[.//android.view.View[@content-desc=\"Se connecter\"]]",
    ],
    "auth.login_screen_indicators": [
        "//android.widget.Button[contains(@content-desc, \"Français\")]",
        "//android.widget.Button[@content-desc=\"Se connecter\"]",
    ],
    "auth.notification_popup": [
        "//android.widget.Button[contains(@text, \"Pas maintenant\")]",
    ],
    "auth.password_field": [
        "//android.widget.EditText[contains(@content-desc, \"Mot de passe\")]",
    ],
    "auth.password_only_screen_indicators": [
        "//android.widget.Button[@content-desc=\"Mot de passe oublié ?\"]",
    ],
    "auth.profile_selection_screen": [
        "//android.widget.Button[@content-desc=\"Utiliser un autre profil\"]",
        "//android.widget.Button[@content-desc=\"Créer un compte\"]",
        "//*[contains(@text, \"Utiliser un autre profil\")]",
    ],
    "auth.profile_tab_button": [
        "//android.widget.FrameLayout[@content-desc=\"Profil\"]",
    ],
    "auth.save_button_selectors": [
        "//android.widget.Button[@content-desc=\"Enregistrer\"]",
        "//android.widget.Button[.//android.view.View[@content-desc=\"Enregistrer\"]]",
    ],
    "auth.save_login_info_dialog_indicators": [],
    "auth.save_login_info_not_now_button": [
        "//android.widget.Button[@resource-id=\"com.instagram.android:id/negative_button\" and @text=\"Pas maintenant\"]",
    ],
    "auth.save_login_info_not_now_buttons": [
        "//android.widget.Button[@content-desc=\"Pas maintenant\"]",
        "//android.widget.Button[.//android.view.View[@content-desc=\"Pas maintenant\"]]",
    ],
    "auth.save_login_info_popup": [
        "//android.view.View[@content-desc=\"Enregistrer vos informations de connexion ?\"]",
        "//android.widget.TextView[@resource-id=\"com.instagram.android:id/igds_headline_headline\" and contains(@text, \"Enregistrer\")]",
    ],
    "auth.save_login_info_success_popup": [
        "//android.view.View[contains(@content-desc, \"Enregistrer vos informations\")]",
        "//android.view.View[contains(@text, \"Enregistrer vos informations\")]",
    ],
    "auth.signup_next_button": [
        "//android.widget.Button[@content-desc=\"Suivant\"]",
        "//android.view.View[@content-desc=\"Suivant\"]",
    ],
    "auth.two_factor_confirm_button": [
        "//android.widget.Button[contains(@text, \"Confirmer\")]",
        "//android.widget.Button[contains(@text, \"Suivant\")]",
    ],
    "auth.two_factor_indicators": [
        "//android.widget.TextView[contains(@text, \"code de sécurité\")]",
        "//android.widget.TextView[contains(@text, \"vérification\")]",
    ],
    "auth.use_another_profile_button": [
        "//android.widget.Button[@content-desc=\"Utiliser un autre profil\"]",
        "//*[contains(@text, \"Utiliser un autre profil\")]",
    ],
    "auth.username_clear_button": [
        "//android.widget.ImageView[contains(@content-desc, \"Vider\") and contains(@content-desc, \"Nom de profil\")]",
        "//android.widget.ImageView[contains(@content-desc, \"Effacer\") and contains(@content-desc, \"Nom de profil\")]",
    ],
    "auth.username_field": [
        "//android.widget.EditText[contains(@content-desc, \"Nom de profil, e-mail ou numéro de mobile\")]",
    ],
    # --- button ---
    "button.comment_button": [
        "//*[contains(@content-desc, \"Commentaire\")]",
    ],
    "button.like_button": [
        "//*[contains(@content-desc, \"J'aime\")]",
    ],
    "button.save_button": [
        "//*[contains(@content-desc, \"Ajouter aux enregistrements\")]",
    ],
    "button.share_button": [
        "//*[contains(@content-desc, \"Envoyer la publication\")]",
    ],
    # --- content_creation ---
    "content_creation.caption_placeholder_texts": [],
    "content_creation.create_button_texts": [
        "Créer",
    ],
    "content_creation.edit_video_indicators": [
        "Modifier la vidéo",
    ],
    "content_creation.location_button_texts": [],
    "content_creation.next_descriptions": [
        "Suivant",
    ],
    "content_creation.next_texts": [
        "Suivant",
    ],
    "content_creation.popup_button_texts": [],
    "content_creation.post_type_texts": [],
    "content_creation.publish_texts": [
        "Partager",
        "Publier",
    ],
    "content_creation.reel_draft_bodies": [
        "Si vous commencez une nouvelle vidÃ©o, ce brouillon sera enregistrÃ©.",
    ],
    "content_creation.reel_draft_headlines": [
        "Continuer la modification de votre brouillon ?",
    ],
    "content_creation.reel_draft_start_new_texts": [
        "Commencer une nouvelle vidÃ©o",
    ],
    "content_creation.story_publish_texts": [],
    # --- detection ---
    "detection.business_account_indicators": [
        "//*[contains(@text, \"Professionnel\")]",
    ],
    "detection.carousel_selectors": [],
    "detection.end_of_list_indicators": [
        "//*[contains(@text, \"Voir toutes les suggestions\")]",
        "//*[contains(@text, \"Aucun autre\")]",
    ],
    "detection.error_message_indicators": [
        "//*[contains(@text, \"Erreur\")]",
        "//*[contains(@text, \"Impossible\")]",
        "//*[contains(@text, \"Échec\")]",
        "//*[contains(@text, \"Réessayer\")]",
    ],
    "detection.followers_list_end_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/row_text_textview\" and contains(@text, \"Et \") and contains(@text, \" autres\")]",
    ],
    "detection.hashtag_page_indicators": [
        "//*[contains(@text, \"publications\")]",
    ],
    "detection.hashtag_search_bar_selectors": [
        "//android.widget.EditText[contains(@text, \"Rechercher\")]",
    ],
    "detection.home_screen_indicators": [
        "//*[contains(@content-desc, \"Accueil\") and @selected=\"true\"]",
    ],
    "detection.liked_button_indicators": [
        "//*[contains(@content-desc, \"Ne plus aimer\")]",
    ],
    "detection.likes_count_selectors": [
        "//*[contains(@content-desc, \"Nombre de J'aime\")]",
        "//android.widget.TextView[contains(@text, \"J'aime\")]",
    ],
    "detection.limited_followers_indicators": [
        "//*[contains(@text, \"Nous limitons le nombre\")]",
        "//*[contains(@text, \"nombre de followers affiché\")]",
    ],
    "detection.load_more_selectors": [
        "//*[contains(@text, \"Voir plus\")]",
        "//*[contains(@text, \"voir plus\")]",
        "//*[contains(@content-desc, \"Voir plus\")]",
    ],
    "detection.loading_spinner_indicators": [
        "//*[contains(@content-desc, \"Chargement\")]",
    ],
    "detection.login_required_indicators": [
        "//*[contains(@text, \"Se connecter\")]",
        "//*[contains(@text, \"Connexion\")]",
    ],
    "detection.own_profile_indicators": [
        "//*[@content-desc=\"Modifier le profil\"]",
        "//*[contains(@text, \"Modifier le profil\")]",
        "//*[contains(@text, \"Partager le profil\")]",
        "//*[@resource-id=\"com.instagram.android:id/button_container\" and @content-desc=\"Modifier le profil\"]",
    ],
    "detection.post_error_indicators": [
        "//*[contains(@text, \"Désolé\")]",
        "//*[contains(@text, \"introuvable\")]",
        "//*[contains(@text, \"indisponible\")]",
        "//*[contains(@text, \"privé\")]",
    ],
    "detection.post_screen_indicators": [],
    "detection.private_account_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/igds_headline_emphasized_headline\" and contains(@text, \"privé\")]",
        "//*[@resource-id=\"com.instagram.android:id/row_profile_header_empty_profile_notice_title\" and @text=\"Ce compte est privé\"]",
        "//*[contains(@text, \"Ce compte est privé\")]",
        "//*[contains(@content-desc, \"Ce compte est privé\")]",
    ],
    "detection.profile_screen_indicators": [
        "//*[@content-desc=\"Modifier le profil\"]",
        "//*[contains(@text, \"Modifier le profil\")]",
        "//*[@resource-id=\"com.instagram.android:id/profile_header_follow_button\" and contains(@text, \"Suivre\")]",
        "//*[@resource-id=\"com.instagram.android:id/profile_header_follow_button\" and contains(@text, \"Abonné\")]",
    ],
    "detection.rate_limit_indicators": [
        "//*[contains(@text, \"Trop de tentatives\")]",
        "//*[contains(@text, \"Veuillez patienter\")]",
        "//*[contains(@text, \"Action bloquée\")]",
    ],
    "detection.recent_tab_selectors": [
        "//android.widget.TextView[@text=\"Récent\"]",
        "//*[contains(@text, \"Récent\")]",
    ],
    "detection.reel_indicators": [
        "//*[contains(@content-desc, \"Reel de\")]",
    ],
    "detection.search_bar_selectors": [
        "//android.widget.EditText[contains(@text, \"Rechercher\")]",
    ],
    "detection.search_screen_indicators": [
        "//*[contains(@content-desc, \"Rechercher\") and @selected=\"true\"]",
        "//android.widget.TextView[@package=\"com.instagram.android\" and contains(@text, \"Rechercher\")]",
    ],
    "detection.suggestions_section_indicators": [
        "//*[contains(@text, \"Voir toutes les suggestions\")]",
        "//*[contains(@text, \"Suggestions pour vous\")]",
        "//*[@resource-id=\"com.instagram.android:id/row_header_textview\" and contains(@text, \"Suggestions pour vous\")]",
    ],
    "detection.verified_account_indicators": [
        "//*[contains(@content-desc, \"Vérifié\")]",
    ],
    # --- direct_message ---
    "direct_message.conversation_back_description_contains": [
        "Retour",
    ],
    "direct_message.conversation_back_descriptions": [],
    "direct_message.direct_tab_content_desc": [
        "//*[@content-desc=\"Envoyer un message\"]",
    ],
    "direct_message.direct_tab_content_descriptions": [
        "Envoyer un message",
    ],
    "direct_message.dm_inbox_description_contains": [
        "Envoyer un message",
    ],
    "direct_message.inbox_recommendation_texts": [
        "Suggestions pour vous",
    ],
    "direct_message.inbox_top_visible_texts": [
        "Rechercher",
    ],
    "direct_message.new_message_button": [
        "//*[@content-desc=\"Créer une publicité Envoyer un message\"]",
    ],
    "direct_message.outgoing_digest_prefixes": [],
    "direct_message.send_button": [
        "//*[contains(@content-desc, \"Envoyer\")]",
        "//android.widget.ImageButton[contains(@content-desc, \"Envoyer\")]",
    ],
    "direct_message.send_button_content_descriptions": [
        "Envoyer",
    ],
    "direct_message.send_button_descriptions": [
        "Envoyer",
    ],
    # --- feed ---
    "feed.already_liked_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/row_feed_button_like\" and contains(@content-desc, \"Ne plus aimer\")]",
        "//*[contains(@content-desc, \"Ne plus aimer\")]",
    ],
    "feed.comment_button": [
        "//*[contains(@content-desc, \"Commenter\")]",
    ],
    "feed.comment_input": [
        "//*[contains(@text, \"Ajouter un commentaire\")]",
    ],
    "feed.comment_send_button": [
        "//*[contains(@content-desc, \"Publier\")]",
    ],
    "feed.like_button": [
        "//*[contains(@content-desc, \"J'aime\")]",
    ],
    "feed.likes_count_button": [
        "//*[contains(@text, \"J'aime\")]",
    ],
    "feed.reel_indicators": [
        "//*[contains(@content-desc, \"Reel de\")]",
        "//*[contains(@content-desc, \"Réel de\")]",
    ],
    "feed.sponsored_indicators": [
        "//*[contains(@text, \"Sponsorisé\")]",
        "//*[contains(@text, \"Publicité\")]",
    ],
    # --- hashtag ---
    "hashtag.hashtag_header": [
        "//*[contains(@text, \"publications\")]",
    ],
    "hashtag.reel_author_container": [],
    # --- navigation ---
    "navigation.activity_tab": [
        "//*[contains(@content-desc, \"Activité\")]",
    ],
    "navigation.back_button": [
        "//*[contains(@content-desc, \"Retour\")]",
        "//*[contains(@content-desc, \"Précédent\")]",
    ],
    "navigation.back_buttons": [
        "//android.widget.ImageView[@content-desc=\"Retour\"]",
        "//*[@content-desc=\"Retour\"]",
        "//*[@content-desc=\"Précédent\"]",
    ],
    "navigation.close_button": [
        "//*[contains(@content-desc, \"Fermer\")]",
        "//*[contains(@content-desc, \"Annuler\")]",
    ],
    "navigation.explore_search_bar": [
        "//android.widget.TextView[contains(@text, \"Rechercher\")]",
        "//android.widget.EditText[contains(@hint, \"Rechercher\")]",
        "//*[contains(@content-desc, \"Rechercher\")]",
    ],
    "navigation.explore_search_bar_texts": [],
    "navigation.home_tab": [
        # not(systemui): le bouton Accueil de la barre de navigation Android
        # (com.android.systemui:id/home_button) a aussi content-desc "Accueil" ;
        # sans ce garde, en story plein ecran (pas de barre IG) le bot tapait le
        # bouton Home systeme -> sortie de l'app vers le launcher Android.
        "//*[contains(@content-desc, \"Accueil\") and not(@package=\"com.android.systemui\")]",
    ],
    "navigation.home_tab_description_contains": [],
    "navigation.home_tab_descriptions": [],
    "navigation.posts_tab_options": [],
    "navigation.profile_tab": [
        "//*[contains(@content-desc, \"Profil\") and contains(@class, \"ImageView\") and not(@package=\"com.android.systemui\")]",
        "//*[contains(@content-desc, \"Profil\") and not(@package=\"com.android.systemui\")]",
        "//*[contains(@resource-id, \"tab_bar_icon\") and contains(@content-desc, \"Profil\")]",
    ],
    "navigation.recent_tab_selectors": [
        "//*[contains(@text, \"Récents\")]",
        "//*[contains(@content-desc, \"Récents\")]",
    ],
    "navigation.search_tab": [
        "//*[contains(@content-desc, \"Rechercher\") and not(@package=\"com.android.systemui\")]",
    ],
    "navigation.search_tab_description_contains": [],
    "navigation.search_tab_descriptions": [],
    "navigation.top_tab_selectors": [
        "//*[contains(@text, \"Populaires\")]",
    ],
    # --- notification ---
    "notification.activity_entry": [
        "//*[contains(@content-desc, \"Notifications\")]",
    ],
    "notification.activity_tab": [
        "//*[contains(@content-desc, \"Activité\")]",
    ],
    "notification.notifications_screen_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/action_bar_title\" and @text=\"Notifications\"]",
    ],
    "notification.activity_screen_indicators": [
        "//*[contains(@text, \"Activité\")]",
    ],
    "notification.filter_button": [
        "//*[@resource-id=\"com.instagram.android:id/action_bar_button_action\" and @content-desc=\"Filtrer\"]",
        "//*[contains(@content-desc, \"Filtrer\")]",
        "//*[contains(@text, \"Filtrer\")]",
    ],
    "notification.inline_follow_request_text": [
        "//android.widget.TextView[contains(@text, \"a demandé à suivre votre compte\")]",
        "//android.widget.TextView[contains(@text, \"veut suivre votre compte\")]",
    ],
    "notification.inline_confirm_button": [
        "//*[@resource-id=\"com.instagram.android:id/igds_button\" and @text=\"Confirmer\"]",
        "//*[@resource-id=\"com.instagram.android:id/igds_button\" and contains(@text, \"Confirmer\")]",
    ],
    "notification.inline_dismiss_button": [
        "//android.widget.ImageView[@content-desc=\"Fermer\"]",
        "//*[contains(@content-desc, \"Fermer\")]",
    ],
    "notification.follow_requests_header": [
        "//*[contains(@resource-id, \"activity_feed_newsfeed_story_row\")][.//*[contains(@text, \"Demandes de suivi\")]]",
        "//*[contains(@text, \"Demandes de suivi\")]",
    ],
    # Raw text of the grouped follow-requests digest row (NOT an xpath) — used to
    # drop that digest row from the classified feed since requests are surfaced apart.
    "notification.follow_requests_digest": [
        "Demandes de suivi",
    ],
    # "Voir plus" button that loads older notifications (exact text to avoid the
    # inline "… plus" comment expander).
    "notification.show_more": [
        "//*[@text=\"Voir plus\"]",
        "//*[@text=\"Afficher plus\"]",
    ],
    # Header that marks the END of the pending follow-requests list on the
    # sub-screen (everything below is recommendations, not requests).
    "notification.suggested_for_you": [
        "//*[contains(@text, \"Suggestions pour vous\")]",
    ],
    "notification.follow_requests_section": [
        "//*[contains(@text, \"Demandes d'abonnement\")]",
    ],
    "notification.comment_mention_text": [
        "//android.widget.TextView[contains(@text, \"a mentionné votre nom dans un commentaire\")]",
    ],
    "notification.reply_button": [
        "//android.widget.Button[@text=\"Répondre\"]",
        "//*[contains(@text, \"Répondre\")]",
    ],
    # Bouton "J'aime" inline sur une ligne commentaire / mention (content-desc, PAS
    # un xpath — apparié par égalité EXACTE avec le content-desc d'un noeud pour que
    # l'état déjà-aimé "Bouton Je n'aime plus" ne matche pas et ne dé-like pas).
    "notification.inline_like_button": [
        "Bouton J'aime",
    ],
    "notification.comment_like_text": [
        "//android.widget.TextView[contains(@text, \"a aimé votre commentaire\")]",
    ],
    "notification.message_row_text": [
        "//android.widget.TextView[contains(@text, \"Vous avez un message de\")]",
    ],
    "notification.notification_action_text": [
        "//android.widget.TextView[contains(@text, \"aimé\")]",
        "//android.widget.TextView[contains(@text, \"a commencé\")]",
        "//android.widget.TextView[contains(@text, \"commenté\")]",
    ],
    "notification.notification_username": [
        "//android.widget.TextView[contains(@text, \"@\")]",
    ],
    "notification.follow_requests_screen_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/action_bar_title\" and @text=\"Contacts à découvrir\"]",
    ],
    "notification.request_accept_button": [
        "//*[@resource-id=\"com.instagram.android:id/row_requested_user_accept_secondary\" and @text=\"Confirmer\"]",
        "//*[@resource-id=\"com.instagram.android:id/row_requested_user_accept_secondary\" and contains(@text, \"Confirmer\")]",
    ],
    "notification.request_ignore_button": [
        "//*[@resource-id=\"com.instagram.android:id/row_requested_user_ignore\" and @text=\"Supprimer\"]",
        "//*[@resource-id=\"com.instagram.android:id/row_requested_user_ignore\" and contains(@text, \"Supprimer\")]",
    ],
    "notification.see_all_header": [
        "//*[@resource-id=\"com.instagram.android:id/row_header_action\" and contains(@text, \"Voir tout\")]",
        "//*[contains(@text, \"Voir tout\")]",
    ],
    # --- notification classifier text fragments (plain substrings, matched
    # case-insensitively via `contains` against an activity-feed row's text).
    # NOT XPath: these are the localized phrases that identify the row TYPE.
    # FR strings are best-known Instagram wording, to VALIDATE on device. ---
    "notification.type_comment_mention": [
        "a mentionné votre nom dans un commentaire",
        "vous a mentionné dans un commentaire",
        "vous a identifié dans un commentaire",
    ],
    "notification.type_comment_reply": [
        "a répondu à votre commentaire",
        "a répondu à votre comm",
    ],
    "notification.type_comment_like": [
        "a aimé votre commentaire",
    ],
    "notification.type_post_comment": [
        "a commenté votre publication",
        "a commenté votre photo",
        "a commenté votre vidéo",
        "a commenté",
    ],
    "notification.type_post_like": [
        "a aimé votre photo",
        "a aimé votre publication",
        "a aimé votre vidéo",
        "a aimé votre",
    ],
    "notification.type_new_follower": [
        "a commencé à vous suivre",
        "a commencé à suivre",
    ],
    "notification.type_follow_request": [
        "a demandé à suivre votre compte",
        "veut suivre votre compte",
        "a demandé à vous suivre",
    ],
    "notification.type_message": [
        "vous avez un message de",
        "message de",
    ],
    "notification.type_shared": [
        "a partagé une photo",
        "a publié un thread",
        "a partagé une publication",
        "a partagé",
    ],
    # --- popup ---
    "popup.automation_popup_indicators": [
        "//android.widget.TextView[@text='J'aime']",
        "//android.widget.EditText[contains(@text, 'Rechercher')]",
        "//android.widget.ImageView[@content-desc='Fermer']",
        "//android.widget.Button[@text='Suivre']",
    ],
    "popup.automation_user_selectors": [
        "//android.widget.LinearLayout[.//android.widget.TextView and .//android.widget.Button[@text='Suivre']]",
        "//android.view.ViewGroup[.//android.widget.TextView and .//android.widget.Button[@text='Suivre']]",
    ],
    "popup.close_popup_selectors": [
        "//android.widget.ImageView[@content-desc='Fermer']",
        "//android.widget.Button[@content-desc='Fermer']",
    ],
    "popup.comments_view_indicators": [
        "//*[@text=\"Commentaires\"]",
        "//*[contains(@text, \"Ajouter un commentaire\")]",
    ],
    "popup.follow_suggestions_close_methods": [
        "//*[contains(@content-desc, \"Fermer\")]",
    ],
    "popup.follow_suggestions_indicators": [],
    "popup.likers_popup_indicators": [
        "//*[contains(@text, \"J'aime\")]",
        "//*[contains(@text, \"En commun\")]",
    ],
    "popup.not_now_selectors": [
        "//android.widget.Button[contains(@text, \"Pas maintenant\")]",
        "//android.widget.TextView[contains(@text, \"Pas maintenant\")]",
    ],
    "popup.review_account_cancel_button": [
        "//android.widget.Button[@text=\"Annuler\"]",
        "//android.widget.TextView[@text=\"Annuler\"]",
    ],
    "popup.review_account_follow_button": [
        "//android.widget.Button[@text=\"Suivre\"]",
    ],
    "popup.review_account_popup_indicators": [],
    "popup.unfollow_confirmation_selectors": [
        "//*[contains(@text, \"Ne plus suivre\")]",
        "//*[contains(@text, \"Confirmer\")]",
    ],
    # --- post ---
    "post.automation_like_count_selectors": [
        "//android.widget.TextView[contains(@text, 'J'aime')]",
    ],
    "post.automation_like_indicators": [
        "//android.widget.TextView[contains(@text, 'J'aime') and (contains(@text, '1') or contains(@text, '2') or contains(@text, '3') or contains(@text, '4') or contains(@text, '5') or contains(@text, '6') or contains(@text, '7') or contains(@text, '8') or contains(@text, '9'))]",
    ],
    "post.automation_reel_specific_indicators": [
        "//android.widget.TextView[contains(@text, 'Audio original')]",
    ],
    "post.back_button_selectors": [],
    "post.classic_post_indicators": [
        "//android.widget.TextView[contains(@text, 'Voir les') and contains(@text, 'commentaire')]",
        "//android.widget.Button[@content-desc='Commenter']",
    ],
    "post.comment_button_indicators": [
        "//android.widget.Button[contains(@content-desc, 'commentaire')]",
    ],
    "post.comment_button_selectors": [
        "//android.widget.ImageView[contains(@content-desc, \"Commenter\")]",
    ],
    "post.comment_field_selectors": [
        "//*[contains(@hint, \"Ajouter un commentaire\")]",
    ],
    "post.comments_view_indicators": [],
    "post.copy_link_description_labels": [
        "Copier le lien",
    ],
    "post.copy_link_labels": [
        "Copier le lien",
    ],
    "post.like_button_advanced_selectors": [
        "//*[contains(@content-desc, \"J'aime\")][@clickable=\"true\"]",
    ],
    "post.like_button_indicators": [
        "//android.widget.Button[contains(@content-desc, 'aime')]",
        "//android.widget.ImageView[contains(@content-desc, 'aime')]",
    ],
    "post.like_count_selectors": [
        "//*[contains(@content-desc, \"J'aime\")]",
    ],
    "post.liked_by_selectors": [
        "//*[starts-with(@text, \"Aimé par\")]",
    ],
    "post.likes_count_click_selectors": [
        "//*[contains(@text, \"J'aime\")]",
    ],
    "post.next_post_button_selectors": [],
    "post.photo_comment_selectors": [
        "//*[@resource-id=\"com.instagram.android:id/row_feed_photo_imageview\" and contains(@content-desc, \"commentaire\")]",
        "//*[contains(@content-desc, \"J'aime\") and contains(@content-desc, \"commentaire\")]",
    ],
    "post.photo_like_selectors": [
        "//*[@resource-id=\"com.instagram.android:id/row_feed_photo_imageview\" and contains(@content-desc, \"J'aime\")]",
        "//*[contains(@content-desc, \"J'aime\") and contains(@content-desc, \"commentaire\")]",
    ],
    "post.post_comment_button_selectors": [
        "//*[@text=\"Publier\" and @clickable=\"true\"]",
        "//*[contains(@content-desc, \"Publier\") and @clickable=\"true\"]",
    ],
    "post.post_detail_indicators": [
        "//*[@content-desc=\"J'aime\"]",
        "//*[@content-desc=\"Commenter\"]",
        "//*[contains(@content-desc, \"aime\")]",
    ],
    "post.post_elements": [],
    "post.post_view_indicators": [],
    "post.reel_author_username_selectors": [],
    "post.reel_indicators": [
        "//*[contains(@content-desc, \"Reel de\")]",
    ],
    "post.reel_like_selectors": [
        "//android.widget.TextView[contains(@text, \"J'aime\")]",
    ],
    "post.reel_player_indicators": [
        "//*[@content-desc=\"Couper le son\"]",
        "//*[@content-desc=\"Activer le son\"]",
        "//*[contains(@content-desc, \"Musique\")]",
    ],
    "post.save_button_selectors": [
        "//android.widget.ImageView[contains(@content-desc, \"Enregistrer\")]",
    ],
    "post.send_post_button_selectors": [
        "//*[contains(@content-desc, \"Publier\")]",
        "//*[contains(@text, \"Publier\")]",
    ],
    "post.share_button_selectors": [
        "//android.widget.ImageView[contains(@content-desc, \"Partager\")]",
    ],
    "post.timestamp_selectors": [
        "//android.widget.TextView[contains(@content-desc, \"heure\")]",
        "//android.widget.TextView[contains(@content-desc, \"jour\")]",
        "//*[contains(@content-desc, \"heure\")]",
    ],
    "post.username_extraction_selectors": [
        "//android.widget.TextView[contains(@content-desc, \"nom d'utilisateur\")]",
    ],
    "post.video_controls": [],
    "post.video_player_selectors": [
        "//android.widget.ImageView[contains(@content-desc, \"vidéo\")]",
    ],
    # --- post_comments ---
    "post_comments.comment_composer_indicators": [
        "//*[contains(@hint, \"Ajouter un commentaire\")]",
    ],
    # --- post_grid ---
    "post_grid.back_button_selectors": [],
    "post_grid.next_post_button_selectors": [],
    # --- profile ---
    "profile.about_account_based_in_value": [
        "//*[contains(@content-desc, \"Compte basé\")]/android.view.View[2]",
    ],
    "profile.about_account_date_joined_value": [
        "//*[contains(@content-desc, \"Date d'inscription\")]/android.view.View[2]",
    ],
    "profile.about_account_page_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/action_bar_title\" and @text=\"À propos de ce compte\"]",
    ],
    "profile.advanced_follow_selectors": [
        "//android.widget.Button[@text=\"Suivre\" and not(contains(@content-desc, \"followers\")) and not(contains(@content-desc, \"following\"))]",
        "//android.widget.Button[contains(@content-desc, \"Suivre\") and not(contains(@content-desc, \"followers\"))]",
    ],
    "profile.follow_button": [
        "//*[contains(@text, \"Suivre\") and not(contains(@text, \"Abonné\"))]",
    ],
    "profile.follow_button_text_labels": [
        "Suivre",
    ],
    "profile.followers_link": [
        "//*[contains(@content-desc, \"abonnés\")]",
        "//*[contains(@content-desc, \"Abonnés\")]",
        "//android.view.ViewGroup[.//android.widget.TextView[contains(@text, \"abonnés\")]]",
        "//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, \"abonnés\")]]",
        "//android.widget.TextView[contains(@text, \"abonnés\")]",
        "//android.widget.TextView[contains(@text, \"Abonnés\")]",
    ],
    "profile.following_button": [
        "//*[contains(@text, \"Abonné\")]",
        "//*[contains(@text, \"Suivi(e)\")]",
    ],
    "profile.following_link": [
        "//*[contains(@content-desc, \"abonnements\")]",
        "//*[contains(@content-desc, \"Abonnements\")]",
        "//android.view.ViewGroup[.//android.widget.TextView[contains(@text, \"abonnements\")]]",
        "//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, \"abonnements\")]]",
        "//android.widget.TextView[contains(@text, \"abonnements\")]",
        "//android.widget.TextView[contains(@text, \"Abonnements\")]",
    ],
    "profile.message_button": [
        "//*[contains(@text, \"Envoyer un message\")]",
    ],
    "profile.message_button_text_labels": [
        "Envoyer un message",
    ],
    "profile.private_indicators": [
        "//*[contains(@text, \"privé\")]",
        "//*[contains(@text, \"Suivre pour voir\")]",
        "//*[contains(@content-desc, \"privé\")]",
    ],
    "profile.private_text_contains": [
        "compte est privé",
    ],
    "profile.zero_posts_indicators": [
        "//*[contains(@content-desc, \"0publications\")]",
        "//*[contains(@content-desc, \"0 publications\")]",
    ],
    # --- scroll ---
    "scroll.end_of_list_indicators": [
        "//*[contains(@text, \"Voir toutes les suggestions\")]",
        "//*[contains(@text, \"Aucun autre\")]",
    ],
    "scroll.load_more_selectors": [
        "//*[contains(@text, \"Voir plus\")]",
        "//*[contains(@text, \"voir plus\")]",
        "//*[contains(@content-desc, \"Voir plus\")]",
    ],
    # --- settings (Paramètres et activité -> Langue et traduction) ---
    "settings.language_and_translations_row": [
        "//*[@text=\"Langue et traduction\"]",
        "//*[contains(@text, \"Langue et traduction\")]",
    ],
    "settings.set_language_row": [
        "//*[@resource-id=\"com.instagram.android:id/row_simple_text_title\" and @text=\"Définir la langue\"]",
        "//*[@text=\"Définir la langue\"]",
    ],
    # --- text_input ---
    "text_input.bio_field_selectors": [
        "//*[contains(@hint, \"Biographie\")]",
    ],
    "text_input.caption_field_selectors": [
        "//*[contains(@hint, \"Écrivez une légende\")]",
    ],
    "text_input.comment_field_selectors": [
        "//*[contains(@hint, \"Ajouter un commentaire\")]",
    ],
    "text_input.send_button_selectors": [
        "//*[contains(@content-desc, \"Envoyer\")]",
    ],
    # --- unfollow ---
    "unfollow.follow_button_after_unfollow": [
        "//*[contains(@text, \"Suivre\") and not(contains(@text, \"Abonné\"))]",
    ],
    "unfollow.following_button": [
        "//*[contains(@text, \"Abonné\")]",
        "//*[contains(@text, \"Suivi(e)\")]",
        "//*[@resource-id=\"com.instagram.android:id/profile_header_follow_button\" and contains(@text, \"Abonné\")]",
    ],
    "unfollow.following_tab": [
        "//android.widget.Button[contains(@text, \"abonnements\")]",
        "//*[contains(@content-desc, \"abonnements\")]",
    ],
    "unfollow.follows_back_indicators": [
        "//*[contains(@text, \"Vous suit\")]",
        "//*[contains(@text, \"vous suit\")]",
        "//*[contains(@content-desc, \"Vous suit\")]",
    ],
    "unfollow.sort_button": [],
    "unfollow.sort_option_default": [],
    "unfollow.sort_option_earliest": [],
    "unfollow.sort_option_latest": [],
    "unfollow.unfollow_confirm": [
        "//*[contains(@text, \"Ne plus suivre\")]",
        "//android.widget.Button[contains(@text, \"Ne plus suivre\")]",
    ],
    # --- watchdog ---
    "watchdog.ok_button_texts": [
        "Fermer",
    ],
}
