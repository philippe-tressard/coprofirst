"""Demander la suppression de SON compte — et la traiter (#2699, arbitrages du 12/11/2026).

## Pourquoi

La revue de l'App Store (règle 5.1.1 v) exige qu'une app qui ouvre des comptes
permette d'en LANCER la suppression depuis l'app. Jusque-là, seul l'administrateur
supprimait un compte, et le droit à l'effacement passait par courriel (#772).

## Les règles arbitrées

1. **Une demande, traitée par l'administration** — jamais un effacement immédiat :
   un compte porte des lots, des badges, des délégations.
2. **Le mot de passe est exigé à la demande** (comme le changement d'adresse,
   #1549) : une session volée ne suffit pas. Pas de lien par courriel — la demande
   se retire, ce n'est pas l'effacement.
3. **Aucun délai de rétractation** : l'administration peut traiter dès la
   création ; la personne peut retirer sa demande jusque-là.
   `DELAI_TRAITEMENT_JOURS` est le délai MAXIMAL annoncé, pas une attente.
4. **Le traitement est la purge existante** (`suppression_compte.supprimer_compte`,
   celle de `DELETE /admin/utilisateurs/{id}`), inchangée. Ce qu'elle efface et ce
   qu'elle garde sans nom est dit à la personne AVANT qu'elle demande
   (`CONSEQUENCES`), servi par l'API : le site et l'app iOS lisent le même texte.
5. **La démonstration accepte la demande et n'efface jamais** (`demo.est_demo`) :
   ses comptes sont partagés et publiés — la revue d'Apple y voit le geste aboutir.

Journal de sécurité : demande créée, retirée, traitée — un identifiant, jamais une
adresse. Après l'effacement, la ligne du journal est la seule trace qui reste.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.jwt import verify_password
from app.models.core import Utilisateur
from app.models.validations import DemandeSuppressionCompte, StatutDemandeSuppression
from app.utils import demo, horloge
from app.utils.annonce_compte import Annonce
from app.utils.cloche import sonner_systeme
from app.utils.delais_rgpd import DELAI_TRAITEMENT_DEMANDE_JOURS
from app.utils.destinataires import site_manager_user_id
from app.utils.journal_securite import journaliser_securite
from app.utils.lecture import lire_objet
from app.utils.noms import nom_affiche
from app.utils.recuperer import ou_404, present_ou_404
from app.utils.suppression_compte import supprimer_compte

#: Le délai maximal annoncé pour traiter une demande. La politique de
#: confidentialité le compose de la même constante (`utils/delais_rgpd`,
#: `seed/contenus_legaux_suppression`) : il ne peut pas diverger.
DELAI_TRAITEMENT_JOURS = DELAI_TRAITEMENT_DEMANDE_JOURS

#: Ce que la personne lit AVANT de confirmer — le site et l'app iOS le lisent ici.
#: Il dit ce que fait `supprimer_compte`, et rien d'autre : les contenus gardés
#: sans nom sont ceux de `suppression_compte.CONTENUS_GARDES` (#1688, #1821).
CONSEQUENCES: tuple[str, ...] = (
    "Votre compte et vos données personnelles sont effacés : profil, liens à vos lots, "
    "badges et demandes, notifications, sessions, petites annonces, avis, délégations "
    "et mandats.",
    "Ce que vous avez écrit dans la vie collective de la résidence — affaires et leurs "
    "messages, votes, soutiens, réponses dans les échanges, documents publiés — reste, "
    "sans votre nom : il est attribué à « Ancien résident ».",
    "L'effacement est définitif. Vous pouvez retirer votre demande tant que "
    "l'administration ne l'a pas traitée.",
    f"L'administration de la résidence la traite sous {DELAI_TRAITEMENT_JOURS} jours au plus.",
)

DEJA_OUVERTE = "Une demande de suppression est déjà en cours."
MOT_DE_PASSE_INCORRECT = "Mot de passe incorrect."
PAS_OUVERTE = "Cette demande n'est plus en cours."


class DemandeSuppressionRead(BaseModel):
    """Une demande de suppression, telle que la personne et l'administration la lisent."""

    id: int
    statut: StatutDemandeSuppression
    cree_le: datetime
    traitee_le: Optional[datetime] = None
    #: Servi, jamais recopié par un client : le délai maximal annoncé.
    delai_annonce_jours: int = DELAI_TRAITEMENT_JOURS

    class Config:
        from_attributes = True


