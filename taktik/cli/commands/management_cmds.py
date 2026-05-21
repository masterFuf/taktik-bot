import click
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from taktik.core.social_media.instagram.actions.core.device import DeviceManager
from taktik.core.social_media.instagram.core.manager import InstagramManager
from taktik.core.clone import rid

console = Console()


@click.group("management")
def management():
    """🔧 Gestion manuelle Instagram (auth, content, DM)."""
    pass

@management.group("auth")
def auth():
    """🔐 Authentification et gestion de compte."""
    pass

@auth.command("login")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--username', '-u', help="Nom d'utilisateur, email ou numéro de téléphone")
@click.option('--password', '-p', help="Mot de passe (sera demandé de manière sécurisée si non fourni)")
@click.option('--save-session/--no-save-session', default=True, help="Sauvegarder la session après connexion (système Taktik)")
@click.option('--save-instagram-login/--no-save-instagram-login', default=False, help="Sauvegarder les infos de login dans Instagram")
def login_instagram(device_id, username, password, save_session, save_instagram_login):
    """Se connecter à un compte Instagram."""
    from taktik.core.social_media.instagram.workflows.management.login.login_workflow import LoginWorkflow
    import uiautomator2 as u2
    from getpass import getpass
    
    console.print(Panel.fit("[bold green]🔐 Connexion à Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            console.print("[blue]💡 Assurez-vous que l'appareil est connecté et que ADB est configuré.[/blue]")
            return
        device_id = devices[0]
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    # Demander le username si non fourni
    if not username:
        username = Prompt.ask("[cyan]👤 Nom d'utilisateur, email ou numéro de téléphone[/cyan]")
    
    # Demander le password de manière sécurisée si non fourni
    if not password:
        password = getpass("🔑 Mot de passe: ")
    
    if not username or not password:
        console.print("[red]❌ Username et password requis.[/red]")
        return
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Vérifier qu'Instagram est installé
        instagram_manager = InstagramManager(device_id)
        if not instagram_manager.is_installed():
            console.print("[red]❌ Instagram n'est pas installé sur cet appareil.[/red]")
            return
        
        # Lancer Instagram si pas déjà lancé
        console.print("[blue]📱 Lancement d'Instagram...[/blue]")
        instagram_manager.launch()
        time.sleep(3)  # Attendre que l'app se lance
        
        # Créer le workflow de login
        login_workflow = LoginWorkflow(device, device_id)
        
        # Afficher les informations
        console.print(f"\n[cyan]👤 Username:[/cyan] {username}")
        console.print(f"[cyan]💾 Save session (Taktik):[/cyan] {'Yes' if save_session else 'No'}")
        console.print(f"[cyan]💾 Save login info (Instagram):[/cyan] {'Yes' if save_instagram_login else 'No'}\n")
        
        # Exécuter le login
        with console.status("[bold yellow]🔄 Connexion en cours...[/bold yellow]", spinner="dots"):
            result = login_workflow.execute(
                username=username,
                password=password,
                max_retries=3,
                save_session=save_session,
                use_saved_session=True,
                save_login_info_instagram=save_instagram_login
            )
        
        # Afficher le résultat
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
            
            # Suggestions selon le type d'erreur
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
    """💬 Gestion des messages directs Instagram."""
    pass

@dm.command("inbox")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--limit', '-l', default=20, help="Nombre maximum de conversations à récupérer")
@click.option('--unread-only', '-u', is_flag=True, help="Afficher uniquement les messages non lus")
def dm_inbox(device_id, limit, unread_only):
    """📥 Lister les conversations DM reçues."""
    from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]💬 Récupération des DM Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            console.print("[blue]💡 Assurez-vous que l'appareil est connecté et que ADB est configuré.[/blue]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Vérifier qu'Instagram est lancé
        instagram_manager = InstagramManager(device_id)
        if not instagram_manager.is_running():
            console.print("[yellow]📱 Lancement d'Instagram...[/yellow]")
            instagram_manager.launch()
            time.sleep(3)
        
        console.print("[yellow]📥 Navigation vers la boîte de réception DM...[/yellow]")
        
        # Méthode 1: Cliquer sur l'onglet DM dans la tab bar
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
        
        time.sleep(2)  # Attendre le chargement
        
        # Récupérer les conversations avec scroll
        console.print("[yellow]🔍 Récupération des conversations...[/yellow]")
        
        conversations = []
        seen_usernames = set()  # Pour éviter les doublons
        max_scrolls = 10  # Nombre maximum de scrolls
        scroll_count = 0
        no_new_count = 0  # Compteur de scrolls sans nouvelles conversations
        
        # Obtenir les dimensions de l'écran pour le scroll
        screen_info = device.info
        screen_width = screen_info['displayWidth']
        screen_height = screen_info['displayHeight']
        
        # Zone de scroll (éviter les notes en haut et la tab bar en bas)
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
                    
                    # Extraire les infos depuis content-desc
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
                    
                    # Essayer d'extraire le username via le resource-id spécifique
                    try:
                        username_elem = thread.child(resourceId=rid("com.instagram.android:id/row_inbox_username"))
                        if username_elem.exists:
                            username = username_elem.get_text() or username
                    except Exception:
                        pass
                    
                    # Éviter les doublons
                    if username in seen_usernames:
                        continue
                    seen_usernames.add(username)
                    
                    # Essayer d'extraire le digest (preview)
                    try:
                        digest_elem = thread.child(resourceId=rid("com.instagram.android:id/row_inbox_digest"))
                        if digest_elem.exists:
                            preview = digest_elem.get_text() or preview
                    except Exception:
                        pass
                    
                    # Essayer d'extraire le timestamp
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
                if no_new_count >= 2:  # 2 scrolls sans nouvelles conversations = fin de liste
                    console.print(f"[dim]Fin de la liste atteinte après {scroll_count + 1} scrolls[/dim]")
                    break
            else:
                no_new_count = 0
            
            # Scroll vers le bas
            scroll_count += 1
            console.print(f"[dim]Scroll {scroll_count}/{max_scrolls} - {len(conversations)} conversations trouvées...[/dim]")
            device.swipe(scroll_x, scroll_start_y, scroll_x, scroll_end_y, duration=0.3)
            time.sleep(1.5)  # Attendre le chargement
        
        # Afficher les résultats
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
    """📖 Lire les messages de plusieurs conversations DM (click → read → back)."""
    from taktik.core.social_media.instagram.ui.selectors import DM_SELECTORS
    import uiautomator2 as u2
    
    console.print(Panel.fit(f"[bold green]📖 Lecture de {limit} conversations DM[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Redémarrer Instagram pour être sûr d'être sur la bonne page
        instagram_manager = InstagramManager(device_id)
        console.print("[yellow]🔄 Redémarrage d'Instagram...[/yellow]")
        instagram_manager.stop()
        time.sleep(1)
        instagram_manager.launch()
        time.sleep(4)  # Attendre le chargement complet
        console.print("[green]✅ Instagram redémarré[/green]")
        
        # Naviguer vers les DM
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
        
        # Obtenir les dimensions de l'écran
        screen_info = device.info
        screen_width = screen_info['displayWidth']
        screen_height = screen_info['displayHeight']
        
        all_conversations = []
        processed_usernames = set()
        conversations_read = 0
        scroll_count = 0
        max_scrolls = 10
        
        while conversations_read < limit and scroll_count < max_scrolls:
            # Récupérer les threads visibles
            threads = device.xpath(DM_SELECTORS.thread_container).all()
            
            if not threads:
                console.print("[yellow]⚠️ Aucune conversation visible.[/yellow]")
                break
            
            for thread in threads:
                if conversations_read >= limit:
                    break
                
                try:
                    # Extraire le username
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
                                # Vérifier si l'élément est dans le même thread
                                if bounds and thread_bounds:
                                    if (bounds.get('top', 0) >= thread_bounds.get('top', 0) and 
                                        bounds.get('bottom', 0) <= thread_bounds.get('bottom', 0)):
                                        username = elem.get_text() or username
                                        break
                    except Exception:
                        pass
                    
                    # Éviter les doublons
                    if username in processed_usernames:
                        continue
                    processed_usernames.add(username)
                    
                    console.print(f"\n[cyan]📬 [{conversations_read + 1}/{limit}] Ouverture de: {username}[/cyan]")
                    
                    # Cliquer sur la conversation
                    thread.click()
                    time.sleep(2)
                    
                    # Vérifier qu'on est dans la conversation (header_title présent)
                    header_title = device(resourceId=rid("com.instagram.android:id/header_title"))
                    if not header_title.exists(timeout=3):
                        console.print(f"[yellow]⚠️ Impossible d'ouvrir la conversation avec {username}[/yellow]")
                        # Essayer de revenir en arrière
                        device.press("back")
                        time.sleep(1)
                        continue
                    
                    # Récupérer le vrai username depuis le header
                    real_username = header_title.get_text() or username
                    
                    # Détecter si c'est un groupe (subtitle contient "membres" ou "members")
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
                    
                    # Récupérer les DERNIERS messages de l'expéditeur (en bas de l'écran)
                    # On ne scrolle pas vers le haut, on veut juste les messages récents
                    last_messages = []
                    
                    # Collecter tous les éléments visibles avec leur position Y
                    all_items = []
                    
                    # 1. Messages texte
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
                            
                            # Chercher le titre (auteur du reel)
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
                    
                    # Trier par position Y (du haut vers le bas = ordre chronologique)
                    all_items.sort(key=lambda x: x['top'])
                    
                    # DEBUG: Afficher tous les éléments détectés
                    console.print(f"[dim]      DEBUG: Éléments triés par position:[/dim]")
                    for item in all_items:
                        direction = "ENVOYÉ" if item['is_sent'] else "REÇU"
                        console.print(f"[dim]        {direction} ({item['top']}): {item['type']} - {item['text'][:30]}...[/dim]")
                    
                    # Récupérer TOUS les messages reçus (pas seulement les derniers consécutifs)
                    # Car l'utilisateur peut avoir envoyé plusieurs messages séparés par nos réponses
                    received_messages = [item for item in all_items if not item['is_sent']]
                    
                    # Dédupliquer par texte
                    seen_texts = set()
                    for msg in received_messages:
                        if msg['text'] not in seen_texts:
                            seen_texts.add(msg['text'])
                            last_messages.append(msg)
                    
                    console.print(f"[dim]      DEBUG: {len(all_items)} éléments, {len(last_messages)} derniers messages reçus[/dim]")
                    for msg in last_messages:
                        console.print(f"[dim]      → {msg['type']}: {msg['text'][:40]}...[/dim]")
                    
                    # Stocker la conversation
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
            
            # Scroll pour voir plus de conversations
            scroll_count += 1
            console.print(f"[dim]Scroll {scroll_count}/{max_scrolls}...[/dim]")
            device.swipe(screen_width // 2, int(screen_height * 0.7), 
                        screen_width // 2, int(screen_height * 0.3), duration=0.3)
            time.sleep(1.5)
        
        # Afficher le résumé
        console.print(f"\n[bold green]{'='*60}[/bold green]")
        console.print(f"[bold green]📊 RÉSUMÉ: {len(all_conversations)} conversation(s) lue(s)[/bold green]")
        console.print(f"[bold green]{'='*60}[/bold green]\n")
        
        for conv in all_conversations:
            # Afficher le type de conversation
            conv_type = ""
            if conv.get('is_group'):
                conv_type = " [yellow](Groupe)[/yellow]"
                if not conv.get('can_reply'):
                    conv_type += " [red](Lecture seule)[/red]"
            
            console.print(f"\n[bold cyan]💬 Conversation avec: {conv['username']}{conv_type}[/bold cyan]")
            console.print(f"[dim]{'─'*40}[/dim]")
            
            for msg in conv['messages']:
                msg_type = msg.get('type', 'text')
                
                # Icône selon le type
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
    from taktik.core.social_media.instagram.actions.core.device import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📤 Envoi d'un DM Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Initialiser les composants
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Créer la config
        config = DMOutreachConfig(
            recipients=[to],
            message_template=message,
            delay_between_dms=(3, 5),
            follow_before_dm=False
        )
        
        # Créer le workflow
        workflow = DMOutreachWorkflow(device_mgr, nav_actions, detection_actions)
        
        console.print(f"\n[cyan]👤 Destinataire:[/cyan] @{to}")
        console.print(f"[cyan]💬 Message:[/cyan] {message[:50]}{'...' if len(message) > 50 else ''}")
        
        console.print("\n[yellow]⏳ Envoi en cours...[/yellow]")
        
        # Exécuter
        results = workflow.execute(config)
        
        # Afficher le résultat
        if results and results[0].success:
            console.print(Panel(
                f"[green]✅ Message envoyé avec succès ![/green]\n"
                f"[cyan]Destinataire:[/cyan] @{to}",
                title="[bold green]Succès[/bold green]",
                border_style="green"
            ))
        else:
            error = results[0].error if results else "Erreur inconnue"
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
    """📸 Gestion du contenu Instagram (posts, stories, carousel)."""
    pass

@content.command("post")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--image', '-i', required=True, type=click.Path(exists=True), help="Chemin vers l'image à poster")
@click.option('--caption', '-c', help="Légende du post")
@click.option('--location', '-l', help="Localisation du post")
@click.option('--hashtags', '-h', help="Hashtags séparés par des espaces (ex: 'travel nature sunset')")
def post_single(device_id, image, caption, location, hashtags):
    """Poster une photo unique sur Instagram."""
    from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
    from taktik.core.social_media.instagram.actions.core.device import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📸 Publication d'un post Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Initialiser les composants
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Créer le workflow
        workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
        
        # Afficher les infos
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
        
        # Afficher le résultat
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
    from taktik.core.social_media.instagram.actions.core.device import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📸 Publication multiple de posts Instagram[/bold green]"))
    
    if not images:
        console.print("[red]❌ Aucune image fournie.[/red]")
        return
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Initialiser les composants
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Créer le workflow
        workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
        
        # Afficher les infos
        console.print(f"\n[cyan]📷 Nombre d'images:[/cyan] {len(images)}")
        console.print(f"[cyan]⏱️  Délai entre posts:[/cyan] {delay}s")
        
        # Convertir captions en liste
        captions_list = list(captions) if captions else None
        
        console.print("\n[yellow]⏳ Publication en cours...[/yellow]")
        
        # Poster
        results = workflow.post_multiple_photos(list(images), captions_list, delay)
        
        # Afficher le résultat
        console.print(Panel(
            f"[cyan]Total:[/cyan] {results['total']}\n"
            f"[green]✅ Réussis:[/green] {results['success']}\n"
            f"[red]❌ Échoués:[/red] {results['failed']}",
            title="[bold blue]Résultats[/bold blue]",
            border_style="blue"
        ))
        
        # Afficher le détail
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
    """Poster une story sur Instagram."""
    from taktik.core.social_media.instagram.workflows.management.content.content_workflow import ContentWorkflow
    from taktik.core.social_media.instagram.actions.core.device import DeviceManager
    from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
    import uiautomator2 as u2
    
    console.print(Panel.fit("[bold green]📱 Publication d'une story Instagram[/bold green]"))
    
    # Sélectionner le device
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    
    try:
        # Connexion au device
        console.print(f"[blue]📱 Connexion au device {device_id}...[/blue]")
        device = u2.connect(device_id)
        
        # Initialiser les composants
        device_mgr = DeviceManager()
        device_mgr.connect(device_id)
        
        nav_actions = NavigationActions(device)
        detection_actions = DetectionActions(device)
        
        # Créer le workflow
        workflow = ContentWorkflow(device_mgr, nav_actions, detection_actions)
        
        # Afficher les infos
        console.print(f"\n[cyan]📷 Image:[/cyan] {image}")
        
        console.print("\n[yellow]⏳ Publication en cours...[/yellow]")
        
        # Poster
        result = workflow.post_story(image)
        
        # Afficher le résultat
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

