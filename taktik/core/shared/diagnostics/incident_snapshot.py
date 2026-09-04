"""Ce qu'on prend UNE fois, au moment ou l'incident est declare.

L'anneau (`screen_ring`) enregistre en continu et ne coute rien parce qu'il ne demande jamais
rien a l'appareil. Ce module fait l'inverse : il paie, une seule fois, ce qui vaut la peine d'etre
paye quand quelque chose vient de casser -- une capture d'ecran fraiche, et l'etat de la machine.

**Pourquoi maintenant et pas apres.** Les captures de `miss_capture` sont ANTERIEURES a
l'incident : elles montrent l'ecran ou une recherche a echoue, pas celui ou le run s'est arrete.
Et apres une perte de lien ADB, il n'y a plus rien a prendre. La seule fenetre ou l'appareil
repond encore est l'instant ou on constate le probleme.

**Pourquoi l'environnement.** La moitie des incidents s'expliquent par un fait que le rapport ne
portait pas : le telephone etait a 3 % de batterie, le stockage etait plein, l'application cible
avait ete mise a jour la veille, ou le premier plan n'etait plus la bonne application. Chacun de
ces faits coute une commande ; aucun n'etait dans le dossier.

**Chaque lecture est isolee.** Un `dumpsys` qui echoue ne doit pas emporter les six autres :
c'est exactement quand l'appareil va mal que ces informations valent le plus, donc c'est
exactement la que les lectures echouent. Une valeur absente vaut `None`, jamais une exception.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from loguru import logger

from taktik.core.shared.device.app_inspection import foreground_package
from taktik.core.shared.diagnostics.screen_snapshot import capture_screen_snapshot
from taktik.core.shared.diagnostics.surface_capture import captures_dir

#: La surface ou atterrissent les captures d'incident, a cote des autres et distincte d'elles :
#: un ecran d'incident n'est pas un ecran rate, et les melanger empecherait de retrouver « celui
#: du moment ou ca s'est arrete ».
SURFACE = "incident"


def _sortie_shell(device: Any, commande: str) -> Optional[str]:
    """Le texte d'une commande shell, ou None. Ne leve jamais."""
    try:
        resultat = device.shell(commande)
        # uiautomator2 rend soit une chaine, soit un objet portant `.output`.
        texte = getattr(resultat, "output", resultat)
        return texte if isinstance(texte, str) else None
    except Exception:  # noqa: BLE001 -- un diagnostic ne doit jamais terminer un run
        return None


#: Ce que `dumpsys battery` rend quand rien n'a ete lu.
_BATTERIE_INCONNUE = {"level": None, "charging": None, "usbPowered": None,
                      "temperature_c": None, "maybeSpoofed": None}


def _batterie(device: Any) -> Dict[str, Any]:
    """Niveau et etat de charge. Un telephone a 2 % explique beaucoup de runs qui s'arretent.

    `usbPowered` voyage a cote de `charging` parce que les deux se contredisent regulierement, et
    que la contradiction est elle-meme un diagnostic : le spoofing de batterie de l'application
    ecrit `dumpsys battery set level` et `unplug`, donc **la valeur lue peut etre la notre**, pas
    celle du telephone. Mesure le 2026-09-04 sur un Pixel 3a du parc : `USB powered: true` avec
    `status: 3` (decharge). Rendre « 76 %, sur batterie » comme une verite aurait envoye chercher
    une cause d'alimentation la ou il n'y en a pas.
    """
    texte = _sortie_shell(device, "dumpsys battery")
    if not texte:
        return dict(_BATTERIE_INCONNUE)

    def entier(cle: str) -> Optional[int]:
        trouve = re.search(rf"^\s*{cle}:\s*(-?\d+)\s*$", texte, re.MULTILINE)
        return int(trouve.group(1)) if trouve else None

    def booleen(cle: str) -> Optional[bool]:
        trouve = re.search(rf"^\s*{cle}:\s*(true|false)\s*$", texte, re.MULTILINE)
        return None if not trouve else trouve.group(1) == "true"

    etat = entier("status")
    temperature = entier("temperature")
    # 2 = en charge, 5 = plein. Les autres valeurs veulent dire « sur batterie ».
    en_charge = None if etat is None else etat in (2, 5)
    usb = booleen("USB powered")
    return {
        "level": entier("level"),
        "charging": en_charge,
        "usbPowered": usb,
        "temperature_c": None if temperature is None else round(temperature / 10, 1),
        "maybeSpoofed": bool(usb and en_charge is False),
    }


