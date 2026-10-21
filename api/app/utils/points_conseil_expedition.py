"""Le DOCUMENT d'un point CS / Syndic, son aperçu, et son EXPÉDITION une fois validé (#2082).

## Ce que la validation emporte (arbitré le 20/10/2026)

> « Le PDF est sauvegardé dans le CR du point » — et il est **envoyé en pièce
> jointe** aux présents du conseil et du syndic qui ont une adresse, jamais aux
> invités (réponse à la question « qui expédie le PDF validé ? »).

> « Le CR une fois validé doit être envoyé aux présents, copie tout le CS »
> (corrigé le 21/10/2026) : UN courriel, adressé aux présents joignables, avec
> en copie chaque membre du conseil syndical — par son rôle,
> `destinataires.membres_cs_avec_email` — qui n'est pas déjà destinataire.

`expedier` rend le PDF, le RANGE sous le dossier privé du stockage
(`prive/points-conseil/` : jamais servi en direct, `utils/stockage`) — sa clé sur
le point (`pdf_cle`) — puis l'envoie. Il ne lève jamais : une validation est
acquise même si le moteur PDF ou le courriel échouent, et l'échec se journalise.

## Le même document à tout instant

« Exporter en PDF », pendant un point, rend ce document marqué « Projet —
révision N » (`pdf_du_point(…, projet=True)`, #2089 : le bouton « Aperçu PDF »
est retiré).
"""

from __future__ import annotations

import html
import logging
from dataclasses import replace
from typing import Optional

from sqlmodel import Session

from app.models.core import Utilisateur
from app.models.points_conseil import A_VALIDER, VALIDE, PointConseil, PresentPoint
from app.models.tickets import Ticket
from app.utils.config_site import config_site
from app.utils.dates_fr import date_courte, datetime_longue
from app.utils.liens import nom_site
from app.utils.logo import logo_televerse_png
from app.utils.noms import nom_affiche
from app.utils.points_conseil import compte_rendu, nom_present, releve_du_point
from app.utils.points_conseil_etats import changement_a_poser
from app.utils.points_conseil_ou import ou_du_point
from app.utils.points_conseil_pdf import DocumentPoint, generer_pdf
from app.utils.points_conseil_validation import (
    adresse_du_present,
    est_destinataire,
    marque_revision,
    revision_du_document,
)
from app.utils.recuperer import ou_rien
from app.utils.stockage import DOSSIER_PRIVE, stockage
from app.utils.valeurs import valeur

logger = logging.getLogger(__name__)

#: Le dossier des PDF rangés — sous le dossier privé : jamais servis en direct.
DOSSIER_PDF = f"{DOSSIER_PRIVE}/points-conseil"


def _nom_compte(session: Session, user_id: Optional[int]) -> str:
    compte = ou_rien(session, Utilisateur, user_id)
    return nom_affiche(compte.prenom, compte.nom) if compte else "l’administration"


def _validation_present(session: Session, point: PointConseil, p: PresentPoint) -> str:
    nom = nom_present(p)
    if p.valide_le and p.valide_par_id:
        return (
            f"{nom} — validé le {date_courte(p.valide_le)}, par dérogation "
            f"(accord recueilli par {_nom_compte(session, p.valide_par_id)})"
        )
    if p.valide_le:
        return f"{nom} — validé le {date_courte(p.valide_le)}"
    return f"{nom} — {'sans réponse' if point.etat == VALIDE else 'en attente'}"


def _validation_du_point(session: Session, point: PointConseil, tous: bool) -> str:
    if point.etat == VALIDE and point.valide_le:
        jour = date_courte(point.valide_le)
        if tous:
            return f"Validé le {jour} par tous les présents destinataires."
        if point.valide_par_id:
            return f"Validé le {jour} en l’état par {_nom_compte(session, point.valide_par_id)}."
        return f"Validé d’office le {jour}, sept jours après l’envoi."
    if point.etat == A_VALIDER and point.envoye_le:
        return f"Révision {point.revision} envoyée aux présents le {date_courte(point.envoye_le)}."
    return ""


