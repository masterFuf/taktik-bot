import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from taktik.cli.prompts.instagram import _validate_instagram_url, _extract_post_id_from_url

console = Console()

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


