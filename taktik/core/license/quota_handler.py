from rich.console import Console
from rich.panel import Panel
from typing import Dict, Any
import sys

console = Console()

def display_quota_exceeded_message(license_info: Dict[str, Any], usage_stats: Dict[str, Any]):    
    console.print("\n" + "="*80)
    console.print("[bold red]🚫 DAILY QUOTA REACHED[/bold red]", justify="center")
    console.print("="*80)
    
    console.print("\n[yellow]You have reached your daily interaction quota.[/yellow]")
    
    plan = license_info.get('plan', 'Unknown')
    max_actions = license_info.get('max_actions_per_day', 0)
    
    console.print(f"\n[cyan]📋 Your current plan:[/cyan]")
    console.print(f"  • [white]Plan:[/white] {plan}")
    console.print(f"  • [white]Daily actions:[/white] {max_actions}")
    
    actions_used = usage_stats.get('actions_used_today', 0)
    console.print(f"\n[cyan]📊 Today's statistics:[/cyan]")
    console.print(f"  • [green]Actions performed:[/green] {actions_used}/{max_actions}")
    console.print(f"  • [yellow]Remaining actions:[/yellow] 0")
    
    console.print("\n[blue]ℹ️  Important information:[/blue]")
    console.print("  • [white]Your quota will reset tomorrow at midnight[/white]")
    console.print("  • [white]To perform more interactions today, upgrade to a higher license[/white]")
    
    console.print(f"\n[bold cyan]💎 Discover our Premium plans:[/bold cyan]")
    console.print("[bold blue]🔗 https://taktik-bot.com/fr/pricing[/bold blue]")
    
    console.print("\n" + "="*80)
    console.print("[bold]The bot will now stop automatically.[/bold]", justify="center")
    console.print("="*80 + "\n")
    
    sys.exit(0)
