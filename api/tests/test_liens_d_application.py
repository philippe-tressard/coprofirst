"""Garde-fou : les fichiers qui ouvrent les apps depuis un lien sont servis par chaque installation.

POURQUOI : un lien vers une résidence (courriel, QR de la fiche arrivant) ouvre l'app
plutôt que le navigateur si l'hôte publie un fichier d'association, que le système
lit sans jamais le montrer :

  * iOS : `/.well-known/apple-app-site-association` (#2459) — les chemins couverts
    sont tenus par `test_apple_app_site_association.py` ;
  * Android : `/.well-known/assetlinks.json` (#2788) — `android:autoVerify` le lit
    sur chaque hôte que déclare le manifeste de l'app ; les chemins vivent dans ce
    manifeste, pas ici.

Un fichier absent, mal typé ou redirigé ne fait aucune erreur : le lien reste au
navigateur, et personne ne le voit (constaté le 16/11/2026 : `assetlinks.json` rendait
404 sur les deux hôtes pendant que l'AASA était servi). Les deux systèmes exigent la
même chose — HTTPS, 200, `application/json`, sans redirection —, d'où UN bloc du
`Caddyfile` pour les deux, et ici UN contrôle paramétré sur les deux.

Empreintes des certificats (Android) : des données PUBLIQUES, elles se versionnent.
L'app installée par Google Play est signée par la clé de GOOGLE (Play App Signing),
pas par celle du poste : sans son empreinte, le lien reste au navigateur (#2860,
17/11/2026). La liste porte les clés de signature d'application que donne la Play
Console (l'actuelle, classique et post-quantique, puis la précédente), et en DERNIER
celle de débogage du poste, pour les essais. La clé de téléversement n'y figure pas :
Google re-signe ce qu'on lui envoie. Après une MEP, le post-check sonde chaque hôte
(`lib-precheck-post.sh`, P3c et P3d) : le 404 de la démo était passé inaperçu.

Le test lit `front/` depuis `api/tests/` comme `test_security_txt.py` : la CI n'exécute
pytest qu'ici, et un contrôle sans exécution est un contrôle absent.
"""

import json
import pathlib
import re

import pytest

from tests.aides_caddy import bloc_handle, caddyfile, chemins_du_matcher

_WELL_KNOWN = pathlib.Path(__file__).resolve().parents[2] / "front" / "static" / ".well-known"

#: Le nom du matcher du `Caddyfile` qui sert les fichiers d'association.
MATCHER = "@liens_d_application"

#: Chaque fichier d'association, par son nom sous `/.well-known/`.
FICHIERS = ("apple-app-site-association", "assetlinks.json")

#: L'identifiant de l'app, le même sur les deux systèmes : `applicationId` d'Android
#: (coprofirst-android), `PRODUCT_BUNDLE_IDENTIFIER` d'iOS (coprofirst-ios).
IDENTIFIANT_APP = "fr.coprofirst.app"

#: La clé de signature d'application de Google Play, celle que la Play Console met
#: dans son propre extrait d'`assetlinks.json` (#2860).
EMPREINTE_GOOGLE_PLAY = (
    "6F:9E:CD:9F:D5:30:CC:3B:18:AE:5E:70:D9:B6:41:90:C2:6A:7E:09:0D:F3:28:92:53:B4:BC:E8:9C:A9:59:6C"
)

#: Celle du certificat de débogage du poste : pour les essais, toujours en dernier.
EMPREINTE_DEBOGAGE = (
    "DC:C2:DA:73:1A:A7:D7:FB:39:BA:36:67:DC:24:13:45:8D:B8:0F:78:C1:BA:CD:A8:90:86:9B:79:04:9E:1A:B1"
)

#: Une empreinte SHA-256 telle qu'Android l'écrit : 32 octets hexadécimaux en
#: majuscules, séparés par « : ».
_EMPREINTE = re.compile(r"(?:[0-9A-F]{2}:){31}[0-9A-F]{2}")


