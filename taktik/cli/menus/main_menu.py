"""The interactive menu of `taktik`: a platform, then a mode, until Quit.

Every entry ends in the launcher the desktop app runs (a host of `taktik/cli/hosts/`, or a handler
of the workflow registry): the menu builds no engine of its own.
"""
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from taktik.core.shared.device.manager import DeviceManager
from taktik.core.social_media.instagram.manager import InstagramManager
from taktik.core.social_media.tiktok.manager import TikTokManager
from taktik.cli.menus.instagram import select_target_type, generate_dynamic_workflow
from taktik.cli.menus.instagram_cold_dm import generate_cold_dm_workflow
from taktik.cli.menus.instagram_scraping import (
    generate_target_scraping_workflow, generate_hashtag_scraping_workflow,
    generate_url_scraping_workflow, generate_profile_posts_scraping_workflow,
)
from taktik.cli.support import language

device_manager = DeviceManager()


def run_main_menu():
    """Show the main menu and run what the operator picks, until Quit."""
    current_translations = language.current_translations
    console = Console()

    while True:
        # Threads, Gmail and YouTube have runnable handlers but never had a menu entry, so
        # they were unreachable from the terminal. Labels stay literal: they are platform
        # names, and adding three translation keys per language for them would be noise.
        options = ['instagram', 'tiktok', 'threads', 'gmail', 'youtube', 'quit']
        labels = [
            current_translations['option_instagram'],
            current_translations['option_tiktok'],
            '🧵 Threads',
            '📧 Gmail',
            '▶️  YouTube',
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
            
            # Device selection, shared by both modes
            from taktik.cli.support.device_selector import select_device
            device_id = select_device(device_manager, current_translations)
            if not device_id:
                continue
            instagram = InstagramManager(device_id)
            if not instagram.is_installed():
                console.print(f"[red]{current_translations['instagram_not_installed']}[/red]")
                continue
            # Automation and scraping runs restart Instagram themselves, cleanly, like desktop
            # runs: a warm launch here would only be undone.
            def _launch_instagram() -> bool:
                console.print(f"[blue]{current_translations['launching_instagram']}[/blue]")
                if instagram.launch():
                    console.print(f"[green]{current_translations['instagram_launched_success']}[/green]")
                    return True
                console.print(f"[red]{current_translations['instagram_launch_failed']}[/red]")
                return False

            if mode_choice == 1 and not _launch_instagram():
                continue
            
            if mode_choice == 1:
                # Mode Management
                console.print("\n[bold cyan]Management Options[/bold cyan]")
                console.print("[bold]1.[/bold] 🔐 Login")
                console.print("[bold]2.[/bold] 📸 Post Content")
                console.print("[bold]3.[/bold] 📱 Post Story")
                console.print("[bold]4.[/bold] 💬 Cold DM (Send DMs to list)")
                console.print("[bold]5.[/bold] 💬 DM Replies (read the inbox, answer)")
                console.print("[bold]6.[/bold] 📥 View DM Inbox")
                console.print("[bold]7.[/bold] ← Back")
                
                mgmt_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 7), show_choices=False)
                
                if mgmt_choice == 7:
                    continue
                
                elif mgmt_choice == 1:
                    # Login through the desktop's account launcher (clean restart, then login).
                    from taktik.cli.support.device_selector import connect_device
                    from taktik.cli.hosts.instagram import run_instagram_account_payload
                    from getpass import getpass
                    
                    console.print("\n[bold green]🔐 Instagram Login[/bold green]")
                    
                    username = Prompt.ask("[cyan]👤 Username, email or phone[/cyan]")
                    password = getpass("🔑 Password: ")
                    
                    if not username or not password:
                        console.print("[red]❌ Username and password required.[/red]")
                        continue
                    
                    save_session = Confirm.ask("[cyan]💾 Save session (Taktik)?[/cyan]", default=True)
                    save_instagram_login = Confirm.ask("[cyan]💾 Save login info (Instagram)?[/cyan]", default=False)
                    
                    if not connect_device(device_manager, device_id, current_translations):
                        continue

                    try:
                        with console.status("[bold yellow]🔄 Logging in...[/bold yellow]", spinner="dots"):
                            result = run_instagram_account_payload(
                                device_manager, device_id, "instagram.account.login",
                                {
                                    "username": username,
                                    "password": password,
                                    "maxRetries": 3,
                                    "saveSession": save_session,
                                    "saveLoginInfoInstagram": save_instagram_login,
                                },
                            )

                        if result.get('success'):
                            console.print(Panel.fit(
                                f"[bold green]✅ Login successful![/bold green]\n"
                                f"[cyan]👤 Username:[/cyan] {result.get('username', username)}\n"
                                f"[cyan]💾 Session saved:[/cyan] {'Yes' if result.get('session_saved') else 'No'}",
                                title="[bold green]Success[/bold green]",
                                border_style="green"
                            ))
                        else:
                            console.print(Panel.fit(
                                f"[bold red]❌ Login failed[/bold red]\n"
                                f"[cyan]❌ Error:[/cyan] {result.get('message', '')}",
                                title="[bold red]Failed[/bold red]",
                                border_style="red"
                            ))
                    except Exception as e:
                        console.print(f"[bold red]❌ Error: {e}[/bold red]")
                    
                    input("\nPress Enter to continue...")
                    continue
                
                elif mgmt_choice in (2, 3):
                    # Post / story: the desktop's publishing workflow, as `taktik publish`.
                    from taktik.cli.commands.instagram.publish import run_publish

                    is_story = mgmt_choice == 3
                    console.print("\n[bold green]📱 Post Story[/bold green]" if is_story
                                  else "\n[bold green]📸 Post Content[/bold green]")
                    media_path = Prompt.ask("[cyan]📷 Media path (photo or video)[/cyan]")
                    if not media_path:
                        console.print("[red]❌ Media path required.[/red]")
                        continue
                    caption = hashtags_input = ""
                    if not is_story:
                        caption = Prompt.ask("[cyan]✍️  Caption[/cyan] (optional)", default="")
                        hashtags_input = Prompt.ask("[cyan]#️⃣ Hashtags[/cyan] (optional, space-separated)", default="")

                    run_publish("story" if is_story else "post", device_id, (media_path,),
                                caption, hashtags_input)

                    input("\nPress Enter to continue...")
                    continue

                elif mgmt_choice == 4:
                    # Cold DM Workflow
                    cold_dm_config = generate_cold_dm_workflow()
                    if not cold_dm_config:
                        console.print("[red]❌ Cold DM configuration cancelled.[/red]")
                        input("\nPress Enter to continue...")
                        continue
                    
                    from taktik.cli.support.device_selector import connect_device
                    if not connect_device(device_manager, device_id, current_translations):
                        continue
                    
                    # The desktop's cold DM engine, through its handler: the recipient policy,
                    # the record of who already got a DM, AI with OPENROUTER_API_KEY.
                    console.print("[blue]💬 Initializing Cold DM workflow...[/blue]")
                    from taktik.cli.hosts.instagram import run_instagram_cold_dm_payload
                    try:
                        run_instagram_cold_dm_payload(device_manager, device_id, cold_dm_config)
                    except Exception as exc:  # noqa: BLE001 - a failed run reports, not tracebacks
                        console.print(f"[red]Cold DM failed:[/red] {type(exc).__name__}: {exc}")
                        sys.exit(1)
                    
                    console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
                    sys.exit(0)
                
                elif mgmt_choice in (5, 6):
                    # The DM Responses page's launchers: read the inbox (`dm_read`), then one
                    # `dm_send` per reply, typed here; writing replies with AI is the app's.
                    from taktik.cli.support.device_selector import connect_device as _connect
                    if not _connect(device_manager, device_id, current_translations):
                        continue

                    from taktik.cli.menus import instagram_dm as dm_menu
                    limit = int(Prompt.ask("[cyan]Conversations to read (0: the whole inbox)[/cyan]",
                                           default="10"))
                    try:
                        if mgmt_choice == 5:
                            outcome = dm_menu.reply_to_inbox(device_manager, device_id, limit,
                                                             ask=Prompt.ask, show=console.print)
                            read = outcome["read"]
                            sent = outcome["sent"]
                            console.print(f"[green]{sum(1 for s in sent if s['success'])} reply(ies) sent[/green]"
                                          f" / {len(sent)}")
                        else:
                            read = dm_menu.read_inbox(device_manager, device_id, limit)
                            for conv in read.get("conversations") or []:
                                waiting = " (awaits a reply)" if dm_menu.replyable([conv]) else ""
                                console.print(f"@{conv.get('username')}{waiting}")
                        if not read.get("success"):
                            console.print(f"[red]❌ {read.get('error') or 'DM inbox read failed'}[/red]")
                    except Exception as exc:  # noqa: BLE001 - a failed run reports, not tracebacks
                        console.print(f"[red]DM failed:[/red] {type(exc).__name__}: {exc}")

                    input("\nPress Enter to continue...")
                    continue

            elif mode_choice == 2:
                # Mode Automation: the prompts describe the run the way a desktop page does,
                # and the run goes through the automation handler, the desktop's launcher
                # (clean restart, selector overrides, language, AI with OPENROUTER_API_KEY).
                target_type = select_target_type()
                if not target_type:
                    console.print(f"[red]{current_translations['no_target_selected']}[/red]")
                    continue

                payload = generate_dynamic_workflow(target_type)
                if not payload:
                    console.print(f"[red]{current_translations['workflow_generation_error']}[/red]")
                    continue

                from taktik.cli.support.device_selector import connect_device as _conn
                if not _conn(device_manager, device_id, current_translations):
                    continue

                console.print(f"[blue]{current_translations['initializing_automation']}[/blue]")
                from taktik.cli.hosts.instagram import run_instagram_payload
                try:
                    run_instagram_payload(device_manager, device_id, payload)
                except Exception as exc:  # noqa: BLE001 - a failed run reports, not tracebacks
                    console.print(f"[red]Workflow failed:[/red] {type(exc).__name__}: {exc}")
                    sys.exit(1)

                console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
                sys.exit(0)
            
            elif mode_choice == 3:
                # Mode Scraping
                console.print("\n[bold cyan]🔍 Scraping Mode[/bold cyan]")
                console.print("[bold]1.[/bold] 👥 Target Scraping (Followers/Following)")
                console.print("[bold]2.[/bold] #️⃣ Hashtag Scraping (Authors/Likers)")
                console.print("[bold]3.[/bold] 🔗 Post Scraping (a post's likers/commenters, posts of accounts)")
                console.print("[bold]4.[/bold] ← Back")
                
                scraping_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 4), show_choices=False)
                
                if scraping_choice == 4:
                    continue
                
                scraping_config = None
                
                # Build the scraping configuration from the choice
                if scraping_choice == 1:
                    scraping_config = generate_target_scraping_workflow()
                elif scraping_choice == 2:
                    scraping_config = generate_hashtag_scraping_workflow()
                elif scraping_choice == 3:
                    # Post scraping: the Scraping page's post URL and posts-of-accounts sources.
                    console.print("\n[bold cyan]🔗 Post Scraping Options[/bold cyan]")
                    console.print("[bold]1.[/bold] ❤️ Likers of a post")
                    console.print("[bold]2.[/bold] 💬 Commenters of a post")
                    console.print("[bold]3.[/bold] 📊 Likers + commenters of a post, profiles visited")
                    console.print("[bold]4.[/bold] 🗂️ Posts of accounts (link, likes, comments)")
                    console.print("[bold]5.[/bold] ← Back")
                    
                    post_scraping_choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, 5), show_choices=False)
                    
                    if post_scraping_choice == 5:
                        continue
                    if post_scraping_choice == 4:
                        scraping_config = generate_profile_posts_scraping_workflow()
                    else:
                        scraping_config = generate_url_scraping_workflow(
                            ("likers", "commenters", "both")[post_scraping_choice - 1]
                        )
                
                if scraping_choice in (1, 2, 3):
                    if not scraping_config:
                        console.print("[red]❌ Scraping configuration cancelled.[/red]")
                        continue
                    
                    from taktik.cli.support.device_selector import connect_device as _cd3
                    if not _cd3(device_manager, device_id, current_translations):
                        continue
                    
                    # The run goes through the scraping handler, the desktop's launcher: clean
                    # restart, the page's filters, AI with OPENROUTER_API_KEY.
                    console.print("[blue]🔍 Initializing scraping workflow...[/blue]")
                    from taktik.cli.hosts.instagram import run_instagram_scraping_payload
                    try:
                        run_instagram_scraping_payload(device_manager, device_id, scraping_config)
                    except Exception as exc:  # noqa: BLE001 - a failed run reports, not tracebacks
                        console.print(f"[red]Scraping failed:[/red] {type(exc).__name__}: {exc}")
                        sys.exit(1)

                    console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
                    sys.exit(0)
        
        elif choice == 'tiktok':
            # Driven by the Agent registry. This menu used to be nine "Coming soon" entries,
            # one of them claiming the workflows were not implemented yet — while fifteen
            # TikTok workflows ran in production from the desktop app every day.
            from taktik.cli.support.device_selector import select_and_connect_device
            from taktik.cli.menus.registry import run_registry_menu

            device_id = select_and_connect_device(device_manager, current_translations)
            if not device_id:
                continue

            tiktok = TikTokManager(device_id)
            if not tiktok.is_installed():
                console.print("[red]❌ TikTok is not installed on this device.[/red]")
                continue

            console.print("[blue]🚀 Launching TikTok...[/blue]")
            if not tiktok.launch():
                console.print("[red]❌ Failed to launch TikTok.[/red]")
                continue
            console.print("[green]✅ TikTok launched successfully![/green]")

            run_registry_menu('tiktok', device_manager, device_id)
            continue

        elif choice in ('threads', 'gmail', 'youtube'):
            # Platforms that had no CLI surface at all despite having runnable handlers.
            # No app launcher here on purpose: their workflows own their own startup, and
            # guessing a package to force-launch would be a behaviour the desktop does not have.
            from taktik.cli.support.device_selector import select_and_connect_device
            from taktik.cli.menus.registry import run_registry_menu

            device_id = select_and_connect_device(device_manager, current_translations)
            if not device_id:
                continue

            run_registry_menu(choice, device_manager, device_id)
            continue

        elif choice == 'quit':
            console.print(f"\n[yellow]{current_translations['goodbye']}[/yellow]")
            sys.exit(0)
