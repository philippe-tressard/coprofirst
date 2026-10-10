"""Router signalements — modération Communauté.

Un membre de la Communauté peut signaler un contenu inapproprié (idée, annonce,
sondage) ou une réponse/commentaire. Les signalements alimentent une file de
modération visible du conseil syndical et des admins, qui peuvent la traiter ou
la rejeter (la suppression du contenu et le bannissement restent gérés par les
contrôles existants).
"""

from app.utils import horloge

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    CommentaireSondage,
    Idee,
    PetiteAnnonce,
    ReponseCommunaute,
    Signalement,
    Sondage,
    Utilisateur,
)
from app.utils.communaute import exiger_acces
from app.utils.noms import nom_affiche, nom_auteur
from app.utils.destinataires import membres_cs_ou_admin
from app.utils.liens import lien_element, lien_sondage
from app.utils.recuperer import ou_404, present_ou_404
from app.utils.cloche import sonner_systeme

router = APIRouter(prefix="/signalements", tags=["signalements"])

# Types de cible autorisés + libellé lisible pour la file de modération.
_CIBLE_LABELS = {
    "idee": "Idée",
    "annonce": "Annonce",
    "sondage": "Sondage",
    "reponse": "Réponse",
    "commentaire": "Commentaire",
}


def _lien_cible(cible_type: str, cible_id: int) -> str:
    """Lien profond vers le contenu signalé, dans le bon onglet de la Communauté.

    Les réponses et commentaires n'ont pas d'ancre propre : ils s'affichent sous
    leur idée / annonce / sondage, dont on ne connaît pas l'id ici. Le lien reste
    alors la page — c'est déjà la rubrique, pas une route inexistante.
    """
    if cible_type in ("idee", "annonce"):
        #  La table décide de la rubrique et de son adresse : ces deux liens étaient
        #  fabriqués à la main, et ils ont survécu tels quels au passage aux URL
        #  dédiées (05/09/2026) — c'est exactement ce que `liens.py` existe pour
        #  éviter, et ce que la table a corrigé partout ailleurs en une ligne.
        return lien_element(cible_type, cible_id)
    if cible_type == "sondage":
        return lien_sondage(cible_id)
    return lien_sondage()


def _resoudre_cible(cible_type: str, cible_id: int, session: Session):
    """Retourne (apercu, auteur_cible_id) pour la cible, ou (None, None) si absente."""
    if cible_type == "idee":
        o = session.get(Idee, cible_id)
        return (o.titre, o.auteur_id) if o else (None, None)
    if cible_type == "annonce":
        o = session.get(PetiteAnnonce, cible_id)
        return (o.titre, o.auteur_id) if o else (None, None)
    if cible_type == "sondage":
        o = session.get(Sondage, cible_id)
        return (o.question, o.auteur_id) if o else (None, None)
    if cible_type == "reponse":
        o = session.get(ReponseCommunaute, cible_id)
        return (o.contenu[:140], o.auteur_id) if o else (None, None)
    if cible_type == "commentaire":
        o = session.get(CommentaireSondage, cible_id)
        return (o.contenu[:140], o.auteur_id) if o else (None, None)
    return (None, None)


class SignalementCreate(BaseModel):
    cible_type: str
    cible_id: int
    motif: str


@router.post("", status_code=201)
def creer_signalement(
    body: SignalementCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    if body.cible_type not in _CIBLE_LABELS:
        raise HTTPException(422, "Type de contenu invalide")
    motif = (body.motif or "").strip()
    if not motif:
        raise HTTPException(422, "Le motif du signalement est obligatoire")
    apercu, auteur_cible_id = _resoudre_cible(body.cible_type, body.cible_id, session)
    apercu = present_ou_404(apercu, "Contenu introuvable")

    # Anti-doublon : un seul signalement en attente par utilisateur et par contenu.
    existant = session.exec(
        select(Signalement).where(
            Signalement.cible_type == body.cible_type,
            Signalement.cible_id == body.cible_id,
            Signalement.signale_par_id == user.id,
            Signalement.statut == "en_attente",
        )
    ).first()
    if existant:
        raise HTTPException(409, "Vous avez déjà signalé ce contenu")

    sig = Signalement(
        cible_type=body.cible_type,
        cible_id=body.cible_id,
        apercu=apercu or "",
        auteur_cible_id=auteur_cible_id,
        signale_par_id=user.id,
        motif=motif,
    )
    session.add(sig)

    # Notifier les CS/admin (in-app) de l'arrivée d'un signalement.
    cs_members = membres_cs_ou_admin(session)
    for m in cs_members:
        if m.id != user.id:
            sonner_systeme(
                session,
                "moderation",
                destinataire_id=m.id,
                type="moderation",
                titre="Nouveau signalement à modérer",
                corps=f"{_CIBLE_LABELS[body.cible_type]} — {motif[:150]}",
                # Le modérateur doit atterrir sur le contenu signalé, pas sur
                # l'onglet Sondages par défaut (cf. flux.py, même correctif).
                lien=_lien_cible(body.cible_type, body.cible_id),
            )

    session.commit()
    session.refresh(sig)
    return {"id": sig.id, "statut": sig.statut}


def _enrich(sig: Signalement, session: Session) -> dict:
    signaleur = session.get(Utilisateur, sig.signale_par_id)
    auteur = session.get(Utilisateur, sig.auteur_cible_id) if sig.auteur_cible_id else None
    return {
        "id": sig.id,
        "cible_type": sig.cible_type,
        "cible_type_label": _CIBLE_LABELS.get(sig.cible_type, sig.cible_type),
        "cible_id": sig.cible_id,
        "apercu": sig.apercu,
        "motif": sig.motif,
        "statut": sig.statut,
        "cree_le": sig.cree_le,
        "signale_par": nom_affiche(signaleur.prenom, signaleur.nom) if signaleur else "Inconnu",
        "auteur_cible": nom_auteur(auteur),
        "auteur_cible_id": sig.auteur_cible_id,
    }


@router.get("")
def liste_signalements(
    statut: str = "en_attente",
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """File de modération (CS/admin). statut = en_attente | traite | rejete | tous."""
    stmt = select(Signalement).order_by(Signalement.cree_le.desc())
    if statut != "tous":
        stmt = stmt.where(Signalement.statut == statut)
    sigs = session.exec(stmt).all()
    return [_enrich(s, session) for s in sigs]


@router.get("/count")
def compter_en_attente(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    n = len(session.exec(select(Signalement).where(Signalement.statut == "en_attente")).all())
    return {"en_attente": n}


class SignalementResolve(BaseModel):
    statut: str  # traite | rejete


@router.patch("/{sig_id}")
def resoudre_signalement(
    sig_id: int,
    body: SignalementResolve,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    if body.statut not in ("traite", "rejete"):
        raise HTTPException(422, "Statut invalide")
    sig = ou_404(session, Signalement, sig_id, "Signalement")
    sig.statut = body.statut
    sig.traite_par_id = user.id
    sig.traite_le = horloge.maintenant()
    session.add(sig)
    session.commit()
    return {"id": sig.id, "statut": sig.statut}
