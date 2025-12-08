import os
import sys
import click
import logging
import time
import json
import math
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from loguru import logger
from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.core.manager import InstagramManager
from taktik.core.social_media.tiktok.manager import TikTokManager
from taktik.core.license import unified_license_manager
from taktik.core.database import configure_db_service
from taktik.locales import fr, en
from taktik import __version__
from taktik.utils.version_checker import check_version

device_manager = DeviceManager()

LANGUAGES = {
    'en': en,
    'fr': fr
}
DEFAULT_LANGUAGE = 'en'
current_translations = LANGUAGES[DEFAULT_LANGUAGE].TRANSLATIONS
current_banner = LANGUAGES[DEFAULT_LANGUAGE].BANNER

def set_language(lang_code):
    global current_translations, current_banner
    if lang_code in LANGUAGES:
        current_translations = LANGUAGES[lang_code].TRANSLATIONS
        current_banner = LANGUAGES[lang_code].BANNER
    else:
        current_translations = LANGUAGES[DEFAULT_LANGUAGE].TRANSLATIONS
        current_banner = LANGUAGES[DEFAULT_LANGUAGE].BANNER

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
console = Console()


def auto_update():
    """Launch automatic update process."""
    import platform
    import subprocess
    
    console.print("\n[bold yellow]🔄 Starting automatic update...[/bold yellow]\n")
    
    system = platform.system()
    
    try:
        if system == "Windows":
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts", "install.ps1")
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Update"],
                capture_output=True,
                text=True
            )
            
            # Display output
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(f"[yellow]{result.stderr}[/yellow]")
            
            # Check if update was successful by verifying version
            if result.returncode != 0:
                raise Exception(f"Update script failed with exit code {result.returncode}")
                
        else:
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts", "install.sh")
            result = subprocess.run(["bash", script_path, "--update"], capture_output=True, text=True)
            
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(f"[yellow]{result.stderr}[/yellow]")
                
            if result.returncode != 0:
                raise Exception(f"Update script failed with exit code {result.returncode}")
        
        console.print("\n[bold green]✅ Update completed successfully![/bold green]")
        console.print("[yellow]Please restart the application to use the new version.[/yellow]\n")
        sys.exit(0)
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Update failed: {e}[/bold red]")
        console.print("[yellow]Please update manually using the commands shown above.[/yellow]\n")


def display_banner():
    """Display banner with version check integrated."""
    from taktik.utils.version_checker import VersionChecker
    
    # Check for updates
    checker = VersionChecker(__version__)
    update_available, latest_version = checker.check_for_updates()
    
    # Build banner content
    banner_content = f"[bold blue]{current_banner}[/bold blue]\n"
    banner_content += "[bold green]Social Media Automation Tool[/bold green]\n"
    banner_content += f"[dim cyan]Version {__version__}[/dim cyan]\n\n"
    
    # Add update notification if available
    if update_available and latest_version:
        banner_content += "[bold yellow]🎉 NEW VERSION AVAILABLE![/bold yellow]\n\n"
        banner_content += f"[cyan]Current version:[/cyan] {__version__}\n"
        banner_content += f"[cyan]Latest version:[/cyan]  [bold green]{latest_version}[/bold green]\n\n"
        banner_content += "[yellow]📦 To update:[/yellow]\n"
        banner_content += "[dim]Windows:[/dim] .\\scripts\\install.ps1 -Update\n"
        banner_content += "[dim]Linux/macOS:[/dim] ./scripts/install.sh --update\n\n"
    
    # Add links
    banner_content += "[blue]🌐 Website:[/blue] [link=https://taktik-bot.com/]taktik-bot.com[/link]\n"
    banner_content += "[blue]📚 Documentation:[/blue] [link=https://taktik-bot.com/en/docs]taktik-bot.com/en/docs[/link]\n"
    banner_content += "[blue]💻 GitHub:[/blue] [link=https://github.com/masterFuf/taktik-bot]github.com/masterFuf/taktik-bot[/link]\n"
    banner_content += "[blue]💬 Discord:[/blue] [link=https://discord.com/invite/bb7MuMmpKS]discord.gg/bb7MuMmpKS[/link]"
    
    console.print(Panel.fit(
        banner_content,
        border_style="blue",
        padding=(1, 2),
        title="TAKTIK",
        title_align="left"
    ))
    
    # Prompt for auto-update if available
    if update_available and latest_version:
        console.print("")
        if Confirm.ask("[bold cyan]Would you like to update automatically now?[/bold cyan]", default=False):
            auto_update()

def select_language():
    console.print("\n[bold blue]Language Selection / Sélection de la langue[/bold blue]")
    console.print("1. English")
    console.print("2. Français")
    
    choice = click.prompt(
        "\n[bold yellow]Choose your language / Choisissez votre langue[/bold yellow]",
        type=click.IntRange(1, 2),
        default=1,
        show_choices=False
    )
    
    if choice == 1:
        return 'en'
    else:
        return 'fr'

def select_target_type():
    console.print(Panel.fit(f"[bold blue]{current_translations['target_selection_title']}[/bold blue]"))
    
    target_options = {
        "1": current_translations['target_option_target'],
        "2": current_translations['target_option_hashtags'],
        "3": current_translations['target_option_post_url'],
        # "4": current_translations['target_option_place']  # Temporarily disabled
    }
    
    for key, value in target_options.items():
        console.print(f"  {key}. {value}")
    
    choice = Prompt.ask(
        f"\n[bold yellow]{current_translations['choose_target_type']}[/bold yellow]",
        choices=["1", "2", "3"],
        default="1"
    )
    
    if choice == "1":
        return "target"
    elif choice == "2":
        return "hashtags"
    elif choice == "3":
        return "post_url"
    # elif choice == "4":  # Temporarily disabled
    #     return "place"
    
    return None

def generate_dynamic_workflow(target_type):
    if target_type == "target":
        return generate_target_workflow()
    elif target_type == "hashtags":
        return generate_hashtags_workflow()
    elif target_type == "post_url":
        return generate_post_url_workflow()
    # elif target_type == "place":  # Temporarily disabled
    #     return generate_place_workflow()
    
    return None

