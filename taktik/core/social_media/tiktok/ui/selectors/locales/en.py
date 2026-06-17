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
    "comment.comment_input": [
        "//android.widget.EditText[contains(@content-desc, \"Add comment\")]",
    ],
    "comment.post_comment_button": [
        "//android.widget.Button[contains(@content-desc, \"Post\")]",
    ],
    # --- conversation ---
    "conversation.back_button": [
        "//*[contains(@resource-id, \":id/nmy\")][@content-desc=\"Back\"]",
        "//android.widget.ImageView[@content-desc=\"Back\"]",
    ],
    "conversation.close_sticker_suggestion": [
        "//*[contains(@resource-id, \":id/dgd\")][@content-desc=\"Close\"]",
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
    "followers.follower_follow_button": [
        "//*[contains(@resource-id, \":id/rdh\")][@text=\"Follow\"]",
        "//android.widget.Button[contains(@resource-id, \":id/rdh\")][@text=\"Follow\"]",
    ],
    "followers.follower_following_button": [
        "//*[contains(@resource-id, \":id/rdh\")][@text=\"Following\"]",
        "//*[contains(@resource-id, \":id/rdh\")][@text=\"Friends\"]",
    ],
    "followers.followers_counter": [
        "//android.view.ViewGroup[@clickable=\"true\"][.//android.widget.TextView[@text=\"Followers\"]]",
        "//android.view.ViewGroup[@clickable=\"true\"][.//android.widget.TextView[contains(@resource-id, \":id/qfv\")][@text=\"Followers\"]]",
        "//*[.//android.widget.TextView[@text=\"Followers\"]][@clickable=\"true\"]",
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
    "navigation.friends_tab": [
        "//android.widget.FrameLayout[@content-desc=\"Friends\"]",
    ],
    "navigation.home_tab": [
        "//android.widget.FrameLayout[@content-desc=\"Home\"]",
    ],
    "navigation.home_tab_selected": [
        "//android.widget.FrameLayout[@content-desc=\"Home\"][@selected=\"true\"]",
    ],
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
    "popup.dismiss_button": [
        "//android.widget.Button[@text=\"Not now\"]",
        "//android.widget.Button[contains(@text, \"Not now\")]",
        "//android.widget.Button[contains(@text, \"Skip\")]",
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
        "//*[@text=\"Don't allow\"][@clickable=\"true\"]",
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
