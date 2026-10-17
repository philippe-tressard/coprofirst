"""La COPIE des archives d'affaires sur le PC (#2014, lot L3).

Spécification : `specs/architecture/conservation-affaires.md` §6, arbitrée le
16/10/2026 — le même mécanisme que la copie hors site, SANS rotation : le PC garde
toutes les archives, quand la copie ordinaire n'en garde que deux.

## Le cycle d'une archive

1. La tâche nocturne l'écrit (`conservation_application`) : `cree_le`.
2. Le poste la tire (`scripts/poste/export-hors-site.sh`), vérifie son empreinte
   et l'ACCUSE (`POST /admin/maintenance/archives-affaires/copiees`) : `copiee_le`
   — seulement si l'empreinte qu'il annonce est celle que le serveur a écrite.
3. **30 jours** plus tard (§9, arbitrage 3), la tâche nocturne retire la copie du
   serveur : `retiree_le`. D'ici là, la sauvegarde nocturne la porte aussi.

## Le contrôle

Une archive produite et non copiée depuis `DELAI_COPIE_JOURS` est un constat
(`archives_en_retard`) : le poste n'est pas toujours allumé, c'est l'âge qu'on
surveille. Une archive qu'on ne trouve plus sur le serveur avant d'être copiée est
un constat aussi — elle n'existe plus nulle part.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlmodel import Session, col, select

from app.models.conservation import ArchiveAffaires
from app.utils.stockage import stockage

logger = logging.getLogger("hostachy.conservation_affaires")

#: Le serveur garde sa copie ce nombre de jours après l'accusé du poste (§9).
DELAI_RETRAIT_JOURS = 30
#: Au-delà, une archive non copiée sur le PC est un constat (§6).
DELAI_COPIE_JOURS = 30


def accuser_copies(session: Session, copies: dict[str, str], maintenant: datetime) -> dict:
    """Note « copiée le » les archives que le poste a copiées et vérifiées.

    :param copies: nom → empreinte annoncée par le poste. Une empreinte qui n'est pas
        celle du serveur n'accuse rien : la copie du PC n'est pas l'archive écrite.
    :returns: `{"accusees": [...], "refusees": [...], "inconnues": [...]}` — des noms.
    """
    rendu: dict[str, list[str]] = {"accusees": [], "refusees": [], "inconnues": []}
    if not copies:
        return rendu
    lignes = {
        a.nom: a
        for a in session.exec(
            select(ArchiveAffaires).where(col(ArchiveAffaires.nom).in_(list(copies)))
        ).all()
    }
    for nom, empreinte in copies.items():
        archive = lignes.get(nom)
        if archive is None:
            rendu["inconnues"].append(nom)
        elif archive.empreinte != empreinte:
            rendu["refusees"].append(nom)
        else:
            if archive.copiee_le is None:
                archive.copiee_le = maintenant
                session.add(archive)
            rendu["accusees"].append(nom)
    session.commit()
    if rendu["refusees"]:
        logger.warning(
            "Copie d'archive d'affaires REFUSÉE (empreinte différente de celle du serveur) : %s",
            ", ".join(rendu["refusees"]),
        )
    return rendu


def retirer_copies_echues(session: Session, maintenant: datetime) -> int:
    """Retire du serveur les archives copiées sur le PC depuis `DELAI_RETRAIT_JOURS`."""
    limite = maintenant - timedelta(days=DELAI_RETRAIT_JOURS)
    echues = session.exec(
        select(ArchiveAffaires).where(
            col(ArchiveAffaires.copiee_le).is_not(None),
            col(ArchiveAffaires.copiee_le) <= limite,
            col(ArchiveAffaires.retiree_le).is_(None),
        )
    ).all()
    st = stockage()
    for archive in echues:
        st.supprimer(archive.cle)
        archive.retiree_le = maintenant
        session.add(archive)
    session.commit()
    return len(echues)


def archives_en_retard(session: Session, maintenant: datetime) -> list[str]:
    """Les constats sur la copie des archives — vide quand tout est copié à temps."""
    limite = maintenant - timedelta(days=DELAI_COPIE_JOURS)
    constats: list[str] = []
    st = stockage()
    for archive in session.exec(
        select(ArchiveAffaires).where(col(ArchiveAffaires.copiee_le).is_(None))
    ).all():
        if not st.existe(archive.cle):
            constats.append(
                f"Archive d'affaires {archive.nom} absente du serveur et jamais copiée sur le PC"
            )
        elif archive.cree_le <= limite:
            jours = (maintenant - archive.cree_le).days
            constats.append(
                f"Archive d'affaires {archive.nom} produite il y a {jours} jours et pas "
                "encore copiée sur le PC — lancer la sauvegarde hors site"
            )
    return constats
