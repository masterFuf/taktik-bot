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
from taktik.core.social_media.tiktok.core.manager import TikTokManager
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
    from taktik.cli.common.workflow_builder import (
        collect_probabilities, collect_filters, collect_session_settings,
        build_filters_config, build_session_config, build_interaction_settings,
        display_probabilities_rows, display_filters_rows, display_session_rows,
        display_estimates,
    )
    
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
    
    probas = collect_probabilities(current_translations)
    filters = collect_filters(current_translations)
    session = collect_session_settings(current_translations)
    
    interaction_settings = build_interaction_settings(probas)
    
    workflow_config = {
        "filters": build_filters_config(filters),
        "session_settings": build_session_config("target_followers", max_profiles, max_likes_per_profile, probas, session),
        "actions": [
            {
                "type": "interact_with_followers",
                "target_username": target_username,
                "target_usernames": target_usernames,
                "interaction_type": interaction_type,
                "max_interactions": max_profiles,
                "like_posts": True,
                "max_likes_per_profile": max_likes_per_profile,
                "probabilities": {
                    "like_percentage": probas['like_percentage'],
                    "follow_percentage": probas['follow_percentage'],
                    "comment_percentage": probas['comment_percentage'],
                    "story_percentage": probas['story_percentage'],
                    "story_like_percentage": probas['story_like_percentage']
                },
                **interaction_settings
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
    
    display_probabilities_rows(table, probas, current_translations)
    display_filters_rows(table, filters, current_translations)
    display_session_rows(table, session, current_translations)
    
    if filters['blacklist_words']:
        table.add_row(f"→ {current_translations['blacklisted_words']}", ", ".join(filters['blacklist_words'][:3]) + ("..." if len(filters['blacklist_words']) > 3 else ""))
    
    console.print(table)
    
    display_estimates(max_profiles, max_likes_per_profile, probas, current_translations)
    
    console.print(f"\n[green]{current_translations['target_workflow_configured'].format(target_username)}[/green]")
    return workflow_config

def generate_hashtags_workflow():
    from taktik.cli.common.workflow_builder import (
        collect_probabilities, collect_filters, collect_session_settings,
        build_filters_config, build_session_config, build_interaction_settings,
        display_probabilities_rows, display_filters_rows, display_session_rows,
        display_estimates,
    )
    
    console.print(f"\n[bold green]🏷️ Configuration du workflow Hashtags[/bold green]")
    
    hashtag = Prompt.ask(f"[cyan]Hashtag à cibler (sans #)[/cyan]")
    if not hashtag:
        console.print(f"[red]Hashtag requis[/red]")
        return None
    
    hashtag = hashtag.lstrip('#')
    
    console.print(f"\n[yellow]📱 Mode: Extraction et interaction avec les likers des meilleurs posts de #{hashtag}[/yellow]")
    console.print(f"[dim]Note: Les posts seront sélectionnés selon leurs métadonnées (likes, commentaires)[/dim]")
    
    console.print(f"\n[bold yellow]🎯 Critères de sélection des posts[/bold yellow]")
    min_likes = Prompt.ask(f"[cyan]Nombre minimum de likes par post[/cyan]", default="100")
    max_likes = Prompt.ask(f"[cyan]Nombre maximum de likes par post[/cyan]", default="50000")
    
    console.print(f"\n[yellow]📊 Configuration des limites :[/yellow]")
    max_profiles = int(Prompt.ask(f"[cyan]Nombre maximum de profils à traiter[/cyan]", default="30"))
    max_likes_per_profile = int(Prompt.ask(f"[cyan]Nombre maximum de likes par profil[/cyan]", default="2"))
    
    probas = collect_probabilities(current_translations, defaults={'follow': 15, 'story': 20})
    filters = collect_filters(current_translations, defaults={'min_followers': 10, 'min_posts': 3})
    session = collect_session_settings(current_translations)
    
    interaction_settings = build_interaction_settings(probas)
    # Remove comment_settings since hashtag workflow doesn't use it in the same way
    interaction_settings.pop('comment_settings', None)
    
    workflow_config = {
        "filters": build_filters_config(filters),
        "session_settings": build_session_config("hashtag_interactions", max_profiles, max_likes_per_profile, probas, session),
        "actions": [
            {
                "type": "hashtag",
                "hashtag": hashtag,
                "max_interactions": max_profiles,
                "max_likes_per_profile": max_likes_per_profile,
                "post_criteria": {
                    "min_likes": int(min_likes),
                    "max_likes": int(max_likes)
                },
                "probabilities": {
                    "like_percentage": probas['like_percentage'],
                    "follow_percentage": probas['follow_percentage'],
                    "comment_percentage": probas['comment_percentage'],
                    "story_percentage": probas['story_percentage'],
                    "story_like_percentage": probas['story_like_percentage']
                },
                "filter_criteria": {
                    "min_followers": filters['min_followers'],
                    "max_followers": filters['max_followers'],
                    "min_posts": filters['min_posts'],
                    "skip_private": True,
                    "skip_business": False
                },
                **interaction_settings
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
    
    display_probabilities_rows(table, probas, current_translations)
    display_filters_rows(table, filters, current_translations)
    display_session_rows(table, session, current_translations)
    
    console.print(table)
    
    display_estimates(max_profiles, max_likes_per_profile, probas, current_translations)
    
    console.print(f"\n[green]✅ Workflow hashtag #{hashtag} configuré avec succès ![/green]")
    return workflow_config

def generate_post_url_workflow():
    from taktik.cli.common.workflow_builder import (
        collect_probabilities, collect_filters, collect_session_settings,
        build_filters_config, build_session_config, build_interaction_settings,
        display_probabilities_rows, display_filters_rows, display_session_rows,
        display_estimates,
    )
    
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
    max_profiles = int(Prompt.ask(f"[cyan]{current_translations['max_profiles_prompt']}[/cyan]", default="20"))
    max_likes_per_profile = int(Prompt.ask(f"[cyan]{current_translations['max_likes_per_profile']}[/cyan]", default="2"))
    
    probas = collect_probabilities(current_translations)
    filters = collect_filters(current_translations)
    session = collect_session_settings(current_translations)
    
    interaction_settings = build_interaction_settings(probas)
    
    workflow_config = {
        "filters": build_filters_config(filters),
        "session_settings": build_session_config("target_followers", max_profiles, max_likes_per_profile, probas, session),
        'steps': [
            {
                'type': 'post_url',
                'post_url': post_url,
                'interaction_type': 'post-likers',
                'max_interactions': max_profiles,
                'max_likes_per_profile': max_likes_per_profile,
                'probabilities': {
                    'like_percentage': probas['like_percentage'],
                    'follow_percentage': probas['follow_percentage'],
                    'comment_percentage': probas['comment_percentage'],
                    'story_percentage': probas['story_percentage'],
                    'story_like_percentage': probas['story_like_percentage']
                },
                **interaction_settings
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
    
    display_probabilities_rows(table, probas, current_translations)
    display_filters_rows(table, filters, current_translations)
    display_session_rows(table, session, current_translations)
    
    console.print(table)
    
    display_estimates(max_profiles, max_likes_per_profile, probas, current_translations)
    
    console.print(f"\n[green]{current_translations['post_url_workflow_success'].format(post_url)}[/green]")
    
    return workflow_config

def generate_place_workflow():
    console.print("\n[green]🏙️ Configuration du workflow Place[/green]")
    
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
    estimated_likes = int(int(max_users) * (int(like_percentage) / 100))
    estimated_follows = int(int(max_users) * (int(follow_percentage) / 100))
    estimated_comments = int(int(max_users) * (int(comment_percentage) / 100))
    
    console.print(f"• Likes estimés : {estimated_likes}")
    console.print(f"• Follows estimés : {estimated_follows}")
    console.print(f"• Commentaires estimés : {estimated_comments}")
    
    console.print(f"\n[green]✅ Workflow place configuré pour {place_name}[/green]")
    
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


def generate_post_scraping_workflow():
    """Generate configuration for full post scraping (stats + likers + comments)."""
    console.print("\n[bold green]📊 Full Post Scraping Configuration[/bold green]")
    console.print("[dim]Scrape post stats, likers, and comments with profile enrichment[/dim]\n")
    
    post_url = Prompt.ask("[cyan]Instagram post URL[/cyan]")
    if not post_url:
        console.print("[red]❌ Post URL required[/red]")
        return None
    
    if not _validate_instagram_url(post_url):
        console.print("[red]❌ Invalid Instagram URL. Must be a post, reel, or IGTV URL.[/red]")
        return None
    
    console.print("\n[yellow]📊 What to scrape[/yellow]")
    scrape_stats = Confirm.ask("[cyan]Scrape post stats (likes, comments count)?[/cyan]", default=True)
    scrape_likers = Confirm.ask("[cyan]Scrape likers?[/cyan]", default=True)
    scrape_comments = Confirm.ask("[cyan]Scrape comments?[/cyan]", default=True)
    
    console.print("\n[yellow]📊 Limits[/yellow]")
    max_likers = int(Prompt.ask("[cyan]Maximum likers to scrape[/cyan]", default="100"))
    max_comments = int(Prompt.ask("[cyan]Maximum comments to scrape[/cyan]", default="50"))
    
    console.print("\n[yellow]🔍 Profile Enrichment[/yellow]")
    enrich_profiles = Confirm.ask("[cyan]Enrich profiles (visit each profile for bio/stats)?[/cyan]", default=True)
    max_profiles_to_enrich = int(Prompt.ask("[cyan]Max profiles to enrich[/cyan]", default="30")) if enrich_profiles else 0
    
    console.print("\n[yellow]⏱️ Session settings[/yellow]")
    session_duration = int(Prompt.ask("[cyan]Maximum session duration (minutes)[/cyan]", default="60"))
    
    scraping_config = {
        "type": "post_scraping",
        "post_url": post_url,
        "post_id": _extract_post_id_from_url(post_url),
        "scrape_stats": scrape_stats,
        "scrape_likers": scrape_likers,
        "scrape_comments": scrape_comments,
        "max_likers": max_likers,
        "max_comments": max_comments,
        "enrich_profiles": enrich_profiles,
        "max_profiles_to_enrich": max_profiles_to_enrich,
        "session_duration_minutes": session_duration,
        "save_to_db": True,
        "export_csv": True
    }
    
    console.print("\n[green]📋 Post Scraping Configuration Summary:[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Post URL", post_url[:50] + "..." if len(post_url) > 50 else post_url)
    table.add_row("Post ID", scraping_config["post_id"] or "Unknown")
    table.add_row("Scrape stats", "Yes" if scrape_stats else "No")
    table.add_row("Scrape likers", f"Yes (max {max_likers})" if scrape_likers else "No")
    table.add_row("Scrape comments", f"Yes (max {max_comments})" if scrape_comments else "No")
    table.add_row("Enrich profiles", f"Yes (max {max_profiles_to_enrich})" if enrich_profiles else "No")
    table.add_row("Session duration", f"{session_duration} min")
    table.add_row("Save to database", "Yes")
    table.add_row("Export to CSV", "Yes")
    
    console.print(table)
    
    if not Confirm.ask("\n[bold cyan]Start post scraping with this configuration?[/bold cyan]", default=True):
        return None
    
    return scraping_config


def generate_cold_dm_workflow():
    """Generate configuration for Cold DM workflow."""
    console.print("\n[bold green]💬 Cold DM Workflow Configuration[/bold green]")
    console.print("[dim]Send personalized DMs to a list of recipients[/dim]\n")
    
    console.print("[yellow]👥 Recipients[/yellow]")
    console.print("[dim]Enter usernames separated by commas, or path to a CSV/TXT file[/dim]")
    recipients_input = Prompt.ask("[cyan]Recipients (usernames or file path)[/cyan]")
    
    recipients = []
    if recipients_input:
        import os
        if os.path.exists(recipients_input):
            # Load from file
            try:
                with open(recipients_input, 'r', encoding='utf-8') as f:
                    content = f.read()
                    recipients = [r.strip().lstrip('@') for r in content.replace('\n', ',').split(',') if r.strip()]
                console.print(f"[green]✅ Loaded {len(recipients)} recipients from file[/green]")
            except Exception as e:
                console.print(f"[red]❌ Error loading file: {e}[/red]")
                return None
        else:
            recipients = [r.strip().lstrip('@') for r in recipients_input.split(',') if r.strip()]
    
    if not recipients:
        console.print("[red]❌ At least one recipient is required[/red]")
        return None
    
    console.print(f"[green]✅ {len(recipients)} recipients configured[/green]")
    
    console.print("\n[yellow]💬 Message Configuration[/yellow]")
    console.print("[bold]1.[/bold] 📝 Manual (predefined messages)")
    console.print("[bold]2.[/bold] 🤖 AI-generated (coming soon)")
    
    mode_choice = click.prompt("\n[bold]Message mode[/bold]", type=click.IntRange(1, 2), default=1, show_choices=False)
    message_mode = "manual" if mode_choice == 1 else "ai"
    
    messages = []
    if message_mode == "manual":
        console.print("\n[dim]Enter your message templates (one per line, empty line to finish)[/dim]")
        console.print("[dim]Use {username} for personalization[/dim]")
        
        while True:
            msg = Prompt.ask("[cyan]Message template[/cyan]", default="")
            if not msg:
                break
            messages.append(msg)
        
        if not messages:
            default_msg = Prompt.ask("[cyan]Enter at least one message[/cyan]")
            if default_msg:
                messages.append(default_msg)
            else:
                console.print("[red]❌ At least one message is required[/red]")
                return None
    
    console.print("\n[yellow]⚙️ Settings[/yellow]")
    delay_min = int(Prompt.ask("[cyan]Minimum delay between DMs (seconds)[/cyan]", default="30"))
    delay_max = int(Prompt.ask("[cyan]Maximum delay between DMs (seconds)[/cyan]", default="60"))
    max_dms = int(Prompt.ask("[cyan]Maximum DMs to send[/cyan]", default="50"))
    skip_private = Confirm.ask("[cyan]Skip private accounts?[/cyan]", default=True)
    
    console.print("\n[yellow]⏱️ Session settings[/yellow]")
    session_duration = int(Prompt.ask("[cyan]Maximum session duration (minutes)[/cyan]", default="60"))
    
    config = {
        "recipients": recipients,
        "message_mode": message_mode,
        "messages": messages,
        "delay_min": delay_min,
        "delay_max": delay_max,
        "max_dms": max_dms,
        "skip_private": skip_private,
        "session_duration_minutes": session_duration
    }
    
    console.print("\n[green]📋 Cold DM Configuration Summary:[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Recipients", str(len(recipients)))
    table.add_row("Message mode", message_mode.capitalize())
    table.add_row("Messages", str(len(messages)))
    table.add_row("Delay", f"{delay_min}-{delay_max}s")
    table.add_row("Max DMs", str(max_dms))
    table.add_row("Skip private", "Yes" if skip_private else "No")
    table.add_row("Session duration", f"{session_duration} min")
    
    console.print(table)
    
    if not Confirm.ask("\n[bold cyan]Start Cold DM workflow with this configuration?[/bold cyan]", default=True):
        return None
    
    return config


def generate_dm_auto_reply_workflow():
    """Generate configuration for DM Auto-Reply workflow."""
    console.print("\n[bold green]🤖 DM Auto-Reply Workflow Configuration[/bold green]")
    console.print("[dim]Automatically reply to incoming DMs using AI[/dim]\n")
    
    console.print("[yellow]🔑 API Configuration[/yellow]")
    fal_api_key = Prompt.ask("[cyan]Fal.ai API Key[/cyan]", default="")
    
    if not fal_api_key:
        console.print("[yellow]⚠️ No API key provided. You can set it later via environment variable FAL_KEY[/yellow]")
    
    console.print("\n[yellow]👤 Persona Configuration[/yellow]")
    persona_name = Prompt.ask("[cyan]Your name/brand name[/cyan]", default="")
    persona_description = Prompt.ask("[cyan]Brief description of who you are[/cyan]", default="")
    business_context = Prompt.ask("[cyan]What is your business/service about?[/cyan]", default="")
    
    console.print("\n[yellow]⚙️ Behavior Settings[/yellow]")
    check_interval_min = int(Prompt.ask("[cyan]Min interval to check new messages (seconds)[/cyan]", default="30"))
    check_interval_max = int(Prompt.ask("[cyan]Max interval to check new messages (seconds)[/cyan]", default="120"))
    reply_delay_min = int(Prompt.ask("[cyan]Min delay before replying (seconds)[/cyan]", default="5"))
    reply_delay_max = int(Prompt.ask("[cyan]Max delay before replying (seconds)[/cyan]", default="30"))
    max_replies = int(Prompt.ask("[cyan]Maximum replies per session[/cyan]", default="50"))
    
    console.print("\n[yellow]🚫 Filters[/yellow]")
    ignore_input = Prompt.ask("[cyan]Usernames to ignore (comma-separated)[/cyan]", default="")
    ignore_usernames = [u.strip().lstrip('@') for u in ignore_input.split(',') if u.strip()] if ignore_input else []
    
    console.print("\n[yellow]⏱️ Session settings[/yellow]")
    session_duration = int(Prompt.ask("[cyan]Maximum session duration (minutes)[/cyan]", default="60"))
    
    config = {
        "fal_api_key": fal_api_key,
        "persona_name": persona_name,
        "persona_description": persona_description,
        "business_context": business_context,
        "check_interval_min": check_interval_min,
        "check_interval_max": check_interval_max,
        "reply_delay_min": reply_delay_min,
        "reply_delay_max": reply_delay_max,
        "max_replies_per_session": max_replies,
        "ignore_usernames": ignore_usernames,
        "session_duration_minutes": session_duration
    }
    
    console.print("\n[green]📋 DM Auto-Reply Configuration Summary:[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("API Key", "Configured" if fal_api_key else "Not set")
    table.add_row("Persona", persona_name or "Not set")
    table.add_row("Check interval", f"{check_interval_min}-{check_interval_max}s")
    table.add_row("Reply delay", f"{reply_delay_min}-{reply_delay_max}s")
    table.add_row("Max replies", str(max_replies))
    table.add_row("Ignored users", str(len(ignore_usernames)))
    table.add_row("Session duration", f"{session_duration} min")
    
    console.print(table)
    
    if not Confirm.ask("\n[bold cyan]Start DM Auto-Reply workflow with this configuration?[/bold cyan]", default=True):
        return None
    
    return config


def generate_discovery_workflow():
    """Generate configuration for AI-powered prospect discovery."""
    console.print("\n[bold green]🎯 Discovery Workflow Configuration[/bold green]")
    console.print("[dim]Find and qualify prospects based on engagement patterns and AI scoring[/dim]\n")
    
    # Campaign name
    campaign_name = Prompt.ask("[cyan]Campaign name[/cyan]", default=f"Discovery {datetime.now().strftime('%Y-%m-%d')}")
    
    # Niche keywords for scoring
    console.print("\n[yellow]🔑 Niche Keywords (for AI scoring)[/yellow]")
    console.print("[dim]Enter keywords that define your target audience (comma-separated)[/dim]")
    console.print("[dim]Example: automation, growth, marketing, instagram bot[/dim]")
    keywords_input = Prompt.ask("[cyan]Keywords[/cyan]", default="")
    niche_keywords = [k.strip() for k in keywords_input.split(',') if k.strip()] if keywords_input else []
    
    # Sources configuration
    console.print("\n[yellow]📍 Discovery Sources[/yellow]")
    
    # Hashtags
    console.print("\n[bold]Hashtags[/bold] [dim](find users engaging with these hashtags)[/dim]")
    hashtags_input = Prompt.ask("[cyan]Hashtags (comma-separated, without #)[/cyan]", default="")
    hashtags = [f"#{h.strip().lstrip('#')}" for h in hashtags_input.split(',') if h.strip()] if hashtags_input else []
    
    # Target accounts
    console.print("\n[bold]Target Accounts[/bold] [dim](find users engaging with these accounts' posts)[/dim]")
    accounts_input = Prompt.ask("[cyan]Accounts (comma-separated, without @)[/cyan]", default="")
    target_accounts = [f"@{a.strip().lstrip('@')}" for a in accounts_input.split(',') if a.strip()] if accounts_input else []
    
    # Post URLs
    console.print("\n[bold]Specific Post URLs[/bold] [dim](find likers/commenters of specific posts)[/dim]")
    urls_input = Prompt.ask("[cyan]Post URLs (comma-separated)[/cyan]", default="")
    post_urls = [u.strip() for u in urls_input.split(',') if u.strip() and 'instagram.com' in u] if urls_input else []
    
    if not hashtags and not target_accounts and not post_urls:
        console.print("[red]❌ At least one source (hashtag, account, or URL) is required[/red]")
        return None
    
    # Limits
    console.print("\n[yellow]📊 Limits[/yellow]")
    max_profiles = int(Prompt.ask("[cyan]Maximum profiles to discover[/cyan]", default="200"))
    max_posts_per_source = int(Prompt.ask("[cyan]Max posts to check per source[/cyan]", default="5"))
    max_profiles_to_enrich = int(Prompt.ask("[cyan]Max profiles to enrich (visit profile)[/cyan]", default="50"))
    
    # Scoring
    console.print("\n[yellow]🤖 AI Scoring[/yellow]")
    min_score = int(Prompt.ask("[cyan]Minimum score to qualify (0-100)[/cyan]", default="60"))
    
    # Session settings
    console.print("\n[yellow]⏱️ Session settings[/yellow]")
    session_duration = int(Prompt.ask("[cyan]Maximum session duration (minutes)[/cyan]", default="60"))
    
    # Options
    console.print("\n[yellow]⚙️ Options[/yellow]")
    enrich_profiles = Confirm.ask("[cyan]Enrich profiles (visit each profile for bio/stats)?[/cyan]", default=True)
    score_profiles = Confirm.ask("[cyan]Score profiles with AI?[/cyan]", default=True)
    
    discovery_config = {
        "campaign_name": campaign_name,
        "niche_keywords": niche_keywords,
        "hashtags": hashtags,
        "target_accounts": target_accounts,
        "post_urls": post_urls,
        "max_profiles": max_profiles,
        "max_posts_per_source": max_posts_per_source,
        "max_profiles_to_enrich": max_profiles_to_enrich,
        "min_score_threshold": min_score,
        "session_duration_minutes": session_duration,
        "enrich_profiles": enrich_profiles,
        "score_profiles": score_profiles,
    }
    
    # Summary
    console.print("\n[green]📋 Discovery Configuration Summary:[/green]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Campaign", campaign_name)
    table.add_row("Niche keywords", ", ".join(niche_keywords) if niche_keywords else "None")
    table.add_row("Hashtags", ", ".join(hashtags) if hashtags else "None")
    table.add_row("Target accounts", ", ".join(target_accounts) if target_accounts else "None")
    table.add_row("Post URLs", str(len(post_urls)) + " URLs" if post_urls else "None")
    table.add_row("Max profiles", str(max_profiles))
    table.add_row("Posts per source", str(max_posts_per_source))
    table.add_row("Profiles to enrich", str(max_profiles_to_enrich))
    table.add_row("Min score", str(min_score))
    table.add_row("Session duration", f"{session_duration} min")
    table.add_row("Enrich profiles", "Yes" if enrich_profiles else "No")
    table.add_row("AI scoring", "Yes" if score_profiles else "No")
    
    console.print(table)
    
    if not Confirm.ask("\n[bold cyan]Start discovery with this configuration?[/bold cyan]", default=True):
        return None
    
    return discovery_config


@click.group(invoke_without_command=True)
@click.option('--lang', '-l', type=click.Choice(['fr', 'en']), help='Language (fr/en)')
@click.pass_context
def cli(ctx, lang=None):
    if not lang:
        lang = select_language()
    
    set_language(lang)
    
    console = Console()
    
    configure_db_service()
    
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
                from taktik.cli.common.device_selector import select_device
                device_id = select_device(device_manager, current_translations)
                if not device_id:
                    continue
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
                    console.print("[bold]4.[/bold] 💬 Cold DM (Send DMs to list)")
                    console.print("[bold]5.[/bold] 🤖 DM Auto-Reply (AI-powered)")
                    console.print("[bold]6.[/bold] 📥 View DM Inbox")
                    console.print("[bold]7.[/bold] ← Back")
                    
                    mgmt_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 7), show_choices=False)
                    
                    if mgmt_choice == 7:
                        continue
                    
                    elif mgmt_choice == 1:
                        # Login interactif
                        from taktik.core.social_media.instagram.workflows.management.login.login_workflow import LoginWorkflow
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
                        from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
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
                        from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
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
                        # Cold DM Workflow
                        cold_dm_config = generate_cold_dm_workflow()
                        if not cold_dm_config:
                            console.print("[red]❌ Cold DM configuration cancelled.[/red]")
                            input("\nPress Enter to continue...")
                            continue
                        
                        from taktik.cli.common.device_selector import connect_device
                        if not connect_device(device_manager, device_id, current_translations):
                            continue
                        
                        from taktik.core.social_media.instagram.workflows.cold_dm import ColdDMWorkflow
                        
                        console.print("[blue]💬 Initializing Cold DM workflow...[/blue]")
                        cold_dm_workflow = ColdDMWorkflow(device_manager, cold_dm_config)
                        cold_dm_workflow.run()
                        
                        console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
                        sys.exit(0)
                    
                    elif mgmt_choice == 5:
                        # DM Auto-Reply Workflow
                        auto_reply_config = generate_dm_auto_reply_workflow()
                        if not auto_reply_config:
                            console.print("[red]❌ DM Auto-Reply configuration cancelled.[/red]")
                            input("\nPress Enter to continue...")
                            continue
                        
                        from taktik.cli.common.device_selector import connect_device as _connect
                        if not _connect(device_manager, device_id, current_translations):
                            continue
                        
                        from taktik.core.social_media.instagram.workflows.management.dm.auto_reply_workflow import DMAutoReplyWorkflow, DMAutoReplyConfig
                        
                        console.print("[blue]🤖 Initializing DM Auto-Reply workflow...[/blue]")
                        
                        # Convert dict config to DMAutoReplyConfig
                        dm_config = DMAutoReplyConfig(
                            fal_api_key=auto_reply_config.get('fal_api_key', ''),
                            persona_name=auto_reply_config.get('persona_name', ''),
                            persona_description=auto_reply_config.get('persona_description', ''),
                            business_context=auto_reply_config.get('business_context', ''),
                            check_interval_min=auto_reply_config.get('check_interval_min', 30),
                            check_interval_max=auto_reply_config.get('check_interval_max', 120),
                            reply_delay_min=auto_reply_config.get('reply_delay_min', 5),
                            reply_delay_max=auto_reply_config.get('reply_delay_max', 30),
                            max_replies_per_session=auto_reply_config.get('max_replies_per_session', 50),
                            ignore_usernames=auto_reply_config.get('ignore_usernames', []),
                            session_duration_minutes=auto_reply_config.get('session_duration_minutes', 60)
                        )
                        
                        import uiautomator2 as u2
                        device = u2.connect(device_id)
                        auto_reply_workflow = DMAutoReplyWorkflow(device, dm_config)
                        auto_reply_workflow.run()
                        
                        console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
                        sys.exit(0)
                    
                    elif mgmt_choice == 6:
                        # View DM Inbox - redirect to existing dm inbox command logic
                        from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS
                        import uiautomator2 as u2
                        
                        console.print("\n[bold green]📥 DM Inbox[/bold green]")
                        
                        try:
                            device = u2.connect(device_id)
                            
                            console.print("[yellow]📥 Navigating to DM inbox...[/yellow]")
                            
                            dm_tab = device.xpath(DM_SELECTORS.direct_tab)
                            if dm_tab.exists:
                                dm_tab.click()
                                time.sleep(2)
                                console.print("[green]✅ Navigated to DMs[/green]")
                            else:
                                for selector in DM_SELECTORS.direct_tab_content_desc:
                                    dm_btn = device.xpath(selector)
                                    if dm_btn.exists:
                                        dm_btn.click()
                                        time.sleep(2)
                                        console.print("[green]✅ Navigated to DMs[/green]")
                                        break
                            
                            console.print("[cyan]📬 DM inbox is now visible on device.[/cyan]")
                            console.print("[dim]Use CLI commands 'taktik management dm inbox' for detailed listing.[/dim]")
                            
                        except Exception as e:
                            console.print(f"[bold red]❌ Error: {e}[/bold red]")
                        
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

                    from taktik.cli.common.device_selector import connect_device as _conn
                    if not _conn(device_manager, device_id, current_translations):
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
                    console.print("[bold]2.[/bold] #️⃣ Hashtag Scraping (Authors/Likers)")
                    console.print("[bold]3.[/bold] 🔗 Post URL Scraping (Likers/Comments)")
                    console.print("[bold]4.[/bold] 🎯 Discovery (AI-powered prospect finding)")
                    console.print("[bold]5.[/bold] ← Back")
                    
                    scraping_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 5), show_choices=False)
                    
                    if scraping_choice == 5:
                        continue
                    
                    scraping_config = None
                    
                    # Générer la config de scraping selon le choix
                    if scraping_choice == 1:
                        scraping_config = generate_target_scraping_workflow()
                    elif scraping_choice == 2:
                        scraping_config = generate_hashtag_scraping_workflow()
                    elif scraping_choice == 3:
                        # Post URL Scraping with enhanced options
                        console.print("\n[bold cyan]🔗 Post Scraping Options[/bold cyan]")
                        console.print("[bold]1.[/bold] ❤️ Scrape Likers only")
                        console.print("[bold]2.[/bold] 💬 Scrape Comments only")
                        console.print("[bold]3.[/bold] 📊 Full Post Scraping (Stats + Likers + Comments)")
                        console.print("[bold]4.[/bold] ← Back")
                        
                        post_scraping_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 4), show_choices=False)
                        
                        if post_scraping_choice == 4:
                            continue
                        
                        if post_scraping_choice == 3:
                            # Full Post Scraping Workflow
                            scraping_config = generate_post_scraping_workflow()
                            if scraping_config:
                                from taktik.cli.common.device_selector import connect_device as _cd
                                if not _cd(device_manager, device_id, current_translations):
                                    continue
                                
                                from taktik.core.social_media.instagram.workflows.post_scraping import PostScrapingWorkflow
                                
                                console.print("[blue]📊 Initializing post scraping workflow...[/blue]")
                                post_workflow = PostScrapingWorkflow(device_manager, scraping_config)
                                post_workflow.run()
                                
                                console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
                                sys.exit(0)
                            continue
                        else:
                            scraping_config = generate_url_scraping_workflow()
                            if scraping_config:
                                scraping_config['scrape_type'] = 'likers' if post_scraping_choice == 1 else 'comments'
                    
                    elif scraping_choice == 4:
                        # Discovery Workflow
                        discovery_config = generate_discovery_workflow()
                        if not discovery_config:
                            console.print("[red]❌ Discovery configuration cancelled.[/red]")
                            continue
                        
                        from taktik.cli.common.device_selector import connect_device as _cd2
                        if not _cd2(device_manager, device_id, current_translations):
                            continue
                        
                        # Lancer le Discovery Workflow (v2 takes device_id, not device_manager)
                        from taktik.core.social_media.instagram.workflows.discovery import DiscoveryWorkflow
                        
                        console.print("[blue]🎯 Initializing discovery workflow...[/blue]")
                        discovery_workflow = DiscoveryWorkflow(device_id, discovery_config)
                        discovery_workflow.run()
                        
                        console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
                        sys.exit(0)
                    
                    if scraping_choice in [1, 2] or (scraping_choice == 3 and scraping_config):
                        if not scraping_config:
                            console.print("[red]❌ Scraping configuration cancelled.[/red]")
                            continue
                        
                        from taktik.cli.common.device_selector import connect_device as _cd3
                        if not _cd3(device_manager, device_id, current_translations):
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
                from taktik.cli.common.device_selector import select_device as _select_device
                device_id = _select_device(device_manager, current_translations)
                if not device_id:
                    continue
                
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
    
    devices = DeviceManager.list_devices()
    
    if not devices:
        console.print("[yellow]Aucun appareil connecté.[/yellow]")
        console.print("[blue]Assurez-vous que l'appareil est connecté et que ADB est correctement configuré.[/blue]")
        return
    
    table = Table(title="Appareils connectés")
    table.add_column("ID", style="cyan")
    table.add_column("Statut", style="green")
    
    for i, device_info in enumerate(devices):
        device_id = device_info['id'] if isinstance(device_info, dict) else device_info
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
        devices = DeviceManager.list_devices()
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
        device_manager = DeviceManager()
        if not device_manager.connect(device_id):
            console.print(f"[red]Impossible de se connecter à l'appareil {device_id}[/red]")
            return
        
        if not device_manager.device:
            console.print(f"[red]Erreur: L'appareil n'a pas pu être initialisé correctement[/red]")
            return
            
        console.print("[blue]Initialisation de l'automatisation Instagram...[/blue]")
        automation = InstagramAutomation(device_manager, config=final_config)
        
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
        devices = DeviceManager.list_devices()
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
        devices = DeviceManager.list_devices()
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
    from taktik.core.social_media.instagram.workflows.management.login.login_workflow import LoginWorkflow
    import uiautomator2 as u2
    from getpass import getpass
    
    console.print(Panel.fit("[bold green]🔐 Connexion à Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
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

# ==================== DM GROUP ====================

@management.group("dm")
def dm():
    """💬 Gestion des messages directs Instagram."""
    pass

@dm.command("inbox")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--limit', '-l', default=20, help="Nombre maximum de conversations à récupérer")
@click.option('--unread-only', '-u', is_flag=True, help="Afficher uniquement les messages non lus")
def dm_inbox(device_id, limit, unread_only):
    """📥 Lister les conversations DM reçues."""
    from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]💬 Récupération des DM Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            console.print("[blue]💡 Assurez-vous que l'appareil est connecté et que ADB est configuré.[/blue]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Vérifier qu'Instagram est lancé
        instagram_manager = InstagramManager(device_id)
        if not instagram_manager.is_running():
            console.print("[yellow]📱 Lancement d'Instagram...[/yellow]")
            instagram_manager.launch()
            time.sleep(3)
        
        console.print("[yellow]📥 Navigation vers la boîte de réception DM...[/yellow]")
        
        # Méthode 1: Cliquer sur l'onglet DM dans la tab bar
        dm_tab = device.xpath(DM_SELECTORS.direct_tab)
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            console.print("[green]✅ Navigué vers les DM via direct_tab[/green]")
        else:
            # Méthode 2: Essayer via content-desc
            found = False
            for selector in DM_SELECTORS.direct_tab_content_desc:
                dm_btn = device.xpath(selector)
                if dm_btn.exists:
                    dm_btn.click()
                    time.sleep(2)
                    console.print("[green]✅ Navigué vers les DM via content-desc[/green]")
                    found = True
                    break
            
            if not found:
                console.print("[red]❌ Impossible de trouver l'onglet DM. Assurez-vous d'être sur le feed ou le profil.[/red]")
                return
        
        time.sleep(2)  # Attendre le chargement
        
        # Récupérer les conversations avec scroll
        console.print("[yellow]🔍 Récupération des conversations...[/yellow]")
        
        conversations = []
        seen_usernames = set()  # Pour éviter les doublons
        max_scrolls = 10  # Nombre maximum de scrolls
        scroll_count = 0
        no_new_count = 0  # Compteur de scrolls sans nouvelles conversations
        
        # Obtenir les dimensions de l'écran pour le scroll
        screen_info = device.info
        screen_width = screen_info['displayWidth']
        screen_height = screen_info['displayHeight']
        
        # Zone de scroll (éviter les notes en haut et la tab bar en bas)
        scroll_start_y = int(screen_height * 0.7)
        scroll_end_y = int(screen_height * 0.3)
        scroll_x = screen_width // 2
        
        while len(conversations) < limit and scroll_count < max_scrolls:
            threads = device.xpath(DM_SELECTORS.thread_container).all()
            
            if not threads and scroll_count == 0:
                console.print("[yellow]⚠️ Aucune conversation trouvée ou liste non chargée.[/yellow]")
                console.print("[dim]Essayez de scroller manuellement pour charger les conversations.[/dim]")
                return
            
            new_conversations_this_scroll = 0
            
            for thread in threads:
                if len(conversations) >= limit:
                    break
                    
                try:
                    thread_info = thread.info
                    content_desc = thread_info.get('contentDescription', '')
                    
                    # Extraire les infos depuis content-desc
                    username = "Unknown"
                    is_unread = False
                    preview = ""
                    timestamp = ""
                    
                    if content_desc:
                        parts = [p.strip() for p in content_desc.split(',')]
                        if parts:
                            username = parts[0]
                            is_unread = any('non lu' in p.lower() or 'unread' in p.lower() for p in parts)
                            if len(parts) >= 3:
                                preview = parts[-2] if len(parts) >= 2 else ""
                                timestamp = parts[-1] if parts else ""
                    
                    # Essayer d'extraire le username via le resource-id spécifique
                    try:
                        username_elem = thread.child(resourceId="com.instagram.android:id/row_inbox_username")
                        if username_elem.exists:
                            username = username_elem.get_text() or username
                    except:
                        pass
                    
                    # Éviter les doublons
                    if username in seen_usernames:
                        continue
                    seen_usernames.add(username)
                    
                    # Essayer d'extraire le digest (preview)
                    try:
                        digest_elem = thread.child(resourceId="com.instagram.android:id/row_inbox_digest")
                        if digest_elem.exists:
                            preview = digest_elem.get_text() or preview
                    except:
                        pass
                    
                    # Essayer d'extraire le timestamp
                    try:
                        time_elem = thread.child(resourceId="com.instagram.android:id/row_inbox_timestamp")
                        if time_elem.exists:
                            timestamp = time_elem.get_text() or timestamp
                    except:
                        pass
                    
                    # Filtrer si unread-only
                    if unread_only and not is_unread:
                        continue
                    
                    conversations.append({
                        'username': username,
                        'is_unread': is_unread,
                        'preview': preview[:50] + '...' if len(preview) > 50 else preview,
                        'timestamp': timestamp
                    })
                    new_conversations_this_scroll += 1
                    
                except Exception as e:
                    continue
            
            # Vérifier si on a atteint la limite
            if len(conversations) >= limit:
                break
            
            # Vérifier si on a trouvé de nouvelles conversations
            if new_conversations_this_scroll == 0:
                no_new_count += 1
                if no_new_count >= 2:  # 2 scrolls sans nouvelles conversations = fin de liste
                    console.print(f"[dim]Fin de la liste atteinte après {scroll_count + 1} scrolls[/dim]")
                    break
            else:
                no_new_count = 0
            
            # Scroll vers le bas
            scroll_count += 1
            console.print(f"[dim]Scroll {scroll_count}/{max_scrolls} - {len(conversations)} conversations trouvées...[/dim]")
            device.swipe(scroll_x, scroll_start_y, scroll_x, scroll_end_y, duration=0.3)
            time.sleep(1.5)  # Attendre le chargement
        
        # Afficher les résultats
        if not conversations:
            console.print("[yellow]⚠️ Aucune conversation trouvée avec les critères spécifiés.[/yellow]")
            return
        
        console.print(f"\n[bold green]📬 {len(conversations)} conversation(s) trouvée(s)[/bold green]\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("👤 Username", style="cyan")
        table.add_column("📩", style="yellow", width=3)
        table.add_column("💬 Aperçu", style="white")
        table.add_column("🕐 Date", style="dim")
        
        for i, conv in enumerate(conversations, 1):
            unread_icon = "🔵" if conv['is_unread'] else "⚪"
            table.add_row(
                str(i),
                conv['username'],
                unread_icon,
                conv['preview'],
                conv['timestamp']
            )
        
        console.print(table)
        
        # Statistiques
        unread_count = sum(1 for c in conversations if c['is_unread'])
        console.print(f"\n[cyan]📊 Statistiques:[/cyan]")
        console.print(f"   • Total: {len(conversations)}")
        console.print(f"   • Non lus: {unread_count}")
        console.print(f"   • Lus: {len(conversations) - unread_count}")
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

@dm.command("read-all")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--limit', '-l', default=10, help="Nombre maximum de conversations à lire")
@click.option('--messages-per-conv', '-m', default=20, help="Nombre de messages par conversation")
def dm_read_all(device_id, limit, messages_per_conv):
    """📖 Lire les messages de plusieurs conversations DM (click → read → back)."""
    from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS
    import uiautomator2 as u2
    
    console.print(Panel.fit(f"[bold green]📖 Lecture de {limit} conversations DM[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Redémarrer Instagram pour être sûr d'être sur la bonne page
        instagram_manager = InstagramManager(device_id)
        console.print("[yellow]🔄 Redémarrage d'Instagram...[/yellow]")
        instagram_manager.stop()
        time.sleep(1)
        instagram_manager.launch()
        time.sleep(4)  # Attendre le chargement complet
        console.print("[green]✅ Instagram redémarré[/green]")
        
        # Naviguer vers les DM
        console.print("[yellow]📥 Navigation vers la boîte de réception DM...[/yellow]")
        
        dm_tab = device.xpath(DM_SELECTORS.direct_tab)
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            console.print("[green]✅ Navigué vers les DM[/green]")
        else:
            for selector in DM_SELECTORS.direct_tab_content_desc:
                dm_btn = device.xpath(selector)
                if dm_btn.exists:
                    dm_btn.click()
                    time.sleep(2)
                    console.print("[green]✅ Navigué vers les DM[/green]")
                    break
        
        time.sleep(2)
        
        # Obtenir les dimensions de l'écran
        screen_info = device.info
        screen_width = screen_info['displayWidth']
        screen_height = screen_info['displayHeight']
        
        all_conversations = []
        processed_usernames = set()
        conversations_read = 0
        scroll_count = 0
        max_scrolls = 10
        
        while conversations_read < limit and scroll_count < max_scrolls:
            # Récupérer les threads visibles
            threads = device.xpath(DM_SELECTORS.thread_container).all()
            
            if not threads:
                console.print("[yellow]⚠️ Aucune conversation visible.[/yellow]")
                break
            
            for thread in threads:
                if conversations_read >= limit:
                    break
                
                try:
                    # Extraire le username
                    thread_info = thread.info
                    content_desc = thread_info.get('contentDescription', '')
                    
                    username = "Unknown"
                    if content_desc:
                        parts = content_desc.split(',')
                        if parts:
                            username = parts[0].strip()
                    
                    # Essayer via resource-id
                    try:
                        username_elem = device(resourceId="com.instagram.android:id/row_inbox_username")
                        if username_elem.exists:
                            for i in range(username_elem.count):
                                elem = username_elem[i]
                                bounds = elem.info.get('bounds', {})
                                thread_bounds = thread_info.get('bounds', {})
                                # Vérifier si l'élément est dans le même thread
                                if bounds and thread_bounds:
                                    if (bounds.get('top', 0) >= thread_bounds.get('top', 0) and 
                                        bounds.get('bottom', 0) <= thread_bounds.get('bottom', 0)):
                                        username = elem.get_text() or username
                                        break
                    except:
                        pass
                    
                    # Éviter les doublons
                    if username in processed_usernames:
                        continue
                    processed_usernames.add(username)
                    
                    console.print(f"\n[cyan]📬 [{conversations_read + 1}/{limit}] Ouverture de: {username}[/cyan]")
                    
                    # Cliquer sur la conversation
                    thread.click()
                    time.sleep(2)
                    
                    # Vérifier qu'on est dans la conversation (header_title présent)
                    header_title = device(resourceId="com.instagram.android:id/header_title")
                    if not header_title.exists(timeout=3):
                        console.print(f"[yellow]⚠️ Impossible d'ouvrir la conversation avec {username}[/yellow]")
                        # Essayer de revenir en arrière
                        device.press("back")
                        time.sleep(1)
                        continue
                    
                    # Récupérer le vrai username depuis le header
                    real_username = header_title.get_text() or username
                    
                    # Détecter si c'est un groupe (subtitle contient "membres" ou "members")
                    is_group = False
                    can_reply = True
                    header_subtitle = device(resourceId="com.instagram.android:id/header_subtitle")
                    if header_subtitle.exists:
                        try:
                            subtitle_desc = header_subtitle.info.get('contentDescription', '')
                            if 'membres' in subtitle_desc.lower() or 'members' in subtitle_desc.lower():
                                is_group = True
                                console.print(f"[yellow]      ⚠️ C'est un groupe ({subtitle_desc})[/yellow]")
                                
                                # Vérifier si on peut écrire (champ de saisie présent)
                                composer = device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
                                if not composer.exists:
                                    can_reply = False
                                    console.print(f"[yellow]      ⚠️ Impossible d'écrire dans ce groupe[/yellow]")
                        except:
                            pass
                    
                    # Récupérer les DERNIERS messages de l'expéditeur (en bas de l'écran)
                    # On ne scrolle pas vers le haut, on veut juste les messages récents
                    last_messages = []
                    
                    # Collecter tous les éléments visibles avec leur position Y
                    all_items = []
                    
                    # 1. Messages texte
                    msg_elements = device(resourceId="com.instagram.android:id/direct_text_message_text_view")
                    for i in range(msg_elements.count):
                        try:
                            msg_elem = msg_elements[i]
                            msg_bounds = msg_elem.info.get('bounds', {})
                            text = msg_elem.get_text()
                            if not text:
                                continue
                            
                            msg_left = msg_bounds.get('left', 0)
                            msg_top = msg_bounds.get('top', 0)
                            is_received = msg_left < screen_width * 0.5
                            
                            all_items.append({
                                'type': 'text',
                                'text': text,
                                'is_sent': not is_received,
                                'top': msg_top
                            })
                        except:
                            continue
                    
                    # 2. Reels/médias partagés
                    reel_shares = device(resourceId="com.instagram.android:id/reel_share_item_view")
                    for i in range(reel_shares.count):
                        try:
                            reel = reel_shares[i]
                            reel_bounds = reel.info.get('bounds', {})
                            reel_left = reel_bounds.get('left', 0)
                            reel_top = reel_bounds.get('top', 0)
                            is_received = reel_left < screen_width * 0.5
                            
                            # Chercher le titre (auteur du reel)
                            title_elem = device(resourceId="com.instagram.android:id/title_text")
                            reel_author = ""
                            for j in range(title_elem.count):
                                try:
                                    t = title_elem[j]
                                    t_bounds = t.info.get('bounds', {})
                                    if (t_bounds.get('top', 0) >= reel_bounds.get('top', 0) and
                                        t_bounds.get('bottom', 0) <= reel_bounds.get('bottom', 0)):
                                        reel_author = t.get_text() or ""
                                        break
                                except:
                                    continue
                            
                            all_items.append({
                                'type': 'reel',
                                'text': f"[Reel de @{reel_author}]" if reel_author else "[Reel partagé]",
                                'is_sent': not is_received,
                                'top': reel_top
                            })
                        except:
                            continue
                    
                    # Trier par position Y (du haut vers le bas = ordre chronologique)
                    all_items.sort(key=lambda x: x['top'])
                    
                    # DEBUG: Afficher tous les éléments détectés
                    console.print(f"[dim]      DEBUG: Éléments triés par position:[/dim]")
                    for item in all_items:
                        direction = "ENVOYÉ" if item['is_sent'] else "REÇU"
                        console.print(f"[dim]        {direction} ({item['top']}): {item['type']} - {item['text'][:30]}...[/dim]")
                    
                    # Récupérer TOUS les messages reçus (pas seulement les derniers consécutifs)
                    # Car l'utilisateur peut avoir envoyé plusieurs messages séparés par nos réponses
                    received_messages = [item for item in all_items if not item['is_sent']]
                    
                    # Dédupliquer par texte
                    seen_texts = set()
                    for msg in received_messages:
                        if msg['text'] not in seen_texts:
                            seen_texts.add(msg['text'])
                            last_messages.append(msg)
                    
                    console.print(f"[dim]      DEBUG: {len(all_items)} éléments, {len(last_messages)} derniers messages reçus[/dim]")
                    for msg in last_messages:
                        console.print(f"[dim]      → {msg['type']}: {msg['text'][:40]}...[/dim]")
                    
                    # Stocker la conversation
                    all_conversations.append({
                        'username': real_username,
                        'messages': last_messages,
                        'is_group': is_group,
                        'can_reply': can_reply
                    })
                    
                    console.print(f"[green]   ✅ {len(last_messages)} dernier(s) message(s) reçu(s)[/green]")
                    
                    # Revenir en arrière
                    back_btn = device(resourceId="com.instagram.android:id/header_left_button")
                    if back_btn.exists:
                        back_btn.click()
                    else:
                        device.press("back")
                    time.sleep(1.5)
                    
                    conversations_read += 1
                    
                except Exception as e:
                    console.print(f"[red]   ❌ Erreur: {e}[/red]")
                    # Essayer de revenir en arrière
                    device.press("back")
                    time.sleep(1)
                    continue
            
            # Vérifier si on a atteint la limite
            if conversations_read >= limit:
                break
            
            # Scroll pour voir plus de conversations
            scroll_count += 1
            console.print(f"[dim]Scroll {scroll_count}/{max_scrolls}...[/dim]")
            device.swipe(screen_width // 2, int(screen_height * 0.7), 
                        screen_width // 2, int(screen_height * 0.3), duration=0.3)
            time.sleep(1.5)
        
        # Afficher le résumé
        console.print(f"\n[bold green]{'='*60}[/bold green]")
        console.print(f"[bold green]📊 RÉSUMÉ: {len(all_conversations)} conversation(s) lue(s)[/bold green]")
        console.print(f"[bold green]{'='*60}[/bold green]\n")
        
        for conv in all_conversations:
            # Afficher le type de conversation
            conv_type = ""
            if conv.get('is_group'):
                conv_type = " [yellow](Groupe)[/yellow]"
                if not conv.get('can_reply'):
                    conv_type += " [red](Lecture seule)[/red]"
            
            console.print(f"\n[bold cyan]💬 Conversation avec: {conv['username']}{conv_type}[/bold cyan]")
            console.print(f"[dim]{'─'*40}[/dim]")
            
            for msg in conv['messages']:
                msg_type = msg.get('type', 'text')
                
                # Icône selon le type
                if msg_type == 'reel':
                    icon = "🎬"
                elif msg_type == 'media':
                    icon = "📷"
                elif msg_type == 'reaction':
                    icon = "💬"
                else:
                    icon = ""
                
                if msg['is_sent']:
                    console.print(f"[blue]  → Vous: {icon} {msg['text']}[/blue]")
                else:
                    console.print(f"[green]  ← {conv['username']}: {icon} {msg['text']}[/green]")
            
            if not conv['messages']:
                console.print("[dim]  (Aucun message trouvé)[/dim]")
        
        # Statistiques globales
        total_messages = sum(len(c['messages']) for c in all_conversations)
        text_count = sum(1 for c in all_conversations for m in c['messages'] if m.get('type') == 'text')
        media_count = sum(1 for c in all_conversations for m in c['messages'] if m.get('type') in ['reel', 'media'])
        group_count = sum(1 for c in all_conversations if c.get('is_group'))
        readonly_count = sum(1 for c in all_conversations if not c.get('can_reply', True))
        replyable_count = sum(1 for c in all_conversations if c.get('can_reply', True) and len(c['messages']) > 0)
        
        console.print(f"\n[cyan]📊 Statistiques globales:[/cyan]")
        console.print(f"   • Conversations: {len(all_conversations)}")
        console.print(f"   • Groupes: {group_count}")
        console.print(f"   • Lecture seule: {readonly_count}")
        console.print(f"   • Avec réponse possible: {replyable_count}")
        console.print(f"   • Messages totaux: {total_messages}")
        console.print(f"   • Textes: {text_count}")
        console.print(f"   • Médias (reels/stories): {media_count}")
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

@dm.command("send")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--to', '-t', required=True, help="Username du destinataire")
@click.option('--message', '-m', required=True, help="Message à envoyer")
def dm_send(device_id, to, message):
    """📤 Envoyer un DM à un utilisateur."""
    from taktik.core.social_media.instagram.workflows.management import DMOutreachWorkflow, DMOutreachConfig
    from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📤 Envoi d'un DM Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
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
        
        # Créer la config
        config = DMOutreachConfig(
            recipients=[to],
            message_template=message,
            delay_between_dms=(3, 5),
            follow_before_dm=False
        )
        
        # Créer le workflow
        workflow = DMOutreachWorkflow(device_mgr, nav_actions, detection_actions)
        
        console.print(f"\n[cyan]👤 Destinataire:[/cyan] @{to}")
        console.print(f"[cyan]💬 Message:[/cyan] {message[:50]}{'...' if len(message) > 50 else ''}")
        
        console.print("\n[yellow]⏳ Envoi en cours...[/yellow]")
        
        # Exécuter
        results = workflow.execute(config)
        
        # Afficher le résultat
        if results and results[0].success:
            console.print(Panel(
                f"[green]✅ Message envoyé avec succès ![/green]\n"
                f"[cyan]Destinataire:[/cyan] @{to}",
                title="[bold green]Succès[/bold green]",
                border_style="green"
            ))
        else:
            error = results[0].error if results else "Erreur inconnue"
            console.print(Panel(
                f"[red]❌ Échec de l'envoi[/red]\n"
                f"[cyan]Erreur:[/cyan] {error}",
                title="[bold red]Échec[/bold red]",
                border_style="red"
            ))
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
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
    from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
    from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📸 Publication d'un post Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
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
    from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
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
        devices = DeviceManager.list_devices()
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
    from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
    from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📱 Publication d'une story Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
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
