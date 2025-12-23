# ADB Commands Documentation

Ce document contient les commandes ADB les plus utiles pour l'automatisation et le débogage d'appareils Android.

## Commandes de base

### Lister les appareils connectés
```bash
adb devices
```

### Se connecter à un appareil spécifique
```bash
adb -s <device_id> <command>
# Exemple:
adb -s 39V4C19711015915 shell input keyevent KEYCODE_BACK
```

## Navigation et interaction

### Simuler les touches physiques
```bash
# Bouton retour
adb shell input keyevent KEYCODE_BACK

# Bouton home
adb shell input keyevent KEYCODE_HOME

# Bouton menu
adb shell input keyevent KEYCODE_MENU

# Bouton app switcher (applications récentes)
adb shell input keyevent KEYCODE_APP_SWITCH

# Volume +
adb shell input keyevent KEYCODE_VOLUME_UP

# Volume -
adb shell input keyevent KEYCODE_VOLUME_DOWN

# Power (bouton marche/arrêt)
adb shell input keyevent KEYCODE_POWER
```

### Touches spéciales
```bash
# Enter/Valider
adb shell input keyevent KEYCODE_ENTER

# Échap
adb shell input keyevent KEYCODE_ESCAPE

# Tab
adb shell input keyevent KEYCODE_TAB

# Supprimer
adb shell input keyevent KEYCODE_DEL

# Espace
adb shell input keyevent KEYCODE_SPACE
```

### Gestion des notifications

### Fermer la barre de notifications
```bash
# Méthode 1: Simuler le bouton retour
adb shell input keyevent KEYCODE_BACK

# Méthode 2: Collapser la barre de status directement
adb shell service call statusbar 1

# Méthode 3: Swipe vers le bas pour ouvrir, puis swipe vers le haut pour fermer
adb shell input swipe 500 100 500 800 500  # Ouvrir
adb shell input swipe 500 800 500 100 500  # Fermer
```

### Interaction tactile
```bash
# Tap simple (x y)
adb shell input tap 500 1000

# Swipe (x1 y1 x2 y2 durée_ms)
adb shell input swipe 100 1000 100 200 500

# Long press (tap avec durée)
adb shell input swipe 500 1000 500 1000 1000  # 1 seconde
```

### Saisie de texte
```bash
# Saisir du texte
adb shell input text "votre_texte_ici"

# Pour les caractères spéciaux, utiliser les codes:
adb shell input text " "  # espace
adb shell input text "\&" # &
adb shell input text "\%" # %
```

## Gestion des applications

### Lister les applications installées
```bash
# Toutes les applications
adb shell pm list packages

# Applications système uniquement
adb shell pm list packages -s

# Applications tierces uniquement
adb shell pm list packages -3

# Filtrer par nom
adb shell pm list packages | grep instagram
```

### Lancer une application
```bash
# Par nom de package
adb shell monkey -p com.instagram.android -c android.intent.category.LAUNCHER 1

# Par activité spécifique
adb shell am start -n com.instagram.android/.MainActivity
```

### Fermer une application
```bash
# Force stop
adb shell am force-stop com.instagram.android

# Arrêter proprement
adb shell am kill com.instagram.android
```

### Informations sur une application
```bash
# Version de l'application
adb shell dumpsys package com.instagram.android | grep versionName

# Chemin d'installation
adb shell pm path com.instagram.android
```

## Captures d'écran et enregistrement

### Screenshot
```bash
# Capturer et sauvegarder sur l'appareil
adb shell screencap /sdcard/screenshot.png

# Télécharger sur le PC
adb pull /sdcard/screenshot.png

# En une seule commande
adb exec-out screencap -p > screenshot.png
```

### Enregistrement vidéo
```bash
# Démarrer l'enregistrement (max 3 minutes)
adb shell screenrecord /sdcard/video.mp4

# Avec durée spécifique (30 secondes)
adb shell screenrecord --time-limit 30 /sdcard/video.mp4

# Télécharger la vidéo
adb pull /sdcard/video.mp4
```

## Débogage et logs