def document(
    session: Session, point: PointConseil, user: Optional[Utilisateur], *, projet: bool = False
) -> DocumentPoint:
    """Ce que le PDF du point montre — la vue du conseil, sans filtre de lecture."""
    from app.routers.tickets.commun import STATUT_LABELS

    cr = compte_rendu(session, point, user)
    #  Les affaires du point : sa liste figée, ses abordées, ses non traitées (#2089).
    ids = {
        *(a.id for a in cr.initiales),
        *(a.id for a, _ in cr.abordees),
        *(a.id for a in cr.non_traitees),
    }
    r = releve_du_point(session, point, None)
    r = replace(r, affaires=[a for a in r.affaires if a.id in ids])
    revision = revision_du_document(point, [c for _, c in cr.abordees])
    etats: dict[int, str] = {}
    for a, c in cr.abordees:
        ticket = session.get(Ticket, a.id)
        if not c.etat_cible or ticket is None:
            continue
        actuel = valeur(ticket.statut)
        if point.etat == VALIDE:
            if actuel == c.etat_cible:
                etats[a.id] = f"État décidé : {STATUT_LABELS.get(actuel, actuel)}"
        elif changement_a_poser(ticket, c):
            etats[a.id] = (
                f"État à la validation : {STATUT_LABELS.get(actuel, actuel)} → "
                f"{STATUT_LABELS.get(c.etat_cible, c.etat_cible)}"
            )
    destinataires = [p for p in cr.presents if est_destinataire(p)]
    return DocumentPoint(
        cr=cr,
        releve=r,
        revision=revision,
        marques={a.id: m for a, c in cr.abordees if (m := marque_revision(c, revision))},
        validations=[_validation_present(session, point, p) for p in destinataires],
        validation_du_point=_validation_du_point(
            session, point, bool(destinataires) and all(p.valide_le for p in destinataires)
        ),
        etats=etats,
        projet=projet,
    )


def pdf_du_point(
    session: Session, point: PointConseil, user: Optional[Utilisateur], *, projet: bool = False
) -> bytes:
    """Le PDF du point — l'aperçu (`projet`) ou le document validé."""
    site = config_site(session)
    return generer_pdf(
        document(session, point, user, projet=projet),
        site_nom=nom_site(site.get("site_nom")),
        logo_png=logo_televerse_png(session),
    )


def nom_du_fichier(point: PointConseil) -> str:
    return f"compte-rendu-point-cs-syndic-{point.debut:%Y-%m-%d}.pdf"


async def expedier(session: Session, point: PointConseil) -> int:
    """Range le PDF du CR validé et l'envoie aux présents joignables. Rend le
    nombre d'envois ; ne lève jamais (la validation est acquise)."""
    from fastapi.concurrency import run_in_threadpool

    from app.utils.destinataires import membres_cs_avec_email
    from app.utils.email import send_email_group

    try:
        contenu = await run_in_threadpool(pdf_du_point, session, point, None)
        cle = f"{DOSSIER_PDF}/point-{point.id}-{point.debut:%Y-%m-%d}.pdf"
        depot = stockage()
        depot.ecrire(cle, contenu)
        for colonne, v in depot.colonnes(cle, "pdf").items():
            setattr(point, colonne, v)
        session.add(point)
        session.commit()
    except Exception:
        logger.exception("points conseil : PDF du point %s non rangé", point.id)
        return 0
    piece = str(depot.chemin(cle))
    contexte = {
        "point": {
            "date": datetime_longue(point.debut),
            #  Le modèle n'échappe pas : le texte l'est ici.
            "lieu": html.escape(ou_du_point(point)),
        },
    }
    a, copie = destinataires_du_pdf(
        [adresse_du_present(session, p) for p in compte_rendu(session, point, None).presents],
        membres_cs_avec_email(session),
    )
    if not a and not copie:
        return 0
    try:
        await send_email_group(
            "point_conseil_valide",
            a or copie,
            contexte,
            session,
            cc_recipients=copie if a else [],
            attachments=[piece],
        )
    except Exception:
        logger.exception("points conseil : envoi du PDF du point %s en échec", point.id)
        return 0
    return len(a) + (len(copie) if a else 0)


def destinataires_du_pdf(
    adresses_des_presents: list[Optional[str]], conseil: list[tuple[int, str]]
) -> tuple[list[tuple[Optional[int], str]], list[tuple[Optional[int], str]]]:
    """PURE. À : les présents joignables ; copie : le conseil, sans ceux déjà à « À »."""
    a: list[tuple[Optional[int], str]] = []
    vues: set[str] = set()
    for adresse in adresses_des_presents:
        if adresse and adresse.lower() not in vues:
            vues.add(adresse.lower())
            a.append((None, adresse))
    copie = [(uid, e) for uid, e in conseil if e and e.lower() not in vues]
    return a, copie
