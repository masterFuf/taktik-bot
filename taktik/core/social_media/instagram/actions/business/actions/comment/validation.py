"""Comment text validation (length bounds from the action config).

The bot has no built-in comment template any more (Kevin, 2026-09-24): a comment is the AI's
or one of the operator's custom comments, or nothing.
"""

from loguru import logger


def validate_comment(comment_text: str, config: dict, log: logger = None) -> bool:
    _logger = log or logger
    
    if not comment_text or not isinstance(comment_text, str):
        return False
    
    comment_text = comment_text.strip()
    
    if len(comment_text) < config.get('min_comment_length', 3):
        _logger.warning(f"Comment too short: {len(comment_text)} < {config.get('min_comment_length', 3)}")
        return False
    
    if len(comment_text) > config.get('max_comment_length', 150):
        _logger.warning(f"Comment too long: {len(comment_text)} > {config.get('max_comment_length', 150)}")
        return False
    
    return True
