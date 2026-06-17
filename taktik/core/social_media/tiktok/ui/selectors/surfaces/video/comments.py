"""Sélecteurs UI pour les commentaires TikTok."""

from typing import List
from dataclasses import dataclass, field

from ...locales import L


@dataclass
class CommentSelectors:
    """Sélecteurs pour les commentaires TikTok."""

    _comment_input_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@resource-id, "comment_input")]'
    ])

    @property
    def comment_input(self) -> List[str]:
        return self._comment_input_base + L("comment.comment_input")

    _post_comment_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, "post")]'
    ])

    @property
    def post_comment_button(self) -> List[str]:
        return self._post_comment_button_base + L("comment.post_comment_button")

    comment_list: List[str] = field(default_factory=lambda: [
        '//androidx.recyclerview.widget.RecyclerView[contains(@resource-id, "comment_list")]',
        '//android.widget.ListView[contains(@resource-id, "comment")]'
    ])


COMMENT_SELECTORS = CommentSelectors()
