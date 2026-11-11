"""Les accès (Vigik, télécommandes) qui suivent un bail — et la vue du locataire.

Un bailleur TRANSFÈRE ses badges au locataire pour la durée du bail, puis les
RÉCUPÈRE à la sortie. `mon-bail` est le pendant côté locataire : ce qu'il voit de
son propre bail, y compris les accès qui lui ont été confiés.

Depuis #1194 (23/09/2026), les badges d'un bailleur sont ceux dont il est
PORTEUR — ceux de ses lots (`utils/porteurs_acces`) —, et « remettre » met le
badge dans la main du locataire du bail (`utils/acces_bail`). Les jumeaux
vigik/télécommande qui doublaient chaque route sont fondus sur `TYPES_ACCES`.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.utils.batiments import libelle_batiment_ou
from app.auth.deps import get_current_user, require_proprietaire
from app.database import get_session
from app.models.core import LocationBail, Lot, Batiment, StatutBail, Utilisateur, StatutAcces
from pydantic import BaseModel
from app.auth.appartenance import exiger_bail_du_bailleur
from app.utils.acces_bail import confies, remettre, rendre_au_bailleur
from app.utils.etages import etage_label
from app.utils.lecture import lire_objet
from app.utils.libelles_lot import libelle_type_complet, libelle_type_lot
from app.utils.porteurs_acces import acces_de
from app.utils.types_acces import TYPES_ACCES
from app.utils.valeurs import valeur


router = APIRouter()


def _lot_info(
    lot_map: dict, session: Session, lot_id: Optional[int]
) -> tuple[Optional[str], Optional[str]]:
    """Le type d'un lot et son libellé « Bât. A — Lot 12 ».

    🔴 Cette fonction était écrite DEUX FOIS, à l'identique, dans ce fichier —
    une fermeture par endpoint (09/09/2026). Deux copies dans le même fichier ne
    se voient pas : elles sont à cinquante lignes l'une de l'autre, chacune sous
    son endpoint, et la relecture d'un endpoint ne montre jamais l'autre.

    Elles portaient à elles seules deux des onze écritures de « Bât. {numero} »
    que `utils/batiments` rassemble.

    ⚠️ Le repli « Sans bâtiment » reste ICI : c'est le seul des onze appelants à
    l'employer, et `libelle_batiment` ne l'impose à personne.
    """
    lot = lot_map.get(lot_id) if lot_id else None
    if not lot:
        return None, None
    lot_type = valeur(lot.type)
    bat = session.get(Batiment, lot.batiment_id) if lot.batiment_id else None
    return lot_type, f"{libelle_batiment_ou(bat, 'Sans bâtiment')} — Lot {lot.numero}"


# ── Accès (Vigik / Télécommandes) liés à un bail ────────────────────────────


class AccesOut(BaseModel):
    id: int
    code: str
    type: str  # vigik | telecommande
    lot_id: Optional[int]
    lot_type: Optional[str] = None
    #: Le type du lot en clair — « Appartement », « Cave » (#2507, `utils/libelles_lot`).
    lot_libelle_type: Optional[str] = None
    lot_label: Optional[str] = None
    statut: StatutAcces
    chez_locataire: bool
    bail_id: Optional[int]
    eligible_transfert: bool = False
    recommande: bool = False
    motif_non_eligible: Optional[str] = None
    cree_le: datetime

    class Config:
        from_attributes = True


class TransfertAccesIn(BaseModel):
    vigik_ids: List[int] = []
    tc_ids: List[int] = []


#: Le champ du corps de transfert qui porte les identifiants de chaque type —
#: le contrat du front, qui envoie `vigik_ids` et `tc_ids`.
_CHAMP_IDS = {"vigik": "vigik_ids", "telecommande": "tc_ids"}


def _sortie(session: Session, lot_map: dict, cle: str, o, **extra) -> AccesOut:
    """Un badge tel que les écrans du bail le lisent — une écriture pour les deux types."""
    lot_type, lot_label = _lot_info(lot_map, session, o.lot_id)
    return lire_objet(
        AccesOut,
        o,
        type=cle,
        lot_type=lot_type,
        lot_libelle_type=libelle_type_lot(lot_type) if lot_type else None,
        lot_label=lot_label,
        **extra,
    )


def _motif_non_transferable(cle: str, o, bail, nature_bail: str, lot_map: dict) -> Optional[str]:
    """Pourquoi ce badge ne peut pas partir avec ce bail — `None` s'il le peut.

    🔴 Écrite DEUX fois jusqu'au 23/09/2026 (#1194) — la liste et le transfert —,
    et elles divergeaient : la liste acceptait un Vigik posé sur un lot qui n'est
    ni un parking ni une cave, que le transfert refusait ensuite. La plus stricte
    prévaut.
    """
    if o.statut != StatutAcces.actif:
        return "Accès inactif"
    if o.chez_locataire and o.bail_id != bail.id:
        return "Déjà affecté à un autre bail"
    if cle == "vigik":
        if nature_bail != "appartement":
            return "Vigik non autorisé pour un bail parking/cave"
        lot = lot_map.get(o.lot_id) if o.lot_id else None
        if lot is not None and valeur(lot.type) != "appartement":
            return "Vigik uniquement issu d'un lot appartement"
    return None


def _nature_du_bail(session: Session, bail) -> str:
    lot = session.get(Lot, bail.lot_id)
    return valeur(lot.type) if lot else ""


@router.get("/mes-acces", response_model=List[AccesOut])
def mes_acces(
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Bailleur : ses badges — ceux de ses lots, confiés ou non (`utils/porteurs_acces`)."""
    lot_map = {lot.id: lot for lot in session.exec(select(Lot)).all()}
    return [
        _sortie(session, lot_map, t.cle, o)
        for t in TYPES_ACCES.values()
        for o in acces_de(session, t, user.id)
    ]


