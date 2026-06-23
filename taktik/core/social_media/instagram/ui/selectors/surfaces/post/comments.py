from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .detail import POST_SELECTORS
from ...locales import L


@dataclass
class PostCommentsSelectors:
    """Selectors dedicated to the post comments surface."""

    comment_count: str = POST_SELECTORS.comment_count
    comment_button_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comment_button_indicators)
    )
    photo_comment_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.photo_comment_selectors)
    )
    comment_button_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comment_button_selectors)
    )
    comment_field_selector: str = POST_SELECTORS.comment_field_selector
    comment_field_resource_id: str = "com.instagram.android:id/layout_comment_thread_edittext"
    comment_field_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comment_field_selectors)
    )
    # Specific "is the comment composer already open?" indicators. Keyed off the composer
    # field/parent ids (cross-language — no localized "Comments" text) and the hint; uses
    # contains() so it matches version drift like `layout_comment_thread_edittext_multiline`
    # (IG v410). Deliberately NOT the broad `comment_field_selectors` (those include a bare
    # `//android.widget.EditText` that would false-positive on any screen with a text field).
    _comment_composer_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "layout_comment_thread_edittext")]',
        '//*[contains(@resource-id, "comment_composer")]',
    ])

    @property
    def comment_composer_indicators(self) -> List[str]:
        return self._comment_composer_indicators_base + L("post_comments.comment_composer_indicators")
    post_comment_button_resource_ids: Tuple[str, ...] = (
        "com.instagram.android:id/layout_comment_thread_post_button_icon",
        "com.instagram.android:id/layout_comment_thread_post_button_click_area",
        "com.instagram.android:id/layout_comment_thread_post_button_container",
    )
    post_comment_button_descriptions: Tuple[str, ...] = ("Post", "Publier")
    post_comment_debug_tokens: Tuple[str, ...] = ("post_button", "post", "publier", "send")
    post_comment_button_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.post_comment_button_selectors)
    )
    comment_button_resource_id: str = "com.instagram.android:id/row_feed_button_comment"
    button_class_name: str = POST_SELECTORS.button_class_name
    parent_view_group_class_name: str = "android.view.ViewGroup"
    comment_title_resource_id: str = "com.instagram.android:id/title_text_view"
    comment_title_texts: Tuple[str, ...] = ("Comments", "Commentaires")
    comments_list_resource_id: str = POST_SELECTORS.comments_list_resource_id
    comments_list_resource_key: str = "sticky_header_list"
    comment_username_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comment_username_selectors)
    )
    commenter_button_nodes_selector: str = POST_SELECTORS.all_button_nodes_selector
    comments_view_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comments_view_indicators)
    )
    comment_text_nodes_selector: str = (
        '//android.widget.TextView[contains(@resource-id, "row_comment_textview_comment") or '
        'contains(@resource-id, "comment_text")]'
    )
    comment_empty_state_view: str = '//*[@resource-id="com.instagram.android:id/comment_empty_state_view"]'
    comment_title_defocus: str = (
        '//*[contains(@resource-id, "title_text_view")]'
        '[@text="Comments" or @text="Commentaires"]'
    )
    comment_drag_handle_frame: str = '//*[contains(@resource-id, "bottom_sheet_drag_handle_frame")]'
    ime_nav_back_button: str = '//*[@resource-id="android:id/input_method_nav_back"]'
    comment_sort_button: str = POST_SELECTORS.comment_sort_button
    default_sort_label: str = "For you"
    sort_button_labels: Tuple[str, ...] = ("Most recent", "Les plus récents", "Meta Verified")
    sort_options: Dict[str, Tuple[str, ...]] = field(default_factory=lambda: {
        "for_you": ("For you", "Pour vous"),
        "most_recent": ("Most recent", "Les plus récents"),
        "meta_verified": ("Meta Verified", "Meta vérifié"),
    })
    ignored_username_tokens: Tuple[str, ...] = (
        "reply", "like", "send", "comments", "share", "post",
        "répondre", "publier", "partager", "envoyer",
        "for", "you", "most", "recent", "meta", "verified",
    )
    profile_content_description_patterns: Tuple[str, ...] = (
        r"View ([\w][\w.]{0,29})'s story",
        r"Go to ([\w][\w.]{0,29})'s profile",
        r"Voir le story de ([\w][\w.]{0,29})",
        r"Aller au profil de ([\w][\w.]{0,29})",
    )
    expand_replies_text_contains: Tuple[str, ...] = ("View", "Voir", "Afficher")
    expand_replies_positive_tokens: Tuple[str, ...] = ("repl", "réponse")
    expand_replies_hidden_tokens: Tuple[str, ...] = ("hide", "masquer")
    expand_replies_description_contains: Tuple[str, ...] = ("more repl", "more reply", "réponse")
    reply_button_labels: Tuple[str, ...] = ("reply", "répondre")
    reply_search_ignored_usernames: Tuple[str, ...] = ("like", "reply", "répondre")
    expand_replies_selector: str = POST_SELECTORS.expand_replies_selector
    post_comments_count_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.post_comments_count_selectors)
    )

    @property
    def post_comment_button_xpaths(self) -> List[str]:
        """Send/Post button xpaths, derived from the catalog-owned ids + descriptions.

        Lets callers that resolve selectors as xpath strings (e.g. a workflow's
        ``_find_element``) reuse the same centralized send-button signatures without
        re-declaring any literal id/text."""
        return (
            [f'//*[@resource-id="{rid}"]' for rid in self.post_comment_button_resource_ids]
            + [f'//*[@content-desc="{desc}"]' for desc in self.post_comment_button_descriptions]
        )

    def comments_list_selector(self) -> str:
        """Return the comments list selector from the catalog-owned resource id."""
        return f'//*[@resource-id="{self.comments_list_resource_id}"]'

    def sort_option_by_content_description(self, label: str) -> str:
        """Return the context-menu option selector for a visible sort label."""
        return f'//*[@content-desc="{label}"]'


POST_COMMENTS_SELECTORS = PostCommentsSelectors()
