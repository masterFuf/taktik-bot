"""English (en) UI string overlay for TikTok selectors.

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
        "//android.widget.Button[@content-desc=\"Log in\"]",
        "//android.widget.Button[contains(@text, \"Log in\")]",
    ],
    "auth.login_screen_indicators": [
        "//*[contains(@text, \"Log in\")]",
        "//*[contains(@text, \"Sign up\")]",
    ],
    "auth.password_field": [
        "//android.widget.EditText[contains(@content-desc, \"Password\")]",
    ],
    "auth.username_field": [
        "//android.widget.EditText[contains(@content-desc, \"Email or username\")]",
        "//android.widget.EditText[contains(@content-desc, \"Phone number\")]",
    ],
    # --- comment ---
    # === comment sheet ===
    #
    # Mirrors the French entries measured on device on 2026-08-29. NOT verified on a device: all
    # three phones are fr-FR, so these are the English strings TikTok is expected to use and they
    # carry the same shape (content-desc and hint, never an id) rather than a translation guess at
    # a resource name.
    # See the French entry: the composer affordance, not a comment's like button, because the
    # latter answers NO on an open-but-empty sheet.
    # Vide DELIBEREMENT. Cette entree portait l'affordance du composeur (« Mentionne quelqu'un »
    # / « Stickers »), qui appartient a l'ecran VIDEO et repond donc oui feuille FERMEE — mesure
    # sur appareil le 2026-08-30. La gardee en filet ne servirait a rien : n'importe quelle entree
    # qui matche fait repondre oui a toute la liste, donc un filet ici EST le bug. Le panneau de
    # la feuille, neutre et mesure sur les deux versions, vit dans la base du catalogue.
    "comment.sheet_indicator": [],
    "comment.reply_button": [
        "//android.widget.Button[@text=\"Reply\"]",
    ],
    "comment.comment_input": [
        "//android.widget.EditText[contains(@hint, \"Add comment\")]",
        "//android.widget.EditText[contains(@text, \"Add comment\")]",
    ],
    # See the French entry for the measurement. The send button carries an UNRESOLVED Android
    # resource as its description on both versions, so its only durable anchor is its position
    # after the mention affordance. NOT verified on an English device (all three phones are fr-FR).
    "comment.post_comment_button": [
        "//*[@content-desc=\"Mention someone\"]"
        "/following::android.widget.Button[starts-with(@content-desc, \"@\")][1]",
        "//android.widget.Button[contains(@content-desc, \"Post\")]",
    ],
    "comment.close_button": [
        "//*[@content-desc=\"Close\"][@clickable=\"true\"]",
    ],
    "comment.comment_count_header": [
        "//android.widget.TextView[contains(@text, \"comment\")]",
    ],
    # --- conversation ---
    "conversation.back_button": [
        "//*[contains(@resource-id, \":id/nmy\")][@content-desc=\"Back\"]",
        "//android.widget.ImageView[@content-desc=\"Back\"]",
        "//*[@clickable=\"true\"][@content-desc=\"Retour\" or @content-desc=\"Back\"]",
    ],
    "conversation.close_sticker_suggestion": [
        "//*[contains(@resource-id, \":id/dgd\")][@content-desc=\"Close\"]",
    ],
    # Mirror of the French anchors, which were measured on device. The English container
    # description is NOT verified -- we hold no English capture of this sheet -- so the
    # acknowledgment buttons are listed unscoped BELOW it, matching on their own text only.
    # The obfuscated `dgd` above is kept as the historical sticker close and moves here too.
    "conversation.close_interstitial": [
        "//*[@content-desc=\"Bottom Sheet\" or @content-desc=\"Bottom sheet\"]//*[@content-desc=\"Close\"]",
        "//*[@content-desc=\"Bottom Sheet\" or @content-desc=\"Bottom sheet\"]//android.widget.Button[contains(@text, \"Done\")]",
        "//android.widget.Button[@text=\"Got it\"]",
        "//*[contains(@resource-id, \":id/dgd\")][@content-desc=\"Close\"]",
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
        "[@text!=\"Seen\"]",
    ],
    "conversation.reply_button": [
        "//*[contains(@resource-id, \":id/rh_\")][@text=\"Reply\"]",
    ],
    # --- country_picker ---
    "country_picker.close_button": [
        "//android.widget.ImageView[contains(@resource-id, \":id/be6\") and @content-desc=\"Close\"]",
        "//*[@content-desc=\"Close\"]",
    ],
    "country_picker.screen_indicator": [
        "//android.widget.TextView[contains(@resource-id, \":id/title\") and @text=\"Select country/region\"]",
        "//android.widget.TextView[@text=\"Select country/region\"]",
    ],
    "country_picker.search_input": [
        "//android.widget.EditText[@hint=\"Search countries and regions\"]",
        "//android.widget.EditText[contains(@hint, \"countries\")]",
    ],
    # --- detection ---
    "detection.error_message": [
        "//android.widget.TextView[contains(@text, \"error\")]",
        "//android.widget.TextView[contains(@text, \"Something went wrong\")]",
    ],
    "detection.network_error": [
        "//android.widget.TextView[contains(@text, \"network\")]",
        "//android.widget.TextView[contains(@text, \"No internet\")]",
    ],
    "detection.rate_limit": [
        "//android.widget.TextView[contains(@text, \"too many\")]",
        "//android.widget.TextView[contains(@text, \"Try again later\")]",
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
    "followers.follower_follow_button": [
        "//*[contains(@resource-id, \":id/rdh\")][@text=\"Follow\"]",
        "//android.widget.Button[contains(@resource-id, \":id/rdh\")][@text=\"Follow\"]",
    ],
    "followers.follower_following_button": [
        "//*[contains(@resource-id, \":id/rdh\")][@text=\"Following\"]",
        "//*[contains(@resource-id, \":id/rdh\")][@text=\"Friends\"]",
    ],
    "followers.followers_counter": [
        "//*[@clickable=\"true\"][.//android.widget.TextView[contains(@text, \"Follower\")]]",
        "//android.view.ViewGroup[@clickable=\"true\"][.//android.widget.TextView[@text=\"Followers\"]]",
        "//android.view.ViewGroup[@clickable=\"true\"][.//android.widget.TextView[contains(@resource-id, \":id/qfv\")][@text=\"Followers\"]]",
        "//*[.//android.widget.TextView[@text=\"Followers\"]][@clickable=\"true\"]",
    ],
    # Mirror of the French anchor. NOT verified on an English device (all three phones are
    # fr-FR); the shape is the measured one, only the label differs.
    "followers.followers_list_anchors": [
        "//androidx.recyclerview.widget.RecyclerView[@scrollable=\"true\"][ancestor::*[.//*[@clickable=\"true\"][starts-with(@content-desc, \"Followers\")]]]",
    ],
    "followers.followers_tab": [
        "//android.widget.TextView[contains(@text, \"Followers\")]",
        "//*[contains(@text, \"Followers\")][@clickable=\"true\"]",
    ],
    "followers.followers_tab_selected": [
        "//*[contains(@content-desc, \"Followers\")][@selected=\"true\"]",
    ],
    "followers.following_counter": [
        "//android.widget.LinearLayout[@clickable=\"true\"][.//android.widget.TextView[@text=\"Following\"]]",
        "//*[.//android.widget.TextView[@text=\"Following\"]][@clickable=\"true\"]",
    ],
    "followers.following_list_opener": [
        "//*[contains(@content-desc, \"Following\")]",
        "//*[contains(@text, \"Following\")]",
        "//android.widget.TextView[contains(@text, \"Following\")]",
    ],
    "followers.following_or_friends_button": [
        "//*[@text=\"Following\" or @text=\"Friends\"][@clickable=\"true\"]",
    ],
    "followers.following_tab": [
        "//android.widget.TextView[contains(@text, \"Following\")][@selected=\"false\"]",
    ],
    "followers.profile_follow_button": [
        "//android.widget.TextView[contains(@text, \"Likes\")][string-length(@text)<12]"
        "/following::*[@text=\"Follow\"][1]",
        "//android.widget.TextView[contains(@resource-id, \":id/eme\")][@text=\"Follow\"]",
        "//*[contains(@resource-id, \":id/eme\")][@text=\"Follow\"]",
    ],
    "followers.profile_reposted_tab": [
        "//*[@content-desc=\"Reposted videos\"]",
        "//android.widget.RelativeLayout[@content-desc=\"Reposted videos\"]",
    ],
    "followers.profile_videos_tab": [
        "//*[@content-desc=\"Videos\"]",
        "//android.widget.RelativeLayout[@content-desc=\"Videos\"]",
    ],
    "followers.unfollow_confirm_button": [
        "//*[@text=\"Unfollow\"][@clickable=\"true\"]",
        "//*[contains(@text, \"Unfollow\")][@clickable=\"true\"]",
    ],
    # --- inbox ---
    "inbox.accept_request_button": [
        "//android.widget.Button[@text=\"Accept\"]",
        "//*[@text=\"Accept\"]",
    ],
    "inbox.activity_section": [
        "//*[contains(@resource-id, \":id/b8h\")][@text=\"Activity\"]",
        "//*[@text=\"Activity\"]",
    ],
    "inbox.activity_status": [
        "//*[contains(@content-desc, \"Activity status\")]",
    ],
    "inbox.add_people_button": [
        "//android.widget.ImageView[@content-desc=\"Add people\"]",
    ],
    # Measured on device (46.6.3, 2026-08-29): tapping « Supprimer » on an open request does not
    # decline it — TikTok raises a confirmation ("Supprimer ce message ?") and waits. Without
    # this, `decline_request` reported a refusal that had not happened AND left the dialog on
    # screen, which then blocked every later navigation ("Inbox inatteignable").
    #
    # A confirmation dialog IS a pair of buttons, so the anchor names the pairing rather than a
    # container: the delete button that is a SIBLING of Cancel. One hit on the dialog, none on
    # the request screen where a « Supprimer » also lives.
    "inbox.decline_request_confirm_button": [
        "//android.widget.Button[@text=\"Cancel\"]/../android.widget.Button[@text=\"Delete\"]",
        "//*[@content-desc=\"Dialog\"]//android.widget.Button[@text=\"Delete\"]",
    ],
    "inbox.decline_request_button": [
        "//android.widget.Button[@text=\"Delete\"]",
        "//android.widget.Button[@text=\"Decline\"]",
    ],
    "inbox.follow_back_button": [
        "//android.widget.Button[@text=\"Follow back\"]",
        "//*[@text=\"Follow back\"]",
    ],
    "inbox.inbox_title": [
        "//*[contains(@resource-id, \":id/title\")][@text=\"Inbox\"]",
    ],
    "inbox.message_requests_page_title": [
        "//*[contains(@resource-id, \":id/nmh\")][contains(@text, \"Message requests\")]",
    ],
    "inbox.message_requests_section": [
        "//*[contains(@text, \"Message requests\")]",
    ],
    "inbox.new_followers_section": [
        "//*[contains(@resource-id, \":id/b8h\")][@text=\"New followers\"]",
        "//*[@text=\"New followers\"]",
    ],
    "inbox.search_inbox_button": [
        "//android.widget.ImageView[@content-desc=\"Search\"]",
    ],
    "inbox.see_all_button": [
        "//*[@text=\"View all\"]",
    ],
    "inbox.seen_marker": [
        "//*[contains(@resource-id, \":id/l35\")][@text=\"Seen\"]",
        "//*[contains(@resource-id, \":id/l35\")][starts-with(@text, \"Seen\")]",
    ],
    "inbox.suggested_accounts_section": [
        "//*[@text=\"Suggested accounts\"]",
    ],
    "inbox.system_notifications_section": [
        "//*[contains(@resource-id, \":id/b8h\")][@text=\"System notifications\"]",
        "//*[@text=\"System notifications\"]",
    ],
    # --- logout ---
    "logout.logout_button": [
        "//*[@text=\"Log out\"]",
    ],
    "logout.logout_confirm_button": [
        "//*[@content-desc=\"Log out\"]",
        "//*[contains(@resource-id, \":id/wk\") and @text=\"Log out\"]",
    ],
    "logout.profile_menu_button": [
        "//*[@content-desc=\"Profile menu\"]",
    ],
    "logout.profile_tab": [
        "//*[@content-desc=\"Profile\"][contains(@resource-id, \":id/nce\")]",
        "//*[@content-desc=\"Profile\" and @clickable=\"true\"]",
    ],
    # --- navigation ---
    "navigation.back_button": [
        "//android.widget.ImageButton[@content-desc=\"Back\"]",
        "//android.widget.ImageView[@content-desc=\"Back\"]",
    ],
    "navigation.create_button": [
        "//android.widget.Button[@content-desc=\"Create\"]",
    ],
    "navigation.explore_tab": [
        "//*[@content-desc=\"Explore\"]",
        "//*[@text=\"Explore\"]",
    ],
    "navigation.following_tab": [
        "//*[@content-desc=\"Following\"]",
        "//*[@text=\"Following\"]",
    ],
    # `contains(…, "Friend")` and not an equality on `Friends`: TikTok pluralises its own
    # labels, and the French side of this key was unreachable for exactly that reason.
    "navigation.friends_tab": [
        "//android.widget.FrameLayout[contains(@content-desc, \"Friend\")]",
    ],
    "navigation.home_tab": [
        "//android.widget.FrameLayout[@content-desc=\"Home\"]",
    ],
    "navigation.home_tab_selected": [
        "//android.widget.FrameLayout[@content-desc=\"Home\"][@selected=\"true\"]",
    ],
    # Kept as the app's own wording; the French side asked for a phrase no screen writes.
    "navigation.inbox_tab": [
        "//android.widget.FrameLayout[@content-desc=\"Inbox\"]",
        "//*[@content-desc=\"Inbox\"]",
        "//*[contains(@content-desc, \"Inbox\")]",
    ],
    "navigation.inbox_tab_selected": [
        "//android.widget.FrameLayout[@content-desc=\"Inbox\"][@selected=\"true\"]",
    ],
    "navigation.profile_tab": [
        "//android.widget.FrameLayout[@content-desc=\"Profile\"]",
    ],
    "navigation.search_button": [
        "//*[contains(@resource-id, \":id/irz\")][@content-desc=\"Search\"]",
        "//android.widget.ImageView[@content-desc=\"Search\"]",
        "//*[@content-desc=\"Search\"][@clickable=\"true\"]",
    ],
    "navigation.shop_tab": [
        "//*[@content-desc=\"Shop\"]",
        "//*[@text=\"Shop\"]",
    ],
    # --- popup ---
    "popup.age_verification_popup": [
        "//*[contains(@text, \"birthday\")]",
    ],
    "popup.close_button": [
        "//*[contains(@resource-id, \":id/dga\")][@content-desc=\"Close\"]",
        "//*[contains(@resource-id, \":id/jyh\")][@content-desc=\"Close\"]",
        "//android.widget.ImageView[@content-desc=\"Close\"]",
        "//android.widget.ImageButton[@content-desc=\"Close\"]",
        "//android.widget.Button[@content-desc=\"Close\"]",
    ],
    "popup.collections_close": [
        "//*[contains(@resource-id, \":id/jyh\")][@content-desc=\"Close\"]",
    ],
    "popup.collections_not_now": [
        "//*[contains(@resource-id, \":id/ny9\")][@text=\"Not now\"]",
    ],
    "popup.collections_popup": [
        "//*[contains(@text, \"Create shared collections\")]",
    ],
    "popup.comment_input_area": [
        "//*[contains(@resource-id, \":id/xi_\")][@text=\"Comment...\"]",
    ],
    "popup.comments_close_button": [
        "//*[contains(@resource-id, \":id/dqh\")][@content-desc=\"Close\"]",
        "//android.widget.ImageView[@content-desc=\"Close\"]",
    ],
    # "Got it" closes the in-conversation sticker interstitial; see the note in fr.py.
    "popup.dismiss_button": [
        "//*[contains(@text, \"Got it\")]",
        "//android.widget.Button[@text=\"Not now\"]",
        "//android.widget.Button[contains(@text, \"Not now\")]",
        "//android.widget.Button[contains(@text, \"Skip\")]",
        # Le pendant anglais du rappel de confidentialite mesure en francais le 2026-08-30
        # (« Non, merci »). Ecrit ici pour que la meme popup ne rebloque pas un telephone anglais ;
        # a confirmer sur appareil quand l'app y sera repassee.
        "//*[contains(@text, \"No thanks\")][@clickable=\"true\"]",
        "//*[@clickable=\"true\"][.//*[contains(@text, \"No thanks\")]]",
    ],
    "popup.follow_friends_close": [
        "//android.widget.ImageView[@content-desc=\"Close\"][@clickable=\"true\"]",
    ],
    "popup.follow_friends_popup": [
        "//*[contains(@text, \"Follow your friends\")]",
    ],
    "popup.inbox_page_indicator": [
        "//*[contains(@resource-id, \":id/title\")][@text=\"Inbox\"]",
        "//*[@text=\"New followers\"]",
        "//*[@text=\"Activity\"]",
        "//*[@text=\"System notifications\"]",
    ],
    "popup.link_email_not_now": [
        "//android.widget.Button[@text=\"Not now\"]",
        "//*[@text=\"Not now\"][@clickable=\"true\"]",
    ],
    "popup.notification_banner": [
        "//*[contains(@text, \"Reply\")][@clickable=\"true\"]",
    ],
    "popup.notification_popup": [
        "//*[contains(@text, \"Allow\")]",
    ],
    "popup.promo_close_button": [
        "//*[contains(@resource-id, \":id/fac\")][@content-desc=\"Close\"]",
    ],
    "popup.suggestion_close": [
        "//*[contains(@resource-id, \":id/bjr\")][@content-desc=\"Close\"]",
    ],
    "popup.suggestion_follow_back": [
        "//*[contains(@resource-id, \":id/bjk\")][@text=\"Follow back\"]",
        "//*[contains(@resource-id, \":id/bjk\")][@text=\"Follow\"]",
        "//android.widget.Button[@text=\"Follow back\"]",
        "//android.widget.Button[@text=\"Follow\"]",
    ],
    "popup.suggestion_not_interested": [
        "//*[contains(@resource-id, \":id/bjl\")][@text=\"Not interested\"]",
        "//android.widget.Button[@text=\"Not interested\"]",
    ],
    "popup.system_deny_button": [
        "//*[@text=\"DENY\"][@clickable=\"true\"]",
        "//*[@text=\"Deny\"][@clickable=\"true\"]",
        "//*[(@text=\"Don't allow\" or @text=\"Don’t allow\")][@clickable=\"true\"]",
        "//*[@text=\"No\"][@clickable=\"true\"]",
    ],
    # --- profile ---
    "profile.create_story_button": [
        "//android.widget.Button[@content-desc=\"Create a Story\"]",
    ],
    "profile.edit_profile_button": [
        "//android.widget.Button[@text=\"Edit\"]",
        "//android.widget.Button[contains(@text, \"Edit profile\")]",
    ],
    "profile.favourites_tab": [
        "//*[@content-desc=\"Favourites\"]",
        "//*[@content-desc=\"Favorites\"]",
    ],
    "profile.follow_button": [
        "//android.widget.Button[contains(@content-desc, \"Follow\")]",
        "//android.widget.Button[@text=\"Follow\"]",
    ],
    "profile.followers_count": [
        "//*[contains(@resource-id, \":id/qfv\")][@text=\"Followers\"]/..//*[contains(@resource-id, \":id/qfw\")]",
        "//android.widget.TextView[@text=\"Followers\"]/preceding-sibling::android.widget.TextView",
    ],
    "profile.following_button": [
        "//android.widget.Button[@text=\"Following\"]",
        "//android.widget.Button[contains(@text, \"Friends\")]",
    ],
    "profile.following_count": [
        "//*[contains(@resource-id, \":id/qfv\")][@text=\"Following\"]/..//*[contains(@resource-id, \":id/qfw\")]",
        "//android.widget.TextView[@text=\"Following\"]/preceding-sibling::android.widget.TextView",
    ],
    "profile.liked_videos_tab": [
        "//*[@content-desc=\"Liked videos\"]",
    ],
    "profile.likes_count": [
        "//*[contains(@resource-id, \":id/qfv\")][@text=\"Likes\"]/..//*[contains(@resource-id, \":id/qfw\")]",
        "//android.widget.TextView[@text=\"Likes\"]/preceding-sibling::android.widget.TextView",
    ],
    # Bare LABELS (not xpaths): the profile stat row is paired by POSITION (qfv/qfw
    # resource-ids), but telling WHICH of the three values you hold means reading its
    # label. That classification used to be hardcoded English, so a French TikTok
    # reported zero for all three counts. Order matters in the caller: following
    # before followers, since one contains the other.
    # SINGULAR on purpose. `_matches` asks whether the catalogue entry is CONTAINED in the
    # screen text, so "Follower" covers both "Follower" and "Followers" — and TikTok pluralises
    # its own labels: an account with exactly one follower shows "Follower", which the plural
    # entry could not match. Measured on a real 43.1.4 profile (Pixel 6 Pro, 2026-08-28), where
    # the row read `Suivis 1 / Follower 1 / J'aime 19` and only the last one classified.
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
        "//android.widget.Button[@text=\"Follow\" or @text=\"Follow back\"]",
        "//*[contains(@text, \"Suggested accounts\") or contains(@text, \"People you may know\")]",
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
    # Neutral (a length rule carries no language) -> moved to the dataclass base, where the
    # structural anchor that actually reads a bio now lives.
    "profile.bio_text_anchors": [],
    "profile.stat_label_following": [
        "Following",
    ],
    "profile.stat_label_followers": [
        "Follower",
    ],
    "profile.stat_label_likes": [
        "Likes",
    ],
    # Bare LABEL of a MUTUAL follow button (the unfollow workflow can skip those).
    "profile.following_button_labels": [
        "Following",
    ],
    "profile.friends_button_labels": [
        "Friends",
    ],
    "profile.privacy_blocked_message": [
        "//*[contains(@text, \"Cannot send message\")]",
    ],
    "profile.private_indicator": [
        "//*[contains(@text, \"private\")]",
    ],
    "profile.private_videos_tab": [
        "//*[@content-desc=\"Private videos\"]",
    ],
    "profile.profile_menu_button": [
        "//android.widget.Button[@content-desc=\"Profile menu\"]",
    ],
    "profile.profile_page_indicator": [
        "//*[contains(@resource-id, \":id/qfv\")][@text=\"Followers\"]",
        "//*[contains(@resource-id, \":id/qfv\")][@text=\"Following\"]",
        "//*[contains(@resource-id, \":id/w4m\")][@text=\"No videos yet\"]",
    ],
    "profile.profile_photo": [
        "//android.widget.Button[@content-desc=\"Profile photo\"]",
    ],
    "profile.profile_views_button": [
        "//android.widget.Button[@content-desc=\"Profile views\"]",
    ],
    "profile.story_close_button": [
        "//*[@content-desc=\"Close\"][@clickable=\"true\"]",
    ],
    "profile.unable_to_send_message": [
        "//*[contains(@resource-id, \":id/w4m\")][@text=\"Unable to send message\"]",
        "//*[@text=\"Unable to send message\"]",
        "//*[contains(@text, \"Unable to send\")]",
    ],
    "profile.verified_badge": [
        "//*[contains(@content-desc, \"Verified\")]",
    ],
    "profile.videos_tab": [
        "//*[@content-desc=\"Videos\"]",
    ],
    # --- publish_composer ---
    "publish_composer.caption_input": [
        "//android.widget.EditText[contains(@hint, \"Add a description\")]",
        "//android.widget.EditText[contains(@text, \"Add a description\")]",
        "//android.widget.EditText[contains(@content-desc, \"Add a description\")]",
        "//android.widget.EditText[contains(@hint, \"description\")]",
        "//android.widget.EditText[contains(@hint, \"Description\")]",
        "//android.widget.EditText[contains(@content-desc, \"Description\")]",
        "//android.widget.EditText[contains(@hint, \"caption\")]",
    ],
    "publish_composer.post_btn": [
        "//android.widget.Button[@content-desc=\"Post\"]",
        "//android.widget.Button[contains(@content-desc, \"Post\")]",
        "//android.widget.Button[@text=\"Post\"]",
        "//android.widget.Button[contains(@text, \"Post\")]",
        "//android.widget.TextView[contains(@text, \"Post\")]",
    ],
    "publish_composer.post_screen_xml_markers": [
        "add a description",
    ],
    "publish_composer.publish_confirm_btn": [
        "//android.widget.Button[contains(@text, \"Publish now\")]",
    ],
    "publish_composer.publish_confirm_dialog": [
        "//*[contains(@text, \"Publish video publicly\")]",
    ],
    # --- publish_creation_entry ---
    "publish_creation_entry.create_btn": [
        "//android.widget.Button[@content-desc=\"Create\"]",
        "//android.widget.FrameLayout[@content-desc=\"Create\"]",
        "//android.widget.ImageView[@content-desc=\"Create\"]",
        "//android.widget.Button[contains(@content-desc, \"Create\")]",
    ],
    "publish_creation_entry.home_ready_indicators": [
        "//android.widget.Button[@content-desc=\"Create\"]",
        "//android.widget.Button[contains(@content-desc, \"Create\")]",
        "//android.widget.FrameLayout[@content-desc=\"Create\"]",
    ],
    # --- publish_editor ---
    "publish_editor.popup_cancel_buttons": [
        "//android.widget.Button[@text=\"CANCEL\"]",
        "//android.widget.Button[contains(@text, \"Cancel\")]",
        "//android.widget.Button[contains(@text, \"Not now\")]",
    ],
    "publish_editor.video_edit_cancel_btn": [
        "//android.widget.Button[contains(@text, \"Cancel\")]",
    ],
    # --- publish_media_picker ---
    "publish_media_picker.next_btn": [
        "//android.widget.Button[@text=\"Next\"]",
        "//android.widget.Button[contains(@text, \"Next\")]",
        "//android.widget.TextView[contains(@text, \"Next\")]",
    ],
    "publish_media_picker.upload_btn": [
        "//*[@content-desc=\"Upload\"]",
        "//*[contains(@content-desc, \"Upload\")]",
        "//*[@text=\"Upload\"]",
        "//*[contains(@text, \"Upload\")]",
        "//*[contains(@text, \"Gallery\")]",
    ],
    # --- publish_progress ---
    "publish_progress.success_indicator": [
        "//*[contains(@text, \"successfully\")]",
        "//*[contains(@text, \"published\")]",
        "//*[contains(@content-desc, \"Posted\")]",
    ],
    # --- scroll ---
    "scroll.end_of_list": [
        "//android.widget.TextView[contains(@text, \"No more\")]",
    ],
    # --- search ---
    "search.search_bar": [
        "//android.widget.EditText[contains(@content-desc, \"Search\")]",
    ],
    "search.search_button": [
        "//android.widget.Button[contains(@content-desc, \"Search\")]",
    ],
    "search.search_icon": [
        "//android.widget.ImageView[@content-desc=\"Search\"]",
        "//*[@content-desc=\"Search\"]",
    ],
    "search.search_input": [
        "//android.widget.EditText[contains(@hint, \"Search\")]",
        "//android.widget.EditText[contains(@content-desc, \"Search\")]",
    ],
    # === A2 anchor for the search field ===
    #
    # Measured on device (46.6.3, 2026-08-29): the field is `ho3` there, not `giv`, and it carries
    # NO hint -- its placeholder is a trending topic sitting in @text (a trending topic), so
    # the hint match could never fire either. `open_search` returned True onto a screen whose
    # field nothing could find, and every Followers / Search run died on "Failed to submit search".
    #
    # Anchored on the READABLE id of the neighbouring button rather than on a bare EditText: a
    # bare one also matches the conversation composer, on both versions.
    "search.search_input_anchors": [
        "//*[contains(@resource-id, \":id/tv_search_textview\")]/../..//android.widget.EditText",
    ],
    "search.search_submit_button": [
        "//*[contains(@resource-id, \":id/y61\")][@text=\"Search\"]",
        "//android.widget.Button[@text=\"Search\"]",
    ],
    "search.shop_tab": [
        "//android.widget.TextView[@text=\"Shop\"]",
    ],
    "search.sounds_tab": [
        "//android.widget.TextView[@text=\"Sounds\"]",
    ],
    "search.user_result_follow_button": [
        "//*[contains(@resource-id, \":id/rdh\")][@text=\"Follow\"]",
        "//android.widget.Button[@text=\"Follow\"]",
        "//android.widget.Button[@text=\"Following\"]",
    ],
    "search.videos_tab": [
        "//android.widget.TextView[@text=\"Videos\"]",
    ],
    "search.view_all_button": [
        "//*[contains(@resource-id, \":id/sm6\")][@text=\"View all\"]",
        "//android.widget.TextView[@text=\"View all\"]",
    ],
    # --- settings (path to the app language) ---
    #
    # MEASURED on a real English phone (43.1.4, 2026-08-29) — captured while the app was in
    # English, then used to switch it to French. Every label below was read off the screen, not
    # translated from the French one.
    "settings.settings_and_privacy_row": [
        "//*[@text=\"Settings and privacy\"]",
    ],
    # Ecrit d'apres le libelle francais mesure, et CONFIRME sur appareil au moment du
    # basculement vers l'anglais (aller-retour du 2026-08-30).
    "settings.content_and_display_row": [
        "//android.widget.TextView[@text=\"Content and display\"]",
        "//android.widget.TextView[@text=\"Content & display\"]",
        "//*[@clickable=\"true\"][.//android.widget.TextView[@text=\"Content and display\"]]",
        "//*[@clickable=\"true\"][.//android.widget.TextView[@text=\"Content & display\"]]",
    ],
    # Meme regle structurelle qu'en francais (Compose expose la ligne en `content-desc`).
    # A confirmer sur appareil lors de l'aller-retour vers l'anglais.
    "settings.language_row": [
        "//*[@content-desc=\"Language\"]",
        "//android.widget.TextView[@text=\"Language\"]",
    ],
    "settings.app_language_row": [
        "//*[starts-with(@content-desc, \"App language\")]",
        "//android.widget.TextView[@text=\"App language\"]",
    ],
    "settings.picker_indicator": [
        "//*[@text=\"App language\"][not(@clickable=\"true\")]",
    ],
    "settings.picker_confirm_button": [
        "//android.widget.Button[@text=\"Done\"]",
    ],
    "settings.picker_cancel_button": [
        "//android.widget.Button[@text=\"Cancel\"]",
    ],
    "settings.settings_back_button": [
        "//*[@content-desc=\"Back to previous screen\"]",
    ],
    # --- signup ---
    "signup.back_button": [
        "//android.widget.Button[@content-desc=\"Go back\"]",
        "//android.widget.Button[@content-desc=\"Navigate up\"]",
    ],
    "signup.birthday_continue_button": [
        "//android.widget.Button[@text=\"Continue\"]",
    ],
    "signup.birthday_day_picker": [
        "//android.widget.SeekBar[@content-desc=\"Day picker\"]",
    ],
    "signup.birthday_gate_inscription_link": [
        "//android.widget.Button[contains(@text, \"More fun\") and contains(@text, \"Sign up\")]",
        "//android.widget.Button[contains(@text, \"Sign up\")]",
        "//*[@clickable=\"true\" and contains(@text, \"Sign up\")]",
    ],
    "signup.birthday_input": [
        "//android.widget.EditText[@hint=\"Birthday\"]",
        "//android.widget.EditText[@hint=\"Date of birth\"]",
    ],
    "signup.birthday_month_picker": [
        "//android.widget.SeekBar[@content-desc=\"Month picker\"]",
    ],
    "signup.birthday_screen_indicator": [
        "//android.widget.TextView[contains(@text, \"date of birth\")]",
        "//android.widget.TextView[contains(@text, \"birthday\")]",
    ],
    "signup.birthday_year_picker": [
        "//android.widget.SeekBar[@content-desc=\"Year picker\"]",
    ],
    "signup.continue_button": [
        "//android.widget.Button[@text=\"Continue\"]",
    ],
    "signup.email_input": [
        "//android.widget.EditText[@hint=\"Email address\"]",
    ],
    "signup.nickname_continue_button": [
        "//android.widget.Button[@text=\"Continue\"]",
    ],
    "signup.nickname_entry_indicator": [
        "//android.widget.TextView[contains(@text, \"Create a username\")]",
    ],
    "signup.nickname_input": [
        "//android.widget.EditText[@hint=\"Add your username\"]",
    ],
    "signup.nickname_skip_button": [
        "//android.widget.Button[@text=\"Skip\"]",
    ],
    "signup.otp_continue_button": [
        "//android.widget.Button[@text=\"Continue\"]",
    ],
    "signup.otp_resend_button": [
        "//*[contains(@text, \"Resend\") and contains(@text, \"code\")]",
        "//*[contains(@content-desc, \"Resend\")]",
    ],
    "signup.otp_screen_indicator": [
        "//android.widget.TextView[contains(@text, \"Check your email\")]",
        "//android.widget.TextView[contains(@text, \"Use the link or code\")]",
        "//android.widget.TextView[contains(@text, \"verification code\")]",
        "//android.widget.TextView[contains(@text, \"Enter the code\")]",
        "//android.widget.TextView[contains(@text, \"Enter code\")]",
        "//*[contains(@text, \"Resend code\")]",
    ],
    "signup.password_continue_button": [
        "//android.widget.Button[@text=\"Continue\"]",
    ],
    "signup.password_entry_indicator": [
        "//android.widget.TextView[contains(@text, \"Create a password\")]",
    ],
    "signup.password_input": [
        "//android.widget.EditText[@hint=\"Enter password\"]",
    ],
    "signup.password_skip_button": [
        "//android.widget.Button[@text=\"Skip\"]",
    ],
    "signup.phone_input": [
        "//android.widget.EditText[@hint=\"Phone number\"]",
    ],
    "signup.register_screen_indicator": [
        "//android.widget.TextView[@content-desc=\"Sign up\"]",
    ],
    "signup.signup_link": [
        "//android.widget.Button[contains(@text, \"Sign up\")]",
    ],
    "signup.signup_popup_indicator": [
        "//android.widget.TextView[contains(@resource-id, \":id/title\") and contains(@text, \"Sign up\")]",
        "//android.widget.TextView[contains(@text, \"Sign up for TikTok\")]",
        "//*[@content-desc=\"Use phone or email\"]",
    ],
    "signup.tab_email": [
        "//*[@content-desc=\"Email\" and @clickable=\"true\"]",
        "//android.widget.LinearLayout[@content-desc=\"Email\"]",
    ],
    "signup.tab_phone": [
        "//*[@content-desc=\"Phone\" and @clickable=\"true\"]",
        "//android.widget.LinearLayout[@content-desc=\"Phone\"]",
    ],
    "signup.use_phone_or_email_button": [
        "//*[@content-desc=\"Use phone or email\"]",
        "//*[@clickable=\"true\" and ./android.widget.TextView[@text=\"Use phone or email\"]]",
        "//*[contains(@text, \"Use phone or email\")]",
    ],
    # --- video_creator ---
    "video_creator.creator_profile_image": [],
    "video_creator.follow_button": [
        "//android.widget.Button[contains(@content-desc, \"Follow\")]",
        "//*[contains(@content-desc, \"Follow\") and not(contains(@content-desc, \"Following\"))]",
    ],
    # --- video_engagement ---
    "video_engagement.comment_button": [
        "//*[contains(@content-desc, \"Read or add comments\")]",
    ],
    "video_engagement.comment_button_for_count": [],
    "video_engagement.favorite_button": [
        "//android.widget.Button[contains(@content-desc, \"Favourites\")]",
        "//android.widget.Button[contains(@content-desc, \"Favorites\")]",
        "//*[contains(@content-desc, \"Add or remove this video from Favour\")]",
    ],
    # === A2 anchors for the four video counters ===
    #
    # The count sits INSIDE its own button, and the button is named by its content-desc — not by
    # its id: the like button and the share button carry the SAME id on both versions, so an id
    # cannot tell those two apart at all.
    #
    # `descendant::` and not `following::`. The second steps OVER the button and lands on the
    # next counter, which returns a plausible number for the wrong field on every row — measured.
    # UNVERIFIED: every lab phone is fr-FR, so these phrases could not be read
    # off a screen. They follow the app's own wording; treat as a hypothesis.
    # Two things this rail does, learned from a low-engagement video: TikTok HIDES a count
    # that is zero (no comment node at all, not a node reading "0"), and it writes the
    # word "Partager" where the share count would be when nothing has been shared. So an
    # absent counter means zero, not a dead anchor — and a caller that treats absence as
    # failure will report a healthy screen as broken.
    # MEASURED on an English phone (43.1.4, 2026-08-29) — the first time any English entry in
    # this catalogue was ever put in front of a real screen. The device says
    # `Like video 22 likes`; this looked for "Like this video", which no screen carries, so the
    # like counter read nothing on an English phone while `like_button` (which says "Like video")
    # worked right next to it. The two could not both be right, and the wrong one was silent.
    "video_engagement.like_count_anchors": [
        "//*[starts-with(@content-desc, \"Like video\")]/descendant::*[@text != \"\"][1]",
    ],
    "video_engagement.comment_count_anchors": [
        "//*[starts-with(@content-desc, \"Read or add comments\")]/descendant::*[@text != \"\"][1]",
    ],
    "video_engagement.favorite_count_anchors": [
        "//*[starts-with(@content-desc, \"Add or remove this video\")]/descendant::*[@text != \"\"][1]",
    ],
    # Same measurement, same family: the device says `Share video 1 shares`, not "Share a video".
    # The French wording ("Partager une vidéo. N partages") reads as "Share a video", which is
    # very likely how the guess was made — a plausible translation is not a measurement.
    "video_engagement.share_count_anchors": [
        "//*[starts-with(@content-desc, \"Share video\")]/descendant::*[@text != \"\"][1]",
    ],
    "video_engagement.like_button": [
        "//*[@resource-id=\"com.zhiliaoapp.musically:id/f57\"][contains(@content-desc, \"Like video\")]",
        "//*[@resource-id=\"com.ss.android.ugc.trill:id/f57\"][contains(@content-desc, \"Like video\")]",
        "//*[@resource-id=\"com.ss.android.ugc.aweme:id/f57\"][contains(@content-desc, \"Like video\")]",
        "//android.widget.Button[contains(@content-desc, \"Like video\")]",
        "//*[contains(@content-desc, \"Like video\")]",
    ],
    "video_engagement.like_button_content_desc_fallbacks": [
        "//*[contains(@content-desc, \"Like video\")]",
    ],
    "video_engagement.like_button_for_count": [
        "//*[@resource-id=\"com.zhiliaoapp.musically:id/f57\"][contains(@content-desc, \"Like video\")]",
        "//*[@resource-id=\"com.ss.android.ugc.trill:id/f57\"][contains(@content-desc, \"Like video\")]",
        "//*[@resource-id=\"com.ss.android.ugc.aweme:id/f57\"][contains(@content-desc, \"Like video\")]",
        "//*[contains(@content-desc, \"Like video\")]",
    ],
    "video_engagement.share_button": [
        "//*[@resource-id=\"com.zhiliaoapp.musically:id/f57\"][contains(@content-desc, \"Share video\")]",
        "//*[@resource-id=\"com.ss.android.ugc.trill:id/f57\"][contains(@content-desc, \"Share video\")]",
        "//*[@resource-id=\"com.ss.android.ugc.aweme:id/f57\"][contains(@content-desc, \"Share video\")]",
        "//android.widget.Button[contains(@content-desc, \"Share video\")]",
        "//*[contains(@content-desc, \"Share video\")]",
    ],
    # --- video_media ---
    "video_media.sound_button": [
        "//android.widget.Button[contains(@content-desc, \"Sound:\")]",
    ],
    # --- video_share ---
    # ECRIT d'apres la structure francaise mesuree, PAS encore confirme sur un ecran anglais :
    # aucune feuille de partage n'a ete capturee en anglais. A verifier au prochain aller-retour.
    "video_share.copy_link_button": [
        "//*[@content-desc=\"Copy link\"]",
        "//*[@clickable=\"true\"][.//*[@text=\"Copy link\"]]",
    ],
    # Voir la note francaise : le repost passe par une confirmation. Libelles anglais mesures
    # Voir la note francaise. En anglais, mesure le 2026-08-30, le tap ne montre AUCUN ecran de
    # suite : la feuille se referme et on revient a la video. Un troisieme comportement pour la
    # meme action, ce qui est la raison pour laquelle l'etat -- et non l'ecran -- fait foi.
    "video_share.repost_followup_close": [
        '//*[@text="OK"]',
        '//*[@content-desc="OK"]',
        '//*[@content-desc="Close"]',
    ],
    # `Delete repost`, mesure sur appareil le 2026-08-30 -- PAS « Remove repost », qui etait une
    # traduction et non une mesure. Le repost avait bien pris ; c'est la lecture de l'etat qui
    # echouait, donc `repost_video` rendait False sur une republication reussie.
    "video_share.repost_done_indicator": [
        '//*[@content-desc="Delete repost"]',
        '//*[@clickable="true"][.//*[@text="Delete repost"]]',
    ],
    "video_share.repost_button": [
        "//*[@content-desc=\"Repost\"]",
        "//*[@clickable=\"true\"][.//*[@text=\"Repost\"]]",
    ],
    "video_share.sheet_indicator": [
        "//*[@content-desc=\"Bottom sheet\"]",
    ],
    # --- video_state ---
    "video_state.ad_label": [],
    "video_state.like_button_unliked": [
        "//*[@content-desc=\"Like video\"]",
        "//*[@resource-id=\"com.zhiliaoapp.musically:id/f57\"][contains(@content-desc, \"Like video\")]",
        "//*[@resource-id=\"com.ss.android.ugc.trill:id/f57\"][contains(@content-desc, \"Like video\")]",
        "//*[@resource-id=\"com.ss.android.ugc.aweme:id/f57\"][contains(@content-desc, \"Like video\")]",
    ],
    "video_state.subscribe_button": [
        "//android.widget.Button[contains(@text, \"Subscribe\")]",
        "//android.widget.Button[contains(@text, \"Shop now\")]",
    ],
    "video_state.unlike_indicator": [
        "//*[contains(@content-desc, \"Unlike\")]",
        "//*[contains(@content-desc, \"Liked\")]",
        "//*[@resource-id=\"com.zhiliaoapp.musically:id/f57\"][contains(@content-desc, \"Unlike\")]",
        "//*[@resource-id=\"com.ss.android.ugc.trill:id/f57\"][contains(@content-desc, \"Unlike\")]",
        "//*[@resource-id=\"com.ss.android.ugc.aweme:id/f57\"][contains(@content-desc, \"Unlike\")]",
    ],
    "video_state.user_followed_indicator": [
        "//android.widget.Button[@text=\"Following\"]",
        "//android.widget.Button[contains(@text, \"Friends\")]",
        "//*[contains(@content-desc, \"Unfollow\")]",
    ],
    "video_state.video_already_liked": [],
    "video_state.video_favorited_indicator": [
        "//*[contains(@content-desc, \"Remove from Favourites\")]",
    ],
    "video_state.video_liked_indicator": [
        "//android.widget.ImageView[contains(@content-desc, \"Unlike\")]",
    ],
    "video_state.video_page_indicator": [
        "//*[contains(@content-desc, \"Share video\")]",
    ],
}
