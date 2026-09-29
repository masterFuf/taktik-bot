"""Like action package.

Facade: re-exports LikeBusiness for full backward compatibility.
All existing imports like `from .like import LikeBusiness` continue to work.

Internal structure:
- orchestration.py    — Like orchestration (like_profile_posts, sequential scroll, like_current_post)
- post_navigation.py  — Post navigation helpers (open first post, next post, return to profile)
"""

from taktik.core.social_media.instagram.services.like.orchestration import LikeOrchestration as LikeBusiness

__all__ = ['LikeBusiness']
