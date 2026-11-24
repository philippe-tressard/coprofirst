"""Le cycle de vie d'un bail — le créer, le lire, le corriger, le terminer.

Y est jointe la RECHERCHE d'un locataire inscrit : elle ne sert qu'ici, au
moment de rattacher un compte à un bail qu'on crée ou qu'on corrige.

⚠️ `ObjetOut` et `BailOut` viennent de `commun` : ce sont les schémas que les
quatre modules partagent. Les redéclarer donnerait deux formes de la même
réponse, libres de diverger au premier champ ajouté.
"""

import re
from typing import List, Optional

from app.utils import horloge

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.auth.adresse_compte import adresse_masquee, compte_par_adresse
from app.auth.deps import require_cs_or_admin, require_proprietaire
from app.database import get_session
from app.models.core import (
    LocationBail,
    RemiseObjet,
    StatutBail,
    Utilisateur,
)
from app.utils.lecture import lire_objet
from app.utils.limiter import LIMITE_RECHERCHE_DE_PERSONNES, limiter
from app.utils.recuperer import ou_404, ou_rien, present_ou_404
from app.schemas_nom_servi import NomServi

from .commun import BailCreateMulti, BailOut, BailTerminer, BailUpdate
from app.utils.acces_bail import adopter_declares, rendre_au_bailleur
from app.auth.appartenance import (
    clause_locataire_designable,
    est_locataire_designable,
    exiger_bail_du_bailleur,
    exiger_lot_du_bailleur,
)

router = APIRouter()

# ── Routes baux ──────────────────────────────────────────────────────────────