def generate_target_workflow():
    console.print(f"\n[bold green]{current_translations['target_workflow_title']}[/bold green]")
    
    console.print(f"[dim]💡 Tip: You can enter multiple targets separated by commas (e.g., user1,user2,user3)[/dim]")
    target_username = Prompt.ask(f"[cyan]{current_translations['target_username_prompt']}[/cyan]")
    if not target_username:
        console.print(f"[red]{current_translations['username_required']}[/red]")
        return None
    
    # Parse multiple targets
    target_usernames = [t.strip() for t in target_username.split(',') if t.strip()]
    if len(target_usernames) > 1:
        console.print(f"[green]✅ {len(target_usernames)} targets detected: {', '.join(['@' + t for t in target_usernames])}[/green]")
    target_username = target_usernames[0]  # Keep first for backward compatibility
    
    interaction_types = {
        "1": "followers",
        "2": "following"
    }
    
    console.print(f"\n[yellow]{current_translations['interaction_types_available']}[/yellow]")
    console.print(f"[cyan]1.[/cyan] {current_translations['followers_interaction']}")
    console.print(f"[cyan]2.[/cyan] {current_translations['following_interaction']}")
    
    interaction_choice = Prompt.ask(f"[cyan]{current_translations['choose_interaction_type']}[/cyan]", choices=["1", "2"], default="1")
    interaction_type = interaction_types[interaction_choice]
    
    console.print(f"\n[yellow]{current_translations['limits_configuration']}[/yellow]")
    max_profiles = int(Prompt.ask(
        f"[cyan]{current_translations['max_profiles_prompt']}[/cyan]", 
        default="20"
    ))
    
    max_likes_per_profile = int(Prompt.ask(
        f"[cyan]{current_translations['max_likes_per_profile']}[/cyan]", 
        default="2"
    ))
    
    console.print(f"\n[yellow]{current_translations['probabilities_configuration']}[/yellow]")
    like_percentage = int(Prompt.ask(f"[cyan]{current_translations['like_probability']}[/cyan]", default="80"))
    follow_percentage = int(Prompt.ask(f"[cyan]{current_translations['follow_probability']}[/cyan]", default="20"))
    comment_percentage = int(Prompt.ask(f"[cyan]{current_translations['comment_probability']}[/cyan]", default="5"))
    story_percentage = int(Prompt.ask(f"[cyan]{current_translations['story_probability']}[/cyan]", default="15"))
    story_like_percentage = int(Prompt.ask(f"[cyan]{current_translations['story_like_probability']}[/cyan]", default="10"))
    
    console.print(f"\n[yellow]{current_translations['advanced_filters']}[/yellow]")
    min_followers = int(Prompt.ask(f"[cyan]{current_translations['min_followers_required']}[/cyan]", default="50"))
    max_followers = int(Prompt.ask(f"[cyan]{current_translations['max_followers_accepted']}[/cyan]", default="50000"))
    min_posts = int(Prompt.ask(f"[cyan]{current_translations['min_posts_required']}[/cyan]", default="5"))
    max_followings = int(Prompt.ask(f"[cyan]{current_translations['max_followings_accepted']}[/cyan]", default="7500"))
    
    console.print(f"\n[yellow]{current_translations['blacklist_optional']}[/yellow]")
    blacklist_input = Prompt.ask(f"[cyan]{current_translations['blacklist_keywords']}[/cyan]", default="")
    blacklist_words = [word.strip() for word in blacklist_input.split(",") if word.strip()]
    
    console.print(f"\n[yellow]{current_translations['session_configuration']}[/yellow]")
    console.print(f"\n[yellow]{current_translations['session_configuration']}[/yellow]")
    session_duration = int(Prompt.ask(f"[cyan]{current_translations['max_session_duration']}[/cyan]", default="60"))
    min_delay = int(Prompt.ask(f"[cyan]{current_translations['min_delay_actions']}[/cyan]", default="5"))
    max_delay = int(Prompt.ask(f"[cyan]{current_translations['max_delay_actions']}[/cyan]", default="15"))
    
    workflow_config = {
        "filters": {
            "min_followers": min_followers,
            "max_followers": max_followers,
            "min_followings": 0,
            "max_followings": max_followings,
            "min_posts": min_posts,
            "privacy_relation": "public_and_private",
            "blacklist_words": blacklist_words
        },
        "session_settings": {
            "workflow_type": "target_followers",
            "total_profiles_limit": max_profiles,  # Nombre de profils à traiter
            "total_follows_limit": math.ceil(max_profiles * (follow_percentage / 100)) if follow_percentage > 0 else 0,
            "total_likes_limit": math.ceil(max_profiles * max_likes_per_profile * (like_percentage / 100)) if like_percentage > 0 else 0,
            "session_duration_minutes": session_duration,
            "delay_between_actions": {
                "min": min_delay,
                "max": max_delay
            },
            "randomize_actions": True,
            "enable_screenshots": True,
            "screenshot_path": "screenshots"
        },
        "actions": [
            {
                "type": "interact_with_followers",
                "target_username": target_username,
                "target_usernames": target_usernames,  # Multi-targets support
                "interaction_type": interaction_type,
                "max_interactions": max_profiles,
                "like_posts": True,
                "max_likes_per_profile": max_likes_per_profile,
                "probabilities": {
                    "like_percentage": like_percentage,
                    "follow_percentage": follow_percentage,
                    "comment_percentage": comment_percentage,
                    "story_percentage": story_percentage,
                    "story_like_percentage": story_like_percentage
                },
                "like_settings": {
                    "enabled": like_percentage > 0,
                    "like_carousels": True,
                    "like_reels": True,
                    "randomize_order": True,
                    "methods": ["button_click", "double_tap"],
                    "verify_like_success": True,
                    "max_attempts_per_post": 2,
                    "delay_between_attempts": 2
                },
                "follow_settings": {
                    "enabled": follow_percentage > 0,
                    "unfollow_after_days": 3,
                    "verify_follow_success": True
                },
                "comment_settings": {
                    "enabled": comment_percentage > 0,
                    "verify_comment_success": True
                },
                "story_settings": {
                    "enabled": story_percentage > 0,
                    "watch_duration_range": [3, 8]
                },
                "story_like_settings": {
                    "enabled": story_like_percentage > 0,
                    "max_stories_per_user": 3,
                    "like_probability": story_like_percentage / 100.0,
                    "verify_like_success": True
                },
                "scrolling": {
                    "enabled": True,
                    "max_scroll_attempts": 3,
                    "scroll_delay": 1.5
                }
            }
        ],
        "comments": [
            "Great content! 😊",
            "Love your posts! ❤️",
            "Amazing content! ✨",
            "Nice work! 👍",
            "Awesome! 🔥",
            "Beautiful! 💯"
        ],
        "debug": {
            "save_screenshots": True,
            "screenshot_failed_actions": True,
            "log_level": "DEBUG"
        }
    }
    
    console.print(f"\n[green]{current_translations['target_workflow_summary']}[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column(current_translations['parameter'], style="cyan")
    table.add_column(current_translations['value'], style="yellow") 
    
    table.add_row(current_translations['target'], f"@{target_username}")
    table.add_row(current_translations['interaction_type'], interaction_type)
    table.add_row(current_translations['max_profiles_prompt'], str(max_profiles))
    table.add_row(current_translations['max_likes_per_profile'], str(max_likes_per_profile))
    
    table.add_row("", "")
    table.add_row(f"[bold]{current_translations['probabilities']}[/bold]", "")
    table.add_row(f"→ {current_translations['like_probability']}", f"{like_percentage}%")
    table.add_row(f"→ {current_translations['follow_probability']}", f"{follow_percentage}%")
    table.add_row(f"→ {current_translations['comment_probability']}", f"{comment_percentage}%")
    table.add_row(f"→ {current_translations['story_probability']}", f"{story_percentage}%")
    table.add_row(f"→ {current_translations['story_like_probability']}", f"{story_like_percentage}%")
    
    table.add_row("", "")
    table.add_row(f"[bold]{current_translations['filters']}[/bold]", "")
    table.add_row(f"→ {current_translations['min_followers_required']}", str(min_followers))
    table.add_row(f"→ {current_translations['max_followers_accepted']}", str(max_followers))
    table.add_row(f"→ {current_translations['min_posts_required']}", str(min_posts))
    table.add_row(f"→ {current_translations['max_followings_accepted']}", str(max_followings))
    
    table.add_row("", "")
    table.add_row(f"[bold]{current_translations['session']}[/bold]", "")
    table.add_row(f"→ {current_translations['max_session_duration']}", f"{session_duration} min")
    table.add_row(f"→ {current_translations['min_delay_actions']}-{current_translations['max_delay_actions']}", f"{min_delay}-{max_delay}s")
    
    if blacklist_words:
        table.add_row(f"→ {current_translations['blacklisted_words']}", ", ".join(blacklist_words[:3]) + ("..." if len(blacklist_words) > 3 else ""))
    
    console.print(table)
    
    estimated_likes = int(max_profiles * max_likes_per_profile * (like_percentage / 100))
    estimated_follows = int(max_profiles * (follow_percentage / 100))
    estimated_comments = int(max_profiles * (comment_percentage / 100))
    
    console.print(f"\n[bold green]{current_translations['session_estimates']}[/bold green]")
    console.print(f"• [cyan]{current_translations['estimated_likes']}[/cyan] {estimated_likes}")
    console.print(f"• [cyan]{current_translations['estimated_follows']}[/cyan] {estimated_follows}")
    console.print(f"• [cyan]{current_translations['estimated_comments']}[/cyan] {estimated_comments}")
    
    console.print(f"\n[green]{current_translations['target_workflow_configured'].format(target_username)}[/green]")
    return workflow_config

def generate_hashtags_workflow():
    console.print(f"\n[bold green]🏷️ Configuration du workflow Hashtags[/bold green]")
    
    hashtag = Prompt.ask(f"[cyan]Hashtag à cibler (sans #)[/cyan]")
    if not hashtag:
        console.print(f"[red]Hashtag requis[/red]")
        return None
    
    hashtag = hashtag.lstrip('#')
    
    console.print(f"\n[yellow]📱 Mode: Extraction et interaction avec les likers des meilleurs posts de #{hashtag}[/yellow]")
    console.print(f"[dim]Note: Les posts seront sélectionnés selon leurs métadonnées (likes, commentaires)[/dim]")
    
    console.print(f"\n[bold yellow]🎯 Critères de sélection des posts[/bold yellow]")
    
    min_likes = Prompt.ask(
        f"[cyan]Nombre minimum de likes par post[/cyan]",
        default="100"
    )
    
    max_likes = Prompt.ask(
        f"[cyan]Nombre maximum de likes par post[/cyan]",
        default="50000"
    )
    
    console.print(f"\n[yellow]📊 Configuration des limites :[/yellow]")
    max_profiles = Prompt.ask(
        f"[cyan]Nombre maximum de profils à traiter[/cyan]",
        default="30"
    )
    
    max_likes_per_profile = Prompt.ask(
        f"[cyan]Nombre maximum de likes par profil[/cyan]",
        default="2"
    )
    
    console.print(f"\n[yellow]🎲 Configuration des probabilités d'interaction (en %) :[/yellow]")
    like_percentage = Prompt.ask(
        f"[cyan]Probabilité de liker des posts[/cyan]",
        default="80"
    )
    
    follow_percentage = Prompt.ask(
        f"[cyan]Probabilité de follow[/cyan]",
        default="15"
    )
    
    comment_percentage = Prompt.ask(
        f"[cyan]Probabilité de commenter[/cyan]",
        default="5"
    )
    
    story_percentage = Prompt.ask(
        f"[cyan]Probabilité de regarder les stories[/cyan]",
        default="20"
    )
    
    story_like_percentage = Prompt.ask(
        f"[cyan]Probabilité de liker les stories[/cyan]",
        default="10"
    )
    
    console.print(f"\n[yellow]🔍 Filtres avancés de ciblage :[/yellow]")
    min_followers = Prompt.ask(
        f"[cyan]Nombre minimum de followers requis[/cyan]",
        default="10"
    )
    
    max_followers = Prompt.ask(
        f"[cyan]Nombre maximum de followers acceptés[/cyan]",
        default="50000"
    )
    
    min_posts = Prompt.ask(
        f"[cyan]Nombre minimum de posts requis[/cyan]",
        default="3"
    )
    
    max_followings = Prompt.ask(
        f"[cyan]Nombre maximum de comptes suivis acceptés[/cyan]",
        default="7500"
    )
    
    # Liste noire
    console.print(f"\n[yellow]🚫 Liste noire (optionnel) :[/yellow]")
    blacklist_input = Prompt.ask(
        "[cyan]Mots-clés à éviter (séparés par des virgules)[/cyan]",
        default=""
    )
    blacklist_words = [word.strip() for word in blacklist_input.split(",") if word.strip()] if blacklist_input else []
    
    console.print(f"\n[yellow]⏱️ Configuration de session :[/yellow]")
    session_duration = Prompt.ask(
        "[cyan]Durée maximale de session (minutes)[/cyan]",
        default="60"
    )
    min_delay = Prompt.ask(
        "[cyan]Délai minimum entre actions (secondes)[/cyan]",
        default="5"
    )
    max_delay = Prompt.ask(
        "[cyan]Délai maximum entre actions (secondes)[/cyan]",
        default="15"
    )
    
    workflow_config = {
        "filters": {
            "min_followers": int(min_followers),
            "max_followers": int(max_followers),
            "min_followings": 0,
            "max_followings": int(max_followings),
            "min_posts": int(min_posts),
            "privacy_relation": "public_and_private",
            "blacklist_words": blacklist_words
        },
        "session_settings": {
            "workflow_type": "hashtag_interactions",
            "total_profiles_limit": int(max_profiles),  # Nombre de profils à traiter
            "total_follows_limit": math.ceil(int(max_profiles) * (int(follow_percentage) / 100)) if int(follow_percentage) > 0 else 0,
            "total_likes_limit": math.ceil(int(max_profiles) * int(max_likes_per_profile) * (int(like_percentage) / 100)) if int(like_percentage) > 0 else 0,
            "session_duration_minutes": int(session_duration),
            "delay_between_actions": {
                "min": int(min_delay),
                "max": int(max_delay)
            },
            "randomize_actions": True,
            "enable_screenshots": True,
            "screenshot_path": "screenshots"
        },
        "actions": [
            {
                "type": "hashtag",
                "hashtag": hashtag,
                "max_interactions": int(max_profiles),
                "max_likes_per_profile": int(max_likes_per_profile),
                "post_criteria": {
                    "min_likes": int(min_likes),
                    "max_likes": int(max_likes)
                },
                "probabilities": {
                    "like_percentage": int(like_percentage),
                    "follow_percentage": int(follow_percentage),
                    "comment_percentage": int(comment_percentage),
                    "story_percentage": int(story_percentage),
                    "story_like_percentage": int(story_like_percentage)
                },
                "filter_criteria": {
                    "min_followers": int(min_followers),
                    "max_followers": int(max_followers),
                    "min_posts": int(min_posts),
                    "skip_private": True,
                    "skip_business": False
                },
                "like_settings": {
                    "enabled": int(like_percentage) > 0,
                    "like_carousels": True,
                    "like_reels": True,
                    "randomize_order": True,
                    "methods": ["button_click", "double_tap"],
                    "verify_like_success": True,
                    "max_attempts_per_post": 2,
                    "delay_between_attempts": 2
                },
                "follow_settings": {
                    "enabled": int(follow_percentage) > 0,
                    "unfollow_after_days": 3,
                    "verify_follow_success": True
                },
                "story_settings": {
                    "enabled": int(story_percentage) > 0,
                    "watch_duration_range": [3, 8]
                },
                "story_like_settings": {
                    "enabled": int(story_like_percentage) > 0,
                    "max_stories_per_user": 3,
                    "like_probability": int(story_like_percentage) / 100.0,
                    "verify_like_success": True
                },
                "scrolling": {
                    "enabled": True,
                    "max_scroll_attempts": 3,
                    "scroll_delay": 1.5
                }
            }
        ]
    }
    
    console.print("\n[green]📋 Résumé de la configuration Hashtag :[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Paramètre", style="cyan")
    table.add_column("Valeur", style="yellow")
    
    table.add_row("Hashtag", f"#{hashtag}")
    table.add_row("Critères posts", f"{min_likes}-{max_likes} likes")
    table.add_row("Nombre maximum de profils", str(max_profiles))
    table.add_row("Nombre maximum de likes par profil", str(max_likes_per_profile))
    table.add_row("", "")
    table.add_row("Probabilités", "")
    table.add_row("→ Probabilité de liker des posts", f"{like_percentage}%")
    table.add_row("→ Probabilité de follow", f"{follow_percentage}%")
    table.add_row("→ Probabilité de commenter", f"{comment_percentage}%")
    table.add_row("→ Probabilité de regarder les stories", f"{story_percentage}%")
    table.add_row("→ Probabilité de liker les stories", f"{story_like_percentage}%")
    table.add_row("", "")
    table.add_row("Filtres", "")
    table.add_row("→ Nombre minimum de followers requis", str(min_followers))
    table.add_row("→ Nombre maximum de followers acceptés", str(max_followers))
    table.add_row("→ Nombre minimum de posts requis", str(min_posts))
    table.add_row("→ Nombre maximum de comptes suivis acceptés", str(max_followings))
    table.add_row("", "")
    table.add_row("Session", "")
    table.add_row("→ Durée maximale de session (minutes)", f"{session_duration} min")
    table.add_row("→ Délai minimum entre actions (secondes)-Délai maximum entre actions (secondes)", f"{min_delay}-{max_delay}s")
    
    console.print(table)
    
    console.print(f"\n[green]📊 Estimations de session :[/green]")
    estimated_likes = int(int(max_profiles) * int(max_likes_per_profile) * (int(like_percentage) / 100))
    estimated_follows = int(int(max_profiles) * (int(follow_percentage) / 100))
    estimated_comments = int(int(max_profiles) * (int(comment_percentage) / 100))
    
    console.print(f"• Likes estimés : {estimated_likes}")
    console.print(f"• Follows estimés : {estimated_follows}")
    console.print(f"• Commentaires estimés : {estimated_comments}")
    
    console.print(f"\n[green]✅ Workflow hashtag #{hashtag} configuré avec succès ![/green]")
    return workflow_config

def generate_post_url_workflow():
    console.print(f"[green]{current_translations['post_url_workflow_config']}[/green]")
    
    post_url = Prompt.ask(f"[cyan]{current_translations['enter_post_url']}[/cyan]")
    if not post_url:
        console.print(f"[red]{current_translations['post_url_required']}[/red]")
        return None
    
    if not _validate_instagram_url(post_url):
        console.print(f"[red]{current_translations['invalid_instagram_url']}[/red]")
        return None
    
    console.print(f"\n[yellow]{current_translations['interaction_mode']}[/yellow]")
    console.print(f"[dim]{current_translations['workflow_extract_likers']}[/dim]")
    
    console.print(f"\n[yellow]{current_translations['limits_configuration']}[/yellow]")
    max_profiles = Prompt.ask(f"[cyan]{current_translations['max_profiles_prompt']}[/cyan]", default="20")
    max_likes_per_profile = Prompt.ask(f"[cyan]{current_translations['max_likes_per_profile']}[/cyan]", default="2")
    
    console.print(f"\n[yellow]{current_translations['probabilities_configuration']}[/yellow]")
    console.print(f"\n[yellow]{current_translations['probabilities_configuration']}[/yellow]")
    like_percentage = Prompt.ask(f"[cyan]{current_translations['like_probability']}[/cyan]", default="80")
    follow_percentage = Prompt.ask(f"[cyan]{current_translations['follow_probability']}[/cyan]", default="20")
    comment_percentage = Prompt.ask(f"[cyan]{current_translations['comment_probability']}[/cyan]", default="5")
    story_percentage = Prompt.ask(f"[cyan]{current_translations['story_probability']}[/cyan]", default="15")
    story_like_percentage = Prompt.ask(f"[cyan]{current_translations['story_like_probability']}[/cyan]", default="10")
    
    console.print(f"\n[yellow]{current_translations['advanced_filters']}[/yellow]")
    min_followers = Prompt.ask(f"[cyan]{current_translations['min_followers_required']}[/cyan]", default="50")
    max_followers = Prompt.ask(f"[cyan]{current_translations['max_followers_accepted']}[/cyan]", default="50000")
    min_posts = Prompt.ask(f"[cyan]{current_translations['min_posts_required']}[/cyan]", default="5")
    max_followings = Prompt.ask(f"[cyan]{current_translations['max_followings_accepted']}[/cyan]", default="7500")
    
    console.print(f"\n[yellow]{current_translations['blacklist_optional']}[/yellow]")
    blacklist_input = Prompt.ask(f"[cyan]{current_translations['blacklist_keywords']}[/cyan]", default="")
    blacklist_words = [word.strip() for word in blacklist_input.split(",") if word.strip()] if blacklist_input else []
    
    console.print(f"\n[yellow]{current_translations['session_configuration']}[/yellow]")
    console.print(f"\n[yellow]{current_translations['session_configuration']}[/yellow]")
    session_duration = Prompt.ask(f"[cyan]{current_translations['max_session_duration']}[/cyan]", default="60")
    min_delay = Prompt.ask(f"[cyan]{current_translations['min_delay_actions']}[/cyan]", default="5")
    max_delay = Prompt.ask(f"[cyan]{current_translations['max_delay_actions']}[/cyan]", default="15")
    
    workflow_config = {
        "filters": {
            "min_followers": int(min_followers),
            "max_followers": int(max_followers),
            "min_followings": 0,
            "max_followings": int(max_followings),
            "min_posts": int(min_posts),
            "privacy_relation": "public_and_private",
            "blacklist_words": blacklist_words
        },
        "session_settings": {
            "workflow_type": "target_followers",
            "total_profiles_limit": int(max_profiles),  # Nombre de profils à traiter
            "total_follows_limit": math.ceil(int(max_profiles) * (int(follow_percentage) / 100)) if int(follow_percentage) > 0 else 0,
            "total_likes_limit": math.ceil(int(max_profiles) * int(max_likes_per_profile) * (int(like_percentage) / 100)) if int(like_percentage) > 0 else 0,
            "session_duration_minutes": int(session_duration),
            "delay_between_actions": {
                "min": int(min_delay),
                "max": int(max_delay)
            },
            "randomize_actions": True,
            "enable_screenshots": True,
            "screenshot_path": "screenshots"
        },
        'steps': [
            {
                'type': 'post_url',
                'post_url': post_url,
                'interaction_type': 'post-likers',
                'max_interactions': int(max_profiles),
                'max_likes_per_profile': int(max_likes_per_profile),
                'probabilities': {
                    'like_percentage': int(like_percentage),
                    'follow_percentage': int(follow_percentage), 
                    'comment_percentage': int(comment_percentage),
                    'story_percentage': int(story_percentage),
                    'story_like_percentage': int(story_like_percentage)
                },
                'like_settings': {
                    'enabled': int(like_percentage) > 0,
                    'like_carousels': True,
                    'like_reels': True,
                    'randomize_order': True,
                    'methods': ['button_click', 'double_tap'],
                    'verify_like_success': True,
                    'max_attempts_per_post': 2,
                    'delay_between_attempts': 2
                },
                'follow_settings': {
                    'enabled': int(follow_percentage) > 0,
                    'unfollow_after_days': 3,
                    'verify_follow_success': True
                },
                'story_settings': {
                    'enabled': int(story_percentage) > 0,
                    'watch_duration_range': [3, 8]
                },
                'story_like_settings': {
                    'enabled': int(story_like_percentage) > 0,
                    'max_stories_per_user': 3,
                    'like_probability': int(story_like_percentage) / 100.0,
                    'verify_like_success': True
                },
                'scrolling': {
                    'enabled': True,
                    'max_scroll_attempts': 3,
                    'scroll_delay': 1.5
                }
            }
        ]
    }
    
    console.print(f"\n[green]{current_translations['post_url_workflow_summary']}[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column(current_translations['parameter'], style="cyan")
    table.add_column(current_translations['value'], style="yellow") 
    
    post_id = _extract_post_id_from_url(post_url)
    table.add_row(current_translations['post_url'], post_url)
    table.add_row(current_translations['post_id'], post_id if post_id else current_translations['post_id_not_detected'])
    table.add_row(current_translations['interaction_type'], current_translations['interaction_type_likers'])
    table.add_row(current_translations['max_profiles_prompt'], str(max_profiles))
    table.add_row(current_translations['max_likes_per_profile'], str(max_likes_per_profile))
    table.add_row("", "")
    table.add_row(current_translations['probabilities'], "")
    table.add_row(f"→ {current_translations['like_probability']}", f"{like_percentage}%")
    table.add_row(f"→ {current_translations['follow_probability']}", f"{follow_percentage}%")
    table.add_row(f"→ {current_translations['comment_probability']}", f"{comment_percentage}%")
    table.add_row(f"→ {current_translations['story_probability']}", f"{story_percentage}%")
    table.add_row(f"→ {current_translations['story_like_probability']}", f"{story_like_percentage}%")
    table.add_row("", "")
    table.add_row(current_translations['filters'], "")
    table.add_row(f"→ {current_translations['min_followers_required']}", str(min_followers))
    table.add_row(f"→ {current_translations['max_followers_accepted']}", str(max_followers))
    table.add_row(f"→ {current_translations['min_posts_required']}", str(min_posts))
    table.add_row(f"→ {current_translations['max_followings_accepted']}", str(max_followings))
    table.add_row("", "")
    table.add_row(current_translations['session'], "")
    table.add_row(f"→ {current_translations['max_session_duration']}", f"{session_duration} min")
    table.add_row(f"→ {current_translations['min_delay_actions']}-{current_translations['max_delay_actions']}", f"{min_delay}-{max_delay}s")
    
    console.print(table)
    
    console.print(f"\n[green]{current_translations['session_estimates']}[/green]")
    estimated_likes = int(int(max_profiles) * int(max_likes_per_profile) * (int(like_percentage) / 100))
    estimated_follows = int(int(max_profiles) * (int(follow_percentage) / 100))
    estimated_comments = int(int(max_profiles) * (int(comment_percentage) / 100))
    
    console.print(f"• {current_translations['estimated_likes']} {estimated_likes}")
    console.print(f"• {current_translations['estimated_follows']} {estimated_follows}")
    console.print(f"• {current_translations['estimated_comments']} {estimated_comments}")
    
    console.print(f"\n[green]{current_translations['post_url_workflow_success'].format(post_url)}[/green]")
    
    return workflow_config

def generate_place_workflow():
    console = Console()
    
    console.print("\n[green]🏙️ Configuration du workflow Place[/green]")
    
    place_name = Prompt.ask("[cyan]Nom du lieu à cibler[/cyan]", default="Paris, France")
    place_name = Prompt.ask("[cyan]Nom du lieu à cibler[/cyan]", default="Paris, France")
    
    max_users = Prompt.ask("[cyan]Nombre maximum d'utilisateurs à traiter[/cyan]", default="20")
    
    max_posts_check = Prompt.ask("[cyan]Nombre maximum de posts à vérifier dans le lieu[/cyan]", default="10")
    
    like_percentage = Prompt.ask("[cyan]Probabilité de like (%)[/cyan]", default="70")
    follow_percentage = Prompt.ask("[cyan]Probabilité de follow (%)[/cyan]", default="30")
    comment_percentage = Prompt.ask("[cyan]Probabilité de commentaire (%)[/cyan]", default="10")
    story_view_percentage = Prompt.ask("[cyan]Probabilité de regarder les stories (%)[/cyan]", default="40")
    story_like_percentage = Prompt.ask("[cyan]Probabilité de liker les stories (%)[/cyan]", default="60")
    
    console.print("\n[yellow]🔍 Configuration des filtres[/yellow]")
    min_followers = Prompt.ask("[cyan]Nombre minimum de followers[/cyan]", default="100")
    max_followers = Prompt.ask("[cyan]Nombre maximum de followers[/cyan]", default="10000")
    min_posts = Prompt.ask("[cyan]Nombre minimum de posts[/cyan]", default="5")
    
    workflow_config = {
        'target_type': 'place',
        'actions': [
            {
                'type': 'place',
                'place_name': place_name,
                'max_users': int(max_users),
                'max_posts_to_check': int(max_posts_check),
                'like_percentage': int(like_percentage),
                'follow_percentage': int(follow_percentage),
                'comment_percentage': int(comment_percentage),
                'story_view_percentage': int(story_view_percentage),
                'story_like_percentage': int(story_like_percentage),
                'filters': {
                    'min_followers': int(min_followers),
                    'max_followers': int(max_followers),
                    'min_posts': int(min_posts)
                }
            }
        ]
    }
    
    console.print("\n[green]📋 Résumé de la configuration Place :[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Paramètre", style="cyan")
    table.add_column("Valeur", style="yellow") 
    
    table.add_row("Lieu cible", place_name)
    table.add_row("Max utilisateurs", str(max_users))
    table.add_row("Max posts à vérifier", str(max_posts_check))
    table.add_row("Probabilité like", f"{like_percentage}%")
    table.add_row("Probabilité follow", f"{follow_percentage}%")
    table.add_row("Probabilité commentaire", f"{comment_percentage}%")
    table.add_row("Probabilité stories", f"{story_view_percentage}%")
    table.add_row("Probabilité like stories", f"{story_like_percentage}%")
    
    console.print(table)
    
    console.print(f"\n[green]📊 Estimations de session :[/green]")
    estimated_likes = int(int(max_profiles) * int(max_likes_per_profile) * (int(like_percentage) / 100))
    estimated_follows = int(int(max_profiles) * (int(follow_percentage) / 100))
    estimated_comments = int(int(max_profiles) * (int(comment_percentage) / 100))
    
    console.print(f"• Likes estimés : {estimated_likes}")
    console.print(f"• Follows estimés : {estimated_follows}")
    console.print(f"• Commentaires estimés : {estimated_comments}")
    
    console.print(f"\n[green]✅ Workflow URL de post configuré pour {post_url}[/green]")
    
    return workflow_config

def _validate_instagram_url(url: str) -> bool:
    import re
    
    patterns = [
        r'^https?://(?:www\.)?instagram\.com/p/([A-Za-z0-9_-]+)/?.*$',  # Posts
        r'^https?://(?:www\.)?instagram\.com/reel/([A-Za-z0-9_-]+)/?.*$',  # Reels
        r'^https?://(?:www\.)?instagram\.com/tv/([A-Za-z0-9_-]+)/?.*$',  # IGTV
    ]
    
    for pattern in patterns:
        if re.match(pattern, url):
            return True
    
    return False

def _extract_post_id_from_url(url: str) -> str:
    import re
    
    patterns = [
        r'instagram\.com/p/([A-Za-z0-9_-]+)',
        r'instagram\.com/reel/([A-Za-z0-9_-]+)',
        r'instagram\.com/tv/([A-Za-z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

# ==================== SCRAPING WORKFLOW GENERATORS ====================

def generate_target_scraping_workflow():
    """Generate configuration for target-based scraping (followers/following)."""
    console.print("\n[bold green]🔍 Target Scraping Configuration[/bold green]")
    
    console.print("[dim]💡 Tip: You can enter multiple targets separated by commas (e.g., user1,user2,user3)[/dim]")
    target_username = Prompt.ask("[cyan]Target username(s) to scrape[/cyan]")
    if not target_username:
        console.print("[red]❌ Username required[/red]")
        return None
    
    # Parse multiple targets
    target_usernames = [t.strip().lstrip('@') for t in target_username.split(',') if t.strip()]
    if len(target_usernames) > 1:
        console.print(f"[green]✅ {len(target_usernames)} targets detected: {', '.join(['@' + t for t in target_usernames])}[/green]")
    
    # Scraping type
    console.print("\n[yellow]📋 What do you want to scrape?[/yellow]")
    console.print("[bold]1.[/bold] 👥 Followers")
    console.print("[bold]2.[/bold] 👤 Following")
    
    scrape_choice = Prompt.ask("[cyan]Your choice[/cyan]", choices=["1", "2"], default="1")
    scrape_type = "followers" if scrape_choice == "1" else "following"
    
    # Limits
    console.print("\n[yellow]📊 Scraping limits[/yellow]")
    max_profiles = int(Prompt.ask("[cyan]Maximum profiles to scrape[/cyan]", default="500"))
    
    # Session settings
    console.print("\n[yellow]⏱️ Session settings[/yellow]")
    session_duration = int(Prompt.ask("[cyan]Maximum session duration (minutes)[/cyan]", default="60"))
    
    scraping_config = {
        "type": "target",
        "scrape_type": scrape_type,
        "target_usernames": target_usernames,
        "max_profiles": max_profiles,
        "session_duration_minutes": session_duration,
        "save_to_db": True,
        "export_csv": True
    }
    
    # Summary
    console.print("\n[green]📋 Scraping Configuration Summary:[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Target(s)", ", ".join(['@' + t for t in target_usernames]))
    table.add_row("Scrape type", scrape_type.capitalize())
    table.add_row("Max profiles", str(max_profiles))
    table.add_row("Session duration", f"{session_duration} min")
    table.add_row("Save to database", "Yes")
    table.add_row("Export to CSV", "Yes")
    
    console.print(table)
    
    if not Confirm.ask("\n[bold cyan]Start scraping with this configuration?[/bold cyan]", default=True):
        return None
    
    return scraping_config


def generate_hashtag_scraping_workflow():
    """Generate configuration for hashtag-based scraping."""
    console.print("\n[bold green]🔍 Hashtag Scraping Configuration[/bold green]")
    
    hashtag = Prompt.ask("[cyan]Hashtag to scrape (without #)[/cyan]")
    if not hashtag:
        console.print("[red]❌ Hashtag required[/red]")
        return None
    
    hashtag = hashtag.lstrip('#')
    
    # Scraping mode
    console.print("\n[yellow]📋 What do you want to scrape?[/yellow]")
    console.print("[bold]1.[/bold] 👤 Post authors (users who posted with this hashtag)")
    console.print("[bold]2.[/bold] ❤️ Post likers (users who liked posts with this hashtag)")
    
    scrape_choice = Prompt.ask("[cyan]Your choice[/cyan]", choices=["1", "2"], default="1")
    scrape_type = "authors" if scrape_choice == "1" else "likers"
    
    # Limits
    console.print("\n[yellow]📊 Scraping limits[/yellow]")
    max_profiles = int(Prompt.ask("[cyan]Maximum profiles to scrape[/cyan]", default="200"))
    max_posts = int(Prompt.ask("[cyan]Maximum posts to check[/cyan]", default="50"))
    
    # Session settings
    console.print("\n[yellow]⏱️ Session settings[/yellow]")
    session_duration = int(Prompt.ask("[cyan]Maximum session duration (minutes)[/cyan]", default="60"))
    
    scraping_config = {
        "type": "hashtag",
        "hashtag": hashtag,
        "scrape_type": scrape_type,
        "max_profiles": max_profiles,
        "max_posts": max_posts,
        "session_duration_minutes": session_duration,
        "save_to_db": True,
        "export_csv": True
    }
    
    # Summary
    console.print("\n[green]📋 Scraping Configuration Summary:[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Hashtag", f"#{hashtag}")
    table.add_row("Scrape type", scrape_type.capitalize())
    table.add_row("Max profiles", str(max_profiles))
    table.add_row("Max posts to check", str(max_posts))
    table.add_row("Session duration", f"{session_duration} min")
    table.add_row("Save to database", "Yes")
    table.add_row("Export to CSV", "Yes")
    
    console.print(table)
    
    if not Confirm.ask("\n[bold cyan]Start scraping with this configuration?[/bold cyan]", default=True):
        return None
    
    return scraping_config


def generate_url_scraping_workflow():
    """Generate configuration for post URL-based scraping (likers)."""
    console.print("\n[bold green]🔍 Post URL Scraping Configuration[/bold green]")
    
    post_url = Prompt.ask("[cyan]Instagram post URL[/cyan]")
    if not post_url:
        console.print("[red]❌ Post URL required[/red]")
        return None
    
    if not _validate_instagram_url(post_url):
        console.print("[red]❌ Invalid Instagram URL. Must be a post, reel, or IGTV URL.[/red]")
        return None
    
    # Limits
    console.print("\n[yellow]📊 Scraping limits[/yellow]")
    max_profiles = int(Prompt.ask("[cyan]Maximum likers to scrape[/cyan]", default="200"))
    
    # Session settings
    console.print("\n[yellow]⏱️ Session settings[/yellow]")
    session_duration = int(Prompt.ask("[cyan]Maximum session duration (minutes)[/cyan]", default="60"))
    
    scraping_config = {
        "type": "post_url",
        "post_url": post_url,
        "post_id": _extract_post_id_from_url(post_url),
        "scrape_type": "likers",
        "max_profiles": max_profiles,
        "session_duration_minutes": session_duration,
        "save_to_db": True,
        "export_csv": True
    }
    
    # Summary
    console.print("\n[green]📋 Scraping Configuration Summary:[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Post URL", post_url[:50] + "..." if len(post_url) > 50 else post_url)
    table.add_row("Post ID", scraping_config["post_id"] or "Unknown")
    table.add_row("Scrape type", "Likers")
    table.add_row("Max profiles", str(max_profiles))
    table.add_row("Session duration", f"{session_duration} min")
    table.add_row("Save to database", "Yes")
    table.add_row("Export to CSV", "Yes")
    
    console.print(table)
    
    if not Confirm.ask("\n[bold cyan]Start scraping with this configuration?[/bold cyan]", default=True):
        return None
    
    return scraping_config


@click.group(invoke_without_command=True)
@click.option('--lang', '-l', type=click.Choice(['fr', 'en']), help='Language (fr/en)')
@click.pass_context
def cli(ctx, lang=None):
    if not lang:
        lang = select_language()
    
    set_language(lang)
    
    console = Console()
    
    from taktik.cli.license_prompt import check_license_on_startup
    
    license_valid, api_key = check_license_on_startup()
    if not license_valid:
        sys.exit(1)
    
    os.environ['TAKTIK_API_KEY'] = api_key
    
    from taktik.core.license.unified_license_manager import unified_license_manager
    
    configure_db_service(api_key)
    
    if ctx.invoked_subcommand is None:
        display_banner()
        
        while True:
            options = ['instagram', 'tiktok', 'quit']
            labels = [
                current_translations['option_instagram'],
                current_translations['option_tiktok'],
                current_translations['option_quit']
            ]
            
            console.print(f"\n[bold cyan]{current_translations['menu_title']}[/bold cyan]")
            
            for i, label in enumerate(labels, 1):
                console.print(f"[bold]{i}.[/bold] {label}")
            
            selected = click.prompt(f"\n[bold]{current_translations['prompt_choice']}[/bold]", 
                                 type=click.IntRange(1, len(options)),
                                 show_choices=False)
            
            choice = options[selected-1]
            
            if choice == 'instagram':
                # Sous-menu: Management, Automation ou Scraping
                console.print("\n[bold cyan]Instagram Mode Selection[/bold cyan]")
                console.print("[bold]1.[/bold] 🔧 Management (Features: Auth, Content, DM)")
                console.print("[bold]2.[/bold] 🤖 Automation (Workflows: Target followers/Followings, Hashtags, Post url)")
                console.print("[bold]3.[/bold] 🔍 Scraping (Extract profiles: Target, Hashtag, Post URL)")
                console.print("[bold]4.[/bold] ← Back")
                
                mode_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 4), show_choices=False)
                
                if mode_choice == 4:
                    continue
                
                # Sélection du device (commun aux deux modes)
                devices = device_manager.list_devices()
                if not devices:
                    console.print(f"[red]{current_translations['no_device_connected']}[/red]")
                    continue
                console.print(f"\n[bold cyan]{current_translations['select_device']}[/bold cyan]")
                for idx, device in enumerate(devices, 1):
                    console.print(f"[bold]{idx}.[/bold] {device['id']} ({device['status']})")
                selected_device = click.prompt(f"\n[bold]{current_translations['prompt_choice']}[/bold]", type=click.IntRange(1, len(devices)), show_choices=False)
                device_id = devices[selected_device-1]['id']
                console.print(f"[blue]{current_translations['device_selected'].format(device_id)}[/blue]")
                instagram = InstagramManager(device_id)
                if not instagram.is_installed():
                    console.print(f"[red]{current_translations['instagram_not_installed']}[/red]")
                    continue
                console.print(f"[blue]{current_translations['launching_instagram']}[/blue]")
                if instagram.launch():
                    console.print(f"[green]{current_translations['instagram_launched_success']}[/green]")
                else:
                    console.print(f"[red]{current_translations['instagram_launch_failed']}[/red]")
                    continue
                
                if mode_choice == 1:
                    # Mode Management
                    console.print("\n[bold cyan]Management Options[/bold cyan]")
                    console.print("[bold]1.[/bold] 🔐 Login")
                    console.print("[bold]2.[/bold] 📸 Post Content")
                    console.print("[bold]3.[/bold] 📱 Post Story")
                    console.print("[bold]4.[/bold] 💬 Manage DMs (Coming soon)")
                    console.print("[bold]5.[/bold] ← Back")
                    
                    mgmt_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 5), show_choices=False)
                    
                    if mgmt_choice == 5:
                        continue
                    
                    elif mgmt_choice == 1:
                        # Login interactif
                        from taktik.core.social_media.instagram.workflows.management.login_workflow import LoginWorkflow
                        import uiautomator2 as u2
                        from getpass import getpass
                        
                        console.print("\n[bold green]🔐 Instagram Login[/bold green]")
                        
                        username = Prompt.ask("[cyan]👤 Username, email or phone[/cyan]")
                        password = getpass("🔑 Password: ")
                        
                        if not username or not password:
                            console.print("[red]❌ Username and password required.[/red]")
                            continue
                        
                        save_session = Confirm.ask("[cyan]💾 Save session (Taktik)?[/cyan]", default=True)
                        save_instagram_login = Confirm.ask("[cyan]💾 Save login info (Instagram)?[/cyan]", default=False)
                        
                        try:
                            device = u2.connect(device_id)
                            login_workflow = LoginWorkflow(device, device_id)
                            
                            with console.status("[bold yellow]🔄 Logging in...[/bold yellow]", spinner="dots"):
                                result = login_workflow.execute(
                                    username=username,
                                    password=password,
                                    max_retries=3,
                                    save_session=save_session,
                                    use_saved_session=True,
                                    save_login_info_instagram=save_instagram_login
                                )
                            
                            if result['success']:
                                console.print(Panel.fit(
                                    f"[bold green]✅ Login successful![/bold green]\n"
                                    f"[cyan]👤 Username:[/cyan] {result['username']}\n"
                                    f"[cyan]💾 Session saved:[/cyan] {'Yes' if result['session_saved'] else 'No'}",
                                    title="[bold green]Success[/bold green]",
                                    border_style="green"
                                ))
                            else:
                                console.print(Panel.fit(
                                    f"[bold red]❌ Login failed[/bold red]\n"
                                    f"[cyan]❌ Error:[/cyan] {result['message']}",
                                    title="[bold red]Failed[/bold red]",
                                    border_style="red"
                                ))
                        except Exception as e:
                            console.print(f"[bold red]❌ Error: {e}[/bold red]")
                        
                        input("\nPress Enter to continue...")
                        continue
                    
                    elif mgmt_choice == 2:
                        # Post Content interactif
                        from taktik.core.social_media.instagram.workflows.management.content_workflow import ContentWorkflow
                        from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
                        from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
                        import uiautomator2 as u2
                        
                        console.print("\n[bold green]📸 Post Content[/bold green]")
                        
                        image_path = Prompt.ask("[cyan]📷 Image path[/cyan]")
                        caption = Prompt.ask("[cyan]✍️  Caption[/cyan] (optional)", default="")
                        location = Prompt.ask("[cyan]📍 Location[/cyan] (optional)", default="")
                        hashtags_input = Prompt.ask("[cyan]#️⃣ Hashtags[/cyan] (optional, space-separated)", default="")
                        
                        if not image_path:
                            console.print("[red]❌ Image path required.[/red]")
                            continue
                        
                        hashtag_list = None
                        if hashtags_input:
                            hashtag_list = [tag.strip() for tag in hashtags_input.split()]
                        
                        try:
                            device = u2.connect(device_id)
                            device_mgr = DeviceManager()
                            device_mgr.connect(device_id)
                            
                            nav_actions = NavigationActions(device)
                            detection_actions = DetectionActions(device)
                            workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
                            
                            console.print("\n[yellow]⏳ Publishing...[/yellow]")
                            result = workflow.post_single_photo(
                                image_path, 
                                caption if caption else None, 
                                location if location else None,
                                hashtag_list
                            )
                            
                            if result['success']:
                                console.print(Panel.fit(
                                    f"[green]✅ Post published successfully![/green]",
                                    title="[bold green]Success[/bold green]",
                                    border_style="green"
                                ))
                            else:
                                console.print(Panel.fit(
                                    f"[red]❌ Failed to publish[/red]\n"
                                    f"[cyan]Error:[/cyan] {result['message']}",
                                    title="[bold red]Failed[/bold red]",
                                    border_style="red"
                                ))
                        except Exception as e:
                            console.print(f"[bold red]❌ Error: {e}[/bold red]")
                        
                        input("\nPress Enter to continue...")
                        continue
                    
                    elif mgmt_choice == 3:
                        # Post Story interactif
                        from taktik.core.social_media.instagram.workflows.management.content_workflow import ContentWorkflow
                        from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
                        from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
                        import uiautomator2 as u2
                        
                        console.print("\n[bold green]📱 Post Story[/bold green]")
                        
                        image_path = Prompt.ask("[cyan]📷 Image path[/cyan]")
                        
                        if not image_path:
                            console.print("[red]❌ Image path required.[/red]")
                            continue
                        
                        try:
                            device = u2.connect(device_id)
                            device_mgr = DeviceManager()
                            device_mgr.connect(device_id)
                            
                            nav_actions = NavigationActions(device)
                            detection_actions = DetectionActions(device)
                            workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
                            
                            console.print("\n[yellow]⏳ Publishing story...[/yellow]")
                            result = workflow.post_story(image_path)
                            
                            if result['success']:
                                console.print(Panel.fit(
                                    f"[green]✅ Story published successfully![/green]",
                                    title="[bold green]Success[/bold green]",
                                    border_style="green"
                                ))
                            else:
                                console.print(Panel.fit(
                                    f"[red]❌ Failed to publish story[/red]\n"
                                    f"[cyan]Error:[/cyan] {result['message']}",
                                    title="[bold red]Failed[/bold red]",
                                    border_style="red"
                                ))
                        except Exception as e:
                            console.print(f"[bold red]❌ Error: {e}[/bold red]")
                        
                        input("\nPress Enter to continue...")
                        continue
                    
                    elif mgmt_choice == 4:
                        console.print("[yellow]💬 DM management coming soon![/yellow]")
                        input("\nPress Enter to continue...")
                        continue
                
                elif mode_choice == 2:
                    # Mode Automation (ancien workflow)
                    from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
                    
                    target_type = select_target_type()
                    if not target_type:
                        console.print(f"[red]{current_translations['no_target_selected']}[/red]")
                        continue
                    
                    dynamic_config = generate_dynamic_workflow(target_type)
                    if not dynamic_config:
                        console.print(f"[red]{current_translations['workflow_generation_error']}[/red]")
                        continue

                    if not device_manager.connect(device_id):
                        console.print(f"[red]{current_translations['cannot_connect_device'].format(device_id)}[/red]")
                        continue

                    if not device_manager.device:
                        console.print(f"[red]{current_translations['device_init_error']}[/red]")
                        continue

                    console.print(f"[blue]{current_translations['initializing_automation']}[/blue]")
                    automation = InstagramAutomation(device_manager)
                    
                    automation._initialize_license_limits(api_key)
                    automation.config = dynamic_config
                    console.print(f"[green]{current_translations['dynamic_config_applied']}[/green]")
                    
                    automation.run_workflow()
                    
                    console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
                    sys.exit(0)
                
                elif mode_choice == 3:
                    # Mode Scraping
                    console.print("\n[bold cyan]🔍 Scraping Mode[/bold cyan]")
                    console.print("[bold]1.[/bold] 👥 Target Scraping (Followers/Following)")
                    # console.print("[bold]2.[/bold] #️⃣ Hashtag Scraping")  # TODO: À implémenter
                    console.print("[bold]2.[/bold] 🔗 Post URL Scraping (Likers)")
                    console.print("[bold]3.[/bold] ← Back")
                    
                    scraping_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 3), show_choices=False)
                    
                    if scraping_choice == 3:
                        continue
                    
                    # Générer la config de scraping selon le choix
                    if scraping_choice == 1:
                        scraping_config = generate_target_scraping_workflow()
                    # elif scraping_choice == 2:
                    #     scraping_config = generate_hashtag_scraping_workflow()  # TODO: À implémenter
                    elif scraping_choice == 2:
                        scraping_config = generate_url_scraping_workflow()
                    
                    if not scraping_config:
                        console.print("[red]❌ Scraping configuration cancelled.[/red]")
                        continue
                    
                    # Connexion au device
                    if not device_manager.connect(device_id):
                        console.print(f"[red]{current_translations['cannot_connect_device'].format(device_id)}[/red]")
                        continue
                    
                    if not device_manager.device:
                        console.print(f"[red]{current_translations['device_init_error']}[/red]")
                        continue
                    
                    # Lancer le scraping
                    from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import ScrapingWorkflow
                    
                    console.print("[blue]🔍 Initializing scraping workflow...[/blue]")
                    scraping_workflow = ScrapingWorkflow(device_manager, scraping_config)
                    scraping_workflow.run()
                    
                    console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
                    sys.exit(0)
            
            elif choice == 'tiktok':
                # Menu TikTok
                console.print("\n[bold cyan]TikTok Mode Selection[/bold cyan]")
                console.print("[bold]1.[/bold] 🔧 Management (Features: Auth, Profile, Videos)")
                console.print("[bold]2.[/bold] 🤖 Automation (Workflows: Target users, Hashtags, For You, Sounds)")
                console.print("[bold]3.[/bold] ← Back")
                
                mode_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 3), show_choices=False)
                
                if mode_choice == 3:
                    continue
                
                # Sélection du device
                devices = device_manager.list_devices()
                if not devices:
                    console.print(f"[red]{current_translations['no_device_connected']}[/red]")
                    continue
                
                console.print(f"\n[bold cyan]{current_translations['select_device']}[/bold cyan]")
                for idx, device in enumerate(devices, 1):
                    console.print(f"[bold]{idx}.[/bold] {device['id']} ({device['status']})")
                
                selected_device = click.prompt(f"\n[bold]{current_translations['prompt_choice']}[/bold]", type=click.IntRange(1, len(devices)), show_choices=False)
                device_id = devices[selected_device-1]['id']
                console.print(f"[blue]{current_translations['device_selected'].format(device_id)}[/blue]")
                
                # Initialiser TikTok
                tiktok = TikTokManager(device_id)
                if not tiktok.is_installed():
                    console.print("[red]❌ TikTok is not installed on this device.[/red]")
                    continue
                
                console.print("[blue]🚀 Launching TikTok...[/blue]")
                if tiktok.launch():
                    console.print("[green]✅ TikTok launched successfully![/green]")
                else:
                    console.print("[red]❌ Failed to launch TikTok.[/red]")
                    continue
                
                if mode_choice == 1:
                    # Mode Management
                    console.print("\n[bold cyan]TikTok Management Options[/bold cyan]")
                    console.print("[bold]1.[/bold] 🔐 Login (Coming soon)")
                    console.print("[bold]2.[/bold] 👤 Profile Management (Coming soon)")
                    console.print("[bold]3.[/bold] 🎬 Video Management (Coming soon)")
                    console.print("[bold]4.[/bold] 📊 Statistics (Coming soon)")
                    console.print("[bold]5.[/bold] ← Back")
                    
                    mgmt_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 5), show_choices=False)
                    
                    if mgmt_choice == 5:
                        continue
                    else:
                        console.print("[yellow]⚠️ This feature is coming soon![/yellow]")
                        input("\nPress Enter to continue...")
                        continue
                
                elif mode_choice == 2:
                    # Mode Automation
                    console.print("\n[bold cyan]TikTok Automation Workflows[/bold cyan]")
                    console.print("[bold]1.[/bold] 👥 Target Users (Followers/Following) - Coming soon")
                    console.print("[bold]2.[/bold] #️⃣ Hashtag Targeting - Coming soon")
                    console.print("[bold]3.[/bold] 🎯 For You Feed - Coming soon")
                    console.print("[bold]4.[/bold] 🎵 Sound/Music Targeting - Coming soon")
                    console.print("[bold]5.[/bold] 📊 View Statistics - Coming soon")
                    console.print("[bold]6.[/bold] ← Back")
                    
                    auto_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 6), show_choices=False)
                    
                    if auto_choice == 6:
                        continue
                    else:
                        console.print("[yellow]⚠️ TikTok automation workflows are coming soon![/yellow]")
                        console.print("[cyan]💡 The architecture is ready. Workflows will be implemented in the next update.[/cyan]")
                        input("\nPress Enter to continue...")
                        continue
                    
            elif choice == 'quit':
                console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
                sys.exit(0)

