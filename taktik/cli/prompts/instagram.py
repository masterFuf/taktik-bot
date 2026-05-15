import re
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from taktik.cli.context import get_translations

console = Console()

# Functions that need the active translations call get_translations() on first line.

def select_target_type():
    current_translations = get_translations()
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
    current_translations = get_translations()
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
    current_translations = get_translations()
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
    current_translations = get_translations()
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

