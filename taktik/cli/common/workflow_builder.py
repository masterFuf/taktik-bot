"""
Workflow Config Builder (Shared CLI utility)

Eliminates duplication between generate_target_workflow, generate_hashtags_workflow,
and generate_post_url_workflow by providing reusable config collection and display functions.
"""

import math
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

console = Console()


def collect_probabilities(translations: dict, defaults: dict = None) -> dict:
    """Collect interaction probability percentages from user.
    
    Args:
        translations: Current translations dict
        defaults: Optional dict of default values {like, follow, comment, story, story_like}
    
    Returns:
        Dict with like_percentage, follow_percentage, etc. as ints
    """
    d = defaults or {}
    console.print(f"\n[yellow]{translations.get('probabilities_configuration', '🎲 Probabilities configuration')}[/yellow]")
    
    like_percentage = int(Prompt.ask(
        f"[cyan]{translations.get('like_probability', 'Like probability (%)')}[/cyan]",
        default=str(d.get('like', 80))
    ))
    follow_percentage = int(Prompt.ask(
        f"[cyan]{translations.get('follow_probability', 'Follow probability (%)')}[/cyan]",
        default=str(d.get('follow', 20))
    ))
    comment_percentage = int(Prompt.ask(
        f"[cyan]{translations.get('comment_probability', 'Comment probability (%)')}[/cyan]",
        default=str(d.get('comment', 5))
    ))
    story_percentage = int(Prompt.ask(
        f"[cyan]{translations.get('story_probability', 'Story view probability (%)')}[/cyan]",
        default=str(d.get('story', 15))
    ))
    story_like_percentage = int(Prompt.ask(
        f"[cyan]{translations.get('story_like_probability', 'Story like probability (%)')}[/cyan]",
        default=str(d.get('story_like', 10))
    ))
    
    return {
        'like_percentage': like_percentage,
        'follow_percentage': follow_percentage,
        'comment_percentage': comment_percentage,
        'story_percentage': story_percentage,
        'story_like_percentage': story_like_percentage,
    }


def collect_filters(translations: dict, defaults: dict = None) -> dict:
    """Collect profile filtering criteria from user.
    
    Returns:
        Dict with min_followers, max_followers, min_posts, max_followings, blacklist_words
    """
    d = defaults or {}
    console.print(f"\n[yellow]{translations.get('advanced_filters', '🔍 Advanced filters')}[/yellow]")
    
    min_followers = int(Prompt.ask(
        f"[cyan]{translations.get('min_followers_required', 'Minimum followers required')}[/cyan]",
        default=str(d.get('min_followers', 50))
    ))
    max_followers = int(Prompt.ask(
        f"[cyan]{translations.get('max_followers_accepted', 'Maximum followers accepted')}[/cyan]",
        default=str(d.get('max_followers', 50000))
    ))
    min_posts = int(Prompt.ask(
        f"[cyan]{translations.get('min_posts_required', 'Minimum posts required')}[/cyan]",
        default=str(d.get('min_posts', 5))
    ))
    max_followings = int(Prompt.ask(
        f"[cyan]{translations.get('max_followings_accepted', 'Maximum followings accepted')}[/cyan]",
        default=str(d.get('max_followings', 7500))
    ))
    
    console.print(f"\n[yellow]{translations.get('blacklist_optional', '🚫 Blacklist (optional)')}[/yellow]")
    blacklist_input = Prompt.ask(
        f"[cyan]{translations.get('blacklist_keywords', 'Blacklist keywords (comma-separated)')}[/cyan]",
        default=""
    )
    blacklist_words = [word.strip() for word in blacklist_input.split(",") if word.strip()] if blacklist_input else []
    
    return {
        'min_followers': min_followers,
        'max_followers': max_followers,
        'min_posts': min_posts,
        'max_followings': max_followings,
        'blacklist_words': blacklist_words,
    }


def collect_session_settings(translations: dict, defaults: dict = None) -> dict:
    """Collect session duration and delay settings from user.
    
    Returns:
        Dict with session_duration, min_delay, max_delay
    """
    d = defaults or {}
    console.print(f"\n[yellow]{translations.get('session_configuration', '⏱️ Session configuration')}[/yellow]")
    
    session_duration = int(Prompt.ask(
        f"[cyan]{translations.get('max_session_duration', 'Maximum session duration (minutes)')}[/cyan]",
        default=str(d.get('session_duration', 60))
    ))
    min_delay = int(Prompt.ask(
        f"[cyan]{translations.get('min_delay_actions', 'Minimum delay between actions (seconds)')}[/cyan]",
        default=str(d.get('min_delay', 5))
    ))
    max_delay = int(Prompt.ask(
        f"[cyan]{translations.get('max_delay_actions', 'Maximum delay between actions (seconds)')}[/cyan]",
        default=str(d.get('max_delay', 15))
    ))
    
    return {
        'session_duration': session_duration,
        'min_delay': min_delay,
        'max_delay': max_delay,
    }


def build_filters_config(filters: dict) -> dict:
    """Build the standard 'filters' section of workflow config."""
    return {
        "min_followers": filters['min_followers'],
        "max_followers": filters['max_followers'],
        "min_followings": 0,
        "max_followings": filters['max_followings'],
        "min_posts": filters['min_posts'],
        "privacy_relation": "public_and_private",
        "blacklist_words": filters.get('blacklist_words', [])
    }


