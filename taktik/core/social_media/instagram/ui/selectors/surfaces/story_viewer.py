from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class StorySelectors:
    """Selectors for stories."""
    
    # === Éléments de base ===
    # Two ids and NO tag constraint, on purpose. IG 442 renamed the still-image node to
    # `reel_viewer_image_view` and made it a FrameLayout, so the old
    # `//android.widget.ImageView[... "reel_media_image"]` failed twice over — wrong id and wrong
    # class. Verified on a live 442 story: the node is
    # `FrameLayout#reel_viewer_image_view`. The legacy id stays for older builds; `contains`
    # keeps both forms package-agnostic, and this selector is joined into a `|` union by the
    # story-viewer detector, so a wider match here only makes that detection more robust.
    story_image: str = (
        '//*[contains(@resource-id, "reel_media_image")'
        ' or contains(@resource-id, "reel_viewer_image_view")]'
    )
    # No VideoView and no `reel_media_video` id survive on 442 — a video story renders into the
    # same `reel_viewer_media_container` a photo uses, with no distinct node of its own. This
    # selector is only ever read as part of the story-viewer DETECTION union (see
    # search_navigation), never to tell a photo from a video, so matching the shared container is
    # exactly what it needs: the union keeps firing whatever the story is made of.
    story_video: str = (
        '//*[contains(@resource-id, "reel_media_video")'
        ' or contains(@resource-id, "reel_viewer_media_container")]'
    )

    # === Home feed story tray ===
    feed_story_tray: str = '//*[contains(@resource-id, "reels_tray_container")]'
    feed_story_recycler: str = '//*[contains(@content-desc, "conteneur barre des reels") or contains(@content-desc, "reels tray")]'
    feed_story_buttons: str = '//*[contains(@resource-id, "reels_tray_container")]//android.widget.Button[contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "story")]'
    feed_unseen_story_buttons: str = '//*[contains(@resource-id, "reels_tray_container")]//android.widget.Button[contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "story") and (contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "non vus") or contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "unseen"))]'

    # === Profile / highlights ===
    # Active profile-avatar story ring (NOT a highlight, NOT a feed-tray bubble).
    #
    # IG v410 (real dump 2026-06-25, FR) reworked the profile header: the avatar story ring is now a
    # dedicated `reel_ring` View INSIDE `profile_header_avatar_container_*`, and the old
    # `row_profile_header_imageview` is gone — the clickable `avatar_on_profile_header_view` button's
    # content-desc is an UNRESOLVED resource ref (e.g. "@2131954018"), so the "story"/"non vue"
    # text marker no longer exists. We therefore detect the ring structurally via `reel_ring`,
    # scoped to the avatar container so highlights (highlights_reel_tray_recycler_view) and the home
    # feed tray (reels_tray_container) can never match. This is language-independent, and its centre
    # coincides with the avatar so clicking it opens the story. Note: the a11y tree no longer
    # exposes seen-vs-unseen, but a freshly-visited profile's ring is unseen in practice, and the
    # caller verifies the story viewer actually opened (a no-story tap is a harmless no-op).
    #
    # The second branch keeps the older-IG path (row_profile_header_imageview + "story"+"non
    # vue"/"unseen" content-desc) for cross-version coverage.
    profile_unseen_story_avatar: str = (
        '//*[contains(@resource-id, "profile_header_avatar_container")]'
        '//*[contains(@resource-id, "reel_ring")]'
        ' | '
        '//*[contains(@resource-id, "row_profile_header_imageview")'
        ' and contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "story")'
        ' and (contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "non vue")'
        ' or contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "unseen"))]'
    )
    highlight_tray: str = '//*[contains(@resource-id, "highlights_tray")]'
    highlight_recycler: str = '//*[contains(@resource-id, "highlights_reel_tray_recycler_view")]'
    highlight_buttons: str = '//*[contains(@resource-id, "highlights_reel_tray_recycler_view")]//android.widget.Button[contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "story")]'
    # Highlight thumbnail image. The content-desc wording differs per language and
    # EN: "<user>'s highlight story". Real dump 2026-06-08 (IG v410, FR).
    highlight_images: str = (
        '//*[contains(@resource-id, "highlights_reel_tray_recycler_view")]'
        '//*[contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "à la une")'
        ' or contains(translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "highlight story")]'
    )
    
    # === Stickers interactifs a EVITER quand on avance la story ===
    # Tapping these stickers opens a consumption sheet (countdown, poll, quiz, question,
    # slider, link…) that BLOCKS the story from advancing. The forward tap must avoid
    # their bounds. Based on resource-id, so language-independent. Only the countdown
    # sticker is confirmed by a real dump; the others are the known interactive stickers
    # (harmless when absent).
    interactive_sticker_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "countdown_sticker")]',
        '//*[contains(@resource-id, "poll_sticker")]',
        '//*[contains(@resource-id, "quiz_sticker")]',
        '//*[contains(@resource-id, "question_sticker")]',
        '//*[contains(@resource-id, "slider_sticker")]',
        '//*[contains(@resource-id, "story_link_sticker")]',
    ])

    # === Navigation ===
    next_story: str = '//android.widget.FrameLayout[contains(@resource-id, "story_viewer_container")]//android.widget.ImageView[contains(@content-desc, "Suivant") or contains(@content-desc, "Next")]'
    close_story: str = '//android.widget.ImageView[contains(@content-desc, "Fermer") or contains(@content-desc, "Close")]'
    
    # === Story count detection ===
    # Story viewer — the content-desc carries "story X of Y"
    story_viewer_text_container: str = '//*[contains(@resource-id, "reel_viewer_text_container")]'
    
    # Story header, with username and timestamp
    story_viewer_header: str = '//*[contains(@resource-id, "reel_viewer_header")]'
    story_viewer_title: str = '//*[contains(@resource-id, "reel_viewer_title")]'
    story_viewer_timestamp: str = '//*[contains(@resource-id, "reel_viewer_timestamp")]'
    story_author_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "reel_viewer_title")]',
        '//*[contains(@resource-id, "story_username")]',
        '//*[contains(@resource-id, "reel_viewer_username")]',
        '//*[contains(@resource-id, "username")]',
    ])
    
    # Story progress bar
    story_progress_bar: str = '//*[contains(@resource-id, "reel_viewer_progress_bar")]'
    story_viewer_root: str = '//*[contains(@resource-id, "reel_viewer_root")]'

    # === Ad / sponsored story (NOT to be treated as a friend story) ===
    story_sponsored_label: str = '//*[contains(@resource-id, "reel_item_sponsored_label") or contains(@content-desc, "sponsored story") or contains(@content-desc, "story sponsorisée") or contains(@content-desc, "Sponsorisé")]'
    
    # Story actions
    story_like_button: str = '//*[contains(@resource-id, "toolbar_like_button")]'
    story_share_button: str = '//*[contains(@resource-id, "toolbar_reshare_button")]'
    story_message_composer: str = '//*[contains(@resource-id, "message_composer_container") or contains(@resource-id, "reel_viewer_message_composer")]'
    story_reaction_toolbar: str = '//*[contains(@resource-id, "reel_reaction_toolbar")]'
    story_reaction_emojis: str = '//*[contains(@resource-id, "story_reactions_emoji")]'

STORY_SELECTORS = StorySelectors()
