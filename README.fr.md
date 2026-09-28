<div align="center">
  <h1>Plateforme d'automatisation des réseaux sociaux</h1>

  <p><strong>Automatisation Instagram, TikTok, YouTube, Threads et Gmail sur de vrais appareils Android. Likes, follows, DM, scraping, publication, ciblage par hashtag, commentaires et qualification de profils par IA. Construit avec Python, uiautomator2 et ADB.</strong></p>

  [![GitHub stars](https://img.shields.io/github/stars/masterFuf/taktik-bot?style=social)](https://github.com/masterFuf/taktik-bot/stargazers)
  [![GitHub forks](https://img.shields.io/github/forks/masterFuf/taktik-bot?style=social)](https://github.com/masterFuf/taktik-bot/network/members)
  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
  [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
  [![Discord](https://img.shields.io/badge/Discord-Rejoindre-7289da?logo=discord&logoColor=white)](https://discord.com/invite/6tTBRTMhBj)

  <br/>

  <a href="https://taktik-bot.com/">Site web</a> •
  <a href="https://taktik-bot.com/fr/docs">Documentation</a> •
  <a href="https://www.youtube.com/@taktik-bot">YouTube</a> •
  <a href="https://discord.com/invite/6tTBRTMhBj">Discord</a> •
  <a href="./README.md">English</a>
</div>

---

<div align="center">

  [![Demo TAKTIK](https://img.youtube.com/vi/mFh0iv3Hzck/maxresdefault.jpg)](https://www.youtube.com/watch?v=mFh0iv3Hzck)

  **Les conditions d'accès à l'application desktop sont disponibles sur le site**

  <a href="https://taktik-bot.com/fr">**Voir les conditions actuelles** →</a>

  <br/><br/>

</div>

---

## Qu'est-ce que TAKTIK ?

**TAKTIK** automatise Instagram, TikTok, YouTube, Threads et Gmail sur de vrais téléphones Android.
Il a deux moitiés :

- **Le moteur (ce dépôt, GPLv3).** Un bot Python qui pilote le téléphone par ADB et uiautomator2,
  avec une ligne de commande (`taktik`). Chaque workflow de la liste ci-dessous se lance depuis la
  ligne de commande, sans limite de licence.
- **L'application desktop (commerciale).** Une interface graphique qui lance le même moteur et
  ajoute ce qui est listé dans [Ce qui demande l'application desktop](#ce-qui-demande-lapplication-desktop).

La ligne de commande et l'application lancent les mêmes workflows avec les mêmes réglages (sauf le
changement d'IP avant un run, qui est celui de l'application) : l'application passe par les
lanceurs du moteur, elle n'en a pas une deuxième copie.

---

## Fonctionnalités

Chaque ligne se lance depuis la ligne de commande (`taktik workflows run <id>`), sauf mention
contraire. `taktik workflows list` affiche tous les identifiants.

### Instagram

| Fonctionnalité | Identifiants / commande |
|---|---|
| **Abonnés ou abonnements de comptes cibles** | `instagram.automation.target_followers`, `target_following` |
| **Une liste de profils cibles** | `instagram.automation.target_profiles` |
| **Hashtags** | `instagram.automation.hashtags` |
| **Likers d'un post** | `instagram.automation.post_url` |
| **Fil d'actualité** | `instagram.automation.feed` |
| **Désabonnement** | `instagram.automation.unfollow` |
| **Synchronisation des abonnements et des abonnés** | `instagram.automation.sync_following`, `sync_followers_following` |
| **Scraping** : abonnés ou abonnements d'un compte, un hashtag, likers et commentateurs d'un post, une liste de pseudos, les posts de comptes | `instagram.scraping.target`, `hashtag`, `post_url`, `usernames`, `profile_posts` |
| **DM à froid** : une liste de comptes, messages fixes ou un message écrit par l'IA pour chacun | `instagram.engagement.coldDm` |
| **Boîte DM** : lire la boîte ou les demandes, répondre dans une conversation | `instagram.engagement.dm_read`, `dm_send` |
| **Notifications** : lire l'activité, accepter les demandes, liker, suivre en retour, répondre, lots | `instagram.engagement.notifications` |
| **Relais de stories** : repartager les stories d'un compte source | `instagram.task.story_relay` |
| **Publication** : post, carrousel, reel, story | `taktik publish post\|carousel\|reel\|story` |
| **Comptes** : connexion, inscription, déconnexion, changement de compte, liste des comptes, langue de l'app | `instagram.account.*` |

> En détail : [automatisation Instagram](https://taktik-bot.com/fr/fonctionnalites/instagram-automation)
> et [DM IA Instagram](https://taktik-bot.com/fr/fonctionnalites/instagram-ai-dm) sur le site.

### TikTok

| Fonctionnalité | Identifiants |
|---|---|
| **Fil Pour toi** | `tiktok.automation.for_you` |
| **Hashtags, recherche de compte** | `tiktok.automation.hashtag`, `search` |
| **Abonnés de comptes cibles, une liste de profils cibles** | `tiktok.automation.followers`, `target_profiles` |
| **Commentateurs d'une vidéo** | `tiktok.automation.post_url` |
| **Synchronisation des abonnements et des abonnés** | `tiktok.automation.sync_lists`, `sync_following`, `sync_followers` |
| **DM** : lecture et envoi | `tiktok.automation.dm_read`, `dm_send` |
| **Boîte de réception** : nouveaux abonnés (avec une passe d'accueil par IA), conversations sans réponse, demandes, activité | `tiktok.automation.new_followers`, `dm_unreplied`, `dm_requests`, `dm_activity` |
| **Notifications** | `tiktok.automation.notifications` |
| **DM à froid** : messages fixes ou un message écrit par l'IA pour chacun | `tiktok.standalone.tiktok_dm_outreach` |
| **Désabonnement** | `tiktok.standalone.tiktok_unfollow` |
| **Scraping** : abonnés d'un compte, un hashtag, commentateurs d'une vidéo, un son, les posts de comptes | `tiktok.standalone.tiktok_scraping` |
| **Publication** : une vidéo, ou un post texte | `tiktok.standalone.upload_post` |
| **Comptes** : connexion, inscription, déconnexion, langue de l'app | `tiktok.account.*` |

> En détail : [automatisation TikTok](https://taktik-bot.com/fr/fonctionnalites/tiktok-automation) sur le site.

### YouTube, Threads, Gmail

| Fonctionnalité | Identifiants |
|---|---|
| **YouTube** : connexion, déconnexion ; publier un Short ou une vidéo avec titre, description et visibilité | `youtube.account.login`, `logout`, `youtube.publish.upload_post` |
| **Threads** : suivre des comptes trouvés par une recherche, interagir avec le fil | `threads.automation.follow`, `feed` |
| **Gmail** : ajouter et retirer un compte, lire le dernier code, lister les comptes du téléphone | `gmail.account.login`, `logout`, `read_otp`, `scan_accounts` |

### L'IA dans le moteur

Elle marche depuis la ligne de commande avec votre propre clé [OpenRouter](https://openrouter.ai)
(demandée au lancement quand un run utilise l'IA ; un run manuel n'en demande aucune).

| Fonctionnalité | Où |
|---|---|
| **Commentaires IA** : un commentaire écrit pour le post qu'il accompagne | le bloc `ai` d'un run d'automatisation |
| **Qualification de profils** : un modèle de vision lit le profil visité, donne sa niche et un score de pertinence | le bloc `ai` d'un run d'automatisation ou de scraping |
| **DM à froid écrit par l'IA**, un message par destinataire | `messageMode: "ai"` (Instagram et TikTok) |
| **Passe d'accueil TikTok** : nouveaux abonnés qualifiés, les pertinents suivis en retour | `tiktok.automation.new_followers` avec `ai.newFollowers` |
| **Taktik Agent** : une session Instagram autonome où un modèle de vision décide chaque like, commentaire, visite de profil et follow | `taktik agent run` |

---

## Ce qui demande l'application desktop

| Fonctionnalité | Sans l'application |
|---|---|
| **Interface graphique**, panneaux en direct, historique des sessions, tableaux de bord | La ligne de commande affiche des journaux et le résultat final. |
| **Planificateur** (éditeur visuel, plans de journée et de période, plans générés par l'IA), **campagnes autonomes** | Une tâche cron peut enchaîner des commandes. |
| **Changer d'IP avant un run** (données mobiles ou mode avion), pools réseau, un seul téléphone à la fois sur une connexion partagée | La ligne de commande ne change jamais d'IP. |
| **Montée en charge** : plafonds calculés d'après l'âge et l'intensité du compte (`warmupPolicy`) | Vous pouvez écrire `warmupPolicy` vous-même dans le JSON d'un run ; le moteur applique ces plafonds. |
| **Persona du compte** : le compte opéré analysé (profil, posts, style d'écriture) pour guider ce que l'IA écrit (`ai.accountProfile`) | Vous pouvez écrire `ai.accountProfile` vous-même. |
| **Taxonomie des niches** (catégories, sous-niches, alias) utilisée par la qualification IA (`ai.nicheTaxonomy`) | La qualification est libre, ou vous écrivez `ai.nicheTaxonomy` vous-même. |
| **Mode décision** : l'application planifie les actions sur chaque profil | Le moteur n'agit pas sans le plan de l'application. |
| **Réponses IA aux DM**, messages de bienvenue Instagram écrits par l'IA, réponses IA aux commentaires | Les réponses se tapent au terminal. |
| **Contenu IA pour publier** : images, légendes, hashtags | La publication prend vos médias et vos textes. |
| **Target Search** (explorer la base locale), carte du monde, audience, export CSV/XLSX | La base est un fichier SQLite local, que vous pouvez interroger vous-même. |
| **Cartography Lab** (banc de test des actions atomiques), miroir d'écran, mur d'appareils, groupes d'appareils | - |
| **Synchronisation entre plusieurs PC** | - |

Le nombre de téléphones que pilote l'application dépend de son abonnement. Le moteur n'a pas cette
limite : une commande par téléphone.

> Catalogue complet : [toutes les fonctionnalités](https://taktik-bot.com/fr/fonctionnalites), dont
> le [planificateur](https://taktik-bot.com/fr/fonctionnalites/app-scheduler), les
> [analytics](https://taktik-bot.com/fr/fonctionnalites/app-sessions-analytics) et la
> [recherche de cibles](https://taktik-bot.com/fr/fonctionnalites/app-target-search).

---

## Démarrage rapide

### Application desktop

1. S'inscrire sur [taktik-bot.com](https://taktik-bot.com/fr/nos-prix)
2. Télécharger l'application desktop pour Windows
3. Brancher un appareil Android par ADB
4. Lancer un workflow depuis l'interface

### Ligne de commande

```bash
git clone https://github.com/masterFuf/taktik-bot.git
cd taktik-bot
pip install -r requirements.txt

python -m taktik                         # menu interactif
python -m taktik workflows list          # tous les identifiants
python -m taktik workflows run instagram.automation.feed --dry-run
```

Au démarrage, la ligne de commande dit dans quelle base elle écrit. Sans `TAKTIK_DB_PATH`, c'est
la base de l'application desktop (`%APPDATA%/taktik-desktop/taktik-data.db` sous Windows) ;
`TAKTIK_DB_PATH` en désigne une autre.

La référence de la ligne de commande (paramètres, clé IA, un exemple par workflow) est dans la
documentation.

### Prérequis

- Un téléphone **Android** joignable par **ADB** (les téléphones sur lesquels TAKTIK est testé :
  [Testé sur](#testé-sur))
- **Instagram** et/ou **TikTok** installés, dans une version listée dans [COMPATIBILITY.md](COMPATIBILITY.md)
- **Python 3.10+** pour la ligne de commande

### Versions et langues prises en charge

Les versions d'Instagram et de TikTok prises en charge, par architecture, avec un lien de
téléchargement de l'APK d'origine pour chacune, sont dans **[COMPATIBILITY.md](COMPATIBILITY.md)**
(en anglais). Ce fichier est généré depuis les données de sélecteurs du bot
(`python scripts/audit_compatibility_file.py --write`) et vérifié par le même script.

Le bot lit la langue de l'app, anglais ou français, au début d'un run et prend les libellés qui vont
avec. La ligne de commande elle-même parle anglais et français (`--lang en|fr`).

### Testé sur

Ce sur quoi TAKTIK est testé au 2026-09-28 : des runs réels et le banc de test du Lab, sur ces quatre
téléphones.

| Téléphone | Android | Instagram | TikTok |
|---|---|---|---|
| Pixel 3 | 12 | 410.0.0.53.71, en français | non testé |
| Pixel 3a | 12 | 410.0.0.53.71, en anglais | 43.1.4, en français |
| Pixel 4a | 13 | 410.0.0.53.71, en français | non testé |
| Pixel 6a | 16 | 447.0.0.55.81, en français | 47.0.3, en français |

L'ordinateur est un PC sous Windows.

Tout le reste est **non testé** : les autres téléphones et marques, les autres versions d'Android, les
émulateurs, les versions marquées « Under validation » dans [COMPATIBILITY.md](COMPATIBILITY.md) (le
bot porte des ajustements de sélecteurs pour certaines, mais aucun de ces téléphones ne les fait
tourner), Instagram 447 en anglais, TikTok en anglais, macOS et Linux. Non testé ne promet rien, dans
un sens comme dans l'autre.

### Tests de développement

```bash
python -m pytest
```

Les tests sont sous `tests/unit` (base de données, ligne de commande, contrat entre le bot et
l'application, un dossier par plateforme). Les POC locaux et scripts smoke dépendants d'un appareil
vont dans `tests/poc/` et `tests/smoke/`, ignorés par git parce qu'ils peuvent contenir des dumps,
des captures ou des essais propres à un appareil.

---

## Accès et conditions commerciales

Le moteur Python de ce dépôt est open source. Les modalités d'accès à l'application desktop et les
conditions commerciales actuelles sont maintenues sur le site :

- **[Site web TAKTIK](https://taktik-bot.com/fr)**
- **[Contact commercial](https://taktik-bot.com/fr/contact)**

---

## Documentation

Documentation complète sur **[taktik-bot.com/fr/documentation](https://taktik-bot.com/fr/documentation)**.

---

## Contribuer

Les issues sont bienvenues : un bug, une version d'Instagram ou de TikTok qui casse un workflow, une
question. Les pull requests extérieures ne sont pas acceptées pour l'instant. Voir
[CONTRIBUTING.md](CONTRIBUTING.md).

## Communauté et support

- **[Discord](https://discord.com/invite/6tTBRTMhBj)** : aide et astuces
- **[GitHub Issues](https://github.com/masterFuf/taktik-bot/issues)** : bugs et demandes
- **[Contact](https://taktik-bot.com/fr/contact)** : demandes commerciales

---

## Licence

Ce projet est sous licence **GNU General Public License v3.0**. Voir [LICENSE](LICENSE).

Un fichier de données relève d'une autre licence : `taktik/core/app/ai/data/agreement_fr.tsv` dérive
de Lexique 3.83 et est distribué sous CC BY-SA 4.0. Voir [NOTICE](NOTICE).

L'application desktop est un produit commercial ; les conditions actuelles sont détaillées sur le site.

---

## Avertissement

**À des fins éducatives et de recherche uniquement.**

Ce logiciel est fourni tel quel. Les utilisateurs doivent respecter les conditions des plateformes automatisées. Les développeurs ne sont pas responsables des restrictions de compte ou bannissements. Utilisation à vos risques.
