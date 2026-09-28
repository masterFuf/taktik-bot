"""The banner of the interactive menu: the version, the links, and the update when a newer one is out."""
import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from taktik import __version__
from taktik.cli.support import language

console = Console()


def auto_update():
    """Launch automatic update process."""
    import platform
    import subprocess
    
    console.print("\n[bold yellow]🔄 Starting automatic update...[/bold yellow]\n")
    
    system = platform.system()
    
    try:
        if system == "Windows":
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "scripts", "install.ps1")
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
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "scripts", "install.sh")
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
    current_banner = language.current_banner
    from taktik.cli.support.version_checker import VersionChecker
    
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
    banner_content += "[blue]💬 Discord:[/blue] [link=https://discord.com/invite/6tTBRTMhBj]discord.gg/6tTBRTMhBj[/link]"
    
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
