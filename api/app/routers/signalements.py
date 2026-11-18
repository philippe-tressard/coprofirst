"""Router signalements — la file de modération du conseil syndical.

Un résident signale un contenu inapproprié qu'il voit : une publication de la
Communauté (idée, annonce, sondage, réponse, commentaire), une affaire ou l'une de
ses suites, ou la réponse de l'assistant IA à une question au règlement (#2861).
Ce qui se signale, qui le voit, son aperçu et son lien : `utils/signalement_cibles`,
seul registre. Les signalements alimentent une file visible du conseil syndical et
des admins, qui les traitent ou les rejettent (la suppression du contenu et le
bannissement restent gérés par les contrôles existants).
"""

from app.utils import horloge

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import Signalement, Utilisateur
from app.utils.communaute import exiger_acces
from app.utils.noms import nom_affiche, nom_auteur
from app.utils.destinataires import membres_cs_ou_admin
from app.utils.recuperer import ou_404, present_ou_404
from app.utils.signalement_cibles import CIBLES, cible_lisible
from app.utils.cloche import sonner_systeme

router = APIRouter(prefix="/signalements", tags=["signalements"])


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
    cible = CIBLES.get(body.cible_type)
    if cible is None:
        raise HTTPException(422, "Type de contenu invalide")
    if cible.communaute:
        exiger_acces(user)
    motif = (body.motif or "").strip()
    if not motif:
        raise HTTPException(422, "Le motif du signalement est obligatoire")
    #  🔴 Ne signale que qui la voit (#2861) : un contenu invisible rend 404, comme
    #  un contenu absent — l'identifiant ne dit rien de plus.
    objet = present_ou_404(
        cible_lisible(session, body.cible_type, body.cible_id, user), "Contenu introuvable"
    )
    apercu, auteur_cible_id = cible.apercu(objet), cible.auteur_id(objet)

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
                corps=f"{cible.libelle} — {motif[:150]}",
                # Le modérateur doit atterrir sur le contenu signalé, pas sur
                # l'onglet Sondages par défaut (cf. flux.py, même correctif).
                lien=cible.lien(objet),
            )

    session.commit()
    session.refresh(sig)
    return {"id": sig.id, "statut": sig.statut}


def _enrich(sig: Signalement, session: Session) -> dict:
    cible = CIBLES.get(sig.cible_type)
    objet = session.get(cible.modele, sig.cible_id) if cible else None
    signaleur = session.get(Utilisateur, sig.signale_par_id)
    auteur = session.get(Utilisateur, sig.auteur_cible_id) if sig.auteur_cible_id else None
    return {
        "id": sig.id,
        "cible_type": sig.cible_type,
        "cible_type_label": cible.libelle if cible else sig.cible_type,
        "cible_id": sig.cible_id,
        "apercu": sig.apercu,
        "motif": sig.motif,
        "statut": sig.statut,
        "cree_le": sig.cree_le,
        "signale_par": nom_affiche(signaleur.prenom, signaleur.nom) if signaleur else "Inconnu",
        "auteur_cible": nom_auteur(auteur),
        "auteur_cible_id": sig.auteur_cible_id,
        #  Où le modérateur lit le contenu — calculé ici, jamais par l'écran ; `None`
        #  si le contenu a disparu depuis.
        "lien": cible.lien(objet) if cible and objet else None,
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
