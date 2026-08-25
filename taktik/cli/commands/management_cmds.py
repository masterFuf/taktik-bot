import click
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from taktik.core.shared.device.manager import DeviceManager
from taktik.core.social_media.instagram.core.manager import InstagramManager
from taktik.core.clone import rid

console = Console()


@click.group("management")
def management():
    """🔧 Gestion manuelle Instagram (auth, content, DM)."""
    pass

@management.group("auth")
def auth():
    """Authentication and account management."""
    pass

@auth.command("login")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--username', '-u', help="Nom d'utilisateur, email ou numéro de téléphone")
@click.option('--password', '-p', help="Mot de passe (sera demandé de manière sécurisée si non fourni)")
@click.option('--save-session/--no-save-session', default=True, help="Sauvegarder la session après connexion (système Taktik)")
@click.option('--save-instagram-login/--no-save-instagram-login', default=False, help="Sauvegarder les infos de login dans Instagram")
def login_instagram(device_id, username, password, save_session, save_instagram_login):
    """Log in to an Instagram account."""
    from taktik.core.social_media.instagram.workflows.management.login.login_workflow import LoginWorkflow
    import uiautomator2 as u2
    from getpass import getpass
    
    console.print(Panel.fit("[bold green]🔐 Connexion à Instagram[/bold green]"))
    
    # Pick the device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            console.print("[blue]💡 Assurez-vous que l'appareil est connecté et que ADB est configuré.[/blue]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    # Ask for the username when not provided
    if not username:
        username = Prompt.ask("[cyan]👤 Nom d'utilisateur, email ou numéro de téléphone[/cyan]")
    
    # Ask for the password securely when not provided
    if not password:
        password = getpass("🔑 Mot de passe: ")
    
    if not username or not password:
        console.print("[red]❌ Username et password requis.[/red]")
        return
    
    try:
        # Connect to the device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Check Instagram is installed
        instagram_manager = InstagramManager(device_id)
        if not instagram_manager.is_installed():
            console.print("[red]❌ Instagram n'est pas installé sur cet appareil.[/red]")
            return
        
        # Launch Instagram when not already running
        console.print("[blue]📱 Lancement d'Instagram...[/blue]")
        instagram_manager.launch()
        time.sleep(3)  # Wait for the app to start
        
        # Build the login workflow
        login_workflow = LoginWorkflow(device, device_id)
        
        # Show the information
        console.print(f"\n[cyan]👤 Username:[/cyan] {username}")
        console.print(f"[cyan]💾 Save session (Taktik):[/cyan] {'Yes' if save_session else 'No'}")
        console.print(f"[cyan]💾 Save login info (Instagram):[/cyan] {'Yes' if save_instagram_login else 'No'}\n")
        
        # Run the login
        with console.status("[bold yellow]🔄 Connexion en cours...[/bold yellow]", spinner="dots"):
            result = login_workflow.execute(
                username=username,
                password=password,
                max_retries=3,
                save_session=save_session,
                use_saved_session=True,
                save_login_info_instagram=save_instagram_login
            )
        
        # Show the result
        console.print()
        if result['success']:
            console.print(Panel.fit(
                f"[bold green]✅ Connexion réussie ![/bold green]\n\n"
                f"[cyan]👤 Username:[/cyan] {result['username']}\n"
                f"[cyan]🔄 Tentatives:[/cyan] {result['attempts']}\n"
                f"[cyan]💾 Session sauvegardée:[/cyan] {'Oui' if result['session_saved'] else 'Non'}",
                title="[bold green]Succès[/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel.fit(
                f"[bold red]❌ Échec de la connexion[/bold red]\n\n"
                f"[cyan]👤 Username:[/cyan] {result['username']}\n"
                f"[cyan]🔄 Tentatives:[/cyan] {result['attempts']}\n"
                f"[cyan]❌ Erreur:[/cyan] {result['message']}\n"
                f"[cyan]🏷️ Type d'erreur:[/cyan] {result['error_type'] or 'unknown'}",
                title="[bold red]Échec[/bold red]",
                border_style="red"
            ))
            
            # Hints depending on the error type
            if result['error_type'] == 'credentials_error':
                console.print("\n[yellow]💡 Vérifiez vos identifiants et réessayez.[/yellow]")
            elif result['error_type'] == '2fa_required':
                console.print("\n[yellow]💡 2FA requis - Cette fonctionnalité sera bientôt disponible.[/yellow]")
            elif result['error_type'] == 'suspicious_login':
                console.print("\n[yellow]💡 Instagram a détecté une connexion inhabituelle.[/yellow]")
                console.print("[yellow]   Essayez de vous connecter manuellement d'abord.[/yellow]")
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur inattendue: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

