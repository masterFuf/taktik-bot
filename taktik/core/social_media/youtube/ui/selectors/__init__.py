"""YouTube UI selector catalogs organized by workflow surface."""

from .account import AccountSelectors, ACCOUNT_SELECTORS, YOUTUBE_HOME_ACTIVITY
from .upload import UploadSelectors, UPLOAD_SELECTORS, YOUTUBE_PACKAGE

__all__ = [
    "ACCOUNT_SELECTORS",
    "YOUTUBE_HOME_ACTIVITY",
    "YOUTUBE_PACKAGE",
    "AccountSelectors",
    "UPLOAD_SELECTORS",
    "UploadSelectors",
]
