"""La VALIDATION du CR d'un point conseil syndical / syndic (#2042) — écrite UNE fois.

À part de `utils/points_conseil` (la saisie) : celui-ci porte ce qui suit
« Terminer le point » — l'envoi aux présents, leur réponse, l'échéance de
7 jours, et ce que la validation rend lisible.

## Qui reçoit la demande (arbitré le 17/10/2026)

Les présents du conseil et du syndic qui ont une ADRESSE — un membre du CS par
le compte rattaché à sa fiche, un membre du syndic par l'adresse de sa fiche.
Jamais un invité. Un présent sans adresse ne reçoit rien et ne bloque rien.

## Le lien (`standards/03` §5 bis)

Valider ENGAGE : ouvrir le lien ne consomme rien — la page montre le CR et ses
deux gestes, et seul le clic (`POST`) valide. Un scanner de messagerie qui ouvre
le lien ne valide donc pas. Le jeton se stocke par son empreinte
(`auth/empreinte_jeton`), un par présent, refait à chaque envoi.

## Quand le CR est validé

Quand TOUS les destinataires ont validé ; sinon 7 jours après l'envoi
(`auto_valider`, tâche horaire) ; ou à tout moment par un membre du conseil.
Un commentaire reçu APRÈS l'envoi suspend les 7 jours, jusqu'à un nouvel envoi
(le CR corrigé) ou une validation du conseil.

## Ce que la validation rend lisible — et pas avant

Le CR de chaque affaire abordée, dans sa rubrique « Comptes rendus »
(`crs_lisibles`), et UNE entrée au fil (`routers/flux/points_conseil`). Elle
pose aussi l'état décidé de chaque affaire (`points_conseil_etats`) ; le PDF est
alors rangé et envoyé (`points_conseil_expedition`).

## Les révisions (#2082, arbitrées le 20/10/2026)

Chaque envoi aux présents est une révision : la 1 à « Terminer », +1 par
« Renvoyer ». Un CR qui change APRÈS un envoi porte la révision qu'il
rejoindra : le prochain document le marque « Modifié en révision N ».

## « CS et présents » (#2082)

Un CR coché se lit des présents : il part dans le courriel de validation et sur
la page de relecture. Il ne reste masqué qu'au fil et dans la rubrique de
l'affaire, pour qui n'est pas un lecteur du conseil (`lecteurs_du_conseil`).

## La dérogation de l'administrateur (#2082)

Pour un présent qui ne peut pas valider mais donne son accord, l'administrateur
valide POUR lui (`valider_pour`), avec un commentaire facultatif qui le dit.
Ce commentaire ne suspend pas les 7 jours : c'est un accord, pas une objection.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from markupsafe import Markup
from sqlmodel import Session, col, select

from app.auth.adresse_compte import normaliser_adresse
from app.auth.empreinte_jeton import empreinte
from app.models.core import Utilisateur
from app.models.gouvernance import MembreCS, MembreSyndic
from app.models.points_conseil import (
    A_VALIDER,
    PRESENT_CS,
    PRESENT_SYNDIC,
    VALIDE,
    CommentairePoint,
    CompteRenduAffaire,
    PointConseil,
    PresentPoint,
)
from app.models.tickets import Ticket
from app.utils import horloge
from app.utils.annonce_hall import texte_brut
from app.utils.cloche import sonner_systeme
from app.utils.dates_fr import date_longue, datetime_longue
from app.utils.destinataires import membres_cs_ou_admin, motif_injoignable
from app.utils.journal_securite import journaliser_securite
from app.utils.lecteurs_du_conseil import lit_les_points_conseil
from app.utils.points_conseil import compte_rendu, crs_du_point, nom_present, presents_du_point
from app.utils.points_conseil_etats import appliquer_etats
from app.utils.points_conseil_ou import ou_du_point
from app.utils.recuperer import ou_rien, present_ou_404

logger = logging.getLogger(__name__)

#: Sans réponse de tous les présents, le CR est validé au bout de ce délai.
DELAI_VALIDATION_JOURS = 7

# ── Les destinataires ─────────────────────────────────────────────────────


def adresse_du_present(session: Session, present: PresentPoint) -> Optional[str]:
    """L'adresse où envoyer la demande — `None` pour un invité ou un injoignable."""
    if present.nature == PRESENT_CS:
        fiche = ou_rien(session, MembreCS, present.membre_cs_id)
        compte = ou_rien(session, Utilisateur, fiche.user_id) if fiche else None
        return compte.email if compte and motif_injoignable(compte) is None else None
    if present.nature == PRESENT_SYNDIC:
        fiche = ou_rien(session, MembreSyndic, present.membre_syndic_id)
        return (normaliser_adresse(fiche.email) or None) if fiche else None
    return None