def _document(nom: str):
    return json.loads((_WELL_KNOWN / nom).read_text(encoding="utf-8"))


def _declaration_android() -> dict:
    (declaration,) = _document("assetlinks.json")
    return declaration


@pytest.mark.parametrize("nom", FICHIERS)
def test_le_fichier_est_en_json_utf8_sans_bom_ni_crlf(nom):
    octets = (_WELL_KNOWN / nom).read_bytes()
    assert not octets.startswith(b"\xef\xbb\xbf"), f"{nom} : BOM en tête"
    assert b"\r" not in octets, f"{nom} : fins de ligne CRLF"
    _document(nom)


@pytest.mark.parametrize("nom", FICHIERS)
def test_le_fichier_ne_nomme_pas_la_residence(nom):
    """Il part chez toutes les installations (`lint:nom-residence` le garde aussi)."""
    texte = (_WELL_KNOWN / nom).read_text(encoding="utf-8").lower()
    for mot in ("hostachy", "résidence", "residence"):
        assert mot not in texte, f"{nom} nomme « {mot} »"


@pytest.mark.parametrize("nom", FICHIERS)
def test_caddy_le_sert_en_json_sans_redirection(nom):
    """Le serveur du front ne pose aucun type à un fichier sans extension (l'AASA), et
    les deux systèmes exigent `application/json` et refusent toute redirection : UN
    bloc les sert tous les deux, par un matcher qui les nomme."""
    contenu = caddyfile()
    chemins = chemins_du_matcher(contenu, MATCHER)
    assert chemins is not None, f"aucun matcher `{MATCHER} path …` dans le Caddyfile"
    assert f"/.well-known/{nom}" in chemins, f"{nom} absent du matcher {MATCHER} : {chemins}"
    bloc = bloc_handle(contenu, MATCHER)
    assert bloc is not None, f"aucun `handle {MATCHER}` dans le Caddyfile"
    assert 'header >Content-Type "application/json"' in bloc
    assert "reverse_proxy front:3000" in bloc
    assert "redir" not in bloc


def test_android_delegue_l_ouverture_de_tous_les_liens_a_l_app():
    declaration = _declaration_android()
    assert declaration["relation"] == ["delegate_permission/common.handle_all_urls"]
    cible = declaration["target"]
    assert cible["namespace"] == "android_app"
    assert cible["package_name"] == IDENTIFIANT_APP


def test_android_nomme_des_empreintes_sha256_en_paires_hexadecimales():
    empreintes = _declaration_android()["target"]["sha256_cert_fingerprints"]
    assert empreintes, "aucune empreinte : Android ne vérifierait aucune signature"
    invalides = [e for e in empreintes if not _EMPREINTE.fullmatch(e)]
    assert not invalides, f"empreintes hors format SHA-256 « AA:BB:… » : {invalides}"
    assert len(set(empreintes)) == len(empreintes), "empreinte en double"


def test_android_admet_l_app_signee_par_google_play():
    """L'app installée depuis Google Play porte la signature de Google : sans son
    empreinte, Android refuse l'association et le lien reste au navigateur (#2860)."""
    empreintes = _declaration_android()["target"]["sha256_cert_fingerprints"]
    assert EMPREINTE_GOOGLE_PLAY in empreintes, "empreinte de Google Play absente"
    assert empreintes[0] == EMPREINTE_GOOGLE_PLAY, "la clé de Google Play passe en tête"
    if EMPREINTE_DEBOGAGE in empreintes:
        assert empreintes[-1] == EMPREINTE_DEBOGAGE, "la clé de débogage reste en dernier"


def test_ios_et_android_ouvrent_la_meme_app():
    """L'AASA préfixe l'identifiant par l'équipe Apple (`<équipe>.fr.coprofirst.app`)."""
    (detail,) = _document("apple-app-site-association")["applinks"]["details"]
    assert detail["appIDs"], "aucune app dans l'AASA"
    for app_id in detail["appIDs"]:
        assert app_id.split(".", 1)[1] == IDENTIFIANT_APP, app_id
