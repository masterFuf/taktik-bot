"""Sélecteurs UI pour les commentaires TikTok."""

from typing import List
from dataclasses import dataclass, field


@dataclass
class CommentSelectors:
    """Sélecteurs pour les commentaires TikTok."""
    
    comment_input: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@content-desc, "Add comment")]',
        '//android.widget.EditText[contains(@content-desc, "Ajouter un commentaire")]',
        '//android.widget.EditText[contains(@resource-id, "comment_input")]'
    ])
    
    post_comment_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@content-desc, "Post")]',
        '//android.widget.Button[contains(@content-desc, "Publier")]',
        '//android.widget.Button[contains(@resource-id, "post")]'
    ])
    
    comment_list: List[str] = field(default_factory=lambda: [
        '//androidx.recyclerview.widget.RecyclerView[contains(@resource-id, "comment_list")]',
        '//android.widget.ListView[contains(@resource-id, "comment")]'
    ])


COMMENT_SELECTORS = CommentSelectors()
