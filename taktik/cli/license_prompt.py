import sys
from typing import Tuple
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from datetime import datetime
from taktik.core.license import unified_license_manager
from taktik.cli.main import current_translations

console = Console()

def prompt_for_license() -> Tuple[bool, str]:
    console.print(f"\n[bold blue]{current_translations['license_config_title']}[/bold blue]")
    console.print(f"[yellow]{current_translations['license_required_message']}[/yellow]")
    console.print(f"[cyan]{current_translations['api_key_auto_message']}[/cyan]")
    
    license_key = Prompt.ask(
        f"\n[cyan]{current_translations['enter_license_key']}[/cyan]",
        password=False
    )
    
    if not license_key or len(license_key.strip()) == 0:
        console.print(f"[red]{current_translations['license_key_required']}[/red]")
        return False, None
    
    console.print(f"\n[yellow]{current_translations['verifying_license']}[/yellow]")
    
    try:
        is_valid, api_key, license_data = unified_license_manager.verify_and_setup_license(license_key.strip())
        
        if is_valid and api_key:
            console.print(f"[green]{current_translations['license_valid_api_retrieved']}[/green]")
            console.print(f"[green]{current_translations['api_key_display'].format(api_key[:12] + '...' + api_key[-8:])}[/green]")
            
            if license_data and license_data.get('valid'):
                full_license_info = license_data.get('license_info', {})
                plan_info = license_data.get('plan_info', {})
                
                full_license_info.update({
                    'plan_name': plan_info.get('name') or plan_info.get('plan_name') or 'Standard',
                    'plan_type': plan_info.get('type') or plan_info.get('plan_type') or 'Premium',
                    'status': 'active' if license_data.get('valid') else 'inactive',
                    'max_accounts': plan_info.get('max_accounts') or 1,
                    'max_actions_per_day': plan_info.get('max_actions_per_day') or 5000,
                    'max_devices': plan_info.get('max_devices') or 1,
                    'has_ai_optimization': plan_info.get('has_ai_optimization', True),
                    'has_intelligent_targeting': plan_info.get('has_intelligent_targeting', True),
                    'has_advanced_reports': plan_info.get('has_advanced_reports', True),
                    'expires_at': full_license_info.get('expires_at') or 'Illimité'
                })
                
                display_license_info(full_license_info)
                license_info = full_license_info
            else:
                console.print(f"[yellow]{current_translations['cannot_retrieve_license_details']}[/yellow]")
                license_info = None
            
            if license_info and license_info.get('id'):
                remaining_actions = unified_license_manager.get_remaining_actions()
                usage_stats = unified_license_manager.get_usage_stats()
                actions_used = usage_stats.get('actions_used_today', 0) if usage_stats else 0
                max_actions = license_info.get('max_actions_per_day', 5000)
                
                limits_check = {
                    'within_limits': remaining_actions > 0 if remaining_actions is not None else True, 
                    'warnings': [],
                    'usage': {'actions_used_today': actions_used},
                    'limits': {'max_actions_per_day': max_actions}
                }
            else:
                limits_check = {
                    'within_limits': True, 
                    'warnings': [],
                    'usage': {'actions_used_today': 0},
                    'limits': {'max_actions_per_day': 5000}
                }
            
            if not limits_check['within_limits']:
                console.print(f"\n[red]{current_translations['daily_limits_reached']}[/red]")
                console.print(f"[yellow]{current_translations['limits_details']}[/yellow]")
                for warning in limits_check['warnings']:
                    console.print(f"  • [yellow]{warning}[/yellow]")
                
                console.print(f"\n[cyan]{current_translations['increase_limits_info']}[/cyan]")
                console.print(f"[bold blue]{current_translations['pricing_url']}[/bold blue]")
                console.print(f"[yellow]{current_translations['contact_support']}[/yellow]")
                return False, None
            
            display_usage_info(limits_check)
            
            remaining_actions = unified_license_manager.get_remaining_actions()
            if remaining_actions is not None:
                console.print(f"[cyan]{current_translations['remaining_actions_today'].format(remaining_actions)}[/cyan]")
            
            console.print("\n" + "="*60 + "\n")
            
            return True, api_key
            
        else:
            error_message = license_data.get('message', 'Erreur de vérification de licence') if license_data else 'Licence invalide'
            console.print(f"[red]❌ {error_message}[/red]")
            
            if "invalide" in error_message.lower():
                console.print(f"\n[yellow]{current_translations['license_error_solutions']}[/yellow]")
                console.print(current_translations['check_license_key'])
                console.print(current_translations['contact_support_persist'])
            elif "expirée" in error_message.lower():
                console.print(f"\n[yellow]{current_translations['license_expired']}[/yellow]")
                console.print(current_translations['renew_license'])
                console.print(current_translations['contact_support_info'])
            elif "appareil" in error_message.lower():
                console.print(f"\n[yellow]{current_translations['license_other_device']}[/yellow]")
                console.print(current_translations['license_already_activated'])
                console.print(current_translations['transfer_license'])
            
            return False, None
            
    except Exception as e:
        console.print(f"[red]{current_translations['configuration_error'].format(str(e))}[/red]")
        console.print(f"[yellow]{current_translations['check_internet_connection']}[/yellow]")
        return False, None


