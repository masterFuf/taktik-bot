"""Comment action package.

Facade: re-exports CommentBusiness for full backward compatibility.
All existing imports like `from .comment import CommentBusiness` continue to work.

Internal structure:
- action.py    — Comment posting logic (comment_on_post, click/type/post/close)
- templates.py — Comment templates data and management functions
"""

from .action import CommentAction as CommentBusiness

__all__ = ['CommentBusiness']
