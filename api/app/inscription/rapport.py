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

import logging
import os
import platform
import shutil
from datetime import datetime
from typing import Optional

from sqlmodel import func, select

from app import contexte
from app.config import get_settings
from app.inscription import depot
from app.registre.contrat import (
    VERSION_CONTRAT,
    Consommation,
    CoproprieteRapport,
    Hebergement,
    Identite,
    Posture,
    Rapport,
    Sauvegarde,
)
from app.utils import installation
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


def hebergement() -> Hebergement:
    disque = _mesure(_disque)
    return Hebergement(
        architecture=platform.machine() or None,
        memoire_mo=_mesure(_memoire_mo),
        disque_total_mo=disque[0] if disque else None,
        disque_occupe_mo=disque[1] if disque else None,
        moteur_base=_mesure(lambda: contexte.moteur().dialect.name),
    )


def posture() -> Posture:
    s = get_settings()
    return Posture(
        documentation_api_coupee=_mesure(_documentation_coupee),
        cookie_securise=bool(s.cookie_secure),
        secret_suffisant=all(len(c.secret) >= 32 for c in contexte.coproprietes()),
        lien_source_present=bool(DEPOT_SOURCE),
    )


def _copropriete(identifiant_installation: str) -> tuple[CoproprieteRapport, Optional[datetime]]:
    """Les NOMBRES d'une copropriété — dans son contexte, sans lire une donnée de résident."""
    from app.models.copropriete import Lot
    from app.models.core import Utilisateur
    from app.utils.backup import derniere_sauvegarde_reussie
    from app.utils.config_site import config_site
    from app.utils.liens import nom_site
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
        return rendu, _mesure(derniere_sauvegarde_reussie, session)


def construire() -> Rapport:
    """Le rapport de cette nuit, validé par le contrat avant de partir."""
    etat = depot.lire()
    identifiant = etat.identifiant or ""
    bail = (etat.bail or {}).get("bail") or {}
    coproprietes, sauvegardes = [], []
    for copro in contexte.coproprietes():
        with contexte.dans(copro):
            rendu, sauvee = _copropriete(identifiant)
        coproprietes.append(rendu)
        sauvegardes.append(sauvee)
    #  La sauvegarde de l'INSTALLATION est celle de sa copropriété la moins à jour :
    #  une seule qui manque, et il en manque une.
    derniere = None if (not sauvegardes or None in sauvegardes) else min(sauvegardes)
    return Rapport(
        version_contrat=VERSION_CONTRAT,
        identite=Identite(
            identifiant=identifiant,
            canal=bail.get("canal") or "replica",
            version_logicielle=installation.version_logicielle(),
            se_declare_reference=installation.est_reference(),
        ),
        hebergement=hebergement(),
        sauvegarde=Sauvegarde(derniere_reussie_le=derniere),
        posture=posture(),
        coproprietes=coproprietes,
        consommation=Consommation(),  # R7 (#1883) : quand le modèle économique sera choisi
    )