# ==================== DM GROUP ====================

@management.group("dm")
def dm():
    """Instagram direct message management."""
    pass

@dm.command("inbox")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--limit', '-l', default=20, help="Nombre maximum de conversations à récupérer")
@click.option('--unread-only', '-u', is_flag=True, help="Afficher uniquement les messages non lus")
def dm_inbox(device_id, limit, unread_only):
    """List the received DM conversations."""
    from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]💬 Récupération des DM Instagram[/bold green]"))
    
    # Pick the device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            console.print("[blue]💡 Assurez-vous que l'appareil est connecté et que ADB est configuré.[/blue]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connect to the device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Check Instagram is running
        instagram_manager = InstagramManager(device_id)
        if not instagram_manager.is_running():
            console.print("[yellow]📱 Lancement d'Instagram...[/yellow]")
            instagram_manager.launch()
            time.sleep(3)
        
        console.print("[yellow]📥 Navigation vers la boîte de réception DM...[/yellow]")
        
        # Way 1: tap the DM tab in the tab bar
        dm_tab = device.xpath(DM_SELECTORS.direct_tab)
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            console.print("[green]✅ Navigué vers les DM via direct_tab[/green]")
        else:
            # Méthode 2: Essayer via content-desc
            found = False
            for selector in DM_SELECTORS.direct_tab_content_desc:
                dm_btn = device.xpath(selector)
                if dm_btn.exists:
                    dm_btn.click()
                    time.sleep(2)
                    console.print("[green]✅ Navigué vers les DM via content-desc[/green]")
                    found = True
                    break
            
            if not found:
                console.print("[red]❌ Impossible de trouver l'onglet DM. Assurez-vous d'être sur le feed ou le profil.[/red]")
                return
        
        time.sleep(2)  # Wait for the load
        
        # Read the conversations, scrolling
        console.print("[yellow]🔍 Récupération des conversations...[/yellow]")
        
        conversations = []
        seen_usernames = set()  # To avoid duplicates
        max_scrolls = 10  # Nombre maximum de scrolls
        scroll_count = 0
        no_new_count = 0  # Scrolls with no new conversation
        
        # Screen size, for the scroll
        screen_info = device.info
        screen_width = screen_info['displayWidth']
        screen_height = screen_info['displayHeight']
        
        # Scroll area, avoiding the notes at the top and the tab bar at the bottom
        scroll_start_y = int(screen_height * 0.7)
        scroll_end_y = int(screen_height * 0.3)
        scroll_x = screen_width // 2
        
        while len(conversations) < limit and scroll_count < max_scrolls:
            threads = device.xpath(DM_SELECTORS.thread_container).all()
            
            if not threads and scroll_count == 0:
                console.print("[yellow]⚠️ Aucune conversation trouvée ou liste non chargée.[/yellow]")
                console.print("[dim]Essayez de scroller manuellement pour charger les conversations.[/dim]")
                return
            
            new_conversations_this_scroll = 0
            
            for thread in threads:
                if len(conversations) >= limit:
                    break
                    
                try:
                    thread_info = thread.info
                    content_desc = thread_info.get('contentDescription', '')
                    
                    # Extract the information from the content-desc
                    username = "Unknown"
                    is_unread = False
                    preview = ""
                    timestamp = ""
                    
                    if content_desc:
                        parts = [p.strip() for p in content_desc.split(',')]
                        if parts:
                            username = parts[0]
                            is_unread = any('non lu' in p.lower() or 'unread' in p.lower() for p in parts)
                            if len(parts) >= 3:
                                preview = parts[-2] if len(parts) >= 2 else ""
                                timestamp = parts[-1] if parts else ""
                    
                    # Try to extract the username through its specific resource-id
                    try:
                        username_elem = thread.child(resourceId=rid("com.instagram.android:id/row_inbox_username"))
                        if username_elem.exists:
                            username = username_elem.get_text() or username
                    except Exception:
                        pass
                    
                    # Avoid duplicates
                    if username in seen_usernames:
                        continue
                    seen_usernames.add(username)
                    
                    # Try to extract the preview
                    try:
                        digest_elem = thread.child(resourceId=rid("com.instagram.android:id/row_inbox_digest"))
                        if digest_elem.exists:
                            preview = digest_elem.get_text() or preview
                    except Exception:
                        pass
                    
                    # Try to extract the timestamp
                    try:
                        time_elem = thread.child(resourceId=rid("com.instagram.android:id/row_inbox_timestamp"))
                        if time_elem.exists:
                            timestamp = time_elem.get_text() or timestamp
                    except Exception:
                        pass
                    
                    # Filtrer si unread-only
                    if unread_only and not is_unread:
                        continue
                    
                    conversations.append({
                        'username': username,
                        'is_unread': is_unread,
                        'preview': preview[:50] + '...' if len(preview) > 50 else preview,
                        'timestamp': timestamp
                    })
                    new_conversations_this_scroll += 1
                    
                except Exception as e:
                    continue
            
            # Vérifier si on a atteint la limite
            if len(conversations) >= limit:
                break
            
            # Vérifier si on a trouvé de nouvelles conversations
            if new_conversations_this_scroll == 0:
                no_new_count += 1
                if no_new_count >= 2:  # Two scrolls with no new conversation means the end of the list
                    console.print(f"[dim]Fin de la liste atteinte après {scroll_count + 1} scrolls[/dim]")
                    break
            else:
                no_new_count = 0
            
            # Scroll down
            scroll_count += 1
            console.print(f"[dim]Scroll {scroll_count}/{max_scrolls} - {len(conversations)} conversations trouvées...[/dim]")
            device.swipe(scroll_x, scroll_start_y, scroll_x, scroll_end_y, duration=0.3)
            time.sleep(1.5)  # Wait for the load
        
        # Show the results
        if not conversations:
            console.print("[yellow]⚠️ Aucune conversation trouvée avec les critères spécifiés.[/yellow]")
            return
        
        console.print(f"\n[bold green]📬 {len(conversations)} conversation(s) trouvée(s)[/bold green]\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("👤 Username", style="cyan")
        table.add_column("📩", style="yellow", width=3)
        table.add_column("💬 Aperçu", style="white")
        table.add_column("🕐 Date", style="dim")
        
        for i, conv in enumerate(conversations, 1):
            unread_icon = "🔵" if conv['is_unread'] else "⚪"
            table.add_row(
                str(i),
                conv['username'],
                unread_icon,
                conv['preview'],
                conv['timestamp']
            )
        
        console.print(table)
        
        # Statistiques
        unread_count = sum(1 for c in conversations if c['is_unread'])
        console.print(f"\n[cyan]📊 Statistiques:[/cyan]")
        console.print(f"   • Total: {len(conversations)}")
        console.print(f"   • Non lus: {unread_count}")
        console.print(f"   • Lus: {len(conversations) - unread_count}")
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

@dm.command("read-all")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--limit', '-l', default=10, help="Nombre maximum de conversations à lire")
@click.option('--messages-per-conv', '-m', default=20, help="Nombre de messages par conversation")
def dm_read_all(device_id, limit, messages_per_conv):
    """Read the messages of several DM conversations (tap, read, back)."""
    from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS
    import uiautomator2 as u2
    
    console.print(Panel.fit(f"[bold green]📖 Lecture de {limit} conversations DM[/bold green]"))
    
    # Pick the device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connect to the device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Restart Instagram to be sure of the starting screen
        instagram_manager = InstagramManager(device_id)
        console.print("[yellow]🔄 Redémarrage d'Instagram...[/yellow]")
        instagram_manager.stop()
        time.sleep(1)
        instagram_manager.launch()
        time.sleep(4)  # Wait for the full load
        console.print("[green]✅ Instagram redémarré[/green]")
        
        # Navigate to the DM screen
        console.print("[yellow]📥 Navigation vers la boîte de réception DM...[/yellow]")
        
        dm_tab = device.xpath(DM_SELECTORS.direct_tab)
        if dm_tab.exists:
            dm_tab.click()
            time.sleep(2)
            console.print("[green]✅ Navigué vers les DM[/green]")
        else:
            for selector in DM_SELECTORS.direct_tab_content_desc:
                dm_btn = device.xpath(selector)
                if dm_btn.exists:
                    dm_btn.click()
                    time.sleep(2)
                    console.print("[green]✅ Navigué vers les DM[/green]")
                    break
        
        time.sleep(2)
        
        # Screen size
        screen_info = device.info
        screen_width = screen_info['displayWidth']
        screen_height = screen_info['displayHeight']
        
        all_conversations = []
        processed_usernames = set()
        conversations_read = 0
        scroll_count = 0
        max_scrolls = 10
        
        while conversations_read < limit and scroll_count < max_scrolls:
            # Read the visible threads
            threads = device.xpath(DM_SELECTORS.thread_container).all()
            
            if not threads:
                console.print("[yellow]⚠️ Aucune conversation visible.[/yellow]")
                break
            
            for thread in threads:
                if conversations_read >= limit:
                    break
                
                try:
                    # Extract the username
                    thread_info = thread.info
                    content_desc = thread_info.get('contentDescription', '')
                    
                    username = "Unknown"
                    if content_desc:
                        parts = content_desc.split(',')
                        if parts:
                            username = parts[0].strip()
                    
                    # Essayer via resource-id
                    try:
                        username_elem = device(resourceId=rid("com.instagram.android:id/row_inbox_username"))
                        if username_elem.exists:
                            for i in range(username_elem.count):
                                elem = username_elem[i]
                                bounds = elem.info.get('bounds', {})
                                thread_bounds = thread_info.get('bounds', {})
                                # Is the element in the same thread?
                                if bounds and thread_bounds:
                                    if (bounds.get('top', 0) >= thread_bounds.get('top', 0) and 
                                        bounds.get('bottom', 0) <= thread_bounds.get('bottom', 0)):
                                        username = elem.get_text() or username
                                        break
                    except Exception:
                        pass
                    
                    # Avoid duplicates
                    if username in processed_usernames:
                        continue
                    processed_usernames.add(username)
                    
                    console.print(f"\n[cyan]📬 [{conversations_read + 1}/{limit}] Ouverture de: {username}[/cyan]")
                    
                    # Tap the conversation
                    thread.click()
                    time.sleep(2)
                    
                    # Confirm we are inside the conversation (its header title is present)
                    header_title = device(resourceId=rid("com.instagram.android:id/header_title"))
                    if not header_title.exists(timeout=3):
                        console.print(f"[yellow]⚠️ Impossible d'ouvrir la conversation avec {username}[/yellow]")
                        # Essayer de revenir en arrière
                        device.press("back")
                        time.sleep(1)
                        continue
                    
                    # Read the real username from the header
                    real_username = header_title.get_text() or username
                    
                    # Detect a group conversation from its subtitle
                    is_group = False
                    can_reply = True
                    header_subtitle = device(resourceId=rid("com.instagram.android:id/header_subtitle"))
                    if header_subtitle.exists:
                        try:
                            subtitle_desc = header_subtitle.info.get('contentDescription', '')
                            if 'membres' in subtitle_desc.lower() or 'members' in subtitle_desc.lower():
                                is_group = True
                                console.print(f"[yellow]      ⚠️ C'est un groupe ({subtitle_desc})[/yellow]")
                                
                                # Vérifier si on peut écrire (champ de saisie présent)
                                composer = device(resourceId=rid("com.instagram.android:id/row_thread_composer_edittext"))
                                if not composer.exists:
                                    can_reply = False
                                    console.print(f"[yellow]      ⚠️ Impossible d'écrire dans ce groupe[/yellow]")
                        except Exception:
                            pass
                    
                    # Read the LAST messages of the sender, at the bottom of the screen.
                    # No upward scrolling: only the recent messages are wanted
                    last_messages = []
                    
                    # Collect every visible element with its vertical position
                    all_items = []
                    
                    # 1. Text messages
                    msg_elements = device(resourceId=rid("com.instagram.android:id/direct_text_message_text_view"))
                    for i in range(msg_elements.count):
                        try:
                            msg_elem = msg_elements[i]
                            msg_bounds = msg_elem.info.get('bounds', {})
                            text = msg_elem.get_text()
                            if not text:
                                continue
                            
                            msg_left = msg_bounds.get('left', 0)
                            msg_top = msg_bounds.get('top', 0)
                            is_received = msg_left < screen_width * 0.5
                            
                            all_items.append({
                                'type': 'text',
                                'text': text,
                                'is_sent': not is_received,
                                'top': msg_top
                            })
                        except Exception:
                            continue
                    
                    # 2. Reels/médias partagés
                    reel_shares = device(resourceId=rid("com.instagram.android:id/reel_share_item_view"))
                    for i in range(reel_shares.count):
                        try:
                            reel = reel_shares[i]
                            reel_bounds = reel.info.get('bounds', {})
                            reel_left = reel_bounds.get('left', 0)
                            reel_top = reel_bounds.get('top', 0)
                            is_received = reel_left < screen_width * 0.5
                            
                            # Look for the title (the reel author)
                            title_elem = device(resourceId=rid("com.instagram.android:id/title_text"))
                            reel_author = ""
                            for j in range(title_elem.count):
                                try:
                                    t = title_elem[j]
                                    t_bounds = t.info.get('bounds', {})
                                    if (t_bounds.get('top', 0) >= reel_bounds.get('top', 0) and
                                        t_bounds.get('bottom', 0) <= reel_bounds.get('bottom', 0)):
                                        reel_author = t.get_text() or ""
                                        break
                                except Exception:
                                    continue
                            
                            all_items.append({
                                'type': 'reel',
                                'text': f"[Reel de @{reel_author}]" if reel_author else "[Reel partagé]",
                                'is_sent': not is_received,
                                'top': reel_top
                            })
                        except Exception:
                            continue
                    
                    # Sort by vertical position: top to bottom is chronological order
                    all_items.sort(key=lambda x: x['top'])
                    
                    # DEBUG: show every detected element
                    console.print(f"[dim]      DEBUG: Éléments triés par position:[/dim]")
                    for item in all_items:
                        direction = "ENVOYÉ" if item['is_sent'] else "REÇU"
                        console.print(f"[dim]        {direction} ({item['top']}): {item['type']} - {item['text'][:30]}...[/dim]")
                    
                    # Read EVERY received message, not only the last consecutive ones,
                    # since the contact may have written several separated by our replies
                    received_messages = [item for item in all_items if not item['is_sent']]
                    
                    # Deduplicate by text
                    seen_texts = set()
                    for msg in received_messages:
                        if msg['text'] not in seen_texts:
                            seen_texts.add(msg['text'])
                            last_messages.append(msg)
                    
                    console.print(f"[dim]      DEBUG: {len(all_items)} éléments, {len(last_messages)} derniers messages reçus[/dim]")
                    for msg in last_messages:
                        console.print(f"[dim]      → {msg['type']}: {msg['text'][:40]}...[/dim]")
                    
                    # Store the conversation
                    all_conversations.append({
                        'username': real_username,
                        'messages': last_messages,
                        'is_group': is_group,
                        'can_reply': can_reply
                    })
                    
                    console.print(f"[green]   ✅ {len(last_messages)} dernier(s) message(s) reçu(s)[/green]")
                    
                    # Revenir en arrière
                    back_btn = device(resourceId=rid("com.instagram.android:id/header_left_button"))
                    if back_btn.exists:
                        back_btn.click()
                    else:
                        device.press("back")
                    time.sleep(1.5)
                    
                    conversations_read += 1
                    
                except Exception as e:
                    console.print(f"[red]   ❌ Erreur: {e}[/red]")
                    # Essayer de revenir en arrière
                    device.press("back")
                    time.sleep(1)
                    continue
            
            # Vérifier si on a atteint la limite
            if conversations_read >= limit:
                break
            
            # Scroll to reveal more conversations
            scroll_count += 1
            console.print(f"[dim]Scroll {scroll_count}/{max_scrolls}...[/dim]")
            device.swipe(screen_width // 2, int(screen_height * 0.7), 
                        screen_width // 2, int(screen_height * 0.3), duration=0.3)
            time.sleep(1.5)
        
        # Show the summary
        console.print(f"\n[bold green]{'='*60}[/bold green]")
        console.print(f"[bold green]📊 RÉSUMÉ: {len(all_conversations)} conversation(s) lue(s)[/bold green]")
        console.print(f"[bold green]{'='*60}[/bold green]\n")
        
        for conv in all_conversations:
            # Show the conversation type
            conv_type = ""
            if conv.get('is_group'):
                conv_type = " [yellow](Groupe)[/yellow]"
                if not conv.get('can_reply'):
                    conv_type += " [red](Lecture seule)[/red]"
            
            console.print(f"\n[bold cyan]💬 Conversation avec: {conv['username']}{conv_type}[/bold cyan]")
            console.print(f"[dim]{'─'*40}[/dim]")
            
            for msg in conv['messages']:
                msg_type = msg.get('type', 'text')
                
                # Icon per type
                if msg_type == 'reel':
                    icon = "🎬"
                elif msg_type == 'media':
                    icon = "📷"
                elif msg_type == 'reaction':
                    icon = "💬"
                else:
                    icon = ""
                
                if msg['is_sent']:
                    console.print(f"[blue]  → Vous: {icon} {msg['text']}[/blue]")
                else:
                    console.print(f"[green]  ← {conv['username']}: {icon} {msg['text']}[/green]")
            
            if not conv['messages']:
                console.print("[dim]  (Aucun message trouvé)[/dim]")
        
        # Statistiques globales
        total_messages = sum(len(c['messages']) for c in all_conversations)
        text_count = sum(1 for c in all_conversations for m in c['messages'] if m.get('type') == 'text')
        media_count = sum(1 for c in all_conversations for m in c['messages'] if m.get('type') in ['reel', 'media'])
        group_count = sum(1 for c in all_conversations if c.get('is_group'))
        readonly_count = sum(1 for c in all_conversations if not c.get('can_reply', True))
        replyable_count = sum(1 for c in all_conversations if c.get('can_reply', True) and len(c['messages']) > 0)
        
        console.print(f"\n[cyan]📊 Statistiques globales:[/cyan]")
        console.print(f"   • Conversations: {len(all_conversations)}")
        console.print(f"   • Groupes: {group_count}")
        console.print(f"   • Lecture seule: {readonly_count}")
        console.print(f"   • Avec réponse possible: {replyable_count}")
        console.print(f"   • Messages totaux: {total_messages}")
        console.print(f"   • Textes: {text_count}")
        console.print(f"   • Médias (reels/stories): {media_count}")
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

@dm.command("send")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--to', '-t', required=True, help="Username du destinataire")
@click.option('--message', '-m', required=True, help="Message à envoyer")
def dm_send(device_id, to, message):
    """📤 Envoyer un DM à un utilisateur."""
    from taktik.core.social_media.instagram.workflows.management import DMOutreachWorkflow, DMOutreachConfig
    from taktik.core.shared.device.manager import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📤 Envoi d'un DM Instagram[/bold green]"))
    
    # Pick the device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connect to the device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Set up the components
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Build the configuration
        config = DMOutreachConfig(
            recipients=[to],
            message_template=message,
            delay_min=3,
            delay_max=5,
            follow_before_dm=False
        )
        
        # Build the workflow
        workflow = DMOutreachWorkflow(device_mgr, nav_actions, detection_actions)
        
        console.print(f"\n[cyan]👤 Destinataire:[/cyan] @{to}")
        console.print(f"[cyan]💬 Message:[/cyan] {message[:50]}{'...' if len(message) > 50 else ''}")
        
        console.print("\n[yellow]⏳ Envoi en cours...[/yellow]")
        
        # Run it. The workflow exposes `run()`, not `execute()`, and returns a summary dict
        # rather than a list of objects. The code used to call `execute()` and read an
        # il levait un AttributeError avant même d'atteindre l'affichage.
        outcome = workflow.run(config)

        sent = (outcome or {}).get('results') or []
        first = sent[0] if sent else {}

        if outcome and outcome.get('success') and first.get('success'):
            console.print(Panel(
                f"[green]✅ Message envoyé avec succès ![/green]\n"
                f"[cyan]Destinataire:[/cyan] @{to}",
                title="[bold green]Succès[/bold green]",
                border_style="green"
            ))
        else:
            error = first.get('error') or (outcome or {}).get('error') or "Erreur inconnue"
            console.print(Panel(
                f"[red]❌ Échec de l'envoi[/red]\n"
                f"[cyan]Erreur:[/cyan] {error}",
                title="[bold red]Échec[/bold red]",
                border_style="red"
            ))
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

@management.group("content")
def content():
    """Instagram content management (posts, stories, carousels)."""
    pass

@content.command("post")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--image', '-i', required=True, type=click.Path(exists=True), help="Chemin vers l'image à poster")
@click.option('--caption', '-c', help="Légende du post")
@click.option('--location', '-l', help="Localisation du post")
@click.option('--hashtags', '-h', help="Hashtags séparés par des espaces (ex: 'travel nature sunset')")
def post_single(device_id, image, caption, location, hashtags):
    """Post a single photo."""
    from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
    from taktik.core.shared.device.manager import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📸 Publication d'un post Instagram[/bold green]"))
    
    # Pick the device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connect to the device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Set up the components
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Build the workflow
        workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
        
        # Show the information
        console.print(f"\n[cyan]📷 Image:[/cyan] {image}")
        if caption:
            console.print(f"[cyan]✍️  Caption:[/cyan] {caption[:50]}{'...' if len(caption) > 50 else ''}")
        if location:
            console.print(f"[cyan]📍 Location:[/cyan] {location}")
        
        hashtag_list = None
        if hashtags:
            hashtag_list = [tag.strip() for tag in hashtags.split()]
            console.print(f"[cyan]#️⃣ Hashtags:[/cyan] {', '.join(hashtag_list)}")
        
        console.print("\n[yellow]⏳ Publication en cours...[/yellow]")
        
        result = workflow.post_single_photo(image, caption, location, hashtag_list)
        
        # Show the result
        if result['success']:
            console.print(Panel(
                f"[green]✅ Post publié avec succès ![/green]\n"
                f"[cyan]Image:[/cyan] {result['image_path']}",
                title="[bold green]Succès[/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[red]❌ Échec de la publication[/red]\n"
                f"[cyan]Erreur:[/cyan] {result['message']}",
                title="[bold red]Échec[/bold red]",
                border_style="red"
            ))
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

@content.command("post-bulk")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--images', '-i', required=True, multiple=True, type=click.Path(exists=True), help="Chemins vers les images à poster (peut être répété)")
@click.option('--captions', '-c', multiple=True, help="Légendes des posts (même ordre que les images)")
@click.option('--delay', default=60, help="Délai entre chaque post en secondes (défaut: 60)")
def post_bulk(device_id, images, captions, delay):
    """Poster plusieurs photos successivement."""
    from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
    from taktik.core.shared.device.manager import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📸 Publication multiple de posts Instagram[/bold green]"))
    
    if not images:
        console.print("[red]❌ Aucune image fournie.[/red]")
        return
    
    # Pick the device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connect to the device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Set up the components
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Build the workflow
        workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
        
        # Show the information
        console.print(f"\n[cyan]📷 Nombre d'images:[/cyan] {len(images)}")
        console.print(f"[cyan]⏱️  Délai entre posts:[/cyan] {delay}s")
        
        # Turn the captions into a list
        captions_list = list(captions) if captions else None
        
        console.print("\n[yellow]⏳ Publication en cours...[/yellow]")
        
        # Poster
        results = workflow.post_multiple_photos(list(images), captions_list, delay)
        
        # Show the result
        console.print(Panel(
            f"[cyan]Total:[/cyan] {results['total']}\n"
            f"[green]✅ Réussis:[/green] {results['success']}\n"
            f"[red]❌ Échoués:[/red] {results['failed']}",
            title="[bold blue]Résultats[/bold blue]",
            border_style="blue"
        ))
        
        # Show the detail
        if results['failed'] > 0:
            console.print("\n[yellow]Détails des échecs:[/yellow]")
            for post in results['posts']:
                if not post['success']:
                    console.print(f"  [red]❌ {post['image_path']}: {post['message']}[/red]")
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

@content.command("story")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--image', '-i', required=True, type=click.Path(exists=True), help="Chemin vers l'image de la story")
def post_story(device_id, image):
    """Post a story."""
    from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
    from taktik.core.shared.device.manager import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📱 Publication d'une story Instagram[/bold green]"))
    
    # Pick the device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connect to the device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Set up the components
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Build the workflow
        workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
        
        # Show the information
        console.print(f"\n[cyan]📷 Image:[/cyan] {image}")
        
        console.print("\n[yellow]⏳ Publication en cours...[/yellow]")
        
        # Poster
        result = workflow.post_story(image)
        
        # Show the result
        if result['success']:
            console.print(Panel(
                f"[green]✅ Story publiée avec succès ![/green]\n"
                f"[cyan]Image:[/cyan] {result['image_path']}",
                title="[bold green]Succès[/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[red]❌ Échec de la publication[/red]\n"
                f"[cyan]Erreur:[/cyan] {result['message']}",
                title="[bold red]Échec[/bold red]",
                border_style="red"
            ))
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
