"""Les avis (notations) d'un prestataire, et le couple prestataire / affaire (15/11/2026).

Extrait de `routers/prestataires.py` : ce fichier dépassait 500 lignes en recevant la
modification d'un avis et l'affaire jugée (modularité, rang 1). Même préfixe, même droit
(le conseil syndical), et `routers/prestataires` ré-exporte les noms pour ses lecteurs.
"""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlmodel import Session, col, select

from app.auth.deps import est_auteur, require_cs_or_admin
from app.database import get_session
from app.models.core import Prestataire, Ticket, Utilisateur
from app.models.prestataires import NotationPrestataire
from app.models.tickets import TicketEvolution
from app.utils import horloge
from app.utils.noms import nom_auteur
from app.utils.notes_prestataires import ETATS, NOTE_DE_ETAT, etat_de_note
from app.utils.prestataires_affaire import (
    affaires_du_prestataire,
    noms,
    par_affaire,
    poser,
    prestataires_de,
)
from app.utils.recuperer import ou_404, ou_rien
from app.utils.synthese_affaire.agregats import exercice_de
from app.utils.synthese_affaire.rassemblement import mois_debut_exercice
from app.utils.valeurs import valeur

router = APIRouter(
    tags=["prestataires"]
)  # sans préfixe : `routers/prestataires` l'inclut sous le sien


# ── Notations prestataires ─────────────────────────────────────────────────


class NotationCreate(BaseModel):
    #  ⚠️ `devis_id` a disparu avec la prestation ponctuelle (#603). La COLONNE,
    #  elle, reste en base : les notations deja posees sur un devis gardent leur
    #  rattachement, et un retour arriere du code doit les retrouver. Le schema
    #  ne l'expose simplement plus — on ne peut plus en creer, on n'efface rien.
    prestataire_id: int
    #  🔴 TROIS ÉTATS (14/11/2026) : c'est `etat` qu'écrit l'écran. `note` (1 à 5)
    #  reste accepté pour les clients qui l'envoient encore ; l'un ou l'autre suffit.
    etat: Optional[Literal["mauvais", "neutre", "excellent"]] = None
    note: Optional[int] = None  # ancien format, 1-5
    commentaire: Optional[str] = None
    contrat_id: Optional[int] = None
    #  L'affaire jugée : le couple prestataire / affaire (15/11/2026). Facultative.
    ticket_id: Optional[int] = None
    #  Le vote est confirmé : si le prestataire n'est pas intervenant de l'affaire, il y est
    #  ajouté (15/11/2026). Sans ce consentement explicite, le serveur refuse (409).
    confirmer_ajout: bool = False

    @model_validator(mode="after")
    def valider_etat(self):
        if self.etat is None:
            if self.note is None:
                raise ValueError("Indiquez l'état de l'intervention")
            if not 1 <= self.note <= 5:
                raise ValueError("La note doit être entre 1 et 5")
            self.etat = etat_de_note(self.note)
        #  Un mauvais avis se justifie : sans commentaire, l'historique ne dit pas pourquoi.
        if self.etat == "mauvais" and not (self.commentaire or "").strip():
            raise ValueError("Un avis « Mauvais » doit être justifié par un commentaire")
        return self


class NotationRead(BaseModel):
    id: int
    prestataire_id: int
    note: int
    #  L'état LU de la note (`etat_de_note`) : l'écran ne lit jamais le chiffre.
    etat: str = ""
    #  L'exercice comptable de l'avis — la règle de l'exercice (mois de début réglé) vit
    #  ici, au serveur : l'écran regroupe les avis par exercice sans la recopier (R3d).
    exercice_annee: Optional[int] = None
    exercice_libelle: Optional[str] = None
    ticket_id: Optional[int] = None
    ticket_titre: Optional[str] = None
    #  Le droit SERVI : l'écran ne recompose pas « c'est mon avis » (15/11/2026).
    peut_modifier: bool = False
    commentaire: Optional[str] = None
    contrat_id: Optional[int] = None
    auteur_id: Optional[int] = None  # compte supprimé (#1821)
    auteur_nom: Optional[str] = None
    cree_le: datetime

    class Config:
        from_attributes = True


def _poser_exercice(nr: "NotationRead", n: NotationPrestataire, mois_debut) -> None:
    """L'exercice comptable du jour de l'avis — `exercice_de`, la règle des métriques."""
    exercice = exercice_de(horloge.jour_civil(n.cree_le), mois_debut)
    nr.exercice_annee = exercice.annee
    nr.exercice_libelle = exercice.libelle


