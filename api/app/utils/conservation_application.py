"""L'APPLICATION de la conservation des affaires — la tâche nocturne (#2014, lot L2).

Spécification : `specs/architecture/conservation-affaires.md` §4 et §8. La règle et
le constat vivent dans `utils/conservation_affaires` ; l'archive dans
`utils/conservation_archive` ; la copie sur le PC dans `utils/conservation_copie`.

## Un passage

Seulement si l'administrateur a coché la case (`SERVICE_CONSERVATION`, coupée à la
livraison). Pour chaque exercice et chaque type dont l'échéance est arrivée, dans
cet ordre — chaque étape ne commence que si la précédente est prouvée :

1. **L'archive** est écrite puis relue (`ecrire_archive`). Une archive non
   vérifiée arrête le groupe : rien n'est retiré, rien n'est détaché.
2. **Les auteurs sont détachés** et **les colonnes de fichiers vidées**, l'affaire
   marquée `conservee_le` et l'archive enregistrée — UNE transaction.
3. **Les fichiers d'origine sont retirés du disque**, après la validation : un
   retrait qui échoue laisse un fichier orphelin (dit au journal), jamais une
   affaire qui pointe une archive perdue.

Puis, case cochée ou non : le **retrait différé** des archives que le poste a
copiées et vérifiées depuis 30 jours (`conservation_copie.retirer_copies_echues`).

⚠️ La tâche ne lève jamais (une exception tuerait le job pour de bon) et laisse une
ligne à CHAQUE passage — un battement qu'on n'entend pas ne se distingue pas d'une
tâche morte (`standards/07`).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Optional

from sqlmodel import Session

from app.auth.deps import est_moderateur
from app.models.core import Utilisateur
from app.models.exploitation import HistoriqueMaintenance, TachePlanifiee
from app.utils import horloge
from app.utils.config_site import config_site
from app.utils.declenchement import AUTOMATIQUE
from app.utils.conservation_affaires import Contenu, Echeance, echus
from app.utils.conservation_archive import Piece, ecrire_archive
from app.utils.conservation_copie import retirer_copies_echues
from app.utils.services import SERVICE_CONSERVATION, cle_actif, service_actif
from app.utils.stockage import stockage

logger = logging.getLogger("hostachy.conservation_affaires")

#: L'identifiant de la tâche permanente (`main.py`, `TACHES_PERMANENTES`).
ID_TACHE = "conservation_affaires"

#: Ce que l'auteur détaché était à l'échéance (`utils/noms.QUALITES_AUTEUR`).
RESIDENT = "resident"
CONSEIL = "conseil"


def application_active(session: Session) -> bool:
    """La case d'Admin › Services est-elle cochée ? Sinon, constat seul."""
    cfg = config_site(session, cle_actif(SERVICE_CONSERVATION))
    return service_actif(cfg, SERVICE_CONSERVATION)


def qualite(session: Session, auteur_id: Optional[int]) -> Optional[str]:
    """« conseil » ou « resident » — `None` sans compte (déjà « Ancien résident »)."""
    auteur = session.get(Utilisateur, auteur_id) if auteur_id else None
    if auteur is None:
        return None
    return CONSEIL if est_moderateur(auteur) else RESIDENT


def detacher(session: Session, contenu: Contenu, maintenant: datetime) -> None:
    """Retire d'une affaire ses auteurs et ses références de fichiers ; garde le texte.

    Le périmètre et le bâtiment restent (ils suffisent au carnet) ; le lot part —
    un lot désigne un foyer (§9, arbitrage 2). Le courriel brut d'une suite
    (`contenu_origine`) part aussi : il porte son expéditeur.
    """
    t = contenu.ticket
    t.auteur_qualite = qualite(session, t.auteur_id)
    t.auteur_id = None
    t.saisi_pour_user_id = None
    t.saisi_pour_nom = None
    t.saisi_pour_email = None
    t.lot_id = None
    t.photos_urls = None
    t.fichiers_urls = "[]"
    t.conservee_le = maintenant
    session.add(t)
    for porteur in (*contenu.messages, *contenu.evolutions):
        porteur.auteur_qualite = qualite(session, porteur.auteur_id)
        porteur.auteur_id = None
        porteur.fichiers_urls = "[]"
        session.add(porteur)
    for evolution in contenu.evolutions:
        evolution.contenu_origine = None
    #  Un document rattaché EST son fichier : la ligne part avec lui. Le sommaire
    #  de l'archive garde son nom et son empreinte.
    for document in contenu.documents:
        session.delete(document)


def _ecrire_au_journal(session: Session, groupe: Echeance, rendu: dict, debut: datetime) -> None:
    """Le passage d'un groupe au journal de maintenance — des nombres, jamais un nom."""
    session.add(
        HistoriqueMaintenance(
            tache=TachePlanifiee.conservation_affaires.value,
            statut="succes",
            declenchee_par=AUTOMATIQUE,
            details=json.dumps(rendu, ensure_ascii=False),
            cree_le=debut,
            terminee_le=horloge.maintenant(),
            duree_secondes=int((horloge.maintenant() - debut).total_seconds()),
        )
    )


