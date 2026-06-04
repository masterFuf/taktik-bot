# Installation

Cette page décrit l'installation du bot Python et des outils nécessaires pour piloter un appareil Android.

## 1. Python

Créer et activer un environnement virtuel :

```powershell
cd <repo>\bot
python -m venv venv
.\venv\Scripts\activate
```

Installer les dépendances :

```powershell
pip install -r requirements.txt
```

Installer les dépendances média optionnelles :

```powershell
pip install -r requirements-media.txt
```

## 2. ADB

Installer Android SDK Platform Tools :

```text
https://developer.android.com/tools/releases/platform-tools
```

Ajouter le dossier `platform-tools` au `PATH`, par exemple :

```text
C:\platform-tools\
```

Vérifier :

```powershell
adb version
adb devices
```

## 3. Émulateur ou appareil Android

Options supportées :

| Option | Usage |
|---|---|
| LDPlayer 9 | Recommandé pour les tests multi-instances |
| Appareil Android USB | Recommandé pour validation réelle |
| Émulateur Android standard | Possible si ADB/uiautomator2 fonctionnent |

Connexion LDPlayer :

```powershell
adb connect 127.0.0.1:5555
```

Instances multiples :

```powershell
adb connect 127.0.0.1:5555
adb connect 127.0.0.1:5557
adb connect 127.0.0.1:5559
```

## 4. Vérifier uiautomator2

```powershell
python -c "import uiautomator2 as u2; d = u2.connect('127.0.0.1:5555'); print(d.info)"
```

Si la commande échoue, vérifier :

- que le device est visible dans `adb devices` ;
- que le débogage USB est activé ;
- que l'agent ATX/uiautomator2 est correctement installé ;
- que le device n'est pas offline.

## 5. Fichiers locaux

Les données desktop sont stockées dans :

```text
%APPDATA%/taktik-desktop/
```

Structure principale :

```text
%APPDATA%/taktik-desktop/
+-- taktik-data.db          # Base SQLite locale
+-- config.json             # Configuration desktop
+-- profile-images/         # Avatars/profils capturés
|   +-- {username}.jpg
+-- logs/                   # Logs d'exécution
```

## 6. Documentation locale

```powershell
cd <repo>\taktik-docs
yarn dev
```

Ouvrir :

```text
http://localhost:3000
```
