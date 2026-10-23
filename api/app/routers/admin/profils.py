"""Admin — Workflow de validation des demandes de modification de profil.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.utils.batiments import libelle_batiment_ou
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Batiment,
    DemandeModificationProfil,
    StatutDemandeProfil,
    StatutUtilisateur,
    Utilisateur,
)
from app.utils import horloge
from app.utils.noms import nom_affiche
from app.utils.recuperer import ou_404
from app.utils.cloche import sonner_systeme
from app.utils.journal_securite import journaliser_securite
from app.utils.roles_du_statut import poser_roles_du_statut
from app.utils.demandes_profil import lire_demande
from app.utils.valeurs import valeur

router = APIRouter()


# ── Demandes de modification de profil ─────────────────────────────────


@router.get("/demandes-profil")
def list_demandes_profil(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste toutes les demandes de modification de profil en attente."""
    demandes = session.exec(
        select(DemandeModificationProfil)
        .where(DemandeModificationProfil.statut_demande == StatutDemandeProfil.en_attente)
        .order_by(DemandeModificationProfil.cree_le)
    ).all()
    result = []
    for d in demandes:
        utilisateur = session.get(Utilisateur, d.utilisateur_id)
        item = lire_demande(session, d).model_dump()
        item["utilisateur_nom"] = (
            nom_affiche(utilisateur.prenom, utilisateur.nom) if utilisateur else "?"
        )
        item["utilisateur_email"] = utilisateur.email if utilisateur else None
        item["statut_actuel"] = valeur(utilisateur.statut) if utilisateur else None
        item["batiment_actuel"] = libelle_batiment_ou(
            session.get(Batiment, utilisateur.batiment_id)
            if utilisateur and utilisateur.batiment_id
            else None,
            None,
        )
        result.append(item)
    return result


class DemandeProfilAction(BaseModel):
    action: str  # approuver | rejeter
    motif_refus: str | None = None


@router.post("/demandes-profil/{demande_id}/traiter")
def traiter_demande_profil(
    demande_id: int,
    body: DemandeProfilAction,
    session: Session = Depends(get_session),
    cs: Utilisateur = Depends(require_cs_or_admin),
):
    demande = ou_404(session, DemandeModificationProfil, demande_id, "Demande")
    if demande.statut_demande != StatutDemandeProfil.en_attente:
        raise HTTPException(400, "Cette demande a déjà été traitée.")

    utilisateur = ou_404(session, Utilisateur, demande.utilisateur_id, "Utilisateur")

    if body.action == "approuver":
        if demande.statut_souhaite:
            utilisateur.statut = StatutUtilisateur(demande.statut_souhaite)
            #  🔴 Les rôles suivent le statut (#2161) : `require_proprietaire` lit
            #  les RÔLES. Un copropriétaire devenu locataire gardait le rôle
            #  `propriétaire`, et tout ce qu'il ouvre. Chaque rôle qui change est
            #  un geste sensible : il va au journal de sécurité.
            ajoutes, retires = poser_roles_du_statut(utilisateur, utilisateur.statut)
            for role in sorted(ajoutes):
                journaliser_securite(
                    "role_ajoute", acteur_id=cs.id, cible_id=utilisateur.id, detail=role
                )
            for role in sorted(retires):
                journaliser_securite(
                    "role_retire", acteur_id=cs.id, cible_id=utilisateur.id, detail=role
                )
        if demande.batiment_id_souhaite:
            utilisateur.batiment_id = demande.batiment_id_souhaite
        demande.statut_demande = StatutDemandeProfil.approuvee
        sonner_systeme(
            session,
            "compte",
            destinataire_id=utilisateur.id,
            type="system",
            titre="Modification de profil approuvée",
            corps="Votre demande de modification de profil a été approuvée.",
            lien="/profil",
        )
    elif body.action == "rejeter":
        demande.statut_demande = StatutDemandeProfil.rejetee
        demande.motif_refus = body.motif_refus
        sonner_systeme(
            session,
            "compte",
            destinataire_id=utilisateur.id,
            type="system",
            titre="Modification de profil refusée",
            corps=body.motif_refus or "Votre demande de modification de profil a été refusée.",
            lien="/profil",
        )
    else:
        raise HTTPException(400, "Action invalide (approuver | rejeter)")

    demande.traite_par_id = cs.id
    demande.traite_le = horloge.maintenant()
    session.add(demande)
    session.add(utilisateur)
    session.commit()
    return {"statut": demande.statut_demande}