def est_destinataire(present: PresentPoint) -> bool:
    """A-t-il reçu la demande ? — c'est son lien qui le dit."""
    return present.jeton_empreinte is not None


# ── L'état de la validation ───────────────────────────────────────────────


@dataclass(frozen=True)
class EtatValidation:
    destinataires: int
    valides: int
    #: Un commentaire reçu depuis l'envoi : les 7 jours ne courent plus.
    suspendue: bool
    #: Quand le CR sera validé sans réponse — `None` s'il ne l'est pas d'office.
    echeance: Optional[datetime]


def etat_validation(
    point: PointConseil, presents: list[PresentPoint], commentaires: list[CommentairePoint]
) -> EtatValidation:
    """PURE. Où en est la validation d'un point."""
    recus = [p for p in presents if est_destinataire(p)]
    #  Un accord écrit par l'administrateur (dérogation) n'est pas une objection.
    objections = [c for c in commentaires if c.saisi_par_id is None]
    suspendue = bool(point.envoye_le and any(c.cree_le >= point.envoye_le for c in objections))
    echeance = (
        point.envoye_le + timedelta(days=DELAI_VALIDATION_JOURS)
        if point.etat == A_VALIDER and point.envoye_le and not suspendue
        else None
    )
    return EtatValidation(len(recus), sum(1 for p in recus if p.valide_le), suspendue, echeance)


def commentaires_du_point(session: Session, point_id: int) -> list[CommentairePoint]:
    return list(
        session.exec(
            select(CommentairePoint)
            .where(CommentairePoint.point_id == point_id)
            .order_by(CommentairePoint.cree_le, CommentairePoint.id)
        ).all()
    )


# ── Les révisions ─────────────────────────────────────────────────────────


def marquer_modifie(point: PointConseil, cr: CompteRenduAffaire) -> None:
    """Un CR qui change après un envoi rejoint la révision suivante."""
    if point.revision >= 1:
        cr.revision = point.revision + 1


def revision_du_document(point: PointConseil, crs: list[CompteRenduAffaire]) -> int:
    """PURE. La révision que le document montre : la dernière envoyée, ou la
    suivante si un CR a changé depuis — 0 tant que rien n'est parti."""
    if any((c.revision or 0) > point.revision for c in crs):
        return point.revision + 1
    return point.revision


def marque_revision(cr: CompteRenduAffaire, revision: int) -> Optional[str]:
    """PURE. « Modifié en révision N » — pour les CR changés depuis l'envoi précédent."""
    if revision >= 2 and cr.revision == revision:
        return f"Modifié en révision {revision}"
    return None


# ── L'envoi ───────────────────────────────────────────────────────────────


def _contexte_courriel(session: Session, point: PointConseil, user: Utilisateur) -> dict:
    """Ce que le courriel montre du CR — du TEXTE, que le corps du modèle échappe.

    Il était échappé ICI, à la main, parce que le modèle ne l'était pas : le
    corps des courriels s'échappe depuis #2150, et un second échappement
    écrirait « &amp;amp; ». Seul le retour à la ligne est du balisage : il entre
    marqué sûr, entre des morceaux de texte que `Markup.join` échappe.
    """
    cr = compte_rendu(session, point, user)
    revision = revision_du_document(point, [c for _, c in cr.abordees])
    return {
        "point": {
            "date": datetime_longue(point.debut),
            "lieu": ou_du_point(point),
            "presents": ", ".join(nom_present(p) for p in cr.presents),
        },
        "affaires": [
            {
                "numero": a.numero,
                "titre": a.titre,
                #  « — Modifié en révision N », ou rien (#2082).
                "marque": f" — {m}" if (m := marque_revision(c, revision)) else "",
                "texte": Markup("<br>").join(texte_brut(c.contenu).split("\n")),
            }
            #  « CS et présents » part aux présents : ils le lisent (#2082).
            for a, c in cr.abordees
        ],
        "non_traitees": ", ".join(f"{a.numero} {a.titre}" for a in cr.non_traitees),
        "echeance": date_longue(
            horloge.jour_civil(horloge.maintenant() + timedelta(days=DELAI_VALIDATION_JOURS))
        ),
    }