class EtatDemandeSuppression(BaseModel):
    """`GET /auth/demande-suppression` : ma demande en cours (ou rien), et ce qu'il faut savoir avant."""

    demande: Optional[DemandeSuppressionRead] = None
    delai_annonce_jours: int = DELAI_TRAITEMENT_JOURS
    consequences: list[str]


class DemandeSuppressionEnAttente(DemandeSuppressionRead):
    """Une demande de la file de l'administration : la demande, et qui la fait."""

    utilisateur_id: int
    utilisateur_nom: str
    utilisateur_email: Optional[str] = None
    motif: Optional[str] = None


class DemandeSuppressionTraitee(BaseModel):
    """`POST /admin/demandes-suppression/{id}/traiter` : le nouvel état, et la phrase à afficher."""

    statut: StatutDemandeSuppression
    compte_efface: bool
    annonce: Annonce


def lire(demande: DemandeSuppressionCompte) -> DemandeSuppressionRead:
    return lire_objet(DemandeSuppressionRead, demande)


def demande_ouverte(session: Session, user_id: int) -> Optional[DemandeSuppressionCompte]:
    """La demande en cours de ce compte, ou None — il n'y en a jamais deux."""
    return session.exec(
        select(DemandeSuppressionCompte).where(
            DemandeSuppressionCompte.utilisateur_id == user_id,
            DemandeSuppressionCompte.statut == StatutDemandeSuppression.ouverte.value,
        )
    ).first()


def etat(session: Session, user: Utilisateur) -> EtatDemandeSuppression:
    ouverte = demande_ouverte(session, user.id)
    return EtatDemandeSuppression(
        demande=lire(ouverte) if ouverte else None, consequences=list(CONSEQUENCES)
    )


def deposer_demande(
    session: Session,
    user: Utilisateur,
    mot_de_passe: str,
    motif: Optional[str],
    background_tasks: BackgroundTasks,
) -> DemandeSuppressionCompte:
    """Crée la demande de `user` ; 400 si le mot de passe est faux, 409 si une est déjà en cours."""
    if not verify_password(mot_de_passe or "", user.hashed_password or ""):
        journaliser_securite("connexion_refusee", cible_id=user.id, detail="demande de suppression")
        raise HTTPException(400, MOT_DE_PASSE_INCORRECT)
    if demande_ouverte(session, user.id):
        raise HTTPException(409, DEJA_OUVERTE)

    demande = DemandeSuppressionCompte(utilisateur_id=user.id, motif=(motif or "").strip() or None)
    session.add(demande)
    gestionnaire = site_manager_user_id(session)
    if gestionnaire and gestionnaire != user.id:
        sonner_systeme(
            session,
            "suppression_compte",
            destinataire_id=gestionnaire,
            type="system",
            titre="Demande de suppression de compte",
            corps=f"À traiter sous {DELAI_TRAITEMENT_JOURS} jours au plus.",
            lien="/admin",
        )
    session.commit()
    session.refresh(demande)
    journaliser_securite("suppression_demandee", acteur_id=user.id, cible_id=user.id)

    from app.utils.email import send_email as _send_email

    #  L'accusé de réception part sans `destinataire_id` : aucune préférence ne le
    #  coupe. Sur un compte volé, c'est lui qui prévient le titulaire.
    background_tasks.add_task(
        _send_email,
        code="suppression_compte_demandee",
        to=user.email,
        context={
            "destinataire": {"prenom": user.prenom},
            "delai_jours": DELAI_TRAITEMENT_JOURS,
        },
    )
    return demande


