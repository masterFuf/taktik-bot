"""Sélecteurs UI pour YouTube — organisés par domaine.

    from taktik.core.social_media.youtube.ui.selectors import UPLOAD_SELECTORS, YOUTUBE_PACKAGE
"""

from .upload import UploadSelectors, UPLOAD_SELECTORS, YOUTUBE_PACKAGE

__all__ = [
    'YOUTUBE_PACKAGE',
    'UploadSelectors',
    'UPLOAD_SELECTORS',
]
