from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from taktik.core.shared.ui.selectors.system.permission_prompt import PERMISSION_PROMPT_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.locales import L, L_all

@dataclass
class ProblematicPageSelectors:
    """Selectors for detecting and closing problematic pages."""
    
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
    
    # Android's permission prompt is not Instagram's: its ids and its grant buttons live in the
    # catalogue of Android's own windows (`shared/ui/selectors/system/permission_prompt.py`).
    @property
    def permission_prompt_granted_questions(self) -> List[str]:
        """The questions the check of pages grants, in every language we read: the prompt speaks
        the phone's language, which is not always Instagram's (a capture shows a French prompt
        over Instagram in English)."""
        return L_all('popup.permission_prompt_granted_questions')

    # The CANCEL button of an Instagram alert: the one way to dismiss an alert that is not the
    # rate-limit dialog without accepting what it asks (the contacts request's primary button
    # uploads the address book).
    alert_cancel_button_selectors: List[Dict[str, str]] = field(default_factory=lambda: [
        {'resourceIdMatches': r'(.*:id/)?igds_alert_dialog_cancel_button'},
    ])

    # === Instagram checking the account (its challenge screen) ===
    # Seen on a real one: Instagram 410 on a Pixel 6 Pro (Android 17), 2026-10-24, « Confirmez que
    # vous êtes une personne réelle afin d'utiliser votre compte », a « Continuer » button, the
    # whole page in `bloks_container`, no tab bar; the Lab read its activity (`app_current`).
    # It is the only activity of that name in the manifests of Instagram 410, 444 and 447 (searched
    # for `challenge` and `checkpoint`). Nothing on this screen is ever tapped: the run stops.
    account_challenge_activities: List[str] = field(default_factory=lambda: [
        'com.instagram.challenge.activity.ChallengeActivity',
    ])
    # The page the check is drawn in, and the main shell it never shows. The own profile carries a
    # `bloks_container` too, under its tab bar: without the tab bar's absence, every look at it
    # would pay a read of the activity.
    account_challenge_surface_ids: List[str] = field(default_factory=lambda: ['bloks_container'])
    account_challenge_absent_ids: List[str] = field(default_factory=lambda: ['tab_bar'])

    @property
    def account_challenge_texts(self) -> List[str]:
        """The check's headline in the phone's language (the second proof, after the activity)."""
        return L('popup.account_challenge_texts')

    # === Detection patterns for problematic pages ===
    # Chaque pattern contient: indicators (textes à chercher), close_methods, et flags optionnels
    detection_patterns: Dict[str, Dict] = field(default_factory=lambda: {
        'qr_code_page': {
            # The page's own ids (410, 5 real captures of it): its labels are also the own
            # profile's share button and a row of a profile's options sheet, and one of them was
            # enough to press Back on a profile.
            'indicators': ['nametag_container', 'profile_share_card_share_button',
                           'profile_share_card_copy_link_button'],
            'close_methods': ['back_button', 'x_button', 'tap_outside']
        },
        'story_qr_code_page': {
            'indicators': ['Enregistrer le code QR', 'Terminé', 'Tout le monde peut scanner ce code QR', 'smartphone pour voir ce contenu'],
            'close_methods': ['terminate_button', 'back_button', 'tap_outside']
        },
        'message_contacts_page': {
            'indicators': ['Write a message...', 'Écrivez un message…', 'Send separately', 'Envoyer',
                          'Discussion non sélectionnée', 'New group', 'Nouveau groupe', 
                          'direct_private_share_container_view', 'direct_share_sheet_grid_view_pog'],
            'close_methods': ['swipe_down_handle', 'tap_outside', 'back_button']
        },
        'profile_share_page': {
            'indicators': ['WhatsApp', 'Ajouter à la story', 'Partager', 'Texto', 'Threads'],
            # A sheet must be open (410 share sheet ids): the own profile carries three of these
            # words (its avatar's story badge, its share button, its Threads badge), the home
            # feed two, and neither shows a sheet.
            'surface_ids': ['direct_external_share_container_view',
                            'direct_private_share_container_view', 'bottom_sheet_container'],
            'close_methods': ['swipe_down_handle', 'tap_outside', 'back_button']
        },
        'try_again_later_page': {
            'indicators': ['Réessayer plus tard', 'Try Again Later', 'Nous limitons la fréquence', 'We limit how often',
                          'certaines actions que vous pouvez effectuer', 'certain things on Instagram',
                          'protéger notre communauté', 'protect our community',
                          'igds_alert_dialog_headline', 'igds_alert_dialog_subtext', 'igds_alert_dialog_primary_button',
                          'Contactez-nous', 'Tell us'],
            'close_methods': ['ok_button', 'back_button'],
            'is_soft_ban': True,
            'track_stats': True,
            # The indicators above hold the three GENERIC ids of every Instagram alert: the
            # contacts request carries them too. The block is proven by the dialog's own
            # words, read in its headline and subtext only (not in a bio behind it). Checked
            # on the 33 real captures of this dialog (2026-09-24): all carry these words.
            'dialog_text_ids': ['igds_alert_dialog_headline', 'igds_alert_dialog_subtext'],
            'dialog_texts': ['Réessayer plus tard', 'Try Again Later',
                             'Nous limitons la fréquence', 'We limit how often',
                             'certaines actions que vous pouvez effectuer', 'certain things on Instagram',
                             'protéger notre communauté', 'protect our community',
                             # Instagram's other restriction alert. Never captured by the bot: its
                             # public wording, to check on a real one.
                             'Temporarily Blocked', 'temporairement bloqu'],
        },
        'notifications_popup': {
            'indicators': ['Notifications', 'Get notifications when', 'shares photos, videos or channels', 
                          'Goes live', 'Some', 'Stories', 'Reels'],
            'close_methods': ['back_button', 'tap_outside', 'swipe_down_handle']
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
            # The tap above the sheet, on the part of the dimmer it leaves visible. Never the
            # dimmer's own centre: the dimmer spans the screen behind the sheet, its centre lies
            # on the sheet's rows ("Report" on the options sheet of a profile, 410, English).
            'close_methods': ['tap_outside', 'swipe_down_handle', 'back_button']
        },
        'mute_notifications_popup': {
            'indicators': ['Sourdine', 'Publications', 'Stories', "Bulles d'activité sur le contenu", 
                          'Notes', 'Notes sur la carte', 'Mute', 'Posts', 'Activity bubbles about content',
                          'bottom_sheet_start_nav_button_icon'],
            'close_methods': ['swipe_down_handle', 'tap_outside']
        },
        'android_permission_dialog': {
            # Proven by the window's system ids, never by words: « Autoriser » is also on
            # Instagram's own screens (its contacts request), and one such word, compared
            # lowercased, counted as two indicators (« Autoriser », « AUTORISER »).
            'system_xpaths': PERMISSION_PROMPT_SELECTORS.prompt,
            'close_methods': ['answer_permission_prompt']
        },
        'meta_ad_consent': {
            'indicators': ['free of charge with ads', 'gratuitement avec des publicités',
                          'Want to subscribe', 'Vous souhaitez vous abonner',
                          'Subscribe to use without ads', 'without ads'],
            'close_methods': ['ad_consent_flow']
        },
        'meta_ad_experience': {
            'indicators': ['manage your ad experience', 'gérer votre expérience publicitaire',
                          'Personalized ads', 'Publicités personnalisées',
                          'Less-personalized ads', 'Continue with personalized ads'],
            'close_methods': ['ok_button', 'back_button']
        },
        'instagram_map_popup': {
            'indicators': ['Introducing the Instagram map', 'Présentation de la carte Instagram',
                          'Explore the map', 'Explorer la carte',
                          'not sharing your location', 'ne partagez pas votre position'],
            'close_methods': ['not_now_button', 'back_button']
        }
    })

PROBLEMATIC_PAGE_SELECTORS = ProblematicPageSelectors()
