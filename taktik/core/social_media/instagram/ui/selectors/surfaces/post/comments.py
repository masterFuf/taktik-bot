from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .detail import POST_SELECTORS
from ...locales import L
from ...support.blocking_modals import BLOCKING_MODAL_SELECTORS


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
    # Signature of the Direct "Send post" share sheet (opened by a mis-tap on the share button next to
    # comment). Sourced from the shared blocking-modal registry so the comment action, the interaction
    # engine and the watchdog all detect the SAME language-independent resource-ids (single source of
    # truth). Used to detect + back out of the sheet so a mis-tap never BLOCKS the workflow.
    share_sheet_indicators: List[str] = field(
        default_factory=lambda: BLOCKING_MODAL_SELECTORS.signature_xpath_list("direct_share_sheet")
    )
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

    @property
    def comment_said_connectors(self) -> List[str]:
        """The word IG puts between an author and its comment body on 442 ("said", "a dit").

        Compose renders the body as "<handle> <connector> <text>" in both text and
        content-desc; the reader strips the handle and this fragment to recover the comment.
        """
        return L("post_comments.comment_said_connectors")

    @property
    def comment_like_labels(self) -> List[str]:
        """Content-desc fragments of a comment's heart in its NOT-liked state."""
        return L("post_comments.comment_like_button")

    @property
    def comment_unlike_labels(self) -> List[str]:
        """Content-desc fragments of a comment's heart in its ALREADY-liked state."""
        return L("post_comments.comment_unlike_button")

    @property
    def commenter_button_nodes_in_list_selector(self) -> str:
        """Commenter buttons, scoped to the comments list itself.

        The unscoped variant sweeps the WHOLE screen, so it also returns the post card's own
        counter buttons sitting under the sheet ("18.5K", "428", "4") — empty content-desc,
        numeric text, indistinguishable from a username by attributes alone. Scoping to the
        comments RecyclerView removes them structurally instead of by guesswork.
        """
        return f"{self.comments_list_selector()}{self.commenter_button_nodes_selector}"
    comments_view_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comments_view_indicators)
    )
    comment_text_nodes_selector: str = (
        '//android.widget.TextView[contains(@resource-id, "row_comment_textview_comment") or '
        'contains(@resource-id, "comment_text")]'
    )
    _comment_empty_state_view_base: str = (
        '//*[@resource-id="com.instagram.android:id/comment_empty_state_view"]'
    )

    @property
    def comment_empty_state_view(self) -> str:
        """"Nobody has commented yet" — by id first, then by its localized wording.

        IG 442 draws the empty state in Compose: a ViewGroup carrying the sentence and NO
        resource-id, so the id alone answered "not empty" on a thread that plainly was. The
        difference matters: a thread that is empty and a thread that failed to load look the
        same to a caller that cannot tell them apart.
        """
        clauses = [self._comment_empty_state_view_base]
        for fragment in L("post_comments.comment_empty_state_texts"):
            clauses.append(f'//*[contains(@text, "{fragment}")]')
        return " | ".join(clauses)
    comment_title_defocus: str = (
        '//*[contains(@resource-id, "title_text_view")]'
        '[@text="Comments" or @text="Commentaires"]'
    )
    comment_drag_handle_frame: str = '//*[contains(@resource-id, "bottom_sheet_drag_handle_frame")]'
    ime_nav_back_button: str = '//*[@resource-id="android:id/input_method_nav_back"]'
    @property
    def comment_sort_button(self) -> str:
        """The sort control of a comments sheet, showing whatever sort is CURRENTLY applied.

        It used to be the single English content-desc "For you", so it matched nothing on a
        French phone -- and the caller then went on believing it had switched the sort while the
        thread stayed on the default. Every label the catalog knows is accepted, on text as well
        as content-desc: on IG 442 the label lives in the TEXT of a child View that carries no
        content-desc at all (measured: `<Button><View text="Pour vous"/></Button>`).
        """
        labels = [label for pair in self.sort_options.values() for label in pair]
        predicate = " or ".join(f'@text="{label}" or @content-desc="{label}"' for label in labels)
        # Scoped to the comments list, and not for tidiness: the FEED's own header reads "Pour
        # vous" too, and so does a tab on the hashtag page, so the unscoped form matched a
        # control on screens that have no comment sorting at all. Measured across the captured
        # screens, the scoped form answers 1 on a populated comments sheet and 0 on every other.
        return f"{self.comments_list_selector()}//*[{predicate}]"
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
    @property
    def expand_replies_selector(self) -> str:
        """The "view N replies" affordance, in every language this catalog knows.

        The single English form it replaced ('View ... more repl' on content-desc) matched
        nothing on a French phone and nothing on 442 either, where the row reads "Voir 1
        reponse precedente" / "Voir 3 autres reponses" and carries it in text AND
        content-desc. Composed from the vocabulary already declared above, so no new literal
        enters here, and the COLLAPSE variant is excluded -- it opens with the same word.
        """
        def any_of(tokens):
            forms = []
            for token in tokens:
                for form in {token, token.capitalize(), token.lower()}:
                    forms.append(f'contains(@text, "{form}")')
                    forms.append(f'contains(@content-desc, "{form}")')
            return "(" + " or ".join(forms) + ")"

        return (
            f"//*[{any_of(self.expand_replies_text_contains)}"
            f" and {any_of(self.expand_replies_positive_tokens)}"
            f" and not({any_of(self.expand_replies_hidden_tokens)})]"
        )
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

    def sort_option_selector(self, label: str) -> str:
        """The sort menu's option carrying `label`, by content-desc or by text.

        Measured on 442: an option is `<Button resource-id=context_menu_item content-desc="Les
        plus recents">` wrapping a `<TextView content-desc="" text="Les plus recents">`, so the
        label appears on one attribute or the other depending which node answers first.
        """
        return f'//*[@content-desc="{label}" or @text="{label}"]'


POST_COMMENTS_SELECTORS = PostCommentsSelectors()
