"""Router boîte à idées — idées + upvotes + réponses."""

import json
from app.utils import horloge
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, NaiveDatetime
from sqlmodel import Session, select

from app.auth.deps import (
    exiger_non_externe,
    get_current_user,
    peut_editer,
    require_cs_or_admin,
)
from app.database import get_session
from app.models.core import (
    Idee,
    ReponseCommunaute,
    Utilisateur,
    VoteIdee,
)
from app.utils.archivage import est_archivable, seuil_archivage_jours
from app.utils.communaute import exiger_acces
from app.utils.perimetres import parse_json_perimetres, perimetre_cible_json
from app.auth.appartenance import exiger_cible_visible
from app.utils.visibility import idee_visible
from app.routers.reponses_communaute import (
    enregistrer_routes_reponses,
    reponses_de,
)
from app.utils.liens import lien_element
from app.utils.assiste_ia import (
    AssisteIACorrection,
    AssisteIAEntree,
    AssisteIASortie,
    marquer as marquer_assiste_ia,
)
from app.utils.lecture import lire_objet
from app.utils.recuperer import ou_404
from app.utils.reponses import (
    notifier_votants_idee,
)

router = APIRouter(prefix="/idees", tags=["idées"])

RUBRIQUE = "idee"

# Statuts « positifs » qui déclenchent une notification aux votants.
_STATUT_NOTIF_LABELS = {"retenue": "Retenue", "realisee": "Réalisée"}


def _reponses_for(cible_id: int, session: Session) -> list[dict]:
    """Les réponses de cette rubrique — la règle vit dans la fabrique."""
    return reponses_de(RUBRIQUE, cible_id, session)


class IdeeCreate(AssisteIAEntree):
    titre: str
    description: str
    #  Le périmètre arrive en LISTE de codes et se stocke en JSON : c'est la forme
    #  que `PerimetrePicker` produit et que `perimetreLabel` sait lire, des deux
    #  côtés. Vide vaut « toute la copropriété », comme partout ailleurs.
    perimetre_cible: Optional[list[str]] = None
    #  Section 5 du cadre #430 (#782) — le PUBLIC visé, à côté du lieu.
    #  Vide vaut « tous les résidents » : c'est ce que
    #  `public_cible_visible` fait d'une valeur absente, et l'inverse
    #  rendrait l'idée invisible de tous sans rien dire.
    public_cible: Optional[list[str]] = None


class IdeeUpdate(AssisteIACorrection):
    """Ce qu'une idée accepte de voir corrigé après son dépôt (#783).

    Demandé par Philippe le 06/09/2026 : « il n'est pas possible de l'éditer
    (si erreur de saisie) ». C'est donc la CORRECTION qui est visée, pas la
    réécriture d'une idée en une autre.

    🔴 Les champs de CIBLAGE (`perimetre_cible`, `public_cible`) n'y sont pas,
    et c'est la même décision que pour le sondage (`SondageUpdate`) : restreindre
    après coup masquerait l'idée à des gens qui l'ont déjà votée. Un champ qu'on
    n'expose pas ne se contourne pas — tant que la question n'est pas tranchée,
    son absence vaut refus.

    ⚠️ Le `statut` n'y est pas non plus : il a déjà sa route
    (`PATCH /idees/{id}/statut`, réservée au CS), qui horodate `statut_change_le`
    et prévient les votants. L'exposer ici donnerait DEUX chemins vers le même
    fait, dont un qui oublierait les deux effets de bord.
    """

    titre: Optional[str] = None
    description: Optional[str] = None


class IdeeRead(AssisteIASortie):
    """Ce que `GET /idees` rend — lu SUR le modèle par `lire_objet` (#1660).

    Ce schéma existait sans que rien le rende : la liste assemblait un dictionnaire
    à la main, et `assiste_ia` n'en sortait pas.
    """

    id: int
    titre: str
    description: str
    auteur_id: Optional[int] = None  # compte supprimé (#1821)
    statut: str
    perimetre_cible: list[str] = []
    public_cible: list[str] = []
    cree_le: NaiveDatetime
    nb_votes: int = 0
    mon_vote: bool = False
    #: Calculé par la règle du site (`utils/archivage`), jamais stocké : l'archivage
    #: automatique est une conséquence du temps, pas un état qu'on pose.
    archivee: bool = False
    reponses: list[dict] = []
    nb_reponses: int = 0


def _perimetre_liste(brut: Optional[str]) -> list[str]:
    """La colonne stocke un tableau JSON ; l'API expose une liste.

    🔴 Ce corps RÉÉCRIVAIT `parse_json_perimetres`, mot pour mot — même
    raisonnement, mêmes trois branches, même repli sur le défaut. C'est la forme
    la plus trompeuse de la duplication : une fonction nommée, à l'air factorisée,
    qui ne partage rien avec l'originale.

    ⚠️ Et elle avait DÉJÀ divergé : elle écrivait `"résidence"` **en dur**, trois
    fois, là où la fonction partagée lit `code_par_defaut()` — qui existe
    précisément pour qu'une copropriété qui renomme ou supprime ce nœud ne casse
    pas l'application. Le badge d'une idée aurait alors annoncé un périmètre
    inexistant, et lui seul (06/09/2026, #789).

    Le nom local reste : il porte le sens métier ici. Ce qu'il ne fait plus,
    c'est décider.
    """
    return parse_json_perimetres(brut)