@cli.command()
def setup():
    console.print(Panel.fit("[bold green]Configuration de Taktik-Instagram[/bold green]"))
    console.print("[yellow]Cette fonctionnalité sera implémentée prochainement.[/yellow]")

@cli.group()
def device():
    pass

@cli.group()
def automation():
    """🤖 Instagram automation (workflows, hashtags, followers)."""
    pass

@cli.group()
def tiktok():
    pass

@device.command(name="list")
def list_devices():
    console.print(Panel.fit("[bold green]Liste des appareils connectés[/bold green]"))
    
    devices = SimpleDeviceManager.list_devices()
    
    if not devices:
        console.print("[yellow]Aucun appareil connecté.[/yellow]")
        console.print("[blue]Assurez-vous que l'appareil est connecté et que ADB est correctement configuré.[/blue]")
        return
    
    table = Table(title="Appareils connectés")
    table.add_column("ID", style="cyan")
    table.add_column("Statut", style="green")
    
    for i, device_id in enumerate(devices):
        table.add_row(device_id, "Connecté")
    
    console.print(table)

# Les commandes management et auth sont définies plus bas après la définition des groupes

@automation.command("workflow")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--config', '-c', type=click.Path(exists=True), help="Chemin vers le fichier de configuration JSON du workflow")
def workflow_instagram(device_id, config):
    from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation
    console.print(Panel.fit("[bold green]Lancement du workflow Instagram[/bold green]"))
    
    if not device_id:
        devices = SimpleDeviceManager().list_devices()
        if not devices:
            console.print("[red]Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
    
    console.print(f"[blue]Utilisation de l'appareil: {device_id}[/blue]")
    
    if not config:
        target_type = select_target_type()
        if not target_type:
            console.print("[red]Aucune cible sélectionnée. Arrêt du workflow.[/red]")
            return
        
        dynamic_config = generate_dynamic_workflow(target_type)
        if not dynamic_config:
            console.print("[red]Erreur lors de la génération du workflow dynamique.[/red]")
            return
    
    final_config = None
    if config:
        try:
            with open(config, 'r') as f:
                final_config = json.load(f)
            console.print(f"[green]Configuration chargée depuis {config}[/green]")
        except Exception as e:
            console.print(f"[red]Erreur lors du chargement de la configuration: {e}[/red]")
            return
    elif 'dynamic_config' in locals():
        final_config = dynamic_config
        console.print("[green]Configuration dynamique préparée[/green]")
    else:
        console.print("[yellow]Aucune configuration fournie, utilisation des paramètres par défaut.[/yellow]")
        final_config = {}
    
    try:
        device_manager = SimpleDeviceManager(device_id)
        if not device_manager.connect(device_id):
            console.print(f"[red]Impossible de se connecter à l'appareil {device_id}[/red]")
            return
        
        if not device_manager.device:
            console.print(f"[red]Erreur: L'appareil n'a pas pu être initialisé correctement[/red]")
            return
            
        console.print("[blue]Initialisation de l'automatisation Instagram...[/blue]")
        automation = InstagramAutomation(device_manager, config=final_config)
        
        from taktik.core.license.unified_license_manager import unified_license_manager
        console.print("[green]Automatisation initialisée avec succès[/green]")
        
        if final_config:
            session_settings = final_config.get('session_settings', {})
            duration = session_settings.get('session_duration_minutes', 60)
            max_profiles = session_settings.get('total_profiles_limit', session_settings.get('total_interactions_limit', 'illimité'))
            console.print(f"[cyan]⚙️  Configuration appliquée: {duration} min, {max_profiles} profils max[/cyan]")
        
    except ValueError as e:
        console.print(f"[red]Erreur de configuration: {e}[/red]")
        return
    except Exception as e:
        console.print(f"[red]Erreur inattendue lors de l'initialisation: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return
    automation.run_workflow()
    

@tiktok.command("launch")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
def launch_tiktok(device_id):
    """Lance TikTok sur l'appareil spécifié."""
    console.print(Panel.fit("[bold green]Lancement de TikTok[/bold green]"))
    if not device_id:
        devices = SimpleDeviceManager().list_devices()
        if not devices:
            console.print("[red]Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]Utilisation de l'appareil: {device_id}[/blue]")
    tiktok = TikTokManager(device_id)
    if not tiktok.is_installed():
        console.print("[red]TikTok n'est pas installé sur cet appareil.[/red]")
        return
    console.print("[blue]Lancement de TikTok...[/blue]")
    success = tiktok.launch()
    if success:
        console.print(f"\n[green]{current_translations['hashtag_workflow_success']}[/green]")
    else:
        console.print("[red]Échec du lancement de TikTok.[/red]")

@cli.command()
@click.option('--network', '-n', required=True, type=click.Choice(['instagram', 'tiktok']), help='Réseau social à lancer')
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
def launch(network, device_id):
    """Lance l'application du réseau social choisi sur l'appareil spécifié."""
    console.print(Panel.fit(f"[bold green]Lancement de {network.capitalize()}[/bold green]"))
    if not device_id:
        devices = SimpleDeviceManager().list_devices()
        if not devices:
            console.print("[red]Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]Utilisation de l'appareil: {device_id}[/blue]")
    if network == 'instagram':
        manager = InstagramManager(device_id)
    elif network == 'tiktok':
        manager = TikTokManager(device_id)
    else:
        console.print("[red]Réseau social non supporté.[/red]")
        return
    if not manager.is_installed():
        console.print(f"[red]{network.capitalize()} n'est pas installé sur cet appareil.[/red]")
        return
    console.print(f"[blue]Lancement de {network.capitalize()}...[/blue]")
    success = manager.launch()
    if success:
        console.print(f"[green]{network.capitalize()} a été lancé avec succès ![/green]")
    else:
        console.print(f"[red]Échec du lancement de {network.capitalize()}.[/red]")

@cli.command()
def proxy():
    """Gestion des proxies."""
    console.print(Panel.fit("[bold green]Gestion des proxies[/bold green]"))
    console.print("[yellow]Cette fonctionnalité sera implémentée prochainement.[/yellow]")

@cli.command()
def account():
    """Gestion des comptes Instagram."""
    console.print(Panel.fit("[bold green]Gestion des comptes Instagram[/bold green]"))
    console.print("[yellow]Cette fonctionnalité sera implémentée prochainement.[/yellow]")

@cli.command()
def run():
    """Démarre une session d'interaction."""
    console.print(Panel.fit("[bold green]Démarrage d'une session d'interaction[/bold green]"))
    console.print("[yellow]Cette fonctionnalité sera implémentée prochainement.[/yellow]")

# ==================== MANAGEMENT GROUP ====================

@cli.group("management")
def management():
    """🔧 Gestion manuelle Instagram (auth, content, DM)."""
    pass

@management.group("auth")
def auth():
    """🔐 Authentification et gestion de compte."""
    pass

@auth.command("login")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--username', '-u', help="Nom d'utilisateur, email ou numéro de téléphone")
@click.option('--password', '-p', help="Mot de passe (sera demandé de manière sécurisée si non fourni)")
@click.option('--save-session/--no-save-session', default=True, help="Sauvegarder la session après connexion (système Taktik)")
@click.option('--save-instagram-login/--no-save-instagram-login', default=False, help="Sauvegarder les infos de login dans Instagram")
def login_instagram(device_id, username, password, save_session, save_instagram_login):
    """Se connecter à un compte Instagram."""
    from taktik.core.social_media.instagram.workflows.management.login_workflow import LoginWorkflow
    import uiautomator2 as u2
    from getpass import getpass
    
    console.print(Panel.fit("[bold green]🔐 Connexion à Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = SimpleDeviceManager().list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            console.print("[blue]💡 Assurez-vous que l'appareil est connecté et que ADB est configuré.[/blue]")
            return
        device_id = devices[0]
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    # Demander le username si non fourni
    if not username:
        username = Prompt.ask("[cyan]👤 Nom d'utilisateur, email ou numéro de téléphone[/cyan]")
    
    # Demander le password de manière sécurisée si non fourni
    if not password:
        password = getpass("🔑 Mot de passe: ")
    
    if not username or not password:
        console.print("[red]❌ Username et password requis.[/red]")
        return
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Vérifier qu'Instagram est installé
        instagram_manager = InstagramManager(device_id)
        if not instagram_manager.is_installed():
            console.print("[red]❌ Instagram n'est pas installé sur cet appareil.[/red]")
            return
        
        # Lancer Instagram si pas déjà lancé
        console.print("[blue]📱 Lancement d'Instagram...[/blue]")
        instagram_manager.launch()
        time.sleep(3)  # Attendre que l'app se lance
        
        # Créer le workflow de login
        login_workflow = LoginWorkflow(device, device_id)
        
        # Afficher les informations
        console.print(f"\n[cyan]👤 Username:[/cyan] {username}")
        console.print(f"[cyan]💾 Save session (Taktik):[/cyan] {'Yes' if save_session else 'No'}")
        console.print(f"[cyan]💾 Save login info (Instagram):[/cyan] {'Yes' if save_instagram_login else 'No'}\n")
        
        # Exécuter le login
        with console.status("[bold yellow]🔄 Connexion en cours...[/bold yellow]", spinner="dots"):
            result = login_workflow.execute(
                username=username,
                password=password,
                max_retries=3,
                save_session=save_session,
                use_saved_session=True,
                save_login_info_instagram=save_instagram_login
            )
        
        # Afficher le résultat
        console.print()
        if result['success']:
            console.print(Panel.fit(
                f"[bold green]✅ Connexion réussie ![/bold green]\n\n"
                f"[cyan]👤 Username:[/cyan] {result['username']}\n"
                f"[cyan]🔄 Tentatives:[/cyan] {result['attempts']}\n"
                f"[cyan]💾 Session sauvegardée:[/cyan] {'Oui' if result['session_saved'] else 'Non'}",
                title="[bold green]Succès[/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel.fit(
                f"[bold red]❌ Échec de la connexion[/bold red]\n\n"
                f"[cyan]👤 Username:[/cyan] {result['username']}\n"
                f"[cyan]🔄 Tentatives:[/cyan] {result['attempts']}\n"
                f"[cyan]❌ Erreur:[/cyan] {result['message']}\n"
                f"[cyan]🏷️ Type d'erreur:[/cyan] {result['error_type'] or 'unknown'}",
                title="[bold red]Échec[/bold red]",
                border_style="red"
            ))
            
            # Suggestions selon le type d'erreur
            if result['error_type'] == 'credentials_error':
                console.print("\n[yellow]💡 Vérifiez vos identifiants et réessayez.[/yellow]")
            elif result['error_type'] == '2fa_required':
                console.print("\n[yellow]💡 2FA requis - Cette fonctionnalité sera bientôt disponible.[/yellow]")
            elif result['error_type'] == 'suspicious_login':
                console.print("\n[yellow]💡 Instagram a détecté une connexion inhabituelle.[/yellow]")
                console.print("[yellow]   Essayez de vous connecter manuellement d'abord.[/yellow]")
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur inattendue: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

@management.group("content")
def content():
    """📸 Gestion du contenu Instagram (posts, stories, carousel)."""
    pass

@content.command("post")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--image', '-i', required=True, type=click.Path(exists=True), help="Chemin vers l'image à poster")
@click.option('--caption', '-c', help="Légende du post")
@click.option('--location', '-l', help="Localisation du post")
@click.option('--hashtags', '-h', help="Hashtags séparés par des espaces (ex: 'travel nature sunset')")
def post_single(device_id, image, caption, location, hashtags):
    """Poster une photo unique sur Instagram."""
    from taktik.core.social_media.instagram.workflows.management.content_workflow import ContentWorkflow
    from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📸 Publication d'un post Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = SimpleDeviceManager().list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Initialiser les composants
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Créer le workflow
        workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
        
        # Afficher les infos
        console.print(f"\n[cyan]📷 Image:[/cyan] {image}")
        if caption:
            console.print(f"[cyan]✍️  Caption:[/cyan] {caption[:50]}{'...' if len(caption) > 50 else ''}")
        if location:
            console.print(f"[cyan]📍 Location:[/cyan] {location}")
        
        hashtag_list = None
        if hashtags:
            hashtag_list = [tag.strip() for tag in hashtags.split()]
            console.print(f"[cyan]#️⃣ Hashtags:[/cyan] {', '.join(hashtag_list)}")
        
        console.print("\n[yellow]⏳ Publication en cours...[/yellow]")
        
        result = workflow.post_single_photo(image, caption, location, hashtag_list)
        
        # Afficher le résultat
        if result['success']:
            console.print(Panel(
                f"[green]✅ Post publié avec succès ![/green]\n"
                f"[cyan]Image:[/cyan] {result['image_path']}",
                title="[bold green]Succès[/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[red]❌ Échec de la publication[/red]\n"
                f"[cyan]Erreur:[/cyan] {result['message']}",
                title="[bold red]Échec[/bold red]",
                border_style="red"
            ))
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

@content.command("post-bulk")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--images', '-i', required=True, multiple=True, type=click.Path(exists=True), help="Chemins vers les images à poster (peut être répété)")
@click.option('--captions', '-c', multiple=True, help="Légendes des posts (même ordre que les images)")
@click.option('--delay', default=60, help="Délai entre chaque post en secondes (défaut: 60)")
def post_bulk(device_id, images, captions, delay):
    """Poster plusieurs photos successivement."""
    from taktik.core.social_media.instagram.workflows.management.content_workflow import ContentWorkflow
    from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📸 Publication multiple de posts Instagram[/bold green]"))
    
    if not images:
        console.print("[red]❌ Aucune image fournie.[/red]")
        return
    
    # Sélectionner le device
    if not device_id:
        devices = SimpleDeviceManager().list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Initialiser les composants
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Créer le workflow
        workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
        
        # Afficher les infos
        console.print(f"\n[cyan]📷 Nombre d'images:[/cyan] {len(images)}")
        console.print(f"[cyan]⏱️  Délai entre posts:[/cyan] {delay}s")
        
        # Convertir captions en liste
        captions_list = list(captions) if captions else None
        
        console.print("\n[yellow]⏳ Publication en cours...[/yellow]")
        
        # Poster
        results = workflow.post_multiple_photos(list(images), captions_list, delay)
        
        # Afficher le résultat
        console.print(Panel(
            f"[cyan]Total:[/cyan] {results['total']}\n"
            f"[green]✅ Réussis:[/green] {results['success']}\n"
            f"[red]❌ Échoués:[/red] {results['failed']}",
            title="[bold blue]Résultats[/bold blue]",
            border_style="blue"
        ))
        
        # Afficher le détail
        if results['failed'] > 0:
            console.print("\n[yellow]Détails des échecs:[/yellow]")
            for post in results['posts']:
                if not post['success']:
                    console.print(f"  [red]❌ {post['image_path']}: {post['message']}[/red]")
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

@content.command("story")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--image', '-i', required=True, type=click.Path(exists=True), help="Chemin vers l'image de la story")
def post_story(device_id, image):
    """Poster une story sur Instagram."""
    from taktik.core.social_media.instagram.workflows.management.content_workflow import ContentWorkflow
    from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📱 Publication d'une story Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = SimpleDeviceManager().list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Initialiser les composants
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Créer le workflow
        workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
        
        # Afficher les infos
        console.print(f"\n[cyan]📷 Image:[/cyan] {image}")
        
        console.print("\n[yellow]⏳ Publication en cours...[/yellow]")
        
        # Poster
        result = workflow.post_story(image)
        
        # Afficher le résultat
        if result['success']:
            console.print(Panel(
                f"[green]✅ Story publiée avec succès ![/green]\n"
                f"[cyan]Image:[/cyan] {result['image_path']}",
                title="[bold green]Succès[/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[red]❌ Échec de la publication[/red]\n"
                f"[cyan]Erreur:[/cyan] {result['message']}",
                title="[bold red]Échec[/bold red]",
                border_style="red"
            ))
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

if __name__ == "__main__":
    cli()
