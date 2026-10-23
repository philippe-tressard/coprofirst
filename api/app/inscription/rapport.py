"""Le RAPPORT NOCTURNE de cette installation à la référence (R3 #1879, spec §4.11).

Il se construit depuis les schémas du CONTRAT (`registre/contrat.Rapport`), jamais à
la main : un champ qui n'y est pas ne peut pas partir. Et il ne porte que des
NOMBRES et des oui/non sur les copropriétés — aucun nom, aucun courriel, aucun
contenu de résident (D5) : `tests/test_inscription_rapport.py` sème des résidents
témoins et refuse de retrouver une seule de leurs données dans le rapport.

Le contact de l'administrateur n'y est PAS : il part à l'inscription et quand il
change (conditions §4, minimisation).

Chaque mesure qui ne peut pas se faire rend `None` — « inconnu » —, jamais une
valeur supposée (`standards/04` §1) : la référence distingue ainsi une sauvegarde
absente d'une sauvegarde qu'on n'a pas su lire.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import socket
import ssl
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlsplit

from cryptography import x509

from sqlmodel import func, select

from app import contexte
from app.config import get_settings
from app.inscription import depot
from app.registre.contrat import (
    ISSUES_MISE_A_JOUR,
    VERSION_CONTRAT,
    Consommation,
    CoproprieteRapport,
    Hebergement,
    Identite,
    Posture,
    Rapport,
    Sauvegarde,
)
from app.utils import installation, taches
from app.utils.plateforme import DEPOT_SOURCE
from app.utils.stockage import stockage

logger = logging.getLogger("hostachy.inscription")

MO = 1024 * 1024


def _mesure(geste, *args):
    """Une mesure, ou None si elle ne peut pas se faire — et cela se journalise."""
    try:
        return geste(*args)
    except Exception as exc:  # noqa: BLE001 — une mesure manquée n'arrête pas le rapport
        logger.warning("rapport : mesure %s impossible (%s)", geste.__name__, type(exc).__name__)
        return None


def _memoire_mo() -> int:
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // MO


def _disque() -> tuple[int, int]:
    usage = shutil.disk_usage("/")
    return usage.total // MO, usage.used // MO


def _volume_mo(racine) -> int:
    return sum(f.stat().st_size for f in racine.rglob("*") if f.is_file()) // MO


def _documentation_coupee() -> bool:
    """Le FAIT, lu sur l'application qui tourne — pas le réglage qui l'a demandé."""
    from app.main import app

    return app.openapi_url is None


def _certificat_servi(hote: str, port: int) -> bytes:
    """Le certificat que le public reçoit, en DER — lu, jamais VÉRIFIÉ.

    Sans vérification, et c'est voulu : un certificat expiré ou mal chaîné est
    précisément ce que la référence doit apprendre, et une vérification le
    refuserait avant d'en lire l'échéance. Rien n'est envoyé sur la connexion
    qu'une poignée de main TLS : aucune donnée ne la traverse.
    """
    contexte_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    contexte_tls.check_hostname = False
    contexte_tls.verify_mode = ssl.CERT_NONE
    with socket.create_connection((hote, port), timeout=5) as brut:
        with contexte_tls.wrap_socket(brut, server_hostname=hote) as tls:
            der = tls.getpeercert(binary_form=True)
    if not der:
        raise ValueError("aucun certificat présenté")
    return der


def echeance_certificat(der: bytes) -> datetime:
    """L'échéance d'un certificat, en UTC naïf comme la base — même expiré."""
    fin = x509.load_der_x509_certificate(der).not_valid_after_utc
    return fin.astimezone(timezone.utc).replace(tzinfo=None)


def _certificat_expire_le() -> Optional[datetime]:
    """L'échéance du certificat de l'ORIGIN de l'installation (#1981) — `None` sans
    HTTPS : une installation servie par une adresse locale n'a pas de certificat."""
    url = urlsplit(get_settings().origin)
    if url.scheme != "https" or not url.hostname:
        return None
    return echeance_certificat(_certificat_servi(url.hostname, url.port or 443))


def _moteur_de_base() -> str:
    """Le moteur des bases de l'installation — lu sur la première copropriété : hors
    requête, une installation commune n'en sert aucune par défaut (#2053)."""
    with contexte.dans(contexte.coproprietes()[0]):
        return contexte.moteur().dialect.name


def hebergement() -> Hebergement:
    disque = _mesure(_disque)
    return Hebergement(
        certificat_expire_le=_mesure(_certificat_expire_le),
        architecture=platform.machine() or None,
        memoire_mo=_mesure(_memoire_mo),
        disque_total_mo=disque[0] if disque else None,
        disque_occupe_mo=disque[1] if disque else None,
        moteur_base=_mesure(_moteur_de_base),
    )


def posture() -> Posture:
    s = get_settings()
    return Posture(
        documentation_api_coupee=_mesure(_documentation_coupee),
        cookie_securise=bool(s.cookie_secure),
        secret_suffisant=all(len(c.secret) >= 32 for c in contexte.coproprietes()),
        lien_source_present=bool(DEPOT_SOURCE),
    )


