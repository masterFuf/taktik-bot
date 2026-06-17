"""French (fr) UI string overlay for TikTok selectors.

ONE module per language. Holds ONLY the language-specific selector fragments
(``@text`` / ``@content-desc`` / ``@hint`` / bare labels) keyed by
``"<surface>.<field>"``. Language-neutral selectors (resource-id / class /
position) live in the selector dataclasses under ``ui/selectors/**`` and are
combined with these via ``L(key)`` (see ``locales/__init__.py``).

Provenance: fragments extracted from the historical EN/FR selector lists
(real device dumps).
"""
from typing import Dict, List

STRINGS: Dict[str, List[str]] = {
    # --- auth ---
    "auth.login_button": [
        "//android.widget.Button[@content-desc=\"Se connecter\"]",
        "//android.widget.Button[contains(@text, \"Se connecter\")]",
    ],
    "auth.login_screen_indicators": [],
    "auth.password_field": [
        "//android.widget.EditText[contains(@content-desc, \"Mot de passe\")]",
    ],
    "auth.username_field": [
        "//android.widget.EditText[contains(@content-desc, \"E-mail ou nom d'utilisateur\")]",
    ],
    # --- comment ---
    "comment.comment_input": [
        "//android.widget.EditText[contains(@content-desc, \"Ajouter un commentaire\")]",
    ],
    "comment.post_comment_button": [
        "//android.widget.Button[contains(@content-desc, \"Publier\")]",
    ],
    # --- conversation ---
    "conversation.back_button": [],
    "conversation.close_sticker_suggestion": [],
    "conversation.reply_button": [],
    # --- country_picker ---
    "country_picker.close_button": [],
    "country_picker.screen_indicator": [],
    "country_picker.search_input": [],
    # --- detection ---
    "detection.error_message": [
        "//android.widget.TextView[contains(@text, \"erreur\")]",
    ],
    "detection.network_error": [
        "//android.widget.TextView[contains(@text, \"réseau\")]",
    ],
    "detection.rate_limit": [
        "//android.widget.TextView[contains(@text, \"trop de\")]",
    ],
    # --- followers ---
    "followers.follower_follow_button": [],
    "followers.follower_following_button": [],
    "followers.followers_counter": [],
    "followers.followers_tab": [],
    "followers.followers_tab_selected": [],
    "followers.following_counter": [],
    "followers.following_list_opener": [],
    "followers.following_or_friends_button": [],
    "followers.following_tab": [],
    "followers.profile_follow_button": [],
    "followers.profile_reposted_tab": [],
    "followers.profile_videos_tab": [],
    "followers.unfollow_confirm_button": [],
    # --- inbox ---
    "inbox.accept_request_button": [
        "//android.widget.Button[@text=\"Accepter\"]",
        "//*[@text=\"Accepter\"]",
    ],
    "inbox.activity_section": [
        "//*[contains(@resource-id, \":id/b8h\")][@text=\"Activité\"]",
        "//*[@text=\"Activité\"]",
    ],
    "inbox.activity_status": [
        "//*[contains(@content-desc, \"Statut d'activité\")]",
    ],
    "inbox.add_people_button": [
        "//android.widget.ImageView[@content-desc=\"Ajouter des personnes\"]",
    ],
    "inbox.decline_request_button": [
        "//android.widget.Button[@text=\"Supprimer\"]",
    ],
    "inbox.follow_back_button": [
        "//android.widget.Button[@text=\"Suivre en retour\"]",
        "//*[@text=\"Suivre en retour\"]",
    ],
    "inbox.inbox_title": [],
    "inbox.message_requests_page_title": [
        "//*[contains(@resource-id, \":id/nmh\")][contains(@text, \"Demandes de messages\")]",
    ],
    "inbox.message_requests_section": [
        "//*[contains(@text, \"Demandes de messages\")]",
    ],
    "inbox.new_followers_section": [
        "//*[contains(@resource-id, \":id/b8h\")][@text=\"Nouveaux followers\"]",
        "//*[contains(@resource-id, \":id/b8h\")][@text=\"Nouveaux abonnés\"]",
        "//*[@text=\"Nouveaux followers\"]",
        "//*[@text=\"Nouveaux abonnés\"]",
    ],
    "inbox.search_inbox_button": [
        "//android.widget.ImageView[@content-desc=\"Rechercher\"]",
    ],
    "inbox.see_all_button": [
        "//*[@text=\"Tout voir\"]",
    ],
    "inbox.seen_marker": [
        "//*[contains(@resource-id, \":id/l35\")][@text=\"Vu\"]",
        "//*[contains(@resource-id, \":id/l35\")][starts-with(@text, \"Vu\")]",
    ],
    "inbox.suggested_accounts_section": [
        "//*[@text=\"Comptes suggérés\"]",
    ],
    "inbox.system_notifications_section": [
        "//*[contains(@resource-id, \":id/b8h\")][@text=\"Notifications système\"]",
        "//*[@text=\"Notifications système\"]",
    ],
    # --- logout ---
    "logout.logout_button": [
        "//*[@text=\"Se déconnecter\"]",
        "//*[@text=\"Déconnexion\"]",
    ],
    "logout.logout_confirm_button": [],
    "logout.profile_menu_button": [],
    "logout.profile_tab": [],
    # --- navigation ---
    "navigation.back_button": [
        "//android.widget.ImageButton[@content-desc=\"Retour\"]",
    ],
    "navigation.create_button": [
        "//android.widget.Button[contains(@content-desc, \"Créer\")]",
    ],
    "navigation.explore_tab": [
        "//*[contains(@content-desc, \"Explorer\")]",
    ],
    "navigation.following_tab": [
        "//*[contains(@content-desc, \"Abonnements\")]",
    ],
    "navigation.friends_tab": [
        "//android.widget.FrameLayout[contains(@content-desc, \"Amis\")]",
    ],
    "navigation.home_tab": [
        "//android.widget.FrameLayout[contains(@content-desc, \"Accueil\")]",
    ],
    "navigation.home_tab_selected": [],
    "navigation.inbox_tab": [
        "//android.widget.FrameLayout[contains(@content-desc, \"Boîte de réception\")]",
    ],
    "navigation.inbox_tab_selected": [],
    "navigation.profile_tab": [
        "//android.widget.FrameLayout[contains(@content-desc, \"Profil\")]",
    ],
    "navigation.search_button": [
        "//*[contains(@content-desc, \"Rechercher\")][@clickable=\"true\"]",
    ],
    "navigation.shop_tab": [],
    # --- popup ---
    "popup.age_verification_popup": [
        "//*[contains(@text, \"âge\")]",
    ],
    "popup.close_button": [
        "//android.widget.ImageButton[@content-desc=\"Fermer\"]",
    ],
    "popup.collections_close": [],
    "popup.collections_not_now": [],
    "popup.collections_popup": [],
    "popup.comment_input_area": [],
    "popup.comments_close_button": [],
    "popup.dismiss_button": [
        "//android.widget.Button[contains(@text, \"Pas maintenant\")]",
    ],
    "popup.follow_friends_close": [],
    "popup.follow_friends_popup": [
        "//*[contains(@text, \"Suivez vos amis\")]",
    ],
    "popup.inbox_page_indicator": [],
    "popup.link_email_not_now": [
        "//*[@text=\"Pas maintenant\"][@clickable=\"true\"]",
    ],
    "popup.notification_banner": [
        "//*[contains(@text, \"Répondre\")][@clickable=\"true\"]",
    ],
    "popup.notification_popup": [
        "//*[contains(@text, \"Autoriser\")]",
    ],
    "popup.promo_close_button": [],
    "popup.suggestion_close": [],
    "popup.suggestion_follow_back": [],
    "popup.suggestion_not_interested": [],
    "popup.system_deny_button": [
        "//*[@text=\"REFUSER\"][@clickable=\"true\"]",
        "//*[@text=\"Refuser\"][@clickable=\"true\"]",
        "//*[@text=\"Ne pas autoriser\"][@clickable=\"true\"]",
        "//*[@text=\"Non\"][@clickable=\"true\"]",
    ],
    # --- profile ---
    "profile.create_story_button": [
        "//*[contains(@content-desc, \"Créer une Story\")]",
    ],
    "profile.edit_profile_button": [
        "//android.widget.Button[@text=\"Modifier\"]",
    ],
    "profile.favourites_tab": [
        "//*[contains(@content-desc, \"Favoris\")]",
    ],
    "profile.follow_button": [
        "//android.widget.Button[@text=\"Suivre\"]",
    ],
    "profile.followers_count": [],
    "profile.following_button": [
        "//android.widget.Button[@text=\"Abonné\"]",
    ],
    "profile.following_count": [],
    "profile.liked_videos_tab": [
        "//*[contains(@content-desc, \"Vidéos aimées\")]",
    ],
    "profile.likes_count": [],
    "profile.privacy_blocked_message": [],
    "profile.private_indicator": [],
    "profile.private_videos_tab": [
        "//*[contains(@content-desc, \"Vidéos privées\")]",
    ],
    "profile.profile_menu_button": [
        "//*[contains(@content-desc, \"Menu du profil\")]",
    ],
    "profile.profile_page_indicator": [],
    "profile.profile_photo": [
        "//*[contains(@content-desc, \"Photo de profil\")]",
    ],
    "profile.profile_views_button": [],
    "profile.story_close_button": [],
    "profile.unable_to_send_message": [],
    "profile.verified_badge": [],
    "profile.videos_tab": [
        "//*[contains(@content-desc, \"Vidéos\")]",
    ],
    # --- publish_composer ---
    "publish_composer.caption_input": [
        "//android.widget.EditText[contains(@hint, \"Ajouter une description\")]",
        "//android.widget.EditText[contains(@text, \"Ajouter une description\")]",
        "//android.widget.EditText[contains(@content-desc, \"Ajouter une description\")]",
    ],
    "publish_composer.post_btn": [
        "//android.widget.Button[contains(@text, \"Publier\")]",
        "//android.widget.TextView[contains(@text, \"Publier\")]",
    ],
    "publish_composer.post_screen_xml_markers": [
        "ajouter une description",
    ],
    "publish_composer.publish_confirm_btn": [
        "//android.widget.Button[@text=\"Publier maintenant\"]",
        "//android.widget.Button[contains(@text, \"Publier\")]",
    ],
    "publish_composer.publish_confirm_dialog": [
        "//*[contains(@resource-id, \":id/w4m\")][contains(@text, \"Publier la vidéo publiquement\")]",
        "//*[contains(@text, \"Publier la vidéo publiquement\")]",
    ],
    # --- publish_creation_entry ---
    "publish_creation_entry.create_btn": [
        "//android.widget.Button[contains(@content-desc, \"Créer\")]",
    ],
    "publish_creation_entry.home_ready_indicators": [
        "//android.widget.Button[contains(@content-desc, \"Créer\")]",
    ],
    # --- publish_editor ---
    "publish_editor.popup_cancel_buttons": [
        "//android.widget.Button[contains(@text, \"Annuler\")]",
        "//android.widget.Button[contains(@text, \"Non merci\")]",
    ],
    "publish_editor.video_edit_cancel_btn": [
        "//android.widget.Button[@text=\"Annuler\"]",
        "//android.widget.TextView[@text=\"Annuler\"]",
    ],
    # --- publish_media_picker ---
    "publish_media_picker.next_btn": [
        "//android.widget.Button[contains(@text, \"Suivant\")]",
        "//android.widget.TextView[contains(@text, \"Suivant\")]",
    ],
    "publish_media_picker.upload_btn": [
        "//*[contains(@text, \"Importer\")]",
        "//*[contains(@text, \"Galerie\")]",
    ],
    # --- publish_progress ---
    "publish_progress.success_indicator": [
        "//*[contains(@text, \"publié\")]",
        "//*[contains(@text, \"succès\")]",
    ],
    # --- scroll ---
    "scroll.end_of_list": [
        "//android.widget.TextView[contains(@text, \"Plus de\")]",
    ],
    # --- search ---
    "search.search_bar": [
        "//android.widget.EditText[contains(@content-desc, \"Rechercher\")]",
    ],
    "search.search_button": [
        "//android.widget.Button[contains(@content-desc, \"Rechercher\")]",
    ],
    "search.search_icon": [
        "//*[contains(@content-desc, \"Rechercher\")]",
    ],
    "search.search_input": [
        "//android.widget.EditText[contains(@hint, \"Rechercher\")]",
    ],
    "search.search_submit_button": [
        "//android.widget.Button[@text=\"Rechercher\"]",
    ],
    "search.shop_tab": [],
    "search.sounds_tab": [
        "//android.widget.TextView[@text=\"Sons\"]",
    ],
    "search.user_result_follow_button": [],
    "search.videos_tab": [
        "//android.widget.TextView[@text=\"Vidéos\"]",
    ],
    "search.view_all_button": [],
    # --- signup ---
    "signup.back_button": [
        "//android.widget.Button[@content-desc=\"Retour à l'écran précédent\"]",
    ],
    "signup.birthday_continue_button": [
        "//android.widget.Button[@text=\"Continuer\"]",
    ],
    "signup.birthday_day_picker": [
        "//android.widget.SeekBar[@content-desc=\"Sélecteur du jour\"]",
    ],
    "signup.birthday_gate_inscription_link": [
        "//android.widget.Button[contains(@text, \"fonctionnalités\") and contains(@text, \"Inscription\")]",
        "//android.widget.Button[contains(@text, \"Inscription\")]",
        "//*[@clickable=\"true\" and contains(@text, \"Inscription\")]",
    ],
    "signup.birthday_input": [
        "//android.widget.EditText[contains(@hint, \"naissance\")]",
    ],
    "signup.birthday_month_picker": [
        "//android.widget.SeekBar[@content-desc=\"Sélecteur du mois\"]",
    ],
    "signup.birthday_screen_indicator": [
        "//android.widget.TextView[contains(@text, \"date de naissance\")]",
        "//android.widget.TextView[contains(@text, \"naissance\")]",
        "//android.widget.TextView[contains(@text, \"anniversaire\")]",
    ],
    "signup.birthday_year_picker": [
        "//android.widget.SeekBar[@content-desc=\"Sélecteur de l'année\"]",
    ],
    "signup.continue_button": [
        "//android.widget.Button[@text=\"Continuer\"]",
    ],
    "signup.email_input": [
        "//android.widget.EditText[@hint=\"Adresse e-mail\"]",
    ],
    "signup.nickname_continue_button": [
        "//android.widget.Button[@text=\"Continuer\"]",
    ],
    "signup.nickname_entry_indicator": [
        "//android.widget.TextView[contains(@resource-id, \":id/e_c\") and contains(@text, \"surnom\")]",
        "//android.widget.TextView[contains(@text, \"Créer un surnom\")]",
    ],
    "signup.nickname_input": [
        "//android.widget.EditText[@hint=\"Ajoute ton surnom\"]",
        "//android.widget.EditText[contains(@hint, \"surnom\")]",
    ],
    "signup.nickname_skip_button": [
        "//android.widget.Button[@text=\"Ignorer\"]",
    ],
    "signup.otp_continue_button": [
        "//android.widget.Button[@text=\"Continuer\"]",
    ],
    "signup.otp_resend_button": [
        "//*[contains(@text, \"Renvoyer\") and contains(@text, \"code\")]",
    ],
    "signup.otp_screen_indicator": [
        "//android.widget.TextView[contains(@text, \"Consulte tes e-mails\")]",
        "//android.widget.TextView[contains(@text, \"Utilise le lien ou code\")]",
        "//android.widget.TextView[contains(@text, \"code de vérification\")]",
        "//android.widget.TextView[contains(@text, \"Entrez le code\")]",
        "//android.widget.TextView[contains(@text, \"Saisir le code\")]",
        "//*[contains(@text, \"Renvoyer un code\")]",
    ],
    "signup.password_continue_button": [
        "//android.widget.Button[@text=\"Continuer\"]",
    ],
    "signup.password_entry_indicator": [
        "//android.widget.TextView[contains(@resource-id, \":id/e_c\") and contains(@text, \"mot de passe\")]",
        "//android.widget.TextView[contains(@text, \"Créer un mot de passe\")]",
    ],
    "signup.password_input": [
        "//android.widget.EditText[@hint=\"Saisis le mot de passe\"]",
        "//android.widget.EditText[contains(@hint, \"mot de passe\")]",
    ],
    "signup.password_skip_button": [
        "//android.widget.Button[@text=\"Ignorer\"]",
    ],
    "signup.phone_input": [
        "//android.widget.EditText[@hint=\"Numéro de téléphone\"]",
    ],
    "signup.register_screen_indicator": [
        "//android.widget.TextView[@content-desc=\"Inscription\"]",
        "//android.widget.TextView[@text=\"Inscription\"]",
    ],
    "signup.signup_link": [
        "//android.widget.Button[contains(@text, \"Inscription\")]",
    ],
    "signup.signup_popup_indicator": [
        "//android.widget.TextView[contains(@resource-id, \":id/title\") and contains(@text, \"Inscription\")]",
        "//android.widget.TextView[contains(@text, \"Inscription\") and contains(@text, \"TikTok\")]",
        "//*[@content-desc=\"Utiliser un numéro de téléphone ou une adresse e-mail\"]",
    ],
    "signup.tab_email": [
        "//*[@content-desc=\"E-mail\" and @clickable=\"true\"]",
        "//android.widget.LinearLayout[@content-desc=\"E-mail\"]",
    ],
    "signup.tab_phone": [
        "//*[@content-desc=\"Téléphone\" and @clickable=\"true\"]",
        "//android.widget.LinearLayout[@content-desc=\"Téléphone\"]",
    ],
    "signup.use_phone_or_email_button": [
        "//*[@content-desc=\"Utiliser un numéro de téléphone ou une adresse e-mail\"]",
    ],
    # --- video_creator ---
    "video_creator.creator_profile_image": [
        "//android.widget.ImageView[contains(@content-desc, \"Profil\")]",
    ],
    "video_creator.follow_button": [
        "//android.widget.Button[contains(@content-desc, \"Suivre\")]",
    ],
    # --- video_engagement ---
    "video_engagement.comment_button": [
        "//*[contains(@content-desc, \"Lire ou ajouter des commentaires\")]",
    ],
    "video_engagement.comment_button_for_count": [
        "//*[contains(@content-desc, \"commentaires\")]",
    ],
    "video_engagement.favorite_button": [
        "//*[contains(@content-desc, \"Ajoute ou supprime cette vidéo de tes Favoris\")]",
    ],
    "video_engagement.like_button": [
        "//*[@resource-id=\"com.zhiliaoapp.musically:id/f57\"][contains(@content-desc, \"Attribuer un\")]",
        "//*[@resource-id=\"com.ss.android.ugc.trill:id/f57\"][contains(@content-desc, \"Attribuer un\")]",
        "//*[@resource-id=\"com.ss.android.ugc.aweme:id/f57\"][contains(@content-desc, \"Attribuer un\")]",
        "//android.widget.Button[contains(@content-desc, \"Attribuer un\")]",
        "//*[contains(@content-desc, \"Attribuer un\")]",
    ],
    "video_engagement.like_button_content_desc_fallbacks": [
        "//*[contains(@content-desc, \"Attribuer un\")]",
    ],
    "video_engagement.like_button_for_count": [
        "//*[@resource-id=\"com.zhiliaoapp.musically:id/f57\"][contains(@content-desc, \"Attribuer un\")]",
        "//*[@resource-id=\"com.ss.android.ugc.trill:id/f57\"][contains(@content-desc, \"Attribuer un\")]",
        "//*[@resource-id=\"com.ss.android.ugc.aweme:id/f57\"][contains(@content-desc, \"Attribuer un\")]",
        "//*[contains(@content-desc, \"Attribuer un\")]",
    ],
    "video_engagement.share_button": [],
    # --- video_media ---
    "video_media.sound_button": [
        "//android.widget.Button[contains(@content-desc, \"Son :\")]",
    ],
    # --- video_state ---
    "video_state.ad_label": [
        "//android.widget.TextView[@text=\"Sponsorise\"]",
        "//android.widget.TextView[@text=\"Publicite\"]",
    ],
    "video_state.like_button_unliked": [
        "//*[@resource-id=\"com.zhiliaoapp.musically:id/f57\"][contains(@content-desc, \"Attribuer un\")]",
        "//*[@resource-id=\"com.ss.android.ugc.trill:id/f57\"][contains(@content-desc, \"Attribuer un\")]",
        "//*[@resource-id=\"com.ss.android.ugc.aweme:id/f57\"][contains(@content-desc, \"Attribuer un\")]",
        "//*[contains(@content-desc, \"Attribuer un\")]",
    ],
    "video_state.subscribe_button": [],
    "video_state.unlike_indicator": [
        "//*[contains(@content-desc, \"Retirer\") and contains(@content-desc, \"J'aime\")]",
        "//*[contains(@content-desc, \"Supprimer\") and contains(@content-desc, \"J'aime\")]",
    ],
    "video_state.user_followed_indicator": [],
    "video_state.video_already_liked": [
        "//*[contains(@content-desc, \"Retirer\") and contains(@content-desc, \"J'aime\")]",
        "//*[contains(@content-desc, \"Supprimer\") and contains(@content-desc, \"J'aime\")]",
    ],
    "video_state.video_favorited_indicator": [
        "//*[contains(@content-desc, \"Retirer des favoris\")]",
    ],
    "video_state.video_liked_indicator": [
        "//*[contains(@content-desc, \"Retirer\") and contains(@content-desc, \"J'aime\")]",
        "//*[contains(@content-desc, \"Supprimer\") and contains(@content-desc, \"J'aime\")]",
    ],
    "video_state.video_page_indicator": [],
}
