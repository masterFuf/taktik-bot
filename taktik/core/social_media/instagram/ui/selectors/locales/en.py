"""English (en) UI string overlay for Instagram selectors.

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
        "//*[contains(@text, \"Allow access to your contacts\")]",
        "//android.widget.Button[@content-desc=\"Allow\"]",
    ],
    "auth.create_account_button": [
        "//android.view.View[@content-desc=\"Create new account\"]",
        "//android.widget.Button[@content-desc=\"Create new account\"]",
        "//*[.//android.view.View[@content-desc=\"Create new account\"]]",
    ],
    "auth.error_message_selectors": [
        "//android.widget.TextView[contains(@text, \"incorrect\")]",
        "//android.widget.TextView[contains(@text, \"Incorrect\")]",
        "//android.widget.TextView[contains(@text, \"suspended\")]",
        "//android.widget.TextView[contains(@text, \"blocked\")]",
        "//android.widget.TextView[contains(@text, \"too many\")]",
        "//android.widget.TextView[contains(@text, \"Try again\")]",
    ],
    "auth.forgot_password_button": [
        "//android.widget.Button[@content-desc=\"Forgot password?\"]",
        "//android.widget.Button[.//android.view.View[@content-desc=\"Forgot password?\"]]",
    ],
    "auth.google_autofill_dismiss_button": [
        "//android.widget.ImageView[@content-desc=\"Cancel\"]",
    ],
    "auth.home_logged_out_screen_indicators": [
        "//android.widget.Button[@content-desc=\"Log into another account\"]",
        "//android.view.View[@content-desc=\"Create new account\"]",
        "//android.widget.ImageView[@content-desc=\"Instagram from Meta\"]",
    ],
    "auth.location_permission_dialog": [
        "//*[contains(@text, \"Allow Instagram to access this device's location\")]",
    ],
    "auth.log_into_another_account_button": [
        "//android.widget.Button[@content-desc=\"Log into another account\"]",
        "//android.view.View[@content-desc=\"Log into another account\"]",
        "//*[contains(@content-desc, \"Log into another account\")]",
    ],
    "auth.login_button": [
        "//android.widget.Button[@content-desc=\"Log in\"]",
        "//android.widget.Button[.//android.view.View[@content-desc=\"Log in\"]]",
    ],
    "auth.login_screen_indicators": [
        "//android.widget.ImageView[@content-desc=\"Instagram from Meta\"]",
        "//android.widget.Button[contains(@content-desc, \"English\")]",
        "//android.widget.Button[@content-desc=\"Log in\"]",
    ],
    "auth.notification_popup": [
        "//android.widget.Button[contains(@text, \"Not Now\")]",
    ],
    "auth.password_field": [
        "//android.widget.EditText[contains(@content-desc, \"Password\")]",
    ],
    "auth.password_only_screen_indicators": [
        "//android.widget.Button[@content-desc=\"Forgot password?\"]",
    ],
    "auth.profile_selection_screen": [
        "//android.widget.Button[@content-desc=\"Use another profile\"]",
        "//android.widget.Button[@content-desc=\"Create new account\"]",
        "//*[contains(@text, \"Use another profile\")]",
    ],
    "auth.profile_tab_button": [
        "//android.widget.FrameLayout[@content-desc=\"Profile\"]",
    ],
    "auth.save_button_selectors": [
        "//android.widget.Button[@content-desc=\"Save\"]",
        "//android.widget.Button[.//android.view.View[@content-desc=\"Save\"]]",
    ],
    "auth.save_login_info_dialog_indicators": [
        "//android.widget.TextView[@resource-id=\"com.instagram.android:id/igds_headline_headline\" and @text=\"Save your login info?\"]",
    ],
    "auth.save_login_info_not_now_button": [],
    "auth.save_login_info_not_now_buttons": [],
    "auth.save_login_info_popup": [
        "//android.view.View[@content-desc=\"Save your login info?\"]",
        "//android.widget.TextView[@resource-id=\"com.instagram.android:id/igds_headline_headline\" and contains(@text, \"Save\")]",
    ],
    "auth.save_login_info_success_popup": [
        "//android.view.View[@content-desc=\"Save your login info?\"]",
        "//android.view.View[contains(@content-desc, \"Save your login info\")]",
        "//android.view.View[contains(@text, \"Save your login info\")]",
    ],
    "auth.signup_next_button": [
        "//android.widget.Button[@content-desc=\"Next\"]",
        "//android.view.View[@content-desc=\"Next\"]",
    ],
    "auth.two_factor_confirm_button": [
        "//android.widget.Button[contains(@text, \"Confirm\")]",
        "//android.widget.Button[contains(@text, \"Next\")]",
    ],
    "auth.two_factor_indicators": [
        "//android.widget.TextView[contains(@text, \"security code\")]",
        "//android.widget.TextView[contains(@text, \"verification\")]",
    ],
    "auth.use_another_profile_button": [
        "//android.widget.Button[@content-desc=\"Use another profile\"]",
        "//*[contains(@text, \"Use another profile\")]",
    ],
    "auth.username_clear_button": [
        "//android.widget.ImageView[@content-desc=\"Clear Username, email or mobile number text\"]",
        "//android.widget.ImageView[contains(@content-desc, \"Clear\") and contains(@content-desc, \"Username\")]",
    ],
    "auth.username_field": [
        "//android.widget.EditText[contains(@content-desc, \"Username, email or mobile number\")]",
    ],
    # --- button ---
    "button.comment_button": [
        "//*[contains(@content-desc, \"Comment\")]",
    ],
    "button.like_button": [
        "//*[contains(@content-desc, \"Like\")]",
    ],
    "button.save_button": [
        "//*[contains(@content-desc, \"Save\")]",
    ],
    "button.share_button": [
        "//*[contains(@content-desc, \"Share\")]",
    ],
    # --- content_creation ---
    "content_creation.caption_placeholder_texts": [
        "Write a caption...",
    ],
    "content_creation.create_button_texts": [
        "Create",
    ],
    "content_creation.edit_video_indicators": [
        "Edit video",
    ],
    "content_creation.location_button_texts": [
        "Add location",
    ],
    "content_creation.next_descriptions": [
        "Next",
    ],
    "content_creation.next_texts": [
        "Next",
    ],
    "content_creation.popup_button_texts": [
        "Got it",
        "Continue",
        "Not now",
        "Skip",
    ],
    "content_creation.post_type_texts": [
        "POST",
    ],
    "content_creation.publish_texts": [
        "Share",
    ],
    "content_creation.reel_draft_bodies": [
        "If you start a new video, this draft will be saved.",
    ],
    "content_creation.reel_draft_headlines": [
        "Keep editing your draft?",
    ],
    "content_creation.reel_draft_start_new_texts": [
        "Start new video",
    ],
    "content_creation.story_publish_texts": [
        "Share",
        "Your story",
    ],
    # --- detection ---
    "detection.business_account_indicators": [
        "//*[contains(@text, \"Professional\")]",
    ],
    "detection.carousel_selectors": [
        "//*[contains(@content-desc, \"likes\") and contains(@content-desc, \"comment\")]",
    ],
    "detection.end_of_list_indicators": [
        "//*[contains(@text, \"See all suggestions\")]",
        "//*[contains(@text, \"caught up\")]",
        "//*[contains(@text, \"No more suggestions\")]",
        "//*[contains(@text, \"End of list\")]",
        "//*[contains(@text, \"No more\")]",
        "//*[contains(@text, \"That's all\")]",
    ],
    "detection.error_message_indicators": [
        "//*[contains(@text, \"Error\")]",
        "//*[contains(@text, \"Failed\")]",
        "//*[contains(@text, \"Retry\")]",
    ],
    "detection.followers_list_end_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/row_text_textview\" and contains(@text, \"And \") and contains(@text, \" others\")]",
        "//*[contains(@text, \" others\") and @resource-id=\"com.instagram.android:id/row_text_textview\"]",
    ],
    "detection.hashtag_page_indicators": [
        "//*[contains(@text, \"posts\")]",
        "//*[contains(@text, \"Recent\")]",
        "//*[contains(@text, \"Top\")]",
    ],
    "detection.hashtag_search_bar_selectors": [
        "//android.widget.EditText[contains(@text, \"Search\")]",
    ],
    "detection.home_screen_indicators": [
        "//*[contains(@content-desc, \"Home\") and @selected=\"true\"]",
    ],
    "detection.liked_button_indicators": [
        "//*[contains(@content-desc, \"Unlike\")]",
    ],
    "detection.likes_count_selectors": [
        "//*[contains(@content-desc, \"likes\")]",
        "//android.widget.TextView[contains(@text, \"likes\")]",
    ],
    "detection.limited_followers_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/row_text_textview\" and contains(@text, \"We limit the number of followers\")]",
        "//*[contains(@text, \"We limit the number of followers shown\")]",
    ],
    "detection.load_more_selectors": [
        "//*[contains(@text, \"See more\")]",
        "//*[contains(@text, \"see more\")]",
        "//*[contains(@content-desc, \"See more\")]",
        "//*[contains(@text, \"Load more\")]",
        "//*[contains(@text, \"Show more\")]",
        "//*[@content-desc=\"Load more\"]",
        "//*[@content-desc=\"Show more\"]",
    ],
    "detection.loading_spinner_indicators": [
        "//*[contains(@content-desc, \"Loading\")]",
    ],
    "detection.login_required_indicators": [
        "//*[contains(@text, \"Log in\")]",
        "//*[contains(@text, \"Login\")]",
    ],
    "detection.own_profile_indicators": [
        "//*[@content-desc=\"Edit profile\"]",
        "//*[contains(@text, \"Edit profile\")]",
        "//*[contains(@text, \"Share profile\")]",
    ],
    "detection.post_error_indicators": [
        "//*[contains(@text, \"Sorry\")]",
        "//*[contains(@text, \"not found\")]",
        "//*[contains(@text, \"unavailable\")]",
        "//*[contains(@text, \"private\")]",
    ],
    "detection.post_screen_indicators": [
        "//*[contains(@content-desc, \"Like\")]",
        "//*[contains(@content-desc, \"Comment\")]",
    ],
    "detection.private_account_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/igds_headline_emphasized_headline\" and contains(@text, \"private\")]",
        "//*[@resource-id=\"com.instagram.android:id/row_profile_header_empty_profile_notice_title\" and @text=\"This account is private\"]",
        "//*[contains(@text, \"This account is private\")]",
        "//*[contains(@content-desc, \"This account is private\")]",
    ],
    "detection.profile_screen_indicators": [
        "//*[@content-desc=\"Edit profile\"]",
        "//*[contains(@text, \"Edit profile\")]",
        "//*[@resource-id=\"com.instagram.android:id/profile_header_follow_button\" and contains(@text, \"Follow\")]",
        "//*[@resource-id=\"com.instagram.android:id/profile_header_follow_button\" and contains(@text, \"Following\")]",
    ],
    "detection.rate_limit_indicators": [
        "//*[contains(@text, \"Too many requests\")]",
        "//*[contains(@text, \"Please wait\")]",
        "//*[contains(@text, \"Action blocked\")]",
    ],
    "detection.recent_tab_selectors": [
        "//android.widget.TextView[@text=\"Recent\"]",
        "//*[contains(@text, \"Recent\")]",
        "//android.widget.TextView[contains(@content-desc, \"Recent\")]",
    ],
    "detection.reel_indicators": [
        "//*[contains(@content-desc, \"Reel by\")]",
    ],
    "detection.search_bar_selectors": [
        "//android.widget.EditText[contains(@text, \"Search\")]",
    ],
    "detection.search_screen_indicators": [
        "//*[contains(@content-desc, \"Search\") and @selected=\"true\"]",
        "//android.widget.TextView[@package=\"com.instagram.android\" and contains(@text, \"Search\")]",
    ],
    "detection.suggestions_section_indicators": [
        "//*[contains(@text, \"See all suggestions\")]",
        "//*[contains(@text, \"Suggestions for you\")]",
        "//*[@resource-id=\"com.instagram.android:id/row_header_textview\" and contains(@text, \"Suggested for you\")]",
    ],
    "detection.verified_account_indicators": [
        "//*[contains(@content-desc, \"Verified\")]",
    ],
    # --- direct_message ---
    "direct_message.conversation_back_description_contains": [],
    "direct_message.conversation_back_descriptions": [
        "Back",
    ],
    "direct_message.direct_tab_content_desc": [],
    "direct_message.direct_tab_content_descriptions": [],
    "direct_message.dm_inbox_description_contains": [],
    "direct_message.inbox_recommendation_texts": [
        "Suggested for you",
    ],
    "direct_message.inbox_top_visible_texts": [
        "Search or ask Meta AI",
        "Search",
    ],
    "direct_message.new_message_button": [],
    "direct_message.outgoing_digest_prefixes": [],
    "direct_message.send_button": [
        "//*[contains(@content-desc, \"Send\")]",
        "//android.widget.ImageButton[contains(@content-desc, \"Send\")]",
    ],
    "direct_message.send_button_content_descriptions": [
        "Send",
    ],
    "direct_message.send_button_descriptions": [
        "Send",
        "Send message",
    ],
    # --- feed ---
    "feed.already_liked_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/row_feed_button_like\" and contains(@content-desc, \"Unlike\")]",
        "//*[contains(@content-desc, \"Unlike\")]",
    ],
    "feed.comment_button": [
        "//*[contains(@content-desc, \"Comment\")]",
    ],
    "feed.comment_input": [
        "//*[contains(@text, \"Add a comment\")]",
    ],
    "feed.comment_send_button": [
        "//*[contains(@content-desc, \"Post\")]",
        "//*[contains(@text, \"Post\")]",
    ],
    "feed.like_button": [
        "//*[contains(@content-desc, \"Like\")]",
    ],
    "feed.likes_count_button": [
        "//*[contains(@text, \"likes\")]",
    ],
    "feed.reel_indicators": [
        "//*[contains(@content-desc, \"Reel by\")]",
    ],
    "feed.sponsored_indicators": [
        "//*[contains(@text, \"Sponsored\")]",
        "//*[contains(@text, \"Ad\")]",
    ],
    # --- hashtag ---
    "hashtag.hashtag_header": [
        "//*[contains(@text, \"posts\")]",
    ],
    "hashtag.reel_author_container": [
        "//*[contains(@content-desc, \"Reel by\")]",
    ],
    # --- navigation ---
    "navigation.activity_tab": [
        "//*[contains(@content-desc, \"Activity\")]",
    ],
    "navigation.back_button": [
        "//*[contains(@content-desc, \"Back\")]",
    ],
    "navigation.back_buttons": [
        "//android.widget.ImageView[@content-desc=\"Back\"]",
        "//*[@content-desc=\"Back\"]",
    ],
    "navigation.close_button": [
        "//*[contains(@content-desc, \"Close\")]",
        "//*[contains(@content-desc, \"Cancel\")]",
    ],
    "navigation.explore_search_bar": [
        "//android.widget.TextView[contains(@text, \"Search\")]",
        "//android.widget.EditText[contains(@hint, \"Search\")]",
        "//*[contains(@content-desc, \"Search\")]",
    ],
    "navigation.explore_search_bar_texts": [
        "Search",
    ],
    "navigation.home_tab": [
        # not(systemui): the Android navigation bar Home button
        # (com.android.systemui:id/home_button) also has content-desc "Home";
        # without this guard, in a fullscreen story (no IG bottom bar) the bot
        # tapped the system Home button -> dropped out to the Android launcher.
        "//*[contains(@content-desc, \"Home\") and not(@package=\"com.android.systemui\")]",
    ],
    "navigation.home_tab_description_contains": [
        "Home",
    ],
    "navigation.home_tab_descriptions": [
        "Home",
    ],
    "navigation.posts_tab_options": [
        "//*[@content-desc=\"Posts\"]",
        "//*[@text=\"Posts\"]",
        "//android.widget.ImageView[@content-desc=\"Grid view\"]",
    ],
    "navigation.profile_tab": [
        "//*[contains(@content-desc, \"Profile\") and contains(@class, \"ImageView\") and not(@package=\"com.android.systemui\")]",
        "//*[contains(@content-desc, \"Profile\") and not(@package=\"com.android.systemui\")]",
    ],
    "navigation.recent_tab_selectors": [
        "//*[contains(@text, \"Recent\")]",
        "//*[contains(@content-desc, \"Recent\")]",
    ],
    "navigation.search_tab": [
        "//*[contains(@content-desc, \"Search\") and not(@package=\"com.android.systemui\")]",
    ],
    "navigation.search_tab_description_contains": [
        "Search",
    ],
    "navigation.search_tab_descriptions": [
        "Search and explore",
    ],
    "navigation.top_tab_selectors": [
        "//*[contains(@text, \"Top\")]",
        "//*[contains(@content-desc, \"Top\")]",
    ],
    # --- notification ---
    "notification.activity_entry": [
        "//*[contains(@content-desc, \"Notifications\")]",
    ],
    "notification.activity_tab": [
        "//*[contains(@content-desc, \"Activity\")]",
    ],
    "notification.notifications_screen_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/action_bar_title\" and @text=\"Notifications\"]",
    ],
    "notification.activity_screen_indicators": [
        "//*[contains(@text, \"Activity\")]",
    ],
    "notification.filter_button": [
        "//*[@resource-id=\"com.instagram.android:id/action_bar_button_action\" and @content-desc=\"Filter\"]",
        "//*[contains(@content-desc, \"Filter\")]",
        "//*[contains(@text, \"Filter\")]",
    ],
    "notification.inline_follow_request_text": [
        "//android.widget.TextView[contains(@text, \"requested to follow you\")]",
        "//android.widget.TextView[contains(@text, \"wants to follow you\")]",
    ],
    "notification.inline_confirm_button": [
        "//*[@resource-id=\"com.instagram.android:id/igds_button\" and @text=\"Confirm\"]",
        "//*[@resource-id=\"com.instagram.android:id/igds_button\" and contains(@text, \"Confirm\")]",
    ],
    "notification.inline_dismiss_button": [
        "//android.widget.ImageView[@content-desc=\"Dismiss\"]",
        "//*[contains(@content-desc, \"Dismiss\")]",
    ],
    "notification.follow_requests_header": [
        "//*[contains(@resource-id, \"activity_feed_newsfeed_story_row\")][.//*[contains(@text, \"Follow requests\")]]",
        "//*[contains(@text, \"Follow requests\")]",
    ],
    # Raw text of the grouped follow-requests digest row (NOT an xpath) — used to
    # drop that digest row from the classified feed since requests are surfaced apart.
    "notification.follow_requests_digest": [
        "Follow requests",
    ],
    # "Show more" button that loads older notifications (exact text to avoid the
    # inline "… more" comment expander).
    "notification.show_more": [
        "//*[@text=\"Show more\"]",
    ],
    # Header that marks the END of the pending follow-requests list on the
    # sub-screen (everything below is recommendations, not requests).
    "notification.suggested_for_you": [
        "//*[contains(@text, \"Suggested for you\")]",
    ],
    "notification.follow_requests_section": [
        "//*[contains(@text, \"Follow requests\")]",
    ],
    "notification.comment_mention_text": [
        "//android.widget.TextView[contains(@text, \"mentioned you in a comment\")]",
    ],
    "notification.reply_button": [
        "//android.widget.Button[@text=\"Reply\"]",
        "//*[contains(@text, \"Reply\")]",
    ],
    # Inline "Like button" affordance on a comment / mention row (content-desc,
    # NOT an xpath — matched by EXACT equality against a node's content-desc so the
    # already-liked state "Unlike button" never matches and re-unlikes).
    "notification.inline_like_button": [
        "Like button",
    ],
    "notification.comment_like_text": [
        "//android.widget.TextView[contains(@text, \"liked your comment\")]",
    ],
    "notification.message_row_text": [
        "//android.widget.TextView[contains(@text, \"You have a message from\")]",
    ],
    "notification.notification_action_text": [
        "//android.widget.TextView[contains(@text, \"liked\")]",
        "//android.widget.TextView[contains(@text, \"started following\")]",
        "//android.widget.TextView[contains(@text, \"commented\")]",
    ],
    "notification.notification_username": [
        "//android.widget.TextView[contains(@text, \"@\")]",
    ],
    "notification.follow_requests_screen_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/action_bar_title\" and @text=\"Discover people\"]",
    ],
    "notification.request_accept_button": [
        "//*[@resource-id=\"com.instagram.android:id/row_requested_user_accept_secondary\" and @text=\"Confirm\"]",
        "//*[@resource-id=\"com.instagram.android:id/row_requested_user_accept_secondary\" and contains(@text, \"Confirm\")]",
    ],
    "notification.request_ignore_button": [
        "//*[@resource-id=\"com.instagram.android:id/row_requested_user_ignore\" and @text=\"Remove\"]",
        "//*[@resource-id=\"com.instagram.android:id/row_requested_user_ignore\" and contains(@text, \"Remove\")]",
    ],
    "notification.see_all_header": [
        "//*[@resource-id=\"com.instagram.android:id/row_header_action\" and contains(@text, \"See all\")]",
        "//*[contains(@text, \"See all\")]",
    ],
    # --- notification classifier text fragments (plain substrings, matched
    # case-insensitively via `contains` against an activity-feed row's text).
    # NOT XPath: these are the localized phrases that identify the row TYPE.
    # EN strings are confirmed from real device dumps. ---
    "notification.type_comment_mention": [
        "mentioned you in a comment",
    ],
    "notification.type_comment_reply": [
        "replied to your comment",
    ],
    "notification.type_comment_like": [
        "liked your comment",
    ],
    "notification.type_post_comment": [
        "commented on your post",
        "commented on your photo",
        "commented on your video",
        "commented",
    ],
    "notification.type_post_like": [
        "liked your photo",
        "liked your post",
        "liked your video",
        "liked your reel",
    ],
    "notification.type_new_follower": [
        "started following you",
    ],
    "notification.type_follow_request": [
        "requested to follow you",
        "wants to follow you",
    ],
    "notification.type_message": [
        "you have a message from",
        "message from",
    ],
    "notification.type_shared": [
        "shared a photo",
        "published a thread",
        "shared a post",
        "shared",
    ],
    # --- popup ---
    "popup.automation_popup_indicators": [
        "//android.widget.TextView[@text='Likes']",
        "//android.widget.TextView[@text='Like']",
        "//android.widget.EditText[contains(@text, 'Search')]",
        "//android.widget.ImageView[@content-desc='Close']",
        "//android.widget.Button[@text='Follow']",
    ],
    "popup.automation_user_selectors": [
        "//android.widget.LinearLayout[.//android.widget.TextView and .//android.widget.Button[@text='Follow']]",
        "//android.view.ViewGroup[.//android.widget.TextView and .//android.widget.Button[@text='Follow']]",
    ],
    "popup.close_popup_selectors": [
        "//android.widget.ImageView[@content-desc='Close']",
        "//android.widget.Button[@content-desc='Close']",
    ],
    "popup.comments_view_indicators": [
        "//*[@text=\"Comments\"]",
        "//*[contains(@text, \"What do you think\")]",
        "//*[contains(@text, \"Add a comment\")]",
        "//*[contains(@hint, \"Add a comment\")]",
        "//*[contains(@hint, \"What do you think\")]",
    ],
    "popup.follow_suggestions_close_methods": [
        "//*[contains(@content-desc, \"Close\")]",
        "//*[contains(@content-desc, \"Dismiss\")]",
    ],
    "popup.follow_suggestions_indicators": [
        "//android.widget.TextView[contains(@text, \"Suggested for you\")]",
        "//*[contains(@content-desc, \"Suggested\")]",
    ],
    "popup.likers_popup_indicators": [],
    "popup.not_now_selectors": [
        "//android.widget.Button[contains(@text, \"Not Now\")]",
        "//android.widget.TextView[contains(@text, \"Not Now\")]",
    ],
    "popup.review_account_cancel_button": [
        "//android.widget.Button[@text=\"Cancel\"]",
        "//android.widget.TextView[@text=\"Cancel\"]",
    ],
    "popup.review_account_follow_button": [
        "//android.widget.Button[@text=\"Follow\"]",
        "//android.widget.Button[contains(@text, \"Follow\") and not(contains(@text, \"Following\"))]",
    ],
    "popup.review_account_popup_indicators": [
        "//android.widget.TextView[contains(@text, \"Review this account\")]",
        "//android.widget.TextView[contains(@text, \"before following\")]",
        "//android.widget.TextView[contains(@text, \"Date joined\")]",
        "//android.widget.TextView[contains(@text, \"Account based in\")]",
    ],
    "popup.unfollow_confirmation_selectors": [
        "//*[contains(@text, \"Unfollow\")]",
        "//*[contains(@text, \"Confirm\")]",
    ],
    # --- post ---
    "post.automation_like_count_selectors": [
        "//android.view.ViewGroup[@content-desc='Like']/following-sibling::android.widget.Button[1]",
        "//android.widget.TextView[contains(@text, 'like') and not(contains(@text, 'comment'))]",
    ],
    "post.automation_like_indicators": [
        "//android.view.ViewGroup[@content-desc='Like']/following-sibling::android.widget.Button[contains(@text, '1') or contains(@text, '2') or contains(@text, '3') or contains(@text, '4') or contains(@text, '5') or contains(@text, '6') or contains(@text, '7') or contains(@text, '8') or contains(@text, '9')]",
    ],
    "post.automation_reel_specific_indicators": [
        "//android.widget.Button[@content-desc='Like this reel']",
        "//android.widget.Button[@content-desc='Share this reel']",
        "//android.widget.TextView[contains(@text, 'Original audio')]",
    ],
    "post.back_button_selectors": [
        "//android.widget.ImageView[@content-desc=\"Back\"]",
        "//*[@content-desc=\"Back\"]",
    ],
    "post.classic_post_indicators": [
        "//android.widget.TextView[contains(@text, 'View all') and contains(@text, 'comment')]",
        "//android.widget.Button[@content-desc='Comment']",
    ],
    "post.comment_button_indicators": [
        "//android.widget.Button[contains(@content-desc, 'Comment')]",
    ],
    "post.comment_button_selectors": [
        "//*[contains(@content-desc, \"Comment\") and @clickable=\"true\"]",
        "//android.widget.ImageView[contains(@content-desc, \"Comment\")]",
    ],
    "post.comment_field_selectors": [
        "//*[contains(@hint, \"Add a comment\")]",
    ],
    "post.comments_view_indicators": [
        "//*[contains(@text, \"Comments\")]",
        "//*[contains(@content-desc, \"Add a comment\")]",
    ],
    "post.copy_link_description_labels": [
        "Copy link",
    ],
    "post.copy_link_labels": [
        "Copy link",
        "Copy Link",
    ],
    "post.like_button_advanced_selectors": [
        "//*[contains(@content-desc, \"Like\")][@clickable=\"true\"]",
    ],
    "post.like_button_indicators": [],
    "post.like_count_selectors": [],
    "post.liked_by_selectors": [
        "//*[starts-with(@text, \"Liked by\")]",
    ],
    "post.likes_count_click_selectors": [
        "//*[contains(@text, \"likes\")]",
    ],
    "post.next_post_button_selectors": [
        "//android.widget.Button[contains(@content-desc, \"Next\")]",
        "//android.widget.ImageView[contains(@content-desc, \"Next\")]",
    ],
    "post.photo_comment_selectors": [
        "//*[@resource-id=\"com.instagram.android:id/row_feed_photo_imageview\" and contains(@content-desc, \"comment\")]",
        "//*[contains(@content-desc, \"likes\") and contains(@content-desc, \"comment\")]",
    ],
    "post.photo_like_selectors": [
        "//*[@resource-id=\"com.instagram.android:id/row_feed_photo_imageview\" and contains(@content-desc, \"likes\")]",
        "//*[contains(@content-desc, \"likes\") and contains(@content-desc, \"comment\")]",
    ],
    "post.post_comment_button_selectors": [
        "//*[@text=\"Post\" and @clickable=\"true\"]",
        "//*[contains(@content-desc, \"Post\") and @clickable=\"true\"]",
    ],
    "post.post_detail_indicators": [
        "//*[@content-desc=\"Like\"]",
        "//*[@content-desc=\"Comment\"]",
    ],
    "post.post_elements": [
        "//android.widget.Button[@content-desc='Like']",
        "//android.widget.Button[@content-desc='Comment']",
    ],
    "post.post_view_indicators": [
        "//*[contains(@content-desc, \"Like\")]",
        "//*[contains(@content-desc, \"Comment\")]",
    ],
    "post.reel_author_username_selectors": [
        "//*[contains(@content-desc, \"Profile picture of\")]/..//android.widget.Button[@text]",
    ],
    "post.reel_indicators": [
        "//*[contains(@content-desc, \"Reel by\")]",
    ],
    "post.reel_like_selectors": [
        "//android.widget.TextView[contains(@text, \"likes\")]",
    ],
    "post.reel_player_indicators": [
        "//*[contains(@content-desc, \"Turn sound on\")]",
        "//*[contains(@content-desc, \"Turn sound off\")]",
    ],
    "post.save_button_selectors": [
        "//android.widget.ImageView[contains(@content-desc, \"Save\")]",
    ],
    "post.send_post_button_selectors": [
        "//*[contains(@content-desc, \"Post\")]",
        "//*[contains(@text, \"Post\")]",
        "//*[contains(@content-desc, \"Share\")]",
        "//*[contains(@text, \"Share\")]",
    ],
    "post.share_button_selectors": [
        "//*[@content-desc=\"Send Post\"]",
        "//android.widget.ImageView[contains(@content-desc, \"Share\")]",
    ],
    "post.timestamp_selectors": [],
    "post.username_extraction_selectors": [],
    "post.video_controls": [
        "//android.widget.Button[@content-desc='Play']",
        "//android.widget.Button[@content-desc='Pause']",
    ],
    "post.video_player_selectors": [
        "//android.widget.ImageView[contains(@content-desc, \"video\")]",
    ],
    # --- post_comments ---
    "post_comments.comment_composer_indicators": [
        "//*[contains(@hint, \"Add a comment\")]",
    ],
    # --- post_grid ---
    "post_grid.back_button_selectors": [
        "//android.widget.ImageView[@content-desc=\"Back\"]",
        "//*[@content-desc=\"Back\"]",
    ],
    "post_grid.next_post_button_selectors": [
        "//android.widget.Button[contains(@content-desc, \"Next\")]",
        "//android.widget.ImageView[contains(@content-desc, \"Next\")]",
    ],
    # --- profile ---
    "profile.about_account_based_in_value": [
        "//*[contains(@content-desc, \"Account based in\")]/android.view.View[2]",
    ],
    "profile.about_account_date_joined_value": [
        "//*[contains(@content-desc, \"Date joined\")]/android.view.View[2]",
    ],
    "profile.about_account_page_indicators": [
        "//*[@resource-id=\"com.instagram.android:id/action_bar_title\" and @text=\"About this account\"]",
    ],
    "profile.advanced_follow_selectors": [
        "//android.widget.Button[@text=\"Follow\" and not(contains(@content-desc, \"followers\")) and not(contains(@content-desc, \"following\"))]",
        "//android.widget.Button[contains(@content-desc, \"Follow\") and not(contains(@content-desc, \"followers\"))]",
    ],
    "profile.follow_button": [
        "//*[contains(@text, \"Follow\") and not(contains(@text, \"Following\"))]",
    ],
    "profile.follow_button_text_labels": [
        "Follow",
    ],
    "profile.followers_link": [
        "//*[contains(@content-desc, \"followers\")]",
        "//*[contains(@content-desc, \"Followers\")]",
        "//android.view.ViewGroup[.//android.widget.TextView[contains(@text, \"followers\")]]",
        "//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, \"followers\")]]",
        "//android.widget.TextView[contains(@text, \"followers\")]",
        "//android.widget.TextView[contains(@text, \"Followers\")]",
    ],
    "profile.following_button": [
        "//*[contains(@text, \"Following\")]",
    ],
    "profile.following_link": [
        "//*[contains(@content-desc, \"following\")]",
        "//*[contains(@content-desc, \"Following\")]",
        "//android.view.ViewGroup[.//android.widget.TextView[contains(@text, \"following\")]]",
        "//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, \"following\")]]",
        "//android.widget.TextView[contains(@text, \"following\")]",
        "//android.widget.TextView[contains(@text, \"Following\")]",
    ],
    "profile.message_button": [],
    "profile.message_button_text_labels": [],
    "profile.private_indicators": [
        "//*[contains(@text, \"Private\")]",
        "//*[contains(@text, \"private\")]",
        "//*[contains(@text, \"Follow to see\")]",
        "//*[contains(@content-desc, \"Private\")]",
    ],
    "profile.private_text_contains": [
        "account is private",
    ],
    "profile.zero_posts_indicators": [],
    # --- scroll ---
    "scroll.end_of_list_indicators": [
        "//*[contains(@text, \"See all suggestions\")]",
        "//*[contains(@text, \"caught up\")]",
        "//*[contains(@text, \"No more suggestions\")]",
        "//*[contains(@text, \"End of list\")]",
        "//*[contains(@text, \"No more\")]",
        "//*[contains(@text, \"That's all\")]",
    ],
    "scroll.load_more_selectors": [
        "//*[contains(@text, \"See more\")]",
        "//*[contains(@text, \"see more\")]",
        "//*[contains(@content-desc, \"See more\")]",
        "//*[contains(@text, \"Load more\")]",
        "//*[contains(@text, \"Show more\")]",
        "//*[@content-desc=\"Load more\"]",
        "//*[@content-desc=\"Show more\"]",
    ],
    # --- settings (Settings and activity -> Language and translations) ---
    "settings.language_and_translations_row": [
        "//*[@text=\"Language and translations\"]",
        "//*[contains(@text, \"Language and translations\")]",
    ],
    "settings.set_language_row": [
        "//*[@resource-id=\"com.instagram.android:id/row_simple_text_title\" and @text=\"Set language\"]",
        "//*[@text=\"Set language\"]",
    ],
    # --- text_input ---
    "text_input.bio_field_selectors": [
        "//*[contains(@hint, \"Bio\")]",
    ],
    "text_input.caption_field_selectors": [
        "//*[contains(@hint, \"Write a caption\")]",
    ],
    "text_input.comment_field_selectors": [
        "//*[contains(@hint, \"Add a comment\")]",
    ],
    "text_input.send_button_selectors": [
        "//*[contains(@content-desc, \"Send\")]",
    ],
    # --- unfollow ---
    "unfollow.follow_button_after_unfollow": [
        "//*[contains(@text, \"Follow\") and not(contains(@text, \"Following\"))]",
    ],
    "unfollow.following_button": [
        "//*[contains(@text, \"Following\")]",
        "//*[@resource-id=\"com.instagram.android:id/profile_header_follow_button\" and contains(@text, \"Following\")]",
    ],
    "unfollow.following_tab": [
        "//android.widget.Button[contains(@text, \"following\")]",
        "//*[contains(@content-desc, \"following\")]",
    ],
    "unfollow.follows_back_indicators": [
        "//*[contains(@text, \"Follows you\")]",
        "//*[contains(@content-desc, \"Follows you\")]",
    ],
    "unfollow.sort_button": [
        "//*[@content-desc=\"Sort by\"]",
    ],
    "unfollow.sort_option_default": [
        "//*[@resource-id=\"com.instagram.android:id/follow_list_sorting_option\"][@text=\"Default\"]",
    ],
    "unfollow.sort_option_earliest": [
        "//*[@resource-id=\"com.instagram.android:id/follow_list_sorting_option\"][@text=\"Date followed: Earliest\"]",
    ],
    "unfollow.sort_option_latest": [
        "//*[@resource-id=\"com.instagram.android:id/follow_list_sorting_option\"][@text=\"Date followed: Latest\"]",
    ],
    "unfollow.unfollow_confirm": [
        "//*[contains(@text, \"Unfollow\")]",
        "//android.widget.Button[contains(@text, \"Unfollow\")]",
    ],
    # --- watchdog ---
    "watchdog.ok_button_texts": [
        "Dismiss",
    ],
}
