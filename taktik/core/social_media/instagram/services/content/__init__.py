"""Content management package.

Facade: re-exports ContentBusiness for full backward compatibility.
All existing imports like `from .content import ContentBusiness` continue to work.

Internal structure:
- extraction.py  — Extract users, likers, posts, stats from Instagram UI
- navigation.py  — Navigate to post URLs and hashtag pages
"""

from taktik.core.social_media.instagram.services.content.extraction import ContentExtraction as ContentBusiness

__all__ = ['ContentBusiness']