def _retirer(session: Session, pieces: list[Piece]) -> int:
    """Retire du disque les fichiers archivés, par le stockage ; rend le nombre d'échecs.

    🔴 Jamais un fichier qu'un AUTRE objet cite encore (#2157). Appelée après le
    commit qui a détaché les fichiers du groupe : toute référence qui reste en base
    est celle d'un objet hors du groupe — une affaire qui a repris la même pièce
    jointe, une affiche, un événement. Le fichier part dans l'archive ET reste
    sur le disque pour lui.
    """
    from app.utils.photos import cles_citees

    st = stockage()
    racine = st.racine.resolve()
    encore_citees = cles_citees(session)
    echecs = 0
    for piece in pieces:
        try:
            cle = piece.chemin.relative_to(racine).as_posix()
            if cle in encore_citees:
                continue
            st.supprimer(cle)
        except (OSError, ValueError) as exc:
            echecs += 1
            logger.warning("Fichier archivé non retiré (%s) : %s", piece.nom, exc)
    return echecs


def traiter_groupe(
    session: Session, groupe: Echeance, contenus: list[Contenu], maintenant: datetime
) -> dict:
    """Un exercice et un type : archiver, détacher, retirer. Lève si l'archive est invalide."""
    archive, pieces = (
        (None, []) if groupe.fichiers == 0 else ecrire_archive(session, groupe, contenus)
    )
    for contenu in contenus:
        detacher(session, contenu, maintenant)
    if archive is not None:
        session.add(archive)
    rendu = {
        "exercice": groupe.exercice_cloture,
        "type": groupe.type.code,
        "affaires": len(contenus),
        "fichiers": len(pieces),
        "octets": sum(p.octets for p in pieces),
        "archive": archive.nom if archive else None,
        "empreinte": archive.empreinte if archive else None,
    }
    _ecrire_au_journal(session, groupe, rendu, maintenant)
    try:
        session.commit()
    except Exception:
        session.rollback()
        if archive is not None:
            stockage().supprimer(archive.cle)  # l'archive n'a plus de ligne : elle part
        raise
    rendu["retraits_echoues"] = _retirer(session, pieces)
    return rendu


def appliquer_conservation(
    session: Optional[Session] = None,
    *,
    aujourd_hui: Optional[date] = None,
    maintenant: Optional[datetime] = None,
) -> dict:
    """La tâche permanente. Rend le compte rendu du passage ; ne lève jamais."""
    from app import contexte

    propre = session is None
    session = session or contexte.nouvelle_session()
    maintenant = maintenant or horloge.maintenant()
    aujourd_hui = aujourd_hui or horloge.aujourd_hui()
    rendu: dict = {"active": False, "groupes": [], "echecs": 0, "archives_retirees": 0}
    try:
        rendu["active"] = application_active(session)
        if rendu["active"]:
            for groupe, contenus in echus(session, aujourd_hui):
                try:
                    rendu["groupes"].append(traiter_groupe(session, groupe, contenus, maintenant))
                except Exception as exc:  # une archive invalide, ou autre : ce groupe seul
                    session.rollback()
                    rendu["echecs"] += 1
                    logger.warning(
                        "Conservation %s %s non appliquée — rien n'est retiré : %s",
                        groupe.type.code,
                        groupe.exercice_cloture,
                        exc,
                    )
        rendu["archives_retirees"] = retirer_copies_echues(session, maintenant)
        logger.info(
            "Conservation des affaires : %s, %d groupe(s) traité(s), %d en échec, "
            "%d archive(s) retirée(s) du serveur après leur copie",
            "appliquée" if rendu["active"] else "case coupée (constat seul)",
            len(rendu["groupes"]),
            rendu["echecs"],
            rendu["archives_retirees"],
        )
    except Exception as exc:  # pragma: no cover - la tâche ne meurt pas
        session.rollback()
        logger.warning("Conservation des affaires non traitée : %s", exc)
    finally:
        if propre:
            session.close()
    return rendu


def enregistrer(planificateur) -> None:
    """La tâche permanente, chaque jour à 04:45 — après la sauvegarde de la nuit et la
    purge des comptes —, jouée pour chaque copropriété. Un passage manqué décale d'un
    jour, dans le sens de la conservation."""
    from app import contexte

    planificateur.add_job(
        contexte.pour_chaque_copropriete(appliquer_conservation, "conservation_affaires"),
        "cron",
        hour=4,
        minute=45,
        id="conservation_affaires",
    )


__all__ = [
    "ID_TACHE",
    "application_active",
    "appliquer_conservation",
    "detacher",
    "enregistrer",
    "qualite",
    "traiter_groupe",
]