@router.get("/mes-baux", response_model=List[BailOut])
def mes_baux(
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    baux = session.exec(
        select(LocationBail)
        .where(LocationBail.bailleur_id == user.id)
        .order_by(LocationBail.cree_le.desc())
    ).all()
    return baux


@router.get("/tous-les-baux", response_model=List[BailOut])
def tous_les_baux(
    user: Utilisateur = Depends(require_cs_or_admin),
    session: Session = Depends(get_session),
):
    """Admin / CS : liste de tous les baux (tous statuts, tous bailleurs)."""
    return session.exec(select(LocationBail).order_by(LocationBail.cree_le.desc())).all()


@router.delete("/baux/{bail_id}", status_code=204)
def supprimer_bail(
    bail_id: int,
    user: Utilisateur = Depends(require_cs_or_admin),
    session: Session = Depends(get_session),
):
    """Admin / CS : supprimer un bail et ses objets associés."""
    bail = ou_404(session, LocationBail, bail_id, "Bail")
    #  Libérer les accès confiés au locataire — la même règle qu'à la fin du bail.
    rendre_au_bailleur(session, bail)
    # Supprimer les objets remis
    for obj in session.exec(select(RemiseObjet).where(RemiseObjet.bail_id == bail_id)).all():
        session.delete(obj)
    session.delete(bail)
    session.commit()


#  🔴 `POST /bailleur/lots/{lot_id}/bail` A ÉTÉ RETIRÉ le 12/09/2026 (#932).
#
#  C'était `creer_bail_multi` **recopié pour un seul lot** : même garde « ce lot
#  a déjà un bail en cours », même construction du `LocationBail`, à la boucle
#  près. Deux copies d'un même invariant divergent, et celle-ci n'avait aucun
#  appelant — masquée dans le relevé par l'homonyme `creerBailMulti`.
#
#  Créer un bail sur UN lot, c'est `POST /bailleur/baux/creer-multi` avec un seul
#  `lot_ids`. Une seule garde, une seule construction.


def _exiger_locataire(
    session: Session, locataire_id: Optional[int], *, deja: Optional[int] = None
) -> None:
    """Le compte désigné comme locataire est de ceux que la recherche rendrait — **404** sinon.

    Le locataire d'un bail devient porteur des badges remis à CE lot (#1535). Le
    bailleur le choisit parmi ce que la recherche lui ouvre (`search-locataire`,
    ses suggestions) : un compte locataire, jamais un compte technique —
    `appartenance.est_locataire_designable`, la même règle. Hors de ce périmètre,
    la réponse est celle d'un compte inexistant (claude-config#656).

    `deja` : le locataire que le bail porte déjà. L'écran de correction le renvoie
    avec chaque modification ; il a pu y être rattaché par le serveur
    (`auto_match_service`, `rattachement_bailleur`) ou changer de statut depuis —
    ce n'est pas une désignation nouvelle, et il reste admis.
    """
    if locataire_id is None or locataire_id == deja:
        return
    compte = ou_rien(session, Utilisateur, locataire_id)
    designable = compte is not None and est_locataire_designable(session, compte.id)
    present_ou_404(compte if designable else None, "Locataire introuvable")


@router.post("/baux/creer-multi", response_model=List[BailOut], status_code=201)
@limiter.limit(LIMITE_RECHERCHE_DE_PERSONNES)
def creer_bail_multi(
    request: Request,
    data: BailCreateMulti,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Créer un bail sur plusieurs lots en une seule opération."""
    if not data.lot_ids:
        raise HTTPException(status_code=422, detail="Au moins un lot est requis")

    #  🔒 « Ce lot est-il le vôtre ? » AVANT toute écriture, pour TOUS les lots :
    #  la demande est refusée entière, jamais un bail posé à moitié (#1535).
    lots = [exiger_lot_du_bailleur(session, lot_id, user) for lot_id in data.lot_ids]
    _exiger_locataire(session, data.locataire_id)

    created: List[LocationBail] = []
    now = horloge.maintenant()
    for lot in lots:
        bail_actif = session.exec(
            select(LocationBail).where(
                LocationBail.lot_id == lot.id,
                LocationBail.statut.in_([StatutBail.actif, StatutBail.en_cours_sortie]),
            )
        ).first()
        if bail_actif:
            raise HTTPException(
                status_code=409,
                detail=f"Le lot {lot.numero} a déjà un bail en cours",
            )
        bail = LocationBail(
            lot_id=lot.id,
            bailleur_id=user.id,
            locataire_id=data.locataire_id,
            locataire_nom=data.locataire_nom,
            locataire_prenom=data.locataire_prenom,
            locataire_email=data.locataire_email,
            locataire_telephone=data.locataire_telephone,
            date_entree=data.date_entree,
            date_sortie_prevue=data.date_sortie_prevue,
            notes=data.notes,
            statut=StatutBail.actif,
            cree_le=now,
            mis_a_jour_le=now,
        )
        session.add(bail)
        created.append(bail)
    session.flush()
    for bail in created:
        adopter_declares(session, bail)
    session.commit()
    for b in created:
        session.refresh(b)
    return created


@router.get("/baux/{bail_id}", response_model=BailOut)
def get_bail(
    bail_id: int,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    return exiger_bail_du_bailleur(session, bail_id, user)


@router.patch("/baux/{bail_id}", response_model=BailOut)
@limiter.limit(LIMITE_RECHERCHE_DE_PERSONNES)
def update_bail(
    request: Request,
    bail_id: int,
    data: BailUpdate,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    bail = exiger_bail_du_bailleur(session, bail_id, user)
    _exiger_locataire(session, data.locataire_id, deja=bail.locataire_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(bail, k, v)
    bail.mis_a_jour_le = horloge.maintenant()
    session.add(bail)
    session.commit()
    session.refresh(bail)
    return bail


@router.post("/baux/{bail_id}/terminer", response_model=BailOut)
def terminer_bail(
    bail_id: int,
    data: BailTerminer,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    bail = exiger_bail_du_bailleur(session, bail_id, user)
    #  Retour automatique de tous les accès confiés — la règle : `utils/acces_bail`.
    rendre_au_bailleur(session, bail)
    bail.statut = StatutBail.termine
    bail.date_sortie_reelle = data.date_sortie_reelle or horloge.aujourd_hui()
    bail.mis_a_jour_le = horloge.maintenant()
    session.add(bail)
    session.commit()
    session.refresh(bail)
    return bail


# ── Recherche locataire inscrit ────────────────────────────────────────────────


class LocataireInfo(NomServi):
    """Un compte locataire proposé au bailleur — son adresse MASQUÉE (#2153).

    L'adresse entière servait d'annuaire : tout copropriétaire balayait `q=aa`,
    `q=ab`… et repartait avec le nom et l'adresse de chaque compte. Masquée, elle
    suffit à distinguer deux homonymes ; le bailleur qui la connaît la saisit.
    """

    id: int
    nom: str
    prenom: str
    email_masque: str
    actif: bool

    class Config:
        from_attributes = True


def _info(u: Utilisateur) -> LocataireInfo:
    return lire_objet(LocataireInfo, u, email_masque=adresse_masquee(u.email))


#  « Ce compte peut-il être le locataire d'un bail ? » — `appartenance.clause_locataire_designable`
#  (#2153) : la recherche portait sur tous les comptes — conseil, administration,
#  syndic, autres copropriétaires. La recherche, ses suggestions et la désignation
#  au bail (`_exiger_locataire`) lisent la même règle.


@router.get("/locataires-suggeres", response_model=List[LocataireInfo])
def locataires_suggeres(
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Locataires inscrits qui ont déclaré ce bailleur dans leur nom_proprietaire.

    🔴 Sur le NOM du bailleur, mot pour mot (#2153). Un mot quelconque du prénom
    OU du nom, cherché comme sous-chaîne, suffisait : un bailleur prénommé
    « Jean » recevait tout locataire dont le propriétaire déclaré s'appelait
    « Jean … » — et son adresse avec.
    """
    mots_du_nom = {m for m in (user.nom or "").lower().split() if len(m) > 2}
    if not mots_du_nom:
        return []
    candidats = session.exec(
        select(Utilisateur).where(
            clause_locataire_designable(),
            Utilisateur.nom_proprietaire.isnot(None),  # type: ignore[attr-defined]
        )
    ).all()
    return [
        _info(u)
        for u in candidats
        if u.nom_proprietaire
        and mots_du_nom & set(re.findall(r"[\w-]+", u.nom_proprietaire.lower()))
    ]


@router.get("/search-locataire", response_model=List[LocataireInfo])
@limiter.limit(LIMITE_RECHERCHE_DE_PERSONNES)
def search_locataire(
    request: Request,
    q: str,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Chercher un compte LOCATAIRE par adresse exacte ou nom/prénom, pour un bail.

    🔴 Ni l'annuaire de la résidence, ni ses adresses (#2153) : seuls les comptes
    locataires sont cherchés, et leur adresse revient masquée. Jamais un compte
    technique (#1985) : il n'est le locataire de personne.
    """
    q = q.strip()
    if not q:
        return []
    if "@" in q:
        # Recherche exacte par email
        trouve = compte_par_adresse(session, q)
        ok = trouve is not None and est_locataire_designable(session, trouve.id)
        results = [trouve] if ok else []
    else:
        # Recherche partielle insensible à la casse par nom ou prénom
        pattern = f"%{q.lower()}%"
        results = session.exec(
            select(Utilisateur)
            .where((Utilisateur.nom.ilike(pattern)) | (Utilisateur.prenom.ilike(pattern)))
            .where(clause_locataire_designable())
            .limit(10)
        ).all()
    return [_info(u) for u in results]