def _stockage(device: Any) -> Dict[str, Any]:
    """Espace libre sur /data. Un telephone plein fait echouer des ecritures sans le dire."""
    texte = _sortie_shell(device, "df /data")
    if not texte:
        return {"free_mb": None, "used_percent": None}
    for ligne in texte.splitlines():
        colonnes = ligne.split()
        # `df` varie d'un Android a l'autre ; on cherche la ligne qui finit par le point de montage.
        if len(colonnes) >= 5 and colonnes[-1].startswith("/data"):
            try:
                libre_ko = int(colonnes[-3])
                return {
                    "free_mb": round(libre_ko / 1024),
                    "used_percent": int(colonnes[-2].rstrip("%")),
                }
            except (ValueError, IndexError):
                return {"free_mb": None, "used_percent": None}
    return {"free_mb": None, "used_percent": None}


def _version_application(device: Any, paquet: Optional[str]) -> Optional[str]:
    """La version de l'application CIBLE, celle qui casse les selecteurs en changeant."""
    if not paquet:
        return None
    texte = _sortie_shell(device, f"dumpsys package {paquet} | grep versionName")
    if not texte:
        return None
    trouve = re.search(r"versionName=(\S+)", texte)
    return trouve.group(1) if trouve else None


def environnement(device: Any, *, platform: Optional[str] = None,
                  package: Optional[str] = None) -> Dict[str, Any]:
    """L'etat de la machine au moment de l'incident. Aucune cle ne manque, elles valent `None`.

    Une cle absente et une cle a `None` ne se lisent pas pareil : la premiere fait douter de la
    version du client qui a envoye le dossier, la seconde dit « on a essaye, ca n'a pas repondu ».
    """
    etat: Dict[str, Any] = {
        "platform": platform,
        "foregroundPackage": None,
        "targetPackage": package,
        "targetAppVersion": None,
        "battery": dict(_BATTERIE_INCONNUE),
        "storage": {"free_mb": None, "used_percent": None},
        "screen": None,
        "androidRelease": None,
        "deviceModel": None,
        "adbAlive": False,
    }
    if device is None:
        return etat

    try:
        etat["foregroundPackage"] = foreground_package(device)
    except Exception:  # noqa: BLE001
        pass
    # `window_size()` est la sonde de vivacite la moins chere : si elle repond, le lien tient.
    try:
        taille = device.window_size()
        etat["screen"] = f"{taille[0]}x{taille[1]}"
        etat["adbAlive"] = True
    except Exception:  # noqa: BLE001
        etat["adbAlive"] = False
        # Lien tombe : les commandes shell qui suivent echoueraient une par une, chacune sur son
        # propre delai. Rendre tout de suite ce qu'on a plutot que d'attendre sept fois.
        return etat

    etat["battery"] = _batterie(device)
    etat["storage"] = _stockage(device)
    etat["androidRelease"] = (_sortie_shell(device, "getprop ro.build.version.release") or "").strip() or None
    etat["deviceModel"] = (_sortie_shell(device, "getprop ro.product.model") or "").strip() or None
    etat["targetAppVersion"] = _version_application(device, package or etat["foregroundPackage"])
    return etat


def capturer_incident(device: Any, *, platform: str, raison: str,
                      package: Optional[str] = None) -> Dict[str, Any]:
    """L'ecran et l'etat au moment de l'incident. Rend toujours un enregistrement.

    Toujours : meme si l'appareil ne repond plus, l'environnement dit `adbAlive: false`, et c'est
    precisement le diagnostic qu'on cherchait. Un dossier vide aurait dit la meme chose qu'un
    dossier jamais produit.
    """
    enregistrement: Dict[str, Any] = {
        "reason": raison,
        "platform": platform,
        "environment": environnement(device, platform=platform, package=package),
        "screens": [],
        "screenshotPath": None,
        "xmlPath": None,
    }

    try:
        from taktik.core.shared.diagnostics.screen_ring import derniers
        enregistrement["screens"] = derniers()
    except Exception:  # noqa: BLE001
        pass

    if not enregistrement["environment"].get("adbAlive"):
        logger.debug("[incident] appareil injoignable — pas de capture, l'environnement le dit")
        return enregistrement

    try:
        base = capture_screen_snapshot(
            device,
            label=f"incident_{raison[:24]}",
            with_image=True,
            directory=captures_dir(platform, SURFACE),
        )
        if base:
            enregistrement["screenshotPath"] = f"{base}.png"
            enregistrement["xmlPath"] = f"{base}.xml"
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"[incident] capture impossible : {exc}")

    return enregistrement


__all__ = ["environnement", "capturer_incident", "SURFACE"]
