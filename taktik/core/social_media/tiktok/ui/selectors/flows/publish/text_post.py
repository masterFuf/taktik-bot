"""Selectors for TikTok's TEXT post, a format the bot could not reach at all.

The creation screen offers four modes -- CRÉER, PHOTO, TEXTE, LIVE -- beside the gallery upload the
existing workflow uses. This catalogue covers the TEXTE one, measured end to end on 46.6.3 on
2026-08-30 by publishing a real post:

    Créer -> TEXTE -> type into the field -> Terminé -> "Publi. dans le fil" -> published

Everything on that road is readable, which is unusual enough on this app to be worth saying: the
mode tabs carry their labels as text, the composer has a real resource-id (`hnq`) and a placeholder,
and the destination is a labelled button. No obfuscated id is load-bearing here.

The one trap, and it cost an hour: the field is a genuine `EditText` that focuses on tap, but
`set_text` fails on this device -- `NoSuchMethodException: android.hardware.input.InputManager
.getInstance`, so uia2 cannot inject keys. Typing goes through the TAKTIK keyboard, like every
other field in this codebase.
"""

from dataclasses import dataclass, field
from typing import List

from ...locales import L
from ._shared import resource_ids


@dataclass
class PublishTextPostSelectors:
    """The TEXT mode of the creation screen, and the road out of it."""

    #: The composer itself. `hnq` is a readable-enough id and the placeholder is the fallback --
    #: an EditText on this screen is the only one, so the class alone would nearly do.
    _text_field_base: List[str] = field(default_factory=lambda: resource_ids("hnq"))

    @property
    def mode_text_tab(self) -> List[str]:
        """The TEXTE tab of the creation screen. Sits beside CRÉER, PHOTO and LIVE."""
        return L("publish_text.mode_text_tab")

    @property
    def text_field(self) -> List[str]:
        return self._text_field_base + L("publish_text.text_field") + [
            "//android.widget.EditText",
        ]

    @property
    def done_button(self) -> List[str]:
        """`Terminé` -- leaves the composer for the destination screen, not for publication."""
        return L("publish_text.done_button")

    @property
    def post_to_feed(self) -> List[str]:
        """`Publi. dans le fil`. The label is on a TextView whose clickable is its ancestor."""
        return L("publish_text.post_to_feed")

    @property
    def post_to_story(self) -> List[str]:
        """`Ta Story`.

        MEASURED AND NOT EXERCISED: the label is there, and unlike the feed one it reports
        `clickable="false"` on its own node, so its real target is an ancestor. Nothing has been
        published through it, and it is listed so the surface is described rather than implied.
        """
        return L("publish_text.post_to_story")

    @property
    def published_indicator(self) -> List[str]:
        """What proves the post left: the share sheet TikTok raises straight after publishing.

        The outcome, not the tap on the destination. Measured: the sheet comes up carrying our own
        handle and `· Il y a 2 s`, and the profile's post count had gone up.
        """
        return L("publish_text.published_indicator")


PUBLISH_TEXT_POST_SELECTORS = PublishTextPostSelectors()

__all__ = ["PUBLISH_TEXT_POST_SELECTORS", "PublishTextPostSelectors"]
