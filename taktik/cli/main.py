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
from taktik.core.shared.device.manager import DeviceManager
from taktik.core.social_media.instagram.core.manager import InstagramManager
from taktik.core.social_media.tiktok.core.manager import TikTokManager
from taktik.core.database import configure_db_service
from taktik.locales import fr, en
from taktik import __version__
from taktik.utils.version_checker import check_version
from taktik.cli.context import update_language_state
from taktik.cli.prompts.instagram import (
    select_target_type, generate_dynamic_workflow, generate_target_workflow,
    generate_hashtags_workflow, generate_post_url_workflow, generate_place_workflow,
    _validate_instagram_url, _extract_post_id_from_url,
)
from taktik.cli.prompts.scraping import (
    generate_target_scraping_workflow, generate_hashtag_scraping_workflow,
    generate_url_scraping_workflow, generate_post_scraping_workflow,
)
from taktik.cli.prompts.outreach import (
    generate_cold_dm_workflow, generate_dm_auto_reply_workflow,
)
from taktik.cli.commands.management_cmds import management

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
    update_language_state(current_translations, current_banner)

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
                            openrouter_api_key=auto_reply_config.get('openrouter_api_key', ''),
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
                    console.print("[bold]4.[/bold] ← Back")
                    
                    scraping_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 4), show_choices=False)
                    
                    if scraping_choice == 4:
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
                        from taktik.core.app.ai.providers.openrouter import AIService

                        def _build_scraping_ai_service(*, api_key, ipc=None, vision_model=None, text_model=None):
                            return AIService(
                                api_key=api_key,
                                ipc=ipc,
                                vision_model=vision_model,
                                text_model=text_model,
                            )

                        scraping_workflow = ScrapingWorkflow(
                            device_manager,
                            scraping_config,
                            ai_service_factory=_build_scraping_ai_service,
                        )
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
cli.add_command(management)

if __name__ == "__main__":
    cli()
