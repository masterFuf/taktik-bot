import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from taktik.cli.prompts.instagram import _validate_instagram_url, _extract_post_id_from_url

console = Console()

# ==================== SCRAPING WORKFLOW GENERATORS ====================
#
# Every prompt describes the run the way the desktop's Scraping page does (camelCase payload): the
# menu hands it to the scraping handler, the same launcher as the desktop bridge.

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
        "scrapeType": scrape_type,
        "targetUsernames": target_usernames,
        "maxProfiles": max_profiles,
        "sessionDurationMinutes": session_duration,
        "saveToDb": True,
        "exportCsv": True
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
    console.print("[bold]1.[/bold] ❤️ Post likers (users who liked posts with this hashtag)")
    console.print("[bold]2.[/bold] 💬 Post commenters (users who commented on them)")
    
    scrape_choice = Prompt.ask("[cyan]Your choice[/cyan]", choices=["1", "2"], default="1")
    scrape_type = "likers" if scrape_choice == "1" else "commenters"
    
    # Limits
    console.print("\n[yellow]📊 Scraping limits[/yellow]")
    max_profiles = int(Prompt.ask("[cyan]Maximum profiles to scrape[/cyan]", default="200"))
    max_posts = int(Prompt.ask("[cyan]Maximum posts to check[/cyan]", default="50"))
    
    # Session settings
    console.print("\n[yellow]⏱️ Session settings[/yellow]")
    session_duration = int(Prompt.ask("[cyan]Maximum session duration (minutes)[/cyan]", default="60"))
    
    scraping_config = {
        "type": "hashtag",
        "hashtags": [hashtag],
        "scrapeHashtagLikers": scrape_type == "likers",
        "scrapeHashtagCommenters": scrape_type == "commenters",
        "maxProfiles": max_profiles,
        "maxPosts": max_posts,
        "sessionDurationMinutes": session_duration,
        "saveToDb": True,
        "exportCsv": True
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


#: What a post URL run collects, as the Scraping page's two boxes.
POST_URL_POPULATIONS = {
    "likers": (True, False),
    "commenters": (False, True),
    "both": (True, True),
}


def generate_url_scraping_workflow(population: str = "likers"):
    """Generate configuration for post URL-based scraping: its likers, its commenters, or both."""
    console.print("\n[bold green]🔍 Post URL Scraping Configuration[/bold green]")

    post_url = Prompt.ask("[cyan]Instagram post URL[/cyan]")
    if not post_url:
        console.print("[red]❌ Post URL required[/red]")
        return None

    if not _validate_instagram_url(post_url):
        console.print("[red]❌ Invalid Instagram URL. Must be a post, reel, or IGTV URL.[/red]")
        return None

    scrape_likers, scrape_commenters = POST_URL_POPULATIONS[population]
    label = "likers and commenters" if population == "both" else population

    # Limits
    console.print("\n[yellow]📊 Scraping limits[/yellow]")
    max_profiles = int(Prompt.ask(f"[cyan]Maximum {label} to scrape[/cyan]", default="200"))
    enrich_profiles = Confirm.ask("[cyan]Visit each profile (bio, counters, website)?[/cyan]",
                                  default=population == "both")

    # Session settings
    console.print("\n[yellow]⏱️ Session settings[/yellow]")
    session_duration = int(Prompt.ask("[cyan]Maximum session duration (minutes)[/cyan]", default="60"))

    scraping_config = {
        "type": "post_url",
        "postUrls": [post_url],
        "scrapePostUrlLikers": scrape_likers,
        "scrapePostUrlCommenters": scrape_commenters,
        "maxProfiles": max_profiles,
        "enrichProfiles": enrich_profiles,
        "sessionDurationMinutes": session_duration,
        "saveToDb": True,
        "exportCsv": True
    }

    # Summary
    console.print("\n[green]📋 Scraping Configuration Summary:[/green]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="yellow")

    table.add_row("Post URL", post_url[:50] + "..." if len(post_url) > 50 else post_url)
    table.add_row("Post ID", _extract_post_id_from_url(post_url) or "Unknown")
    table.add_row("Scrape type", label.capitalize())
    table.add_row("Max profiles", str(max_profiles))
    table.add_row("Profiles visited", "Yes" if enrich_profiles else "No")
    table.add_row("Session duration", f"{session_duration} min")
    table.add_row("Save to database", "Yes")
    table.add_row("Export to CSV", "Yes")

    console.print(table)

    if not Confirm.ask("\n[bold cyan]Start scraping with this configuration?[/bold cyan]", default=True):
        return None

    return scraping_config


def generate_profile_posts_scraping_workflow():
    """Generate configuration for collecting the posts of accounts: link, likes, comments."""
    console.print("\n[bold green]🗂️ Posts of Accounts Configuration[/bold green]")
    console.print("[dim]Each post's link and counters are kept; no profile is scraped.[/dim]")

    targets = Prompt.ask("[cyan]Account(s) whose posts to collect[/cyan]")
    target_usernames = [t.strip().lstrip('@') for t in (targets or "").split(',') if t.strip()]
    if not target_usernames:
        console.print("[red]❌ Username required[/red]")
        return None

    max_posts = int(Prompt.ask("[cyan]Posts per account[/cyan]", default="20"))
    session_duration = int(Prompt.ask("[cyan]Maximum session duration (minutes)[/cyan]", default="60"))

    scraping_config = {
        "type": "profile_posts",
        "targetUsernames": target_usernames,
        "maxPostsPerTarget": max_posts,
        "sessionDurationMinutes": session_duration,
        "saveToDb": True,
        "exportCsv": True
    }

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="yellow")
    table.add_row("Accounts", ", ".join('@' + t for t in target_usernames))
    table.add_row("Posts per account", str(max_posts))
    table.add_row("Session duration", f"{session_duration} min")
    console.print(table)

    if not Confirm.ask("\n[bold cyan]Start collecting with this configuration?[/bold cyan]", default=True):
        return None

    return scraping_config
