"""Router lots — consultation et import (staging) des lots."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.utils.batiments import libelle_batiment_ou
from app.auth.deps import (
    est_rattache_au_lot,
    get_current_user,
    require_cs_or_admin,
)
from app.auth.appartenance import exiger_lots_proposes_au_locataire, lit_les_tantiemes
from app.database import get_session
from app.utils.rattachement_locataire import (
    acces_des_lots,
    lots_proposes,
    rattacher_lots_declares,
)
from app.utils.valeurs import valeur
from app.utils.designation_lot import nature_du_lot
from app.utils.lecture import lire_objet
from app.utils.lecture_lots import Designation, designations
from app.utils.lots_rattaches import rattachements_actifs
from app.utils.recuperer import ou_404
from app.utils.etages import (
    ETAGE_HORS_BORNES,
    etage_hors_bornes,
    logement_de_reference,
    type_de_lot,
)
from app.models.core import (
    Lot,
    Utilisateur,
)


#  `_parse_users` et `_type_lien_from_str` sont PARTIS avec l'atelier d'import
#  (`lots_imports.py`, 09/09/2026) : ils n'y servaient qu'à lui. Les laisser ici
#  aurait fait une copie de plus le jour où l'un des deux fichiers apprend
#  quelque chose sur ce JSON (`standards/02` §1 bis).

router = APIRouter(prefix="/lots", tags=["lots"])


#  Helpers

#  🔴 Le vocabulaire de la colonne TYPE (tables, `_norm`, `_type_from_raw`,
#  `_etage_from_raw`) vit dans `utils/import_xlsx` depuis #829 : il décrit ce
#  qu'un CLASSEUR contient, pas ce qu'un routeur fait. Il était écrit ici ET
#  dans `auto_match_service`, où la copie s'était logée dans un corps de
#  fonction pour contourner un homonyme.


#  Schémas


class LotRead(Designation):
    """Un lot — et sa désignation du règlement (#2212), héritée de `Designation`."""

    id: int
    numero: str
    type: str
    type_appartement: Optional[str] = None
    etage: Optional[int] = None
    superficie: Optional[float] = None
    batiment_id: Optional[int] = None
    batiment_nom: Optional[str] = None
    #: Ce lot est-il celui qui renseigne l'étage où l'on VIT ? La règle — un seul
    #: logement, de type appartement, dont l'étage est connu — vit dans
    #: `utils/etages.py` et le front lit ce booléen. Recalculée dans l'écran, elle
    #: y aurait pris sa deuxième écriture, et la divergence que l'API signale
    #: n'aurait plus été la même que celle que l'écran affiche.
    est_logement_de_reference: bool = False
    #: Mon lien à ce lot (`propriétaire`, `bailleur`, `locataire`…), lu dans
    #: `/lots/mes-lots` : l'écran du locataire sépare ce qu'il LOUE de ce qu'il
    #: possède. `None` hors de cette liste.
    type_lien: Optional[str] = None
    #: La nature selon le règlement (`utils/designation_lot.nature_du_lot`).
    nature: Optional[str] = None
    #: La porte ou la place (« 5 & 6 »), ce que le résident dit.
    numero_usage: Optional[str] = None


def _lot_read(lot: Lot, designation: Optional[Designation] = None) -> LotRead:
    nature = nature_du_lot(lot)
    return lire_objet(
        LotRead,
        lot,
        type=type_de_lot(lot),
        batiment_nom=libelle_batiment_ou(lot.batiment, None),
        nature=nature.value if nature else None,
        **(designation or Designation()).model_dump(),
    )


#  Endpoints publics


@router.get("/mes-lots")
def mes_lots(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    #  Les lots du COMPTE, et seulement eux — un administrateur sans lot en a
    #  zéro. Le patrimoine entier est `/lots/admin/tous` : le repli qui le
    #  rendait ici faisait lire « mes lots » à trente lots (`utils/lots_rattaches`).
    rattachements = rattachements_actifs(session, user)
    lots = [lot for lot, _ in rattachements]

    #  Le logement de référence est désigné ICI, sur la liste entière : la règle
    #  porte sur l'ENSEMBLE des lots (« un seul logement »), donc elle ne peut pas
    #  se calculer lot par lot dans `_lot_read`.
    reference = logement_de_reference(lots)
    liens = {lot.id: lien for lot, lien in rattachements}
    lues = designations(session, lots, lambda lot: lit_les_tantiemes(liens[lot.id].type_lien))
    lectures = []
    for lot, lien in rattachements:
        lecture = _lot_read(lot, lues.get(lot.id))
        lecture.est_logement_de_reference = reference is not None and lot.id == reference.id
        lecture.type_lien = valeur(lien.type_lien)
        lectures.append(lecture)
    return lectures


@router.get("/admin/tous")
def tous_les_lots(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste complète de tous les lots (admin/CS)."""
    lots = session.exec(select(Lot)).all()
    #  Le conseil et l'administration lisent le patrimoine entier, tantièmes compris.
    lues = designations(session, lots, lambda _lot: True)
    return [_lot_read(lot, lues.get(lot.id)) for lot in lots]


#  🔴 `_lot_rattache` a été SUPPRIMÉE le 19/09/2026 (#1028), pas renommée : sa
#  docstring annonçait qu'une règle d'accès en deux exemplaires diverge « le jour
#  où l'un des deux apprend quelque chose » — et le second exemplaire existait
#  déjà, dans `routers/acces/resident.py`, sans le test du lien actif.
#
#  La question vit maintenant dans `auth/deps.est_rattache_au_lot`, avec les
#  autres règles d'autorisation, là où `test_autorisation.py` les voit. Un alias
#  local qui aurait délégué à la fonction partagée était exclu : il aurait laissé
#  croire à deux notions (`standards/02` §1.6).


#  🔴 `GET /lots/{lot_id}` A ÉTÉ RETIRÉ le 12/09/2026 (#932), avec sa méthode
#  du client. Aucun écran ne le lisait : les écrans tiennent leurs lots par
#  `/lots/mes-lots` et `/lots/admin/tous`, et travaillent dessus. Relire un lot
#  seul rendait un second exemplaire du même objet, libre de diverger de la
#  liste affichée — le motif de `getBail` (#801).
#
#  ⚠️ Il n'était pas signalé orphelin parce que sa méthode du client, `lots.get`,
#  passait pour appelée : le relevé cherchait `.get` sans savoir de quel objet
#  il s'agissait, et neuf objets du client en portent un.


class EtageLotUpdate(BaseModel):
    """L'étage d'un lot, seul champ que son occupant peut écrire."""

    etage: Optional[int] = None


@router.patch("/{lot_id}/etage")
def maj_etage_de_mon_lot(
    lot_id: int,
    body: EtageLotUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """L'étage d'UN de MES lots, modifiable depuis le profil (#835).

    ## Ce que cet endpoint écrit, et ce qu'il n'écrit pas

    `Lot.etage` seul. Le lot porte le reste du patrimoine — numéro, superficie,
    tantièmes, bâtiment — et rien de tout cela ne s'ouvre ici : la liste blanche
    est le schéma lui-même, à un champ.

    ## Pourquoi l'association ACTIVE, et pas le repli par rôle

    `get_lot` laisse un admin ou un conseiller lire n'importe quel lot. Ce repli
    n'a pas sa place sur une **écriture** : ils ont déjà l'écran du patrimoine,
    avec ses contrôles, et un conseiller qui modifierait depuis son profil un lot
    qui n'est pas le sien écrirait une donnée partagée par un chemin prévu pour
    la sienne. L'endpoint exige donc un `UserLot` actif — pour tout le monde.

    ## ⚠️ Ce que ce choix accepte, dit une fois

    `Lot.etage` est une donnée de **patrimoine** : elle sert aux imports, aux
    fiches et aux affiches. Deux écrans l'écrivent désormais, avec deux niveaux
    de contrôle — celui-ci et l'administration. Arbitré par Philippe le
    09/09/2026, après que l'alternative (lecture seule + signalement) a été
    posée : c'est l'occupant qui sait à quel étage il vit, et le faire passer par
    un ticket pour corriger un chiffre était la friction de trop.
    """
    lot = ou_404(session, Lot, lot_id, "Lot")
    if not est_rattache_au_lot(user, lot_id):
        raise HTTPException(403, "Accès refusé")
    if body.etage is not None and etage_hors_bornes(body.etage):
        raise HTTPException(400, ETAGE_HORS_BORNES)
    #  `None` EFFACE l'étage, et c'est voulu : un champ qu'on vide doit pouvoir
    #  se vider. Il n'y a pas d'ambiguïté ici, contrairement au PATCH du profil
    #  où `None` signifie « ce champ n'est pas dans la requête » — la charge
    #  utile ne porte que lui.
    lot.etage = body.etage
    session.add(lot)
    session.commit()
    session.refresh(lot)
    return _lot_read(lot)


#  Ce que LOUE un locataire, d'après le fichier des lots du syndic (04/10/2026).
#  La règle — quels lots, quels badges, ce qui la borne — vit dans
#  `utils/rattachement_locataire` ; la question « ce lot m'est-il proposé ? »
#  dans `auth/appartenance`. La route ne fait que les appeler.


class LotPropose(LotRead):
    #: Les badges que la location de ce lot remet — `{"vigik": 2, "telecommande": 0}`.
    acces: dict[str, int] = {}


class PropositionsLocation(BaseModel):
    #: Le propriétaire tel que le locataire l'a nommé à l'inscription.
    proprietaire: Optional[str] = None
    appartement: list[LotPropose] = []
    cave: list[LotPropose] = []
    parking: list[LotPropose] = []


class RattachementLocation(BaseModel):
    lot_ids: list[int]


@router.get("/ma-location/propositions", response_model=PropositionsLocation)
def propositions_de_location(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Les lots que ce locataire peut se dire louer — vide s'il n'y a rien à demander."""
    par_nature = lots_proposes(user, session)
    acces = acces_des_lots(session, [lot.id for lots in par_nature.values() for lot in lots])
    return PropositionsLocation(
        proprietaire=user.nom_proprietaire,
        **{
            nature: [LotPropose(**_lot_read(lot).model_dump(), acces=acces[lot.id]) for lot in lots]
            for nature, lots in par_nature.items()
        },
    )


@router.post("/ma-location")
def declarer_ma_location(
    body: RattachementLocation,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Le locataire se rattache aux lots qu'il dit louer, et en reçoit les badges."""
    lots = exiger_lots_proposes_au_locataire(session, body.lot_ids, user)
    remis = rattacher_lots_declares(user, lots, session)
    session.commit()
    return remis


#  🔴 « COMMANDER UN ACCÈS » N'EXISTE QU'UNE FOIS — ici, il n'existe plus
#  (12/09/2026).
#
#  Ce fichier portait `GET /lots/commandes-acces/mes-commandes` et
#  `POST /lots/commandes-acces`, qui créaient le MÊME `CommandeAcces` que
#  `routers/acces/resident.py`. Deux chemins pour un geste, et — c'est le point —
#  **deux règles d'autorisation différentes** :
#
#    * `acces/resident.py` exige un lien `UserLot` avec le lot, et prévient le
#      conseil syndical par courriel ;
#    * la copie d'ici laissait passer admin et conseil syndical sans lien,
#      bornait la quantité à 10, et **ne prévenait personne**.
#
#  Aucun écran n'appelait la copie : ses deux méthodes du client étaient
#  masquées dans `lint:client-appele` par leurs homonymes de `acces` (le
#  contrôle cherche `.<nom>` sans savoir de quel objet il s'agit — c'est la
#  limite relevée le 12/09/2026). Une surface d'écriture sans appelant et avec
#  sa propre règle d'accès est exactement ce que `standards/03` §1 refuse :
#  l'autorisation se décide à UN endroit.

#  L'atelier d'import vit dans `lots_imports.py` depuis le 09/09/2026 (#835) :
#  ce fichier avait franchi les 500 lignes, et la règle de modularité est « au
#  fil de l'eau ». Inclus ICI, à la fin, pour que les chemins et leur ordre de
#  déclaration restent exactement ce qu'ils étaient.
from app.routers.lots_imports import router as _router_imports  # noqa: E402

router.include_router(_router_imports)

#  L'état descriptif du règlement (#2213) : même atelier, même préfixe, autre fichier.
from app.routers.lots_etat_descriptif import router as _router_etat_descriptif  # noqa: E402

router.include_router(_router_etat_descriptif)

#  Admin › Copropriété › Lots (#2216) : constats, re-dérivation, périmètres manuels.
from app.routers.lots_admin import router as _router_admin  # noqa: E402

router.include_router(_router_admin)