def _affaire_pour_avis(
    session: Session, user: Utilisateur, prestataire_id: int, ticket_id: int, confirme: bool
) -> Ticket:
    """L'affaire jugée. Si le prestataire n'y intervient pas : sans confirmation, 409 ;
    confirmé, il est ajouté à l'affaire, et l'ajout s'inscrit au suivi (15/11/2026)."""
    ticket = ou_404(session, Ticket, ticket_id, "Affaire")
    actuelle = prestataires_de(session, ticket)
    if prestataire_id in actuelle:
        return ticket
    if not confirme:
        raise HTTPException(
            409,
            {
                "code": "ajout_intervenant",
                "message": "Ce prestataire n'est pas intervenant de cette affaire : confirmez, "
                "il y sera ajouté.",
            },
        )
    poser(session, ticket, [*actuelle, prestataire_id])
    nom = ou_404(session, Prestataire, prestataire_id, "Prestataire").nom
    session.add(
        TicketEvolution(
            ticket_id=ticket.id,
            type="commentaire",
            contenu=f"Intervenant ajouté par un avis : {nom}",
            auteur_id=user.id,
        )
    )
    session.add(ticket)
    return ticket


def _poser_affaire(session: Session, nr: "NotationRead", n: NotationPrestataire) -> None:
    """Le titre de l'affaire jugée, lu à la lecture : il suit une correction du titre."""
    if n.ticket_id is not None:
        ticket = ou_rien(session, Ticket, n.ticket_id)
        nr.ticket_titre = ticket.titre if ticket else None


def _lire(
    session: Session, n: NotationPrestataire, lecteur: Utilisateur, mois_debut
) -> NotationRead:
    """Un avis tel qu'on le lit : son état, son exercice, son affaire, son auteur, le droit."""
    nr = NotationRead.model_validate(n)
    nr.etat = etat_de_note(n.note)
    _poser_exercice(nr, n, mois_debut)
    _poser_affaire(session, nr, n)
    nr.auteur_nom = nom_auteur(ou_rien(session, Utilisateur, n.auteur_id))
    nr.peut_modifier = est_auteur(n, lecteur)
    return nr


