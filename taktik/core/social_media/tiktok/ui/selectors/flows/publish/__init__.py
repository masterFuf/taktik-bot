"""TikTok publish selector catalogs grouped by flow stage."""

from .composer import PublishComposerSelectors, PUBLISH_COMPOSER_SELECTORS
from .creation_entry import PublishCreationEntrySelectors, PUBLISH_CREATION_ENTRY_SELECTORS
from .editor import PublishEditorSelectors, PUBLISH_EDITOR_SELECTORS
from .media_picker import PublishMediaPickerSelectors, PUBLISH_MEDIA_PICKER_SELECTORS
from .progress import PublishProgressSelectors, PUBLISH_PROGRESS_SELECTORS


class PublishSelectors:
    """Backward-compatible aggregate over specialized publish selector catalogs."""

    _catalogs = (
        PUBLISH_CREATION_ENTRY_SELECTORS,
        PUBLISH_MEDIA_PICKER_SELECTORS,
        PUBLISH_EDITOR_SELECTORS,
        PUBLISH_COMPOSER_SELECTORS,
        PUBLISH_PROGRESS_SELECTORS,
    )

    def __getattr__(self, name: str):
        for catalog in self._catalogs:
            if hasattr(catalog, name):
                return getattr(catalog, name)
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")


PUBLISH_SELECTORS = PublishSelectors()

__all__ = [
    "PUBLISH_COMPOSER_SELECTORS",
    "PUBLISH_CREATION_ENTRY_SELECTORS",
    "PUBLISH_EDITOR_SELECTORS",
    "PUBLISH_MEDIA_PICKER_SELECTORS",
    "PUBLISH_PROGRESS_SELECTORS",
    "PUBLISH_SELECTORS",
    "PublishComposerSelectors",
    "PublishCreationEntrySelectors",
    "PublishEditorSelectors",
    "PublishMediaPickerSelectors",
    "PublishProgressSelectors",
    "PublishSelectors",
]