### Logs système
```bash
# Voir les logs en temps réel
adb logcat

# Filtrer par tag
adb logcat -s Instagram

# Filtrer par niveau d'erreur
adb logcat *:E

# Sauvegarder les logs dans un fichier
adb logcat > logs.txt

# Logs de l'application spécifique
adb logcat | grep "com.instagram.android"
```

### Informations système
```bash
# Informations sur l'appareil
adb shell getprop

# Modèle de l'appareil
adb shell getprop ro.product.model

# Version Android
adb shell getprop ro.build.version.release

# Informations sur la batterie
adb shell dumpsys battery

# Utilisation CPU/Mémoire
adb shell top
adb shell dumpsys meminfo
```

### Dump de l'interface
```bash
# Dump XML de l'interface actuelle
adb shell uiautomator dump

# Sauvegarder dans un fichier spécifique
adb shell uiautomator dump /sdcard/ui_dump.xml

# Télécharger le dump
adb pull /sdcard/ui_dump.xml
```

## Gestion des fichiers

### Transfert de fichiers
```bash
# Télécharger un fichier de l'appareil
adb pull /sdcard/download/fichier.txt

# Envoyer un fichier vers l'appareil
adb push fichier_local.txt /sdcard/download/

# Lister les fichiers
adb shell ls /sdcard/Download/

# Créer un répertoire
adb shell mkdir /sdcard/nouveau_dossier

# Supprimer un fichier
adb shell rm /sdcard/fichier.txt
```

## Réseau et connectivité

### État du réseau
```bash
# État WiFi
adb shell dumpsys wifi

# Adresse IP
adb shell ip addr

# Test de connectivité
adb shell ping google.com
```

### Proxy (utile pour LDPlayer)
```bash
# Configurer un proxy HTTP
adb shell settings put global http_proxy 192.168.1.100:8080

# Supprimer la configuration proxy
adb shell settings put global http_proxy :0
```

## Gestion des appareils LDPlayer

### Commandes spécifiques aux instances LDPlayer
```bash
# Lancer une instance spécifique
launchex.exe --index 0

# Lancer avec proxy
launchex.exe --index 1 --proxy 159.148.109.170:5772

# Mode headless
launchex.exe --index 0 --headless
```

## Commandes avancées

### Reboot et recovery
```bash
# Redémarrer l'appareil
adb reboot

# Redémarrer en mode recovery
adb reboot recovery

# Redémarrer en mode bootloader
adb reboot bootloader
```

### Installation d'APK
```bash
# Installer une application
adb install application.apk

# Forcer la réinstallation
adb install -r application.apk

# Autoriser les applications de test
adb install -t application.apk

# Désinstaller une application
adb uninstall com.nom.package
```

### Scripts utiles

### Script pour fermer automatiquement les notifications
```bash
#!/bin/bash
# Fermer la barre de notifications
adb shell service call statusbar 1
sleep 1
# Simuler un retour pour s'assurer que l'overlay est fermé
adb shell input keyevent KEYCODE_BACK
```

### Script de capture d'écran automatique
```bash
#!/bin/bash
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
adb exec-out screencap -p > "screenshot_${TIMESTAMP}.png"
echo "Screenshot saved: screenshot_${TIMESTAMP}.png"
```

## Dépannage

### Problèmes courants
```bash
# Appareil non autorisé
adb kill-server
adb start-server

# Connexion refusée
adb devices
# Si "unauthorized", autoriser sur l'appareil

# Redémarrer le service ADB
adb kill-server && adb start-server
```

### Vérifier la connectivité
```bash
# Tester si l'appareil répond
adb shell echo "Device is connected"

# Vérifier l'état de l'appareil
adb -s <device_id> get-state
```

## Raccourcis utiles

### Variables d'environnement (à ajouter au .bashrc ou .zshrc)
```bash
export DEVICE_ID="39V4C19711015915"
alias adbd="adb -s $DEVICE_ID"
alias screenshot="adbd exec-out screencap -p > screenshot_$(date +%Y%m%d_%H%M%S).png"
alias logs="adbd logcat"
```

Avec ces alias, vous pouvez utiliser:
```bash
adbd shell input keyevent KEYCODE_BACK
screenshot
logs
```

---

*Ce document sera mis à jour régulièrement avec de nouvelles commandes utiles.*