@router.get("/baux/{bail_id}/acces", response_model=List[AccesOut])
def acces_du_bail(
    bail_id: int,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Les badges du bailleur, avec ce qui les rend transférables à CE bail."""
    bail = exiger_bail_du_bailleur(session, bail_id, user)
    nature_bail = _nature_du_bail(session, bail)
    lot_map = {lot.id: lot for lot in session.exec(select(Lot)).all()}
    result = []
    for t in TYPES_ACCES.values():
        #  Bail parking/cave : pas de Vigik affiché (télécommandes seulement).
        if t.cle == "vigik" and nature_bail != "appartement":
            continue
        for o in acces_de(session, t, user.id):
            motif = _motif_non_transferable(t.cle, o, bail, nature_bail, lot_map)
            recommande = motif is None and not o.chez_locataire and o.lot_id in (None, bail.lot_id)
            result.append(
                _sortie(
                    session,
                    lot_map,
                    t.cle,
                    o,
                    eligible_transfert=motif is None,
                    recommande=recommande,
                    motif_non_eligible=motif,
                )
            )
    return result


@router.post("/baux/{bail_id}/transferer-acces", response_model=List[AccesOut])
def transferer_acces(
    bail_id: int,
    data: TransfertAccesIn,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Remettre des badges au locataire du bail — il les a désormais en main."""
    bail = exiger_bail_du_bailleur(session, bail_id, user)
    if bail.statut == StatutBail.termine:
        raise HTTPException(400, "Bail terminé — impossible de transférer des accès")
    nature_bail = _nature_du_bail(session, bail)
    lot_map = {lot.id: lot for lot in session.exec(select(Lot)).all()}
    updated = []
    for t in TYPES_ACCES.values():
        #  🔒 Seuls les badges dont le bailleur est PORTEUR : un identifiant
        #  quelconque glissé dans le corps est ignoré, comme avant.
        les_siens = {o.id: o for o in acces_de(session, t, user.id)}
        for oid in getattr(data, _CHAMP_IDS[t.cle]):
            o = les_siens.get(oid)
            if o is None:
                continue
            motif = _motif_non_transferable(t.cle, o, bail, nature_bail, lot_map)
            if motif:
                raise HTTPException(400, motif)
            remettre(o, bail)
            session.add(o)
            updated.append(_sortie(session, lot_map, t.cle, o))
    session.commit()
    return updated


@router.post("/baux/{bail_id}/recuperer-acces", response_model=List[AccesOut])
def recuperer_acces(
    bail_id: int,
    data: TransfertAccesIn = TransfertAccesIn(),
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Les badges du bail reviennent au bailleur — ceux désignés, ou tous.

    Si ``data.vigik_ids`` ou ``data.tc_ids`` sont fournis, seuls ces accès sont
    récupérés. Sinon tous les accès du bail le sont (comportement historique).
    """
    bail = exiger_bail_du_bailleur(session, bail_id, user)
    choix = None
    if data.vigik_ids or data.tc_ids:
        choix = {cle: getattr(data, champ) for cle, champ in _CHAMP_IDS.items()}
    lot_map = {lot.id: lot for lot in session.exec(select(Lot)).all()}
    rendus = rendre_au_bailleur(session, bail, choix)
    session.commit()
    return [_sortie(session, lot_map, cle, o) for cle, o in rendus]


# ── Vue locataire : voir les accès reçus de son bailleur ──────────────────────


@router.get("/mes-acces-recus", response_model=List[AccesOut])
def mes_acces_recus(
    user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Locataire : voir les Vigik/TC qui lui ont été confiés par son bailleur."""
    baux = session.exec(
        select(LocationBail).where(
            LocationBail.locataire_id == user.id,
            LocationBail.statut != StatutBail.termine,
        )
    ).all()
    return [_sortie(session, {}, cle, o) for b in baux for cle, o in confies(session, b.id)]


# ── Vue locataire : son bail actif ────────────────────────────────────────────


class BailLocataireOut(BaseModel):
    id: int
    lot_id: int
    lot_numero: Optional[str] = None
    lot_type: Optional[str] = None
    lot_type_appartement: Optional[str] = None
    #: Le type du lot et sa précision en clair — « Appartement – T3 » (#2507).
    lot_libelle_type_complet: Optional[str] = None
    lot_etage: Optional[int] = None
    #: L'étage en clair — « RDC », « 2ème », « SS 1 » ; vide sans étage (#2633).
    lot_etage_libelle: str = ""
    lot_superficie: Optional[float] = None
    lot_batiment_nom: Optional[str] = None
    bailleur_nom: str
    bailleur_prenom: str
    bailleur_email: Optional[str]
    bailleur_telephone: Optional[str]
    date_entree: date
    date_sortie_prevue: Optional[date]
    statut: StatutBail
    acces: List[AccesOut] = []

    class Config:
        from_attributes = True


@router.get("/mon-bail", response_model=Optional[BailLocataireOut])
def mon_bail(
    user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Locataire inscrit : voir son bail actif et les accès confiés par le bailleur."""
    bail = session.exec(
        select(LocationBail).where(
            LocationBail.locataire_id == user.id,
            LocationBail.statut != StatutBail.termine,
        )
    ).first()
    if not bail:
        return None
    bailleur = session.get(Utilisateur, bail.bailleur_id)
    bail_lot = session.get(Lot, bail.lot_id)
    bail_bat = (
        session.get(Batiment, bail_lot.batiment_id) if (bail_lot and bail_lot.batiment_id) else None
    )
    acces_list = [_sortie(session, {}, cle, o) for cle, o in confies(session, bail.id)]
    return lire_objet(
        BailLocataireOut,
        bail,
        lot_numero=bail_lot.numero if bail_lot else None,
        lot_type=valeur(bail_lot.type) if bail_lot else None,
        lot_type_appartement=bail_lot.type_appartement if bail_lot else None,
        lot_libelle_type_complet=(
            libelle_type_complet(bail_lot.type, bail_lot.type_appartement) if bail_lot else None
        ),
        lot_etage=bail_lot.etage if bail_lot else None,
        lot_etage_libelle=etage_label(bail_lot.etage) if bail_lot else "",
        lot_superficie=bail_lot.superficie if bail_lot else None,
        #  🔴 `bail_bat.nom` jusqu'au 02/10/2026 (#1563) : `Batiment` n'a pas de
        #  `nom`, et la route levait dès que le lot du bail avait un bâtiment —
        #  le locataire lisait « Impossible de charger votre bail ».
        lot_batiment_nom=libelle_batiment_ou(bail_bat, None),
        bailleur_nom=bailleur.nom if bailleur else "",
        bailleur_prenom=bailleur.prenom if bailleur else "",
        bailleur_email=bailleur.email if bailleur else None,
        bailleur_telephone=bailleur.telephone if bailleur else None,
        acces=acces_list,
    )
