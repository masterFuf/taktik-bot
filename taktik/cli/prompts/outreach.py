import click
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

console = Console()

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
    openrouter_api_key = Prompt.ask("[cyan]OpenRouter API Key[/cyan]", default="")
    
    if not openrouter_api_key:
        console.print("[yellow]⚠️ No API key provided. You can set it later via environment variable OPENROUTER_API_KEY[/yellow]")
    
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
        "openrouter_api_key": openrouter_api_key,
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
    
    table.add_row("API Key", "Configured" if openrouter_api_key else "Not set")
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
