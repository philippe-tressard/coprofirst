"""Garde-fou : `/.well-known/security.txt` dit où signaler une faille, et ne périme pas.

POURQUOI (22/10/2026) : l'analyse de sécurité de Cloudflare relevait son absence
sur les deux domaines. Le canal existait — les avis de sécurité GitHub, que
`SECURITY.md` décrit —, mais seul qui lisait le dépôt le trouvait ; un chercheur
qui interroge le site, comme le prévoit la RFC 9116, ne trouvait rien.

Le fichier porte un champ `Expires` OBLIGATOIRE : passé cette date, les outils le
tiennent pour caduc, sans un mot de notre côté — le site servirait un canal que
personne ne lit plus. Ce test échoue donc `MARGE_JOURS` avant l'échéance : le
renouvellement est un geste de lot, pas un souvenir.

⚠️ Il ne voit l'échéance qu'à chaque passage de la CI : un dépôt resté sans PR
pendant toute la marge laisserait le fichier expirer.

Le test lit `front/` depuis `api/tests/` comme `test_pwa_maj.py` : la CI n'exécute
pytest qu'ici, et un contrôle sans exécution est un contrôle absent.
"""

import pathlib
import re
from datetime import datetime, timedelta

from app.utils import horloge
from app.utils.plateforme import DEPOT_SOURCE
from tests.aides_caddy import bloc_handle, caddyfile

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_FICHIER = _RACINE / "front" / "static" / ".well-known" / "security.txt"

#: Le renouvellement se demande un mois avant l'échéance.
MARGE_JOURS = 30
#: La RFC recommande une échéance à moins d'un an.
HORIZON_JOURS = 366


def _champs() -> dict[str, list[str]]:
    champs: dict[str, list[str]] = {}
    for ligne in _FICHIER.read_text(encoding="utf-8").splitlines():
        if not ligne.strip() or ligne.startswith("#"):
            continue
        nom, sep, valeur = ligne.partition(":")
        assert sep, f"ligne sans « Champ: valeur » : {ligne!r}"
        champs.setdefault(nom.strip().lower(), []).append(valeur.strip())
    return champs


def _echeance() -> datetime:
    (valeur,) = _champs()["expires"]
    # RFC 9116 §2.5.5 : horodatage ISO 8601 en UTC, suffixe Z.
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", valeur), valeur
    return datetime.fromisoformat(valeur.removesuffix("Z")).replace(tzinfo=None)


def test_le_fichier_est_en_utf8_sans_bom_ni_crlf():
    octets = _FICHIER.read_bytes()
    assert not octets.startswith(b"\xef\xbb\xbf"), "BOM en tête"
    assert b"\r" not in octets, "fins de ligne CRLF"


def test_le_contact_est_le_canal_de_security_md():
    champs = _champs()
    assert champs["contact"] == [f"{DEPOT_SOURCE}/security/advisories/new"]
    assert champs["policy"] == [f"{DEPOT_SOURCE}/blob/main/SECURITY.md"]
    assert (_RACINE / "SECURITY.md").is_file()


def test_les_champs_uniques_ne_sont_ecrits_qu_une_fois():
    champs = _champs()
    assert len(champs.get("expires", [])) == 1
    assert len(champs.get("preferred-languages", [])) <= 1


def test_l_echeance_n_est_pas_proche():
    reste = _echeance() - horloge.maintenant()
    assert reste > timedelta(days=MARGE_JOURS), (
        f"security.txt expire dans {reste.days} jours : repousser `Expires` "
        f"(à moins de {HORIZON_JOURS} jours) dans front/static/.well-known/security.txt"
    )


def test_l_echeance_reste_a_moins_d_un_an():
    assert _echeance() - horloge.maintenant() < timedelta(days=HORIZON_JOURS)


def test_caddy_le_sert_en_utf8_comme_l_exige_la_rfc():
    """Le serveur du front pose `text/plain` sans jeu de caractères (constaté le
    22/10/2026 sur le build) ; la RFC 9116 §3 exige `charset=utf-8`."""
    bloc = bloc_handle(caddyfile(), "/.well-known/security.txt")
    assert bloc is not None, "aucun `handle /.well-known/security.txt` dans le Caddyfile"
    assert 'header >Content-Type "text/plain; charset=utf-8"' in bloc
    assert "reverse_proxy front:3000" in bloc
