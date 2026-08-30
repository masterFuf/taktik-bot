"""Atomic actions for TikTok, arranged by WHAT THEY DO.

Same shape as the Instagram side, which is the point: `detection/ interaction/ navigation/
scroll/`, each folder carrying its own barrel, and this one re-exporting the names everything
already imports. TikTok's atomics had grown flat -- seventeen modules in one directory -- so
nothing said where a new one belonged and they simply piled up.

    detection/    reads the screen: state, extraction, collection. Nothing here acts.
    interaction/  acts on content: tap, like, comment, repost, the negative signal.
    navigation/   moves from one screen to another.
    scroll/       scrolling, humanized.
    messaging/    the DM surface: inbox, threads, requests, sending.

`messaging/` is the one folder Instagram has no equivalent for. Its DM composing lives in
`text/dm_composer.py` and the rest in workflows; TikTok's module opens the inbox, reads it,
navigates it and writes, which is a surface of its own rather than a kind of gesture.

Aggregate classes (backward-compatible):
    ClickActions       — VideoActions + PopupActions + profile/nav clicks
    NavigationActions  — SearchActions + bottom-nav/header/go_back
    DetectionActions   — VideoDetector + PopupDetector + page/error/app state
"""

from .detection import (
    AvatarActions,
    DetectionActions,
    PopupDetector,
    SoundActions,
    VideoDetector,
)
from .interaction import (
    ActivityActions,
    ClickActions,
    CommentActions,
    FeedTrainingActions,
    PopupActions,
    PostLinkActions,
    RepostActions,
    VideoActions,
)
from .messaging import DMActions
from .navigation import NavigationActions, SearchActions
from .scroll import ScrollActions

__all__ = [
    # Aggregate (backward-compat)
    "ClickActions",
    "NavigationActions",
    "ScrollActions",
    "DetectionActions",
    "DMActions",
    # Granular
    "ActivityActions",
    "AvatarActions",
    "CommentActions",
    "FeedTrainingActions",
    "PopupActions",
    "PopupDetector",
    "PostLinkActions",
    "RepostActions",
    "SearchActions",
    "SoundActions",
    "VideoActions",
    "VideoDetector",
]