def _issue_mise_a_jour(session) -> Optional[str]:
    """L'issue de la DERNIÈRE mise à jour nocturne, telle que le script l'a nommée —
    `None` sans mise à jour (la référence n'en fait pas), ou d'un script d'avant #1981."""
    from app.models.core import TachePlanifiee
    from app.utils.etat_taches import dernier_rapport

    derniere = dernier_rapport(session, TachePlanifiee.mise_a_jour.value)
    try:
        issue = (json.loads(derniere.details or "{}") or {}).get("issue") if derniere else None
    except ValueError:
        return None
    return issue if issue in ISSUES_MISE_A_JOUR else None


#: Une installation à plusieurs copropriétés dit l'issue la plus grave.
_GRAVITE_ISSUE = {issue: rang for rang, issue in enumerate(ISSUES_MISE_A_JOUR)}


def _la_plus_grave(issues) -> Optional[str]:
    lues = [i for i in issues if i is not None]
    return max(lues, key=lambda i: (i != "reussie", _GRAVITE_ISSUE[i])) if lues else None


#: L'état des correctifs du système le plus grave d'abord (`ETATS_CORRECTIFS`).
_GRAVITE_CORRECTIFS = {"en_defaut": 2, "muet": 1, "a_jour": 0}


def _pire_correctifs(etats) -> Optional[str]:
    """Une installation à plusieurs copropriétés dit l'état le plus grave."""
    lus = [e for e in etats if e in _GRAVITE_CORRECTIFS]
    return max(lus, key=_GRAVITE_CORRECTIFS.__getitem__) if lus else None


def _copropriete(
    identifiant_installation: str,
) -> tuple[CoproprieteRapport, Optional[datetime], Optional[bool], Optional[str], Optional[str]]:
    """Les NOMBRES d'une copropriété — dans son contexte, sans lire une donnée de résident."""
    from app.models.copropriete import Lot
    from app.models.core import Utilisateur
    from app.utils.backup import derniere_sauvegarde_reussie
    from app.utils.config_site import config_site
    from app.utils.health_monitor import copie_hors_site_a_jour
    from app.utils.liens import nom_site
    from app.utils.sante_correctifs import etat_correctifs
    from app.utils.services import SERVICES, service_actif

    copro = contexte.courante()
    with contexte.nouvelle_session() as session:
        compter = lambda requete: session.exec(requete).one()  # noqa: E731
        #  Les services qui se COUPENT : une infrastructure (l'envoi des courriels) n'a
        #  pas d'interrupteur, donc rien à rapporter.
        coupables = [c for c, s in SERVICES.items() if s.cle_actif]
        cfg = config_site(session, "site_nom", *(SERVICES[c].cle_actif for c in coupables))
        rendu = CoproprieteRapport(
            identifiant=f"{identifiant_installation}-{copro.identifiant}",
            nom=nom_site(cfg.get("site_nom"))[:120],
            lots=_mesure(compter, select(func.count()).select_from(Lot)),
            utilisateurs_inscrits=_mesure(compter, select(func.count()).select_from(Utilisateur)),
            utilisateurs_actifs=_mesure(
                compter,
                select(func.count()).select_from(Utilisateur).where(Utilisateur.actif == True),  # noqa: E712
            ),
            volume_mo=_mesure(_volume_mo, stockage().racine),
            services_actifs=sorted(c for c in coupables if service_actif(cfg, c)),
        )
        return (
            rendu,
            _mesure(derniere_sauvegarde_reussie, session),
            _mesure(copie_hors_site_a_jour, session),
            _mesure(_issue_mise_a_jour, session),
            _mesure(etat_correctifs, session),
        )


def construire() -> Rapport:
    """Le rapport de cette nuit, validé par le contrat avant de partir."""
    etat = depot.lire()
    identifiant = etat.identifiant or ""
    bail = (etat.bail or {}).get("bail") or {}
    coproprietes, sauvegardes, copies, issues, correctifs = [], [], [], [], []
    for copro in contexte.coproprietes():
        with contexte.dans(copro):
            rendu, sauvee, copie, issue, correctif = _copropriete(identifiant)
        coproprietes.append(rendu)
        sauvegardes.append(sauvee)
        copies.append(copie)
        issues.append(issue)
        correctifs.append(correctif)
    #  La sauvegarde de l'INSTALLATION est celle de sa copropriété la moins à jour :
    #  une seule qui manque, et il en manque une. La copie hors de la machine aussi.
    derniere = None if (not sauvegardes or None in sauvegardes) else min(sauvegardes)
    hors_machine = None if (not copies or None in copies) else all(copies)
    return Rapport(
        version_contrat=VERSION_CONTRAT,
        identite=Identite(
            identifiant=identifiant,
            canal=bail.get("canal") or "replica",
            version_logicielle=installation.version_logicielle(),
            derniere_mise_a_jour=_la_plus_grave(issues),
            correctifs_systeme=_pire_correctifs(correctifs),
            se_declare_reference=installation.est_reference(),
        ),
        hebergement=hebergement(),
        sauvegarde=Sauvegarde(
            derniere_reussie_le=derniere,
            copie_hors_machine=hors_machine,
            attendue=not taches.coupee_hors_demo("backup"),
        ),
        posture=posture(),
        coproprietes=coproprietes,
        consommation=Consommation(),  # R7 (#1883) : quand le modèle économique sera choisi
    )
