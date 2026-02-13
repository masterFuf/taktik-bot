"""Comment templates and template management."""

import random
from typing import Dict, List
from loguru import logger


# Default comment templates — can be extended at runtime via add_custom_template()
DEFAULT_TEMPLATES: Dict[str, List[str]] = {
    'generic': [
        "Nice! 🔥",
        "Love this! ❤️",
        "Amazing! 😍",
        "Great content! 👏",
        "Awesome! ✨",
        "Beautiful! 💫",
        "Incredible! 🙌",
        "Perfect! 💯",
        "So cool! 😎",
        "Fantastic! ⭐"
    ],
    'engagement': [
        "This is great! 🔥",
        "Love your content! ❤️",
        "Keep it up! 💪",
        "Amazing work! 👏",
        "So inspiring! ✨",
        "This is fire! 🔥",
        "Absolutely love this! 😍",
        "You're killing it! 💯",
        "Can't get enough! 🙌",
        "This made my day! ☀️"
    ],
    'short': [
        "🔥",
        "❤️",
        "😍",
        "👏",
        "✨",
        "💯",
        "🙌",
        "⭐",
        "💪",
        "👌"
    ]
}


def get_random_comment(templates: Dict[str, List[str]], category: str = 'generic') -> str:
    if category not in templates:
        category = 'generic'
    return random.choice(templates[category])


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


def get_templates(templates: Dict[str, List[str]], category: str = None) -> object:
    if category and category in templates:
        return templates[category].copy()
    return templates.copy()


def add_custom_template(templates: Dict[str, List[str]], comment: str, category: str = 'generic', log: logger = None) -> bool:
    _logger = log or logger
    try:
        if category not in templates:
            templates[category] = []
        
        if comment not in templates[category]:
            templates[category].append(comment)
            _logger.debug(f"Custom template added to '{category}': {comment}")
            return True
        
        return False
        
    except Exception as e:
        _logger.error(f"Error adding custom template: {e}")
        return False