def _enrich(idees: list, user_id: int, session: Session) -> list[dict]:
    #  🔴 LU UNE FOIS, hors de la boucle. `seuil_archivage_jours` interroge la
    #  configuration : le lire par idée ferait N requêtes pour une valeur du site,
    #  et surtout deux idées du même appel pourraient être tranchées sur des
    #  seuils différents si le réglage changeait entre deux tours.
    seuil_jours = seuil_archivage_jours(session)
    result = []
    for idee in idees:
        nb = len(session.exec(select(VoteIdee).where(VoteIdee.idee_id == idee.id)).all())
        mon_vote = bool(
            session.exec(
                select(VoteIdee).where(VoteIdee.idee_id == idee.id, VoteIdee.user_id == user_id)
            ).first()
        )
        reponses = _reponses_for(idee.id, session)
        lue = lire_objet(
            IdeeRead,
            idee,
            #  Exposé en LISTE pour que le front n'ait rien à désérialiser — même
            #  contrat que les événements et les annonces.
            perimetre_cible=_perimetre_liste(idee.perimetre_cible),
            #  Même contrat pour le public cible : une LISTE de codes, que
            #  `#lib/destinataires.ts` lit. Vide = tous les résidents.
            public_cible=json.loads(idee.public_cible or "[]"),
            nb_votes=nb,
            mon_vote=mon_vote,
            #  Calculé côté SERVEUR et transporté (#515). L'écran ne doit pas
            #  refaire la règle : la liste et les Archives trancheraient alors
            #  séparément, et une idée apparaîtrait dans l'une sans l'autre —
            #  c'est le bug du 17/07/2026 sur les actualités.
            archivee=est_archivable("idee", idee, seuil_jours=seuil_jours),
            reponses=reponses,
            nb_reponses=len(reponses),
        )
        result.append(lue.model_dump())
    return result