async def envoyer_pour_validation(session: Session, point: PointConseil, user: Utilisateur) -> int:
    """Envoie le CR à chaque présent joignable, avec SON lien. Rend le nombre d'envois.

    Chaque envoi refait les liens et remet les validations à zéro : un CR
    corrigé se revalide en entier. Le CR passe « à valider » même si personne
    n'est joignable — il le sera alors au bout des 7 jours.
    """
    from app.utils.email import send_email

    contexte = _contexte_courriel(session, point, user)
    envois: list[tuple[str, str]] = []
    for present in presents_du_point(session, point.id):
        adresse = adresse_du_present(session, present)
        present.valide_le = None
        present.jeton_empreinte = None
        if adresse:
            jeton = secrets.token_urlsafe(32)
            present.jeton_empreinte = empreinte(jeton)
            envois.append((adresse, jeton))
        session.add(present)
    point.envoye_le = point.mis_a_jour_le = horloge.maintenant()
    point.revision += 1
    session.add(point)
    session.commit()
    for adresse, jeton in envois:
        await send_email(
            "point_conseil_validation",
            adresse,
            {
                "point": contexte["point"],
                "affaires": contexte["affaires"],
                "non_traitees": contexte["non_traitees"],
                "echeance": contexte["echeance"],
                "jeton": jeton,
            },
            session,
        )
    return len(envois)


# ── Le lien d'un présent ──────────────────────────────────────────────────


def present_par_jeton(session: Session, jeton: str) -> PresentPoint:
    """Le présent dont c'est le lien — 404 pour un jeton inconnu, sans rien dire de plus."""
    present = (
        session.exec(
            select(PresentPoint).where(PresentPoint.jeton_empreinte == empreinte(jeton))
        ).first()
        if jeton
        else None
    )
    return present_ou_404(present, "Lien inconnu ou remplacé par un envoi plus récent")


def valider_par_present(session: Session, present: PresentPoint) -> PointConseil:
    """« Je valide » — idempotent : un second clic, ou un CR déjà validé, ne change rien."""
    point = session.get(PointConseil, present.point_id)
    if point.etat == A_VALIDER and present.valide_le is None:
        present.valide_le = horloge.maintenant()
        session.add(present)
        journaliser_securite(
            "cr_valide_par_lien", cible_id=point.id, detail=f"present={present.id}"
        )
        if all(p.valide_le for p in presents_du_point(session, point.id) if est_destinataire(p)):
            valider_point(session, point, None)
    return point


def commenter(session: Session, present: PresentPoint, contenu: str) -> CommentairePoint:
    """Un présent répond : le commentaire s'inscrit, le conseil est prévenu."""
    point = session.get(PointConseil, present.point_id)
    if point.etat != A_VALIDER:
        raise HTTPException(409, "Ce compte rendu n'attend plus de réponse")
    commentaire = CommentairePoint(point_id=point.id, present_id=present.id, contenu=contenu)
    session.add(commentaire)
    for membre in membres_cs_ou_admin(session):
        sonner_systeme(
            session,
            "tache_du_conseil",
            destinataire_id=membre.id,
            type="system",
            titre="Commentaire sur le compte rendu d'un point CS / Syndic",
            corps=f"{nom_present(present)} a commenté le compte rendu du point du "
            f"{date_longue(point.debut)} : la validation "
            "automatique est suspendue.",
            lien="/espace-cs/reporting",
        )
    return commentaire


# ── La validation ─────────────────────────────────────────────────────────


def valider_point(session: Session, point: PointConseil, par: Optional[Utilisateur]) -> None:
    """Le CR fait foi : il devient lisible dans les affaires et au fil, et chaque
    affaire abordée prend l'état décidé (#2082). Le PDF suit (`expedition`)."""
    crs = crs_du_point(session, point.id)
    ids = [c.ticket_id for c in crs]
    tickets = (
        {t.id: t for t in session.exec(select(Ticket).where(col(Ticket.id).in_(ids))).all()}
        if ids
        else {}
    )
    appliquer_etats(
        session, point, [(tickets[c.ticket_id], c) for c in crs if c.ticket_id in tickets], par
    )
    #  L'affaire « Points annexes » restée sans compte rendu est annulée (#2084).
    from app.utils.points_conseil_seance import annuler_annexe_vide

    annuler_annexe_vide(session, point, par)
    point.etat = VALIDE
    point.valide_le = point.mis_a_jour_le = horloge.maintenant()
    point.valide_par_id = par.id if par else None
    session.add(point)
    if par:
        journaliser_securite("cr_valide_force", acteur_id=par.id, cible_id=point.id)