def retirer(session: Session, user: Utilisateur) -> None:
    """La personne retire sa demande en cours ; 404 s'il n'y en a pas."""
    demande = present_ou_404(
        demande_ouverte(session, user.id), "Aucune demande de suppression en cours."
    )
    demande.statut = StatutDemandeSuppression.retiree.value
    demande.retiree_le = horloge.maintenant()
    session.add(demande)
    session.commit()
    journaliser_securite("suppression_retiree", acteur_id=user.id, cible_id=user.id)


def file_d_attente(session: Session) -> list[DemandeSuppressionEnAttente]:
    """Les demandes en cours, la plus ancienne d'abord — le délai court depuis elle."""
    demandes = session.exec(
        select(DemandeSuppressionCompte)
        .where(DemandeSuppressionCompte.statut == StatutDemandeSuppression.ouverte.value)
        .order_by(DemandeSuppressionCompte.cree_le)
    ).all()
    file = []
    for d in demandes:
        u = session.get(Utilisateur, d.utilisateur_id)
        file.append(
            lire_objet(
                DemandeSuppressionEnAttente,
                d,
                utilisateur_nom=nom_affiche(u.prenom, u.nom) if u else "?",
                utilisateur_email=u.email if u else None,
            )
        )
    return file


def nb_en_attente(session: Session) -> int:
    return len(
        session.exec(
            select(DemandeSuppressionCompte.id).where(
                DemandeSuppressionCompte.statut == StatutDemandeSuppression.ouverte.value
            )
        ).all()
    )


def traiter(
    session: Session, demande_id: int, admin: Utilisateur, background_tasks: BackgroundTasks
) -> DemandeSuppressionTraitee:
    """Efface le compte qui l'a demandé, par la purge de l'administration — sauf en démo."""
    demande = ou_404(session, DemandeSuppressionCompte, demande_id, "Demande")
    if demande.statut != StatutDemandeSuppression.ouverte.value:
        raise HTTPException(409, PAS_OUVERTE)
    user_id = demande.utilisateur_id
    if user_id == admin.id:
        raise HTTPException(400, "Votre propre demande se traite par un autre administrateur.")
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")

    demande.statut = StatutDemandeSuppression.traitee.value
    demande.traitee_le = horloge.maintenant()
    demande.traitee_par_id = admin.id
    session.add(demande)

    if demo.est_demo():
        #  Règle 5 : la démonstration montre le geste, ses comptes restent.
        session.commit()
        journaliser_securite(
            "suppression_traitee", acteur_id=admin.id, cible_id=user_id, detail="démonstration"
        )
        return DemandeSuppressionTraitee(
            statut=StatutDemandeSuppression.traitee,
            compte_efface=False,
            annonce=Annonce(
                ton="info",
                texte="Démonstration : la demande est traitée, le compte est conservé.",
            ),
        )

    adresse, prenom = user.email, user.prenom
    #  La ligne de la demande part avec le compte (`CONTENUS_PERSONNELS`).
    supprimer_compte(session, user_id)
    session.commit()
    journaliser_securite("suppression_traitee", acteur_id=admin.id, cible_id=user_id)
    journaliser_securite("compte_supprime", acteur_id=admin.id, cible_id=user_id)

    from app.utils.email import send_email as _send_email

    #  Le dernier courriel : le compte n'existe plus, seule l'adresse lue avant reste.
    background_tasks.add_task(
        _send_email,
        code="suppression_compte_effectuee",
        to=adresse,
        context={"destinataire": {"prenom": prenom}},
    )
    return DemandeSuppressionTraitee(
        statut=StatutDemandeSuppression.traitee,
        compte_efface=True,
        annonce=Annonce(ton="success", texte="Compte supprimé."),
    )