def build_session_config(workflow_type: str, max_profiles: int, max_likes_per_profile: int,
                         probas: dict, session: dict) -> dict:
    """Build the standard 'session_settings' section of workflow config."""
    like_pct = probas['like_percentage']
    follow_pct = probas['follow_percentage']
    
    return {
        "workflow_type": workflow_type,
        "total_profiles_limit": max_profiles,
        "total_follows_limit": math.ceil(max_profiles * (follow_pct / 100)) if follow_pct > 0 else 0,
        "total_likes_limit": math.ceil(max_profiles * max_likes_per_profile * (like_pct / 100)) if like_pct > 0 else 0,
        "session_duration_minutes": session['session_duration'],
        "delay_between_actions": {
            "min": session['min_delay'],
            "max": session['max_delay']
        },
        "randomize_actions": True,
        "enable_screenshots": True,
        "screenshot_path": "screenshots"
    }


def build_interaction_settings(probas: dict) -> dict:
    """Build the standard like/follow/story/story_like/scrolling settings block."""
    return {
        "like_settings": {
            "enabled": probas['like_percentage'] > 0,
            "like_carousels": True,
            "like_reels": True,
            "randomize_order": True,
            "methods": ["button_click", "double_tap"],
            "verify_like_success": True,
            "max_attempts_per_post": 2,
            "delay_between_attempts": 2
        },
        "follow_settings": {
            "enabled": probas['follow_percentage'] > 0,
            "unfollow_after_days": 3,
            "verify_follow_success": True
        },
        "comment_settings": {
            "enabled": probas['comment_percentage'] > 0,
            "verify_comment_success": True
        },
        "story_settings": {
            "enabled": probas['story_percentage'] > 0,
            "watch_duration_range": [3, 8]
        },
        "story_like_settings": {
            "enabled": probas['story_like_percentage'] > 0,
            "max_stories_per_user": 3,
            "like_probability": probas['story_like_percentage'] / 100.0,
            "verify_like_success": True
        },
        "scrolling": {
            "enabled": True,
            "max_scroll_attempts": 3,
            "scroll_delay": 1.5
        }
    }


def display_probabilities_rows(table: Table, probas: dict, translations: dict):
    """Add probability rows to a summary table."""
    table.add_row("", "")
    table.add_row(f"[bold]{translations.get('probabilities', 'Probabilities')}[/bold]", "")
    table.add_row(f"→ {translations.get('like_probability', 'Like')}", f"{probas['like_percentage']}%")
    table.add_row(f"→ {translations.get('follow_probability', 'Follow')}", f"{probas['follow_percentage']}%")
    table.add_row(f"→ {translations.get('comment_probability', 'Comment')}", f"{probas['comment_percentage']}%")
    table.add_row(f"→ {translations.get('story_probability', 'Story view')}", f"{probas['story_percentage']}%")
    table.add_row(f"→ {translations.get('story_like_probability', 'Story like')}", f"{probas['story_like_percentage']}%")


def display_filters_rows(table: Table, filters: dict, translations: dict):
    """Add filter rows to a summary table."""
    table.add_row("", "")
    table.add_row(f"[bold]{translations.get('filters', 'Filters')}[/bold]", "")
    table.add_row(f"→ {translations.get('min_followers_required', 'Min followers')}", str(filters['min_followers']))
    table.add_row(f"→ {translations.get('max_followers_accepted', 'Max followers')}", str(filters['max_followers']))
    table.add_row(f"→ {translations.get('min_posts_required', 'Min posts')}", str(filters['min_posts']))
    table.add_row(f"→ {translations.get('max_followings_accepted', 'Max followings')}", str(filters['max_followings']))


def display_session_rows(table: Table, session: dict, translations: dict):
    """Add session rows to a summary table."""
    table.add_row("", "")
    table.add_row(f"[bold]{translations.get('session', 'Session')}[/bold]", "")
    table.add_row(f"→ {translations.get('max_session_duration', 'Duration')}", f"{session['session_duration']} min")
    table.add_row(f"→ Delay", f"{session['min_delay']}-{session['max_delay']}s")


def display_estimates(max_profiles: int, max_likes_per_profile: int, probas: dict, translations: dict):
    """Display estimated interaction counts."""
    estimated_likes = int(max_profiles * max_likes_per_profile * (probas['like_percentage'] / 100))
    estimated_follows = int(max_profiles * (probas['follow_percentage'] / 100))
    estimated_comments = int(max_profiles * (probas['comment_percentage'] / 100))
    
    console.print(f"\n[bold green]{translations.get('session_estimates', '📊 Session estimates')}[/bold green]")
    console.print(f"• [cyan]{translations.get('estimated_likes', 'Estimated likes:')}[/cyan] {estimated_likes}")
    console.print(f"• [cyan]{translations.get('estimated_follows', 'Estimated follows:')}[/cyan] {estimated_follows}")
    console.print(f"• [cyan]{translations.get('estimated_comments', 'Estimated comments:')}[/cyan] {estimated_comments}")
