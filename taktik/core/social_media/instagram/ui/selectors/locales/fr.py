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
        "//*[(contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\"))]",
    ],
    "button.save_button": [
        "//*[contains(@content-desc, \"Ajouter aux enregistrements\")]",
    ],
    # Raw LABELS of a post action bar buttons (NOT xpaths). Post scraping identifies a
    # counter by the button PRECEDING it, and used to read that button with hardcoded
    # English, so shares and saves came back as zero in every other language.
    # restaient donc a zero. Compares via `normalize_ui_label` (apostrophes repliees).
    "button.action_label_like": [
        "J'aime",
    ],
    "button.action_label_comment": [
        "Commentaire",
    ],
    "button.action_label_share": [
        "Envoyer la publication",
        "Partager",
    ],
    "button.action_label_save": [
        "Ajouter aux enregistrements",
        "Enregistrer",
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
        "Si vous commencez une nouvelle vidéo, ce brouillon sera enregistré.",
    ],
    "content_creation.reel_draft_headlines": [
        "Continuer la modification de votre brouillon ?",
    ],
    "content_creation.reel_draft_start_new_texts": [
        "Commencer une nouvelle vidéo",
    ],
    # Bouton de publication de l'editeur de story. La cle existait vide, et `L()` ne retombe
    # PAS sur l'anglais quand la cle est presente : sur un device FR `_publish_story()` cherchait
    # donc dans une liste vide et echouait au dernier tap. Le noeud n'a pas de resource-id (dump
    # reel `publish.tap_your_story`, IG v410) — seul le libelle permet de le viser.
    "content_creation.story_publish_texts": [
        "Votre story",
        "Partager",
    ],
    "content_creation.gallery_texts": [
        "Galerie",
    ],
    "content_creation.your_story_texts": [
        "Votre story",
    ],
    # Meme libelle sur le badge du tray (anneau vide) et sur la ligne de repartage externe
    # du share sheet — dump reel `post.open_share`, IG v410, device FR.
    "content_creation.add_to_story_texts": [
        "Ajouter à la story",
        "Ajouter a la story",
    ],
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
        "//*[(contains(@content-desc, \"Nombre de J'aime\") or contains(@content-desc, \"Nombre de J’aime\"))]",
        "//android.widget.TextView[(contains(@text, \"J'aime\") or contains(@text, \"J’aime\"))]",
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
    # PRESENCE prefixes: in a thread row the first content-desc segment is not always
    # the username — when the contact is online the row opens with their status
    # instead. This guard used to know only the English form, so other languages
    # returned the STATUS as the conversation name.
    "direct_message.presence_prefixes": [
        "En ligne",
        "Actif",
        "Active",
    ],
    "direct_message.message_system_text_fragments": [
        # Hints IG renders inside the thread; verified on a live fr-FR 442 device.
        "appuyez deux fois pour",
        "ajoutez à votre story",
        "balayez vers le haut",
        "a mentionné votre nom",
        "vous avez invité",
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
    # --- discover people (suggestions de comptes) ---
    # Raw LABELS (not xpaths): action-bar title of the suggestions screen.
    "discover_people.screen_title_texts": [
        "Découvrir des personnes",
        "Decouvrir des personnes",
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
        "//*[(contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\"))]",
    ],
    "feed.likes_count_button": [
        "//*[(contains(@text, \"J'aime\") or contains(@text, \"J’aime\"))]",
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
    # Header of the suggestions zone at the BOTTOM of the notifications screen. Raw
    # labels, not xpaths: the fields of that surface carry no resource-id, so the text
    # seul point d'ancrage possible.
    "notifications.suggestions_header_texts": [
        "Suggestions",
        "Suggestions pour vous",
    ],
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
        # not(systemui): the Android navigation bar home button also carries the same
        # (com.android.systemui:id/home_button) a aussi content-desc "Accueil" ;
        # content-desc, so without this guard, in a fullscreen story where the Instagram
        # bar is absent, the bot tapped it and dropped out to the Android launcher.
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
    # inline comment expander).
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
        "//*[(contains(@text, \"Demandes d'abonnement\") or contains(@text, \"Demandes d’abonnement\"))]",
    ],
    "notification.comment_mention_text": [
        "//android.widget.TextView[contains(@text, \"a mentionné votre nom dans un commentaire\")]",
    ],
    "notification.reply_button": [
        "//android.widget.Button[@text=\"Répondre\"]",
        "//*[contains(@text, \"Répondre\")]",
    ],
    # Inline like button on a comment / mention row (content-desc, NOT an xpath —
    # matched by EXACT equality against a node content-desc so the already-liked state
    # never matches and a like is never undone).
    "notification.inline_like_button": [
        "Bouton J'aime",
    ],
    # Inline reply LABEL on a comment / mention row (raw text, NOT an xpath — matched
    # by EXACT text equality to pair the reply button with its row by bounds, then
    # tapped to open the thread of that specific comment).
    "notification.reply_label": [
        "Répondre",
    ],
    # Inline follow-back LABEL on a "a commencé à vous suivre" row (raw text, NOT an
    # xpath — the igds_button container is empty, the label lives on a child TextView;
    # matched by EXACT text equality so the already-followed "Suivi(e)" state never
    # matches and a follow is never undone). From dump navigation.go_notifications
    # 2026-06-30 (FR, IG 410.0.0.53.71).
    "notification.inline_follow_back_button": [
        "Suivre en retour",
    ],
    # Inline truncation-expander WORD. A ClickableSpan with no node, so it is located
    # by OCR on the row crop (not an xpath) and tapped to reveal the full comment.
    #
    "notification.expander_words": [
        "suite", "plus",
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
        "//android.widget.TextView[(@text=\"J'aime\" or @text=\"J’aime\")]",
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
    # Raw LABELS (not xpaths): proof that the alert on screen really is the contacts
    # access request and not another alert carrying the same resource-ids.
    "popup.contacts_access_headline_texts": [
        "accéder à vos contacts",
        "acceder a vos contacts",
        "synchroniser vos contacts",
    ],
    "popup.follow_suggestions_close_methods": [
        "//*[contains(@content-desc, \"Fermer\")]",
    ],
    "popup.follow_suggestions_indicators": [],
    "popup.likers_popup_indicators": [
        "//*[(contains(@text, \"J'aime\") or contains(@text, \"J’aime\"))]",
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
        "//android.widget.TextView[(contains(@text, \"J'aime\") or contains(@text, \"J’aime\"))]",
    ],
    "post.automation_like_indicators": [
        "//android.widget.TextView[(contains(@text, \"J'aime\") or contains(@text, \"J’aime\")) and (contains(@text, '1') or contains(@text, '2') or contains(@text, '3') or contains(@text, '4') or contains(@text, '5') or contains(@text, '6') or contains(@text, '7') or contains(@text, '8') or contains(@text, '9'))]",
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
        "//*[(contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\"))][@clickable=\"true\"]",
    ],
    "post.like_button_indicators": [
        "//android.widget.Button[contains(@content-desc, 'aime')]",
        "//android.widget.ImageView[contains(@content-desc, 'aime')]",
    ],
    # The app renders a TYPOGRAPHIC apostrophe, so matching a straight one finds nothing.
    # Matching AROUND the apostrophe avoids the question. The two fragments together are
    # what identify the COUNTER: they exclude the comment counter, the like button and the
    # already-liked state. A consumer clicks this list without validating it, so widening
    # the match would like the post instead of opening the list.
    "post.like_count_selectors": [
        "//*[contains(@content-desc, \"Nombre de \") and contains(@content-desc, \"aime\")]",
    ],
    "post.liked_by_selectors": [
        "//*[starts-with(@text, \"Aimé par\")]",
    ],
    "post.likes_count_click_selectors": [
        "//*[(contains(@text, \"J'aime\") or contains(@text, \"J’aime\"))]",
    ],
    "post.next_post_button_selectors": [],
    "post.photo_comment_selectors": [
        "//*[@resource-id=\"com.instagram.android:id/row_feed_photo_imageview\" and contains(@content-desc, \"commentaire\")]",
        "//*[(contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\")) and contains(@content-desc, \"commentaire\")]",
    ],
    "post.photo_like_selectors": [
        "//*[@resource-id=\"com.instagram.android:id/row_feed_photo_imageview\" and (contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\"))]",
        "//*[(contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\")) and contains(@content-desc, \"commentaire\")]",
    ],
    "post.post_comment_button_selectors": [
        "//*[@text=\"Publier\" and @clickable=\"true\"]",
        "//*[contains(@content-desc, \"Publier\") and @clickable=\"true\"]",
    ],
    "post.post_detail_indicators": [
        "//*[(@content-desc=\"J'aime\" or @content-desc=\"J’aime\")]",
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
        "//android.widget.TextView[(contains(@text, \"J'aime\") or contains(@text, \"J’aime\"))]",
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
        "//android.widget.TextView[(contains(@content-desc, \"nom d'utilisateur\") or contains(@content-desc, \"nom d’utilisateur\"))]",
    ],
    "post.video_controls": [],
    "post.video_player_selectors": [
        "//android.widget.ImageView[contains(@content-desc, \"vidéo\")]",
    ],
    # --- post_comments ---
    "post_comments.comment_composer_indicators": [
        "//*[contains(@hint, \"Ajouter un commentaire\")]",
    ],
    # Heart control of a comment row, NOT-LIKED state (raw text, NOT an xpath —
    # matched by CONTAINMENT against the node content-desc).
    # IG 442 prefixe le corps du commentaire par "<pseudo> a dit ". Fragment retire a la lecture.
    # IG 442 rebuilt the feed suggestions carousel in Compose: no resource-id survives, so
    # the header/CTA pair is the only handle left. Paired on one row, never alone.
    "feed_suggestions.carousel_title_texts": [
        "Suggestions pour vous",
        "Suggestions pour toi",
    ],
    "feed_suggestions.carousel_cta_texts": [
        "Voir tout",
        "Tout afficher",
    ],
    "post_comments.comment_empty_state_texts": [
        "Aucun commentaire",
    ],
    "post_comments.comment_said_connectors": [
        "a dit",
    ],
    "post_comments.comment_like_button": [
        "aimer le commentaire",
    ],
    # Same control, ALREADY-LIKED state. Tested FIRST and taking priority: the
    # already-liked label CONTAINS the fragment above, so testing the positive one
    # first would tap an already-liked comment and silently UNLIKE it.
    "post_comments.comment_unlike_button": [
        "ne plus aimer le commentaire",
    ],
    # --- post_grid ---
    "post_grid.back_button_selectors": [],
    "post_grid.next_post_button_selectors": [],
    # --- profile ---
    "profile.about_account_based_in_value": [
        "//*[contains(@content-desc, \"Compte basé\")]/android.view.View[2]",
    ],
    "profile.about_account_date_joined_value": [
        "//*[(contains(@content-desc, \"Date d'inscription\") or contains(@content-desc, \"Date d’inscription\"))]/android.view.View[2]",
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
    # STATE labels of the profile header action button. These are raw LABELS, not
    # xpaths: the read makes a single device access, since the button is already
    # targeted by resource-id, then compares its text.
    # The stems are deliberately short so they absorb the inflected variants.
    # WARNING: the test order carries meaning on the code side.
    # follow) because the follow-back label contains the follow one.
    # Tested BEFORE every other family: the unfollow label CONTAINS the follow one in
    # both languages. Without this family the unfollow button read as a follow button —
    # harmless on the profile header, where the resource-id scopes it, but not on a
    # list row, where it would have been tapped.
    "profile.follow_state_labels_unfollow": [
        "Ne plus suivre",
        "Se désabonner",
        "Se desabonner",
    ],
    "profile.follow_state_labels_following": [
        "Abonné",
        "Suivi",
    ],
    "profile.follow_state_labels_requested": [
        "Demandé",
    ],
    "profile.follow_state_labels_follow_back": [
        "Suivre en retour",
        # The French app alternates between two verb families depending on the surface and
        # the version. The second one was missing, so one of the follow-back buttons
        # matched no label at all: the row state stayed empty and the row was skipped
        # silently.
        "S'abonner en retour",
    ],
    "profile.follow_state_labels_follow": [
        "Suivre",
        "S'abonner",
    ],
    "profile.followers_link": [
        "//*[contains(@content-desc, \"abonnés\")]",
        "//*[contains(@content-desc, \"Abonnés\")]",
        "//android.view.ViewGroup[.//android.widget.TextView[contains(@text, \"abonnés\")]]",
        "//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, \"abonnés\")]]",
        "//android.widget.TextView[contains(@text, \"abonnés\")]",
        "//android.widget.TextView[contains(@text, \"Abonnés\")]",
    ],
    # SCOPE: a bare text match also caught profile_header_follow_context_text (the
    # mutual-friends line), a NON-clickable TextView sitting above the button ->
    # click_unfollow_button could tap that label. Scoped by resource-id first, then
    # falls back on the Button class (the decoy is a TextView).
    "profile.following_button": [
        "//*[@resource-id=\"com.instagram.android:id/profile_header_follow_button\" and contains(@text, \"Abonné\")]",
        "//*[@resource-id=\"com.instagram.android:id/profile_header_follow_button\" and contains(@text, \"Suivi\")]",
        "//*[@resource-id=\"com.instagram.android:id/follow_button\" and contains(@text, \"Abonné\")]",
        "//*[@resource-id=\"com.instagram.android:id/follow_button\" and contains(@text, \"Suivi\")]",
        "//android.widget.Button[contains(@text, \"Abonné\")]",
        "//android.widget.Button[contains(@text, \"Suivi\")]",
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
    # Bio truncation-expander word (raw text for OCR, NOT an xpath).
    "profile.bio_more_words": [
        "plus", "suite",
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
    # --- settings (settings and activity -> language and translations) ---
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
    # --- text ---
    # Bare labels that a username extractor can pick up by mistake when it reads the
    # wrong node: the row shows "Suivre" or "J'aime", not a handle. Compared through
    # `normalize_ui_label` (apostrophe shapes folded), so the straight form is enough.
    "text.not_a_username": [
        "J'aime",
        "Je n'aime plus",
        "Commentaire",
        "Commentaires",
        "Vues",
        "Suivre",
        "Suivi(e)",
        "Abonné",
        "Abonnés",
        "Abonnements",
        "Partager",
    ],
    # --- watchdog ---
    "watchdog.ok_button_texts": [
        "Fermer",
    ],
}
