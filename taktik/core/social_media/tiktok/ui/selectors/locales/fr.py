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
        "//android.widget.EditText[(contains(@content-desc, \"E-mail ou nom d'utilisateur\") or contains(@content-desc, \"E-mail ou nom d’utilisateur\"))]",
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
    # Measured on device (43.1.4, 2026-08-29): opening a conversation raised a MODAL
    # "Statut de lecture" sheet that replaced the whole hierarchy, so the open was reported as
    # failed. Both anchors are SCOPED to the sheet container: a bare clickable "Fermer" was
    # tested against 25 captured screens and fires on the comments sheet, the followers list
    # and search, where closing would be wrong.
    "conversation.close_interstitial": [
        "//*[@content-desc=\"Feuille du bas\"]//*[@content-desc=\"Fermer\"]",
        "//*[@content-desc=\"Feuille du bas\"]//android.widget.Button[contains(@text, \"Termin\")]",
        "//*[contains(@text, \"J’ai compris\") or contains(@text, \"J'ai compris\")]",
    ],
    # === A2 anchor for message bubbles ===
    #
    # Measured on two real two-way conversations (43.1.4 and 46.6.3, 2026-08-29). The obfuscated
    # id differs per version (`jay` / `koy`), so an id-only selector read nothing on 46.6.3.
    # This resolves BOTH bubbles on both versions and picks up nothing else in a conversation
    # except the read-receipt label, excluded just below.
    "conversation.message_text_anchors": [
        "//*[@focusable=\"true\"][string-length(@text)>0]"
        "[not(@content-desc) or @content-desc=\"\"]"
        "[not(self::android.widget.EditText)][not(self::android.widget.Button)]"
        "[@text!=\"Vu\"]",
    ],
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
    # === A2 anchors for the follower list ===
    #
    # `txt_user_name` and `txt_desc` are names a developer wrote, not build-time symbols — and a
    # readable id survived every version bump measured (100%, against 1% for an obfuscated one).
    # On a real 46.6.3 list they resolve 10 rows, and nothing on the profile, the inbox or the
    # suggestions list.
    #
    # UNVERIFIED on 43.1.4: its follower list rendered only the tab row on the one account
    # available — a single follower, whose row never appeared in the dump. The obfuscated id
    # stays first, so that version is untouched either way.
    # A Button whose GRANDPARENT holds a `txt_user_name` — i.e. the button of a row that
    # names someone. `tvn` alone was tried: it resolves on the suggestions list too, where
    # the same 10 buttons mean "follow a stranger", not "this is a follower row". The
    # structural form gives 10 on a real list and 0 on suggestions, profile and feed.
    "followers.follower_any_button_anchors": [
        "//android.widget.Button[../..//*[contains(@resource-id, \":id/txt_user_name\")]]",
    ],
    "followers.follower_username_anchors": [
        "//*[contains(@resource-id, \":id/txt_desc\")]",
    ],
    "followers.follower_display_name_anchors": [
        "//*[contains(@resource-id, \":id/txt_user_name\")]",
    ],
    "followers.follower_follow_button": [],
    "followers.follower_following_button": [],
    # Measured on device (2026-08-29): this entry was EMPTY, so only the English list applied --
    # and it matches "Followers" by EQUALITY, while French TikTok writes the SINGULAR when the
    # account has exactly one ("Follower"). The Followers workflow died on "Failed to open
    # followers list" for that alone. Containment covers both numbers; "Abonné" covers the other
    # rendering. Resolves 1 on both versions' profile screens, and fires on no other capture.
    "followers.followers_counter": [
        "//*[@clickable=\"true\"][.//android.widget.TextView[contains(@text, \"Follower\") or contains(@text, \"Abonné\")]]",
    ],
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
        "//*[(contains(@content-desc, \"Statut d'activité\") or contains(@content-desc, \"Statut d’activité\"))]",
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
    # One of the empty French keys the audit counted, and the reason every DM flow stopped at
    # "Failed to navigate to Inbox" while standing ON the inbox: with nothing here `L()` fell back
    # to English, which asks for `@text="Inbox"` — and a French phone writes "Messages". The
    # readable id `title` was right all along. Measured on both versions.
    "inbox.inbox_title": [
        "//*[contains(@resource-id, \":id/title\")][@text=\"Messages\"]",
    ],
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
    # `Ami`, not `Amis`. Measured on both phones: the tab's content-desc is `Ami(e)s`, and
    # `Amis` is not contained in it — the string runs A-m-i-(-e-)-s. The id alternative covered
    # for it on 43.1.4; on 46.6.3 that id is gone and ALL THREE alternatives resolved nothing,
    # so the friends tab was unreachable. Scoped to the bottom-bar FrameLayout, so the shorter
    # form cannot wander into another word.
    "navigation.friends_tab": [
        "//android.widget.FrameLayout[contains(@content-desc, \"Ami\")]",
    ],
    "navigation.home_tab": [
        "//android.widget.FrameLayout[contains(@content-desc, \"Accueil\")]",
    ],
    "navigation.home_tab_selected": [],
    # `Messages`, measured on the bar of both versions — not "Boîte de réception", which the
    # catalogue asked for and no screen writes. The obfuscated id covered for it until it died;
    # same family of guessed label as `Amis` against `Ami(e)s`.
    "navigation.inbox_tab": [
        "//android.widget.FrameLayout[contains(@content-desc, \"Messages\")]",
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
    # `J'ai compris` was missing, and it is the button of an interstitial TikTok raises INSIDE
    # a conversation ("Recommandations de stickers personnalisées"). It covers the composer, so
    # the message field reads as absent and a reply cannot be typed — measured on device, mid-DM.
    "popup.dismiss_button": [
        "//android.widget.Button[contains(@text, \"Pas maintenant\")]",
        "//*[contains(@text, \"J’ai compris\") or contains(@text, \"J'ai compris\")]",
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
    # Raw LABELS, not xpaths. The profile stats row is matched by POSITION, since the
    # POSITION (resource-id qfv/qfw), mais dire LAQUELLE des trois valeurs on tient
    # three values share an identifier, so telling WHICH one is held requires reading
    # its label. Order matters here: the following label is a prefix of the followers
    # one, so it must be tested first.
    # Measured on device, not written from a guess — the previous values were, and they were
    # wrong. TikTok 43.1.4 in fr-FR labels the row `Suivis` and `Follower`: a French word for
    # following, and an ENGLISH one, singular, for followers. `Abonnements` / `Abonne` are kept
    # because other versions do show them. Singular everywhere, see the note in en.py.
    # === A2 anchors: a route to the profile that is not an obfuscated id ===
    #
    # The ten profile fields had NO route but a build-time id, which survives a version bump 1%
    # of the time — that is what makes 46.6.3 unreadable. These were written against the dumps of
    # BOTH versions and resolve on both (`data/tiktok-parite/outils/tt_profile_a2_anchors.py`).
    #
    # They come AFTER the id in each field's list: on 43.1.4 the id still wins and nothing moves;
    # on 46.6.3 it resolves nothing and these take over.
    # === A2 anchors for the profile's video grid ===
    #
    # `cover` is one of the eleven readable ids, written identically on both versions. The view
    # count is `tv_play_count` on 46.6.3 — readable too — but obfuscated on 43.1.4, so it is
    # reached structurally: the TextView inside the tile that carries the thumbnail. Measured 6
    # tiles on 43.1.4 and 9 on 46.6.3, and nothing on the feed or the follower list.
    #
    # It does resolve on search RESULTS, which also show video tiles. That is not a leak: a video
    # thumbnail is a video thumbnail, and the caller knows which screen it is on.
    "profile.video_item_anchors": [
        "//android.widget.GridView//*[contains(@resource-id, \":id/cover\")]",
    ],
    "profile.video_view_count_anchors": [
        "//*[contains(@resource-id, \":id/tv_play_count\")]",
        "//*[contains(@resource-id, \":id/cover\")]/../..//android.widget.TextView",
    ],
    # The bar is "whatever holds the Profile tab". Measured: exactly 1 on every screen of
    # both versions — feed, profile, inbox — where the id resolves on neither.
    "navigation.bottom_nav_container_anchors": [
        "//*[@content-desc=\"Profil\"]/..",
        "//*[@content-desc=\"Profile\"]/..",
    ],
    # The INNERMOST container holding both the invite button and its close cross. Without the
    # `not(...)` clause every ancestor matched — 18 of them — and a caller would have dismissed
    # the whole screen instead of the banner.
    "popup.promo_banner_anchors": [
        "//*[.//*[@text=\"Inviter\" or @text=\"Invite\"] and .//*[@content-desc=\"Fermer\" or @content-desc=\"Close\"] and not(.//*[.//*[@text=\"Inviter\" or @text=\"Invite\"] and .//*[@content-desc=\"Fermer\" or @content-desc=\"Close\"]])]",
    ],
    # Same shape as the profile grid's view count: the TextView inside the tile carrying the
    # thumbnail. `cover` is a readable id, written identically on both versions.
    "followers.post_view_count_anchors": [
        "//*[contains(@resource-id, \":id/cover\")]/../..//android.widget.TextView",
    ],
    # === A2 anchors for the composer ===
    #
    # Captured from a real conversation: the send control is an ImageView carrying
    # `content-desc="Envoyer"` and NO resource-id at all; the input is a bare EditText, also
    # without one. Every catalogue anchor for both was an obfuscated id, so neither was ever
    # found — the message stayed in the composer while the send reported success.
    "conversation.message_input_field_anchors": [
        "//android.widget.EditText",
    ],
    "conversation.send_button_anchors": [
        "//*[@content-desc=\"Envoyer\" or @content-desc=\"Send\"]",
    ],
    # === A2 anchors for the message-request rows ===
    #
    # Captured from a list holding four real requests. `user_name` is a readable id; the preview
    # and the timestamp hang off it structurally rather than off their own obfuscated ids.
    #
    # The page title matches on its TEXT. That is what broke `open_message_requests_page`: it
    # required the id `nmh`, dead on 46.6.3, so the condition could never hold — the navigation
    # had landed on the page and the function reported it had not.
    "inbox.conversation_username_anchors": [
        "//*[contains(@resource-id, \":id/user_name\")]",
    ],
    "inbox.conversation_last_message_anchors": [
        # `[2]` was positional over the WHOLE document, not within a row, and resolved to
        # nothing: every preview came back empty, so `unreplied` fell back to True for every
        # conversation -- including the ones we had just answered. Anchored by exclusion
        # instead, it pairs 1:1 with the usernames on the inbox AND on the requests page.
        "//*[contains(@resource-id, \":id/user_name\")]/../.."
        "//android.widget.TextView[not(contains(@resource-id, \":id/user_name\"))]"
        "[not(contains(@text, \"·\"))]",
    ],
    "inbox.conversation_timestamp_anchors": [
        "//android.widget.TextView[contains(@text, \"·\")]",
    ],
    "inbox.message_requests_page_title_anchors": [
        "//*[contains(@text, \"Demandes de messages\") or contains(@text, \"Message requests\")]",
    ],
    # The header name, reached from the back button rather than from its own id — both ids
    # there are obfuscated and dead on 46.6.3, so `get_conversation_info` returned None and
    # the recipient guard could never pass. Measured: the right name on both versions, and
    # nothing on the requests page or a profile.
    "conversation.conversation_name_anchors": [
        "//*[@content-desc=\"Retour\" or @content-desc=\"Back\"]/../..//android.widget.TextView[1]",
    ],
    # === "Messages" showing people suggestions instead of the conversation list ===
    #
    # Observed on device (46.6.3, 2026-08-29): the Messages tab rendered a follow-suggestions
    # list. The title still read "Messages", so `is_on_inbox_page` answered yes, the reader found
    # no conversation and every DM workflow reported an EMPTY INBOX rather than a navigation
    # problem. A cold app restart brought the real list back, which is why the bridges -- which
    # always restart -- never showed it.
    #
    # Signature measured across four captures: the healthy inbox has conversation rows
    # (`user_name`) and NO row-level follow button; the degraded pane has no conversation row and
    # nine follow buttons with suggestion captions.
    "inbox.people_suggestions_markers": [
        "//android.widget.Button[@text=\"Suivre\" or @text=\"Suivre en retour\"]",
        "//*[contains(@text, \"Personnes que tu pourrais connaître\")]",
    ],
    "profile.username_anchors": [
        "//android.widget.Button[starts-with(@text, \"@\")]",
        # `contains(@content-desc, "@")` was tried here and dropped: it matches an inbox
        # row too. It stays available as `username_content_description` for a caller that
        # knows it is on a profile; it has no business in the general anchor list.
    ],
    "profile.display_name_anchors": [
        # The Button just before the handle. "any short Button with text" was tried and
        # matched on the search and inbox screens too — an anchor that fires off its own
        # surface is worse than none, because it answers confidently with someone else.
        "//android.widget.Button[starts-with(@text, \"@\")]/preceding::android.widget.Button[1]",
    ],
    # ONE expression for every language, deliberately — not one anchor per locale.
    #
    # `first_matching` takes the first alternative that finds anything, and TikTok writes
    # "Followers" in English even on a French phone: the English anchor won with that single hit
    # and the French one, which matched all three rows, was never reached. Two counters out of
    # three stayed at zero, silently. Same shape Instagram uses for the same problem.
    #
    # Fires on the followers list too, where the word is everywhere. Harmless by construction:
    # the extractor requires stat_value AND stat_label, and the value anchor is structural — it
    # resolves on the profile and nowhere else.
    "profile.stat_label_anchors": [
        "//android.widget.TextView[contains(@text, \"Suivi\") or contains(@text, \"Abonn\") or contains(@text, \"aime\") or contains(@text, \"Follow\") or contains(@text, \"Like\")]",
    ],
    # Structural: the value is the TextView sitting above its label. "A short TextView" was
    # tried and matched 17 nodes on one screen.
    "profile.stat_value_anchors": [
        "//android.widget.TextView[contains(@text, \"Suivi\") or contains(@text, \"Abonn\") or contains(@text, \"aime\") or contains(@text, \"Follow\") or contains(@text, \"Like\")]/preceding-sibling::android.widget.TextView[1]",
    ],
    "profile.bio_text_anchors": [
        "//android.widget.Button[string-length(@text) > 40]",
    ],
    # Hardening, not a guess: the SAME stats row already serves one of its three labels in
    # English on a French screen ("Followers"). A classification vocabulary only recognises,
    # it never acts, so accepting a rendering TikTok is already known to use costs nothing and
    # closes the door on the identical failure landing here.
    "profile.stat_label_following": [
        "Suivi",
        "Abonnement",
        "Following",
    ],
    # Measured on three real French profiles, on BOTH app versions (2026-08-29): TikTok's
    # French UI writes the followers label in ENGLISH -- "Follower" in the singular, "Followers"
    # in the plural -- while writing "Suivis" and "J'aime" in French. This entry held only the
    # plausible translation, so `classify_profile_stat_label` returned None for the label that is
    # actually on screen and `followers_count` came back 0 for EVERY profile read on a French
    # phone, silently. The filtering shipped the same day then rejected everyone for "Too few
    # followers (0 < N)", on a number that had never been read.
    "profile.stat_label_followers": [
        "Follower",
        "Abonné",
    ],
    # Same hardening as above.
    "profile.stat_label_likes": [
        "J'aime",
        "Likes",
    ],
    # Raw LABEL of a MUTUAL follow button, which the unfollow workflow may skip.
    # Both spellings written out rather than a shortened `Ami`: this one decides a RELATIONSHIP,
    # and a loose substring on a button label is how a match wanders. `Ami(e)s` is what the tab
    # shows; `Amis` stays for versions that write it that way.
    "profile.friends_button_labels": [
        "Ami(e)s",
        "Amis",
    ],
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
    # === A2 anchor for the search field ===
    #
    # Measured on device (46.6.3, 2026-08-29): the field is `ho3` there, not `giv`, and it carries
    # NO hint -- its placeholder is a trending topic sitting in @text ("Vigilance orange Var"), so
    # the hint match could never fire either. `open_search` returned True onto a screen whose
    # field nothing could find, and every Followers / Search run died on "Failed to submit search".
    #
    # Anchored on the READABLE id of the neighbouring button rather than on a bare EditText: a
    # bare one also matches the conversation composer, on both versions.
    "search.search_input_anchors": [
        "//*[contains(@resource-id, \":id/tv_search_textview\")]/../..//android.widget.EditText",
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
        "//android.widget.Button[(@content-desc=\"Retour à l'écran précédent\" or @content-desc=\"Retour à l’écran précédent\")]",
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
        "//android.widget.SeekBar[(@content-desc=\"Sélecteur de l'année\" or @content-desc=\"Sélecteur de l’année\")]",
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
    # === A2 anchors for the four video counters ===
    #
    # The count sits INSIDE its own button, and the button is named by its content-desc — not by
    # its id: the like button and the share button carry the SAME id on both versions, so an id
    # cannot tell those two apart at all.
    #
    # `descendant::` and not `following::`. The second steps OVER the button and lands on the
    # next counter, which returns a plausible number for the wrong field on every row — measured.
    # Two things this rail does, learned from a low-engagement video: TikTok HIDES a count
    # that is zero (no comment node at all, not a node reading "0"), and it writes the
    # word "Partager" where the share count would be when nothing has been shared. So an
    # absent counter means zero, not a dead anchor — and a caller that treats absence as
    # failure will report a healthy screen as broken.
    "video_engagement.like_count_anchors": [
        "//*[starts-with(@content-desc, \"Attribuer\")]/descendant::*[@text != \"\"][1]",
    ],
    "video_engagement.comment_count_anchors": [
        "//*[starts-with(@content-desc, \"Lire ou ajouter\")]/descendant::*[@text != \"\"][1]",
    ],
    "video_engagement.favorite_count_anchors": [
        "//*[starts-with(@content-desc, \"Ajoute ou supprime\")]/descendant::*[@text != \"\"][1]",
    ],
    "video_engagement.share_count_anchors": [
        "//*[starts-with(@content-desc, \"Partager une\")]/descendant::*[@text != \"\"][1]",
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
        "//*[contains(@content-desc, \"Retirer\") and (contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\"))]",
        "//*[contains(@content-desc, \"Supprimer\") and (contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\"))]",
    ],
    "video_state.user_followed_indicator": [],
    "video_state.video_already_liked": [
        "//*[contains(@content-desc, \"Retirer\") and (contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\"))]",
        "//*[contains(@content-desc, \"Supprimer\") and (contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\"))]",
    ],
    "video_state.video_favorited_indicator": [
        "//*[contains(@content-desc, \"Retirer des favoris\")]",
    ],
    "video_state.video_liked_indicator": [
        "//*[contains(@content-desc, \"Retirer\") and (contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\"))]",
        "//*[contains(@content-desc, \"Supprimer\") and (contains(@content-desc, \"J'aime\") or contains(@content-desc, \"J’aime\"))]",
    ],
    "video_state.video_page_indicator": [],
}
