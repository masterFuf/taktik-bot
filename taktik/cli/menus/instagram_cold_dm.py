import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm


console = Console()

def generate_cold_dm_workflow():
    """The cold DM run, described the way the desktop's Cold DM page does (camelCase payload).

    The menu hands it to the cold DM handler, the same engine as the desktop bridge.
    """
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
    console.print("[bold]2.[/bold] 🤖 AI-generated (asks for the OpenRouter key if none is set)")
    
    mode_choice = click.prompt("\n[bold]Message mode[/bold]", type=click.IntRange(1, 2), default=1, show_choices=False)
    message_mode = "manual" if mode_choice == 1 else "ai"
    
    messages = []
    ai_prompt = ""
    if message_mode == "ai":
        ai_prompt = Prompt.ask("[cyan]What the messages should say (instructions for the AI)[/cyan]")
        if not ai_prompt.strip():
            console.print("[red]❌ AI mode needs instructions[/red]")
            return None
    if message_mode == "manual":
        console.print("\n[dim]Enter your messages (one per line, empty line to finish); each is sent as typed[/dim]")
        
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
    skip_verified = Confirm.ask("[cyan]Skip certified accounts?[/cyan]", default=False)

    config = {
        "recipients": recipients,
        "messageMode": message_mode,
        "messages": messages,
        "delayMin": delay_min,
        "delayMax": delay_max,
        "maxDmsPerSession": max_dms,
        "skipPrivateAccounts": skip_private,
        "skipVerifiedAccounts": skip_verified,
    }
    if ai_prompt:
        config["aiPrompt"] = ai_prompt
    
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
    table.add_row("Skip certified", "Yes" if skip_verified else "No")
    
    console.print(table)
    
    if not Confirm.ask("\n[bold cyan]Start Cold DM workflow with this configuration?[/bold cyan]", default=True):
        return None
    
    return config