def valider_pour(
    session: Session,
    present: PresentPoint,
    admin: Utilisateur,
    commentaire: Optional[str],
) -> PointConseil:
    """La dérogation : l'administrateur valide POUR un présent qui a donné son
    accord sans pouvoir cliquer. Le dernier accord valide le CR, comme un lien."""
    point = session.get(PointConseil, present.point_id)
    exiger_a_valider(point)
    if not est_destinataire(present):
        raise HTTPException(422, "Ce présent n'a pas reçu le compte rendu")
    if present.valide_le is not None:
        raise HTTPException(409, "Ce présent a déjà validé")
    present.valide_le = horloge.maintenant()
    present.valide_par_id = admin.id
    session.add(present)
    if commentaire and commentaire.strip():
        session.add(
            CommentairePoint(
                point_id=point.id,
                present_id=present.id,
                contenu=commentaire.strip(),
                saisi_par_id=admin.id,
            )
        )
    journaliser_securite(
        "cr_valide_par_derogation",
        acteur_id=admin.id,
        cible_id=point.id,
        detail=f"present={present.id}",
    )
    if all(p.valide_le for p in presents_du_point(session, point.id) if est_destinataire(p)):
        valider_point(session, point, admin)
    return point


def exiger_a_valider(point: PointConseil) -> PointConseil:
    if point.etat != A_VALIDER:
        raise HTTPException(409, "Ce compte rendu n'est pas en attente de validation")
    return point


def auto_valider(session: Optional[Session] = None) -> int:
    """La tâche horaire : valide les CR dont les 7 jours ont passé.

    ⚠️ Ne lève jamais : sous le planificateur, une exception tuerait le job pour
    de bon (même règle que `synthese_affaire.file.traiter_file`).
    """
    from app import contexte

    propre = session is None
    session = session or contexte.nouvelle_session()
    try:
        limite = horloge.maintenant() - timedelta(days=DELAI_VALIDATION_JOURS)
        echus = session.exec(
            select(PointConseil).where(
                PointConseil.etat == A_VALIDER,
                col(PointConseil.envoye_le).is_not(None),
                col(PointConseil.envoye_le) <= limite,
            )
        ).all()
        valides = 0
        for point in echus:
            etat = etat_validation(
                point,
                presents_du_point(session, point.id),
                commentaires_du_point(session, point.id),
            )
            if etat.suspendue:
                continue
            valider_point(session, point, None)
            journaliser_securite("cr_valide_auto", cible_id=point.id)
            valides += 1
        session.commit()
        logger.info("points conseil : %s compte(s) rendu(s) valide(s) d'office", valides)
        #  Le PDF de chacun se range et part aux présents (#2082) — hors de la
        #  boucle d'événements de l'API : `asyncio.run` y est sûr.
        from app.utils.points_conseil_expedition import expedier

        for point in echus:
            if point.etat == VALIDE:
                asyncio.run(expedier(session, point))
        return valides
    except Exception:
        logger.exception("points conseil : validation automatique en echec")
        return 0
    finally:
        if propre:
            session.close()


# ── Ce que la validation rend lisible ─────────────────────────────────────


def crs_lisibles(
    session: Session, ticket: Ticket, user: Utilisateur
) -> list[tuple[PointConseil, CompteRenduAffaire]]:
    """Les CR VALIDÉS d'une affaire, le plus récent en tête ; « Conseil seul » au conseil seul.

    L'appelant a déjà vérifié que `user` lit l'affaire (`ticket_visible`).
    « CS et présents » : le conseil et les comptes du syndic (#2082).
    """
    lignes = session.exec(
        select(PointConseil, CompteRenduAffaire)
        .join(CompteRenduAffaire, col(CompteRenduAffaire.point_id) == col(PointConseil.id))
        .where(CompteRenduAffaire.ticket_id == ticket.id, PointConseil.etat == VALIDE)
        .order_by(col(PointConseil.debut).desc())
    ).all()
    du_conseil = lit_les_points_conseil(user)
    return [(p, c) for p, c in lignes if du_conseil or not c.conseil_seul]