def display_license_info(license_info: dict):
    table = Table(title=current_translations['license_info_title'], show_header=True, header_style="bold magenta")
    table.add_column(current_translations['property'], style="cyan")
    table.add_column(current_translations['value'], style="yellow")
    
    table.add_row(current_translations['user'], license_info.get('user_name') or license_info.get('user_email', 'N/A'))
    table.add_row(current_translations['email'], license_info.get('user_email', 'N/A'))
    
    table.add_row(current_translations['license_key'], license_info.get('license_key', 'N/A'))
    table.add_row(current_translations['plan'], license_info.get('plan_name', 'N/A'))
    table.add_row(current_translations['type'], license_info.get('plan_type', 'N/A'))
    status_text = "✅ Actif" if license_info.get('status') == 'active' or license_info.get('valid') else "❌ Inactif"
    table.add_row(current_translations['status'], status_text)
    
    if license_info.get('expires_at'):
        table.add_row(current_translations['expires_on'], license_info.get('expires_at'))
    
    if license_info.get('max_accounts'):
        table.add_row(current_translations['max_accounts'], str(license_info.get('max_accounts')))
    if license_info.get('max_actions_per_day'):
        table.add_row(current_translations['max_actions_per_day'], str(license_info.get('max_actions_per_day')))
    if license_info.get('max_devices'):
        table.add_row(current_translations['max_devices'], str(license_info.get('max_devices')))
    
    features = []
    if license_info.get('has_ai_optimization'):
        features.append(current_translations['ai_optimization'])
    if license_info.get('has_intelligent_targeting'):
        features.append(current_translations['intelligent_targeting'])
    if license_info.get('has_advanced_reports'):
        features.append(current_translations['advanced_reports'])
    
    if features:
        table.add_row(current_translations['features'], ", ".join(features))
    
    if license_info.get('last_used_at'):
        last_used_at = license_info.get('last_used_at')
        if isinstance(last_used_at, str):
            if 'T' in last_used_at:
                try:
                    dt = datetime.fromisoformat(last_used_at.replace('Z', '+00:00'))
                    last_used_str = dt.strftime("%d/%m/%Y %H:%M")
                except:
                    last_used_str = last_used_at.split('T')[0]  # Juste la date
            else:
                last_used_str = last_used_at
        else:
            last_used_str = last_used_at.strftime("%d/%m/%Y %H:%M")
        table.add_row(current_translations['last_used'], last_used_str)
    
    console.print(table)

def display_usage_info(limits_check: dict):
    usage = limits_check.get('usage', {})
    limits = limits_check.get('limits', {})
    
    console.print(f"\n[bold cyan]{current_translations['daily_usage']}[/bold cyan]")
    
    actions_used = usage.get('actions_used_today', 0)
    max_actions = limits.get('max_actions_per_day', 0)
    if max_actions > 0:
        actions_percent = (actions_used / max_actions) * 100
        console.print(f"  • [cyan]{current_translations['actions']} :[/cyan] {actions_used}/{max_actions} ({actions_percent:.1f}%)")
    else:
        console.print(f"  • [cyan]{current_translations['actions']} :[/cyan] {actions_used}/∞")
    

def check_license_on_startup() -> Tuple[bool, str]:
    max_attempts = 3
    attempts = 0
    
    while attempts < max_attempts:
        success, api_key = prompt_for_license()
        if success:
            return True, api_key
        
        attempts += 1
        if attempts < max_attempts:
            console.print(f"\n[yellow]{current_translations['attempt_failed'].format(attempts, max_attempts)}[/yellow]")
            retry = Prompt.ask(
                f"[cyan]{current_translations['retry_question']}[/cyan]",
                choices=["y", "n"],
                default="y"
            )
            if retry.lower() != 'y':
                break
        else:
            console.print(f"\n[red]{current_translations['max_attempts_reached'].format(max_attempts)}[/red]")
    
    console.print(f"\n[red]{current_translations['cannot_verify_license']}[/red]")
    console.print(f"[yellow]{current_translations['get_license_info']}[/yellow]")
    
    return False, None