@router.get("/notations", response_model=list[NotationRead])
def list_notations(
    prestataire_id: Optional[int] = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    q = select(NotationPrestataire)
    if prestataire_id is not None:
        q = q.where(NotationPrestataire.prestataire_id == prestataire_id)
    q = q.order_by(NotationPrestataire.cree_le.desc())
    mois_debut = mois_debut_exercice(session)
    return [_lire(session, n, _, mois_debut) for n in session.exec(q).all()]


@router.post("/notations", response_model=NotationRead, status_code=201)
def create_notation(
    body: NotationCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    ou_404(session, Prestataire, body.prestataire_id, "Prestataire")
    if body.ticket_id is not None:
        _affaire_pour_avis(session, user, body.prestataire_id, body.ticket_id, body.confirmer_ajout)
    n = NotationPrestataire(
        prestataire_id=body.prestataire_id,
        note=NOTE_DE_ETAT[body.etat],
        commentaire=body.commentaire,
        contrat_id=body.contrat_id,
        ticket_id=body.ticket_id,
        auteur_id=user.id,
    )
    session.add(n)
    session.commit()
    session.refresh(n)
    return _lire(session, n, user, mois_debut_exercice(session))


class NotationUpdate(BaseModel):
    etat: Optional[Literal["mauvais", "neutre", "excellent"]] = None
    commentaire: Optional[str] = None
    ticket_id: Optional[int] = None
    confirmer_ajout: bool = False


@router.patch("/notations/{n_id}", response_model=NotationRead)
def update_notation(
    n_id: int,
    body: NotationUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """L'auteur corrige son avis — l'état, le commentaire, l'affaire (15/11/2026).

    Seul l'auteur : un autre membre ne réécrit pas l'avis d'un collègue (il peut le retirer).
    """
    n = ou_404(session, NotationPrestataire, n_id, "Notation")
    if not est_auteur(n, user):
        raise HTTPException(403, "Seul l'auteur de l'avis peut le modifier")
    champs = body.model_fields_set
    if "ticket_id" in champs and body.ticket_id is not None:
        _affaire_pour_avis(session, user, n.prestataire_id, body.ticket_id, body.confirmer_ajout)
    if "etat" in champs and body.etat is not None:
        n.note = NOTE_DE_ETAT[body.etat]
    if "commentaire" in champs:
        n.commentaire = body.commentaire
    if "ticket_id" in champs:
        n.ticket_id = body.ticket_id
    if n.note == 1 and not (n.commentaire or "").strip():
        raise HTTPException(422, "Un avis « Mauvais » doit être justifié par un commentaire")
    session.add(n)
    session.commit()
    session.refresh(n)
    return _lire(session, n, user, mois_debut_exercice(session))


@router.delete("/notations/{n_id}", status_code=204)
def delete_notation(
    n_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    n = ou_404(session, NotationPrestataire, n_id, "Notation")
    session.delete(n)
    session.commit()


class AffaireAvis(BaseModel):
    """Une affaire qu'on peut juger — `intervient` dit si le prestataire y figure déjà."""

    id: int
    numero: str
    titre: str
    statut: str
    intervient: bool
    intervenants: str


@router.get("/affaires-a-noter", response_model=list[AffaireAvis])
def lire_affaires_a_noter(
    prestataire_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Toutes les affaires de la copropriété : d'abord celles où le prestataire intervient,
    puis les autres, chaque groupe de la plus récente à la plus ancienne (15/11/2026).

    Pour noter le couple prestataire / affaire, même quand il n'y figure pas encore : ce
    choix-là exige la confirmation de l'ajout. La recherche détaillée (suivi, messages,
    pièces) est celle de la page Affaires, `GET /tickets/recherche` : elle n'est pas
    refaite ici, et l'écran la croise avec cette liste."""
    ou_404(session, Prestataire, prestataire_id, "Prestataire")
    affaires = session.exec(select(Ticket).order_by(col(Ticket.id).desc())).all()
    listes = par_affaire(session, affaires)
    lignes = [
        AffaireAvis(
            id=t.id,
            numero=t.numero,
            titre=t.titre,
            statut=valeur(t.statut),
            intervient=prestataire_id in listes[t.id],
            intervenants=", ".join(noms(session, listes[t.id])),
        )
        for t in affaires
    ]
    #  Tri stable : l'ordre de récence se garde dans chaque groupe.
    return sorted(lignes, key=lambda a: not a.intervient)


# ── Le récapitulatif par intervention (R3d, 15/11/2026) ─────────────────────


class Intervention(BaseModel):
    """Une affaire du prestataire, et les avis portés sur ce couple (aucun : « non notée »)."""

    ticket_id: int
    numero: str
    titre: str
    date: datetime
    avis: list[NotationRead] = []


class ExerciceInterventions(BaseModel):
    """Un exercice comptable : ses interventions, ses avis sans affaire, le compte des états."""

    annee: int
    libelle: str
    nb_interventions: int = 0
    nb_notees: int = 0
    compte: dict[str, int] = {}
    interventions: list[Intervention] = []
    avis_generaux: list[NotationRead] = []


@router.get("/{p_id}/interventions", response_model=list[ExerciceInterventions])
def lire_interventions(
    p_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Les interventions du prestataire rangées par exercice, le plus récent d'abord (R3d).

    Une intervention est une affaire où il est intervenant désigné — ou qu'un avis juge :
    retiré de l'affaire ensuite, il garde l'avis qu'on y a porté. Elle se range dans
    l'exercice de son OUVERTURE ; un avis sans affaire, dans celui de sa date. La règle de
    l'exercice est celle des métriques (`exercice_de`) : l'écran ne la recopie pas."""
    ou_404(session, Prestataire, p_id, "Prestataire")
    mois_debut = mois_debut_exercice(session)
    notations = session.exec(
        select(NotationPrestataire)
        .where(NotationPrestataire.prestataire_id == p_id)
        .order_by(col(NotationPrestataire.cree_le).desc())
    ).all()
    lues = [_lire(session, n, user, mois_debut) for n in notations]
    affaires = {t.id: t for t in affaires_du_prestataire(session, p_id)}
    for nr in lues:
        if nr.ticket_id is not None and nr.ticket_id not in affaires:
            if (t := ou_rien(session, Ticket, nr.ticket_id)) is not None:
                affaires[t.id] = t
    exercices: dict[int, ExerciceInterventions] = {}

    def exercice(jour) -> ExerciceInterventions:
        ex = exercice_de(horloge.jour_civil(jour), mois_debut)
        if ex.annee not in exercices:
            exercices[ex.annee] = ExerciceInterventions(annee=ex.annee, libelle=ex.libelle)
        return exercices[ex.annee]

    for t in sorted(affaires.values(), key=lambda t: t.cree_le, reverse=True):
        avis = [nr for nr in lues if nr.ticket_id == t.id]
        ex = exercice(t.cree_le)
        ex.interventions.append(
            Intervention(ticket_id=t.id, numero=t.numero, titre=t.titre, date=t.cree_le, avis=avis)
        )
    for nr in lues:
        if nr.ticket_id is None or nr.ticket_id not in affaires:
            exercice(nr.cree_le).avis_generaux.append(nr)
    for ex in exercices.values():
        ex.nb_interventions = len(ex.interventions)
        ex.nb_notees = sum(1 for i in ex.interventions if i.avis)
        tous = [a for i in ex.interventions for a in i.avis] + ex.avis_generaux
        ex.compte = {e: sum(1 for a in tous if a.etat == e) for e in ETATS}
    return sorted(exercices.values(), key=lambda e: e.annee, reverse=True)
