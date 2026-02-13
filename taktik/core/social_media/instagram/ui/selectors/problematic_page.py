from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class ProblematicPageSelectors:
    """Sélecteurs pour la détection et fermeture des pages problématiques."""
    
    # === Boutons de fermeture X/Close ===
    close_button_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'resourceId': 'com.instagram.android:id/action_bar_button_back'},
        {'description': 'Close'},
        {'description': 'Dismiss'},
        {'description': 'Cancel'},
        {'description': 'Fermer'},
        {'description': 'Annuler'},
        {'text': '×'},
        {'text': '✕'},
        {'className': 'android.widget.ImageView', 'description': 'Back'}
    ])
    
    # === Boutons Terminé/Done ===
    terminate_button_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'text': 'Terminé'},
        {'text': 'Done'},
        {'text': 'Fermer'},
        {'text': 'Close'},
        {'description': 'Terminé'},
        {'description': 'Done'}
    ])
    
    # === Boutons OK ===
    ok_button_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'resourceId': 'com.instagram.android:id/igds_alert_dialog_primary_button'},
        {'text': 'OK'},
        {'text': 'Ok'},
        {'textContains': 'OK'},
        {'description': 'OK'},
        {'description': 'Ok'}
    ])
    
    # === Background dimmer (pour fermer les bottom sheets) ===
    background_dimmer_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'resourceId': 'com.instagram.android:id/background_dimmer'},
        {'description': '@2131954182'}
    ])
    
    # === Drag handle (trait gris des bottom sheets) ===
    drag_handle_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'resourceId': 'com.instagram.android:id/bottom_sheet_drag_handle_prism'},
        {'resourceId': 'com.instagram.android:id/bottom_sheet_drag_handle_frame'}
    ])
    
    # === Patterns de détection des pages problématiques ===
    # Chaque pattern contient: indicators (textes à chercher), close_methods, et flags optionnels
    detection_patterns: Dict[str, Dict] = field(default_factory=lambda: {
        'qr_code_page': {
            'indicators': ['Partager le profil', 'QR code', 'Copier le lien'],
            'close_methods': ['back_button', 'x_button', 'tap_outside']
        },
        'story_qr_code_page': {
            'indicators': ['Enregistrer le code QR', 'Terminé', 'Tout le monde peut scanner ce code QR', 'smartphone pour voir ce contenu'],
            'close_methods': ['terminate_button', 'back_button', 'tap_outside']
        },
        'message_contacts_page': {
            'indicators': ['Write a message...', 'Écrivez un message…', 'Send separately', 'Envoyer', 'Search', 'Rechercher', 
                          'Discussion non sélectionnée', 'New group', 'Nouveau groupe', 
                          'direct_private_share_container_view', 'direct_share_sheet_grid_view_pog'],
            'close_methods': ['swipe_down_handle', 'tap_outside', 'back_button']
        },
        'profile_share_page': {
            'indicators': ['WhatsApp', 'Ajouter à la story', 'Partager', 'Texto', 'Threads'],
            'close_methods': ['swipe_down_handle', 'swipe_down', 'tap_outside', 'back_button']
        },
        'try_again_later_page': {
            'indicators': ['Réessayer plus tard', 'Try Again Later', 'Nous limitons la fréquence', 'We limit how often',
                          'certaines actions que vous pouvez effectuer', 'certain things on Instagram',
                          'protéger notre communauté', 'protect our community',
                          'igds_alert_dialog_headline', 'igds_alert_dialog_subtext', 'igds_alert_dialog_primary_button',
                          'Contactez-nous', 'Tell us'],
            'close_methods': ['ok_button', 'back_button'],
            'is_soft_ban': True,
            'track_stats': True
        },
        'notifications_popup': {
            'indicators': ['Notifications', 'Get notifications when', 'shares photos, videos or channels', 
                          'Goes live', 'Some', 'Stories', 'Reels'],
            'close_methods': ['back_button', 'tap_outside', 'swipe_down']
        },
        'follow_notification_popup': {
            'indicators': ['Turn on notifications?', 'Get notifications when', 'Turn On', 'Not Now', 'posts a photo or video'],
            'close_methods': ['not_now_button', 'back_button', 'tap_outside']
        },
        'instagram_update_popup': {
            'indicators': ['Update Instagram', 'Get the latest version', 'Update', 'Not Now', 'available on Google Play'],
            'close_methods': ['not_now_button', 'back_button', 'tap_outside']
        },
        'follow_options_bottom_sheet': {
            'indicators': ['Ajouter à la liste Ami(e)s proches', 'Ajouter aux favoris', 'Sourdine', 
                          'Restreindre', 'Ne plus suivre', 'bottom_sheet_container', 'background_dimmer'],
            'close_methods': ['tap_background_dimmer', 'swipe_down_handle', 'back_button']
        },
        'mute_notifications_popup': {
            'indicators': ['Sourdine', 'Publications', 'Stories', "Bulles d'activité sur le contenu", 
                          'Notes', 'Notes sur la carte', 'Mute', 'Posts', 'Activity bubbles about content',
                          'bottom_sheet_start_nav_button_icon'],
            'close_methods': ['swipe_down_handle', 'swipe_down', 'tap_outside']
        },
        'android_permission_dialog': {
            'indicators': ['com.android.packageinstaller', 'permission_allow_button', 'permission_deny_button',
                          'Autoriser', 'AUTORISER', 'Allow', 'ALLOW', 'accéder aux photos',
                          'access to photos', 'contenus multimédias', 'media files'],
            'close_methods': ['allow_permission_button', 'back_button']
        }
    })

PROBLEMATIC_PAGE_SELECTORS = ProblematicPageSelectors()