@router.get("")
def list_idees(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    idees = session.exec(select(Idee).order_by(Idee.cree_le.desc())).all()
    #  🔒 Le ciblage filtre ICI, dans la réponse — jamais dans le front : une
    #  carte masquée par le navigateur reste dans la charge utile. Même
    #  appel que l'annonce, le sondage et la publication (`cible_visible`).
    idees = [i for i in idees if idee_visible(i, user)]
    return _enrich(idees, user.id, session)


@router.post("", status_code=201)
def create_idee(
    body: IdeeCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    exiger_non_externe(user, "soumettre d'idées")
    idee = Idee(
        titre=body.titre,
        description=body.description,
        auteur_id=user.id,
        assiste_ia=body.assiste_ia,
        #  Liste vide == aucune restriction : on retombe sur le défaut, comme le
        #  serveur le fait déjà pour les publications et les sondages.
        perimetre_cible=perimetre_cible_json(body.perimetre_cible),
        #  Liste vide → `None`, PAS `"[]"` : c'est ce que portent les idées
        #  déposées avant la migration 0176, et deux écritures pour un même
        #  sens finissent par se traiter différemment quelque part.
        public_cible=(
            json.dumps(body.public_cible, ensure_ascii=False) if body.public_cible else None
        ),
    )
    session.add(idee)
    session.commit()
    session.refresh(idee)
    return idee


@router.post("/{idee_id}/voter", status_code=201)
def voter(
    idee_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    exiger_non_externe(user, "voter")
    #  🔒 Voir ET voter suivent la même règle : sans ce contrôle, un résident hors
    #  du public visé pesait sur une idée qui ne lui était pas adressée, en
    #  appelant l'endpoint directement — la liste ne la lui montrait déjà plus.
    #  404 et non 403 : « interdit » confirmerait l'existence de l'idée.
    exiger_cible_visible(session, Idee, idee_id, "Idée", user, idee_visible)

    existant = session.exec(
        select(VoteIdee).where(VoteIdee.idee_id == idee_id, VoteIdee.user_id == user.id)
    ).first()
    if existant:
        # toggle
        session.delete(existant)
        session.commit()
        return {"message": "Vote retiré"}

    session.add(VoteIdee(idee_id=idee_id, user_id=user.id))
    session.commit()
    return {"message": "Vote enregistré"}


class StatutUpdate(BaseModel):
    statut: str  # ouverte | retenue | rejetee | realisee


@router.patch("/{idee_id}")
def update_idee(
    idee_id: int,
    body: IdeeUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Corriger le titre ou la description d'une idée (#783).

    L'idée était la seule entité de la Communauté sans aucun moyen de se
    corriger : une faute de frappe y était définitive, ou imposait de supprimer
    et redéposer — ce qui perd les votes et les réponses déjà reçus.
    """
    exiger_acces(user)
    #  404 et non 403 quand elle n'est pas visible : « interdit » confirmerait son
    #  existence. L'auteur, lui, voit toujours la sienne (`cible_visible`).
    idee = exiger_cible_visible(session, Idee, idee_id, "Idée", user, idee_visible)
    #  🔒 `peut_editer` — l'auteur ou un admin, du module central. **Pas le
    #  conseil syndical** : il décide du STATUT d'une idée, il ne réécrit pas la
    #  proposition de quelqu'un. C'est exactement la règle du sondage, et c'est la
    #  même fonction : une règle d'autorisation recopiée se durcit une fois sur deux.
    if not peut_editer(idee, user):
        raise HTTPException(403, "Seul l'auteur ou un admin peut modifier cette idée")
    #  Une idée ARCHIVÉE ne se corrige plus — le pendant de « ce sondage est
    #  clôturé et ne peut plus être modifié ». Elle a quitté la vie active, et la
    #  réécrire changerait rétroactivement ce que les votants ont soutenu.
    if est_archivable("idee", idee, seuil_jours=seuil_archivage_jours(session)):
        raise HTTPException(400, "Cette idée est archivée et ne peut plus être modifiée")

    donnees = body.model_dump(exclude_unset=True)
    #  La marque « assistant IA » ne s'écrit que dans UN sens (`utils/assiste_ia`).
    marquer_assiste_ia(idee, body)
    for champ in ("titre", "description"):
        if champ in donnees:
            valeur = (donnees[champ] or "").strip()
            if not valeur:
                raise HTTPException(422, f"Le champ « {champ} » ne peut pas être vide")
            setattr(idee, champ, valeur)
    #  ⚠️ `statut_change_le` n'est PAS touché : corriger une faute de frappe ne
    #  doit pas repousser l'archivage d'un mois. C'est la leçon que `PetiteAnnonce`
    #  porte déjà, et la raison d'être de ce champ distinct de `mis_a_jour_le`.
    session.add(idee)
    session.commit()
    session.refresh(idee)
    return _enrich([idee], user.id, session)[0]


@router.patch("/{idee_id}/statut")
def update_statut(
    idee_id: int,
    body: StatutUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    idee = ou_404(session, Idee, idee_id, "Idée")
    ancien = idee.statut
    idee.statut = body.statut
    if body.statut != ancien:
        #  ⚠️ Horodater le CHANGEMENT, pas la requête : c'est cette date que lit
        #  l'archivage automatique (`app/utils/archivage.py`). La renseigner à
        #  chaque appel, même sans changement, repousserait l'archivage d'un mois
        #  à chaque clic — le défaut que `PetiteAnnonce` évite déjà en se datant
        #  sur `statut_change_le` et non sur `mis_a_jour_le`.
        idee.statut_change_le = horloge.maintenant()
    session.add(idee)
    # Passage à un statut positif (retenue/réalisée) → prévenir les votants.
    if body.statut != ancien and body.statut in _STATUT_NOTIF_LABELS:
        votant_ids = [
            v.user_id
            for v in session.exec(select(VoteIdee).where(VoteIdee.idee_id == idee_id)).all()
        ]
        notifier_votants_idee(
            session,
            background_tasks,
            votant_ids=votant_ids,
            idee_titre=idee.titre,
            statut_label=_STATUT_NOTIF_LABELS[body.statut],
            # Onglet + ancre : la Communauté a trois rubriques, `/sondages` seul
            # déposait le lecteur sur les sondages (cf. app/utils/liens.py).
            lien_path=lien_element("idee", idee_id),
            exclure_id=user.id,
        )
    session.commit()
    return {"statut": idee.statut}


@router.delete("/{idee_id}", status_code=204)
def delete_idee(
    idee_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Supprimer une idée (admin / CS uniquement)."""
    idee = ou_404(session, Idee, idee_id, "Idée")
    # Supprimer les votes + réponses associés
    votes = session.exec(select(VoteIdee).where(VoteIdee.idee_id == idee_id)).all()
    for v in votes:
        session.delete(v)
    reps = session.exec(
        select(ReponseCommunaute).where(
            ReponseCommunaute.rubrique == RUBRIQUE,
            ReponseCommunaute.cible_id == idee_id,
        )
    ).all()
    for r in reps:
        session.delete(r)
    session.delete(idee)
    session.commit()


# ── Réponses aux idées ─────────────────────────────────────────────────────────

#  🔴 LES RÉPONSES NE SONT PLUS ÉCRITES ICI (05/09/2026).
#
#  Les trois routes — lister, créer, supprimer — étaient identiques à
#  99 %, 94 % et 99 % de celles de l'autre rubrique de communauté. Six
#  fonctions pour deux fois la même chose, dont la règle qui refuse les
#  comptes externes : écrite deux fois, elle se durcit une fois sur deux.
#
#  La fabrique les pose, adaptées par ces cinq paramètres. Ce qui reste
#  ici est ce qui est PROPRE à cette rubrique — et rien d'autre.
enregistrer_routes_reponses(
    router,
    rubrique=RUBRIQUE,
    modele=Idee,
    libelle="Idée",
    rubrique_label="votre idée",
    prefixe_lien="idee",
    #  🔒 La règle d'accès de la rubrique, passée à la fabrique : les trois
    #  routes de réponses la posent, une seule écriture la porte.
    visible_de=idee_visible,
)
