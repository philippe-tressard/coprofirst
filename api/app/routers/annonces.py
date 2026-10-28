"""Router petites annonces — communauté résidence."""

import json
from app.utils import horloge
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import est_auteur, get_current_user, peut_commenter
from app.utils.limiter import LIMITE_TELEVERSEMENT, limiter
from app.database import get_session
from app.models.core import (
    PetiteAnnonce,
    TypeAnnonce,
    CategorieAnnonce,
    StatutAnnonce,
    ReponseCommunaute,
    Utilisateur,
)
from app.routers.uploads import _save_image
from app.utils.archivage import (
    ARCHIVAGE_DELAI_JOURS,
    est_archivable,
    seuil_archivage_jours,
)
from app.routers.reponses_communaute import (
    enregistrer_routes_reponses,
    reponses_de,
)
from app.utils.communaute import exiger_acces
from app.utils.perimetres import parse_json_perimetres, perimetre_defaut_liste
from app.utils.visibility import adresse_de_contact, annonce_visible
from app.utils.assiste_ia import (
    AssisteIACorrection,
    AssisteIAEntree,
    marquer as marquer_assiste_ia,
)
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/annonces", tags=["annonces"])

MAX_PHOTOS = 5

RUBRIQUE = "annonce"


def est_archivee(annonce: PetiteAnnonce, jours: int = ARCHIVAGE_DELAI_JOURS) -> bool:
    """Cette annonce a-t-elle basculé dans les Archives ?

    🔴 **Ne décide plus rien** — la règle vit dans `app/utils/archivage.py`,
    avec celle des six autres objets du site (#515).

    Ce qui a disparu d'ici mérite d'être nommé : un `ARCHIVAGE_JOURS = 30`
    **codé en dur**. Il ne se voyait pas depuis l'écran d'administration, et
    valait par coïncidence la même chose que le délai des actualités. Le jour
    où l'un des deux aurait bougé, l'autre non — et rien ne l'aurait signalé.
    C'était le troisième des « trois délais » que le ticket dénonçait.

    Les deux arbitrages qui vivaient dans ce commentaire sont conservés dans la
    déclaration `REGLES["annonce"]` : `reserve` n'est pas terminal, et la durée
    se mesure sur `statut_change_le` et non sur `mis_a_jour_le`.
    """
    return est_archivable("annonce", annonce, seuil_jours=jours)


def _reponses_for(cible_id: int, session: Session) -> list[dict]:
    """Les réponses de cette rubrique — la règle vit dans `reponses_communaute`.

    Ce corps était identique à celui de l'autre rubrique, au discriminant
    près. Il ne reste qu'un nom local, gardé parce que la fiche détaillée
    l'appelle : le supprimer déplacerait la question sans y répondre.
    """
    return reponses_de(RUBRIQUE, cible_id, session)


def _can_manage(annonce: PetiteAnnonce, user: Utilisateur) -> bool:
    """Auteur, CS ou admin peut modifier/supprimer.

    🔴 Ce corps RÉÉCRIVAIT la règle centrale, mot pour mot. C'est la forme la plus
    trompeuse de la duplication : une fonction nommée, à l'air factorisé, mais qui
    ne partage rien avec les treize autres sites qui disaient la même chose — et
    avec lesquels elle avait déjà divergé (29/08/2026).

    Elle reste comme ALIAS LOCAL, parce que le nom porte le sens métier de cet
    écran ; ce qu'elle ne fait plus, c'est décider.
    """
    return peut_commenter(annonce, user)


def _enrich(annonce: PetiteAnnonce, user: Utilisateur, session: Session) -> dict:
    auteur = session.get(Utilisateur, annonce.auteur_id)
    reponses = _reponses_for(annonce.id, session)
    return {
        **annonce.model_dump(),
        "photos": json.loads(annonce.photos_json),
        #  Le périmètre sort en LISTE de codes, jamais en JSON brut : c'est ce que
        #  `PerimetrePicker` et `perimetreLabel` lisent côté front. Le `or` couvre les
        #  annonces déposées AVANT la migration 0151 — elles valaient « résidence » de
        #  fait, elles le valent explicitement.
        #  🔴 `parse_json_perimetres`, et non un `json.loads` à la main : le défaut
        #  est une DONNÉE (`code_par_defaut()`, lue dans l'arbre), pas la chaîne
        #  « résidence ». Écrite en dur, elle mentirait sur une copropriété qui
        #  renomme ce nœud (#789).
        "perimetre_cible": parse_json_perimetres(annonce.perimetre_cible),
        #  Idem pour le public cible : liste de codes, jamais du JSON brut.
        #  `None` sort en liste VIDE, que `#lib/destinataires.ts` lit comme
        #  « tous les résidents » — le même sens des deux côtés.
        "public_cible": json.loads(annonce.public_cible or "[]"),
        "auteur_prenom": auteur.prenom if auteur else "",
        "auteur_nom": auteur.nom if auteur else "",
        #  Le nom se lit toujours ; l'adresse, si l'auteur l'a permis (#2145).
        "auteur_email": adresse_de_contact(annonce, auteur),
        #  Calculé par la règle centrale, pas recomparé ici : le drapeau que
        #  l'écran reçoit doit dire la même chose que le contrôle qui refuse.
        "est_auteur": est_auteur(annonce, user),
        #  Calculé côté serveur et transporté : l'écran ne doit pas refaire la
        #  règle, sinon la liste et l'Historique peuvent trancher différemment —
        #  c'est le bug du 17/07/2026 sur les actualités, un élément visible dans
        #  une vue et pas dans l'autre.
        "archivee": est_archivee(annonce, seuil_archivage_jours(session)),
        "reponses": reponses,
        "nb_reponses": len(reponses),
    }


# ── Schémas ────────────────────────────────────────────────────────────────


class AnnonceCreate(AssisteIAEntree):
    titre: str
    description: str
    #  Section 4 du cadre #430. Reçu en LISTE, stocké en JSON — même contrat que
    #  `TicketCreate` : la conversion se fait ici, à la frontière, et une
    #  seule fois.
    perimetre_cible: List[str] = Field(default_factory=perimetre_defaut_liste)
    #  Section 5 du cadre #430 (#782). Liste VIDE = tout le monde : c'est ce que
    #  `public_cible_visible` fait d'une valeur absente, et l'inverse rendrait
    #  l'annonce invisible de tous, sans message ni ligne de journal.
    public_cible: List[str] = []
    type_annonce: TypeAnnonce = TypeAnnonce.vente
    categorie: CategorieAnnonce = CategorieAnnonce.divers
    prix: Optional[float] = None
    negotiable: bool = False
    contact_visible: bool = True


class AnnonceUpdate(AssisteIACorrection):
    titre: Optional[str] = None
    perimetre_cible: Optional[List[str]] = None
    public_cible: Optional[List[str]] = None
    description: Optional[str] = None
    type_annonce: Optional[TypeAnnonce] = None
    categorie: Optional[CategorieAnnonce] = None
    prix: Optional[float] = None
    negotiable: Optional[bool] = None
    contact_visible: Optional[bool] = None
    #  Section 3 du cadre : le workflow se corrige comme les autres champs.
    #  Le raccourci de la carte (`PATCH /statut`) reste, pour le geste rapide.
    statut: Optional[StatutAnnonce] = None


class AnnonceStatutUpdate(BaseModel):
    statut: StatutAnnonce


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("")
def list_annonces(
    type_annonce: Optional[str] = None,
    categorie: Optional[str] = None,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    #  ⚠️ Plus aucun filtre sur l'état : les annonces archivées sont RENDUES,
    #  dans leur propre section repliée. Les exclure ici les rendrait
    #  introuvables — or une annonce vendue le mois dernier est précisément ce
    #  qu'on vient chercher quand on se demande à quel prix un voisin a vendu.
    stmt = select(PetiteAnnonce).order_by(
        PetiteAnnonce.cree_le.desc()  # type: ignore[arg-type]
    )
    annonces = session.exec(stmt).all()
    #  🔒 Le ciblage filtre ICI, dans la réponse — jamais dans le front. Une carte
    #  masquée par le navigateur reste dans la charge utile : ce serait une fuite,
    #  pas un filtre. C'est le MÊME appel que les publications et les sondages
    #  (`cible_visible`), et il n'y a pas de seconde règle à maintenir.
    annonces = [a for a in annonces if annonce_visible(a, user)]
    if type_annonce:
        annonces = [a for a in annonces if a.type_annonce == type_annonce]
    if categorie:
        annonces = [a for a in annonces if a.categorie == categorie]
    return [_enrich(a, user, session) for a in annonces]


@router.post("")
def create_annonce(
    data: AnnonceCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    annonce = PetiteAnnonce(
        titre=data.titre,
        description=data.description,
        type_annonce=data.type_annonce,
        categorie=data.categorie,
        prix=data.prix,
        negotiable=data.negotiable,
        contact_visible=data.contact_visible,
        perimetre_cible=json.dumps(data.perimetre_cible, ensure_ascii=False),
        #  Liste vide → `None` en base, PAS `"[]"`. Les deux se lisent « tout le
        #  monde » aujourd'hui, mais `None` est ce que portent les annonces
        #  déposées avant la migration 0176 : deux écritures pour un même sens
        #  finissent par se traiter différemment quelque part.
        public_cible=(
            json.dumps(data.public_cible, ensure_ascii=False) if data.public_cible else None
        ),
        auteur_id=user.id,
        assiste_ia=data.assiste_ia,
    )
    session.add(annonce)
    session.commit()
    session.refresh(annonce)
    return _enrich(annonce, user, session)


@router.patch("/{annonce_id}")
def update_annonce(
    annonce_id: int,
    data: AnnonceUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    annonce = exiger_objet_autorise(
        session, PetiteAnnonce, annonce_id, "Annonce", user, _can_manage, "Non autorisé"
    )
    maj = data.model_dump(exclude_none=True)
    #  La marque « assistant IA » ne s'écrit que dans UN sens (`utils/assiste_ia`).
    marquer_assiste_ia(annonce, data)
    maj.pop("assiste_ia", None)
    #  ⚠️ Le périmètre arrive en LISTE et la colonne est du TEXTE : sans cette
    #  conversion, la base stockerait la repr Python d'une liste — que `json.loads`
    #  ne relit pas, et l'annonce perdrait son périmètre à la première correction.
    #  Le formulaire de correction porte la section Workflow : un changement
    #  d'état arrivant par `PATCH` doit s'horodater comme celui du raccourci de
    #  la carte. Deux chemins vers le même fait, une seule règle.
    if "statut" in maj and maj["statut"] != annonce.statut:
        annonce.statut_change_le = horloge.maintenant()
    #  Les DEUX axes du ciblage subissent la même conversion : les traiter
    #  séparément a produit exactement ce genre d'oubli ailleurs.
    for axe in ("perimetre_cible", "public_cible"):
        if axe in maj:
            maj[axe] = json.dumps(maj[axe], ensure_ascii=False) if maj[axe] else None
    #  ⚠️ `perimetre_cible` vidé retombe donc sur `None`, que `_enrich` relit
    #  comme `["résidence"]` : le défaut du champ, et non une annonce sans lieu.
    for field, value in maj.items():
        setattr(annonce, field, value)
    annonce.mis_a_jour_le = horloge.maintenant()
    session.add(annonce)
    session.commit()
    session.refresh(annonce)
    return _enrich(annonce, user, session)


@router.patch("/{annonce_id}/statut")
def update_statut(
    annonce_id: int,
    data: AnnonceStatutUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    annonce = exiger_objet_autorise(
        session, PetiteAnnonce, annonce_id, "Annonce", user, _can_manage, "Non autorisé"
    )
    #  🔴 `statut_change_le` ne bouge QUE sur un vrai changement. Le poser à
    #  chaque appel ferait repartir le compte à rebours d'archivage même quand
    #  on repose l'état déjà en place — un double-clic suffirait.
    if annonce.statut != data.statut:
        annonce.statut_change_le = horloge.maintenant()
    annonce.statut = data.statut
    annonce.mis_a_jour_le = horloge.maintenant()
    session.add(annonce)
    session.commit()
    return {"ok": True}


@router.delete("/{annonce_id}")
def delete_annonce(
    annonce_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    annonce = exiger_objet_autorise(
        session, PetiteAnnonce, annonce_id, "Annonce", user, _can_manage, "Non autorisé"
    )
    # Réponses associées supprimées en cascade
    reps = session.exec(
        select(ReponseCommunaute).where(
            ReponseCommunaute.rubrique == RUBRIQUE,
            ReponseCommunaute.cible_id == annonce_id,
        )
    ).all()
    for r in reps:
        session.delete(r)
    session.delete(annonce)
    session.commit()
    return {"ok": True}


# ── Réponses aux annonces ────────────────────────────────────────────────────

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
    modele=PetiteAnnonce,
    libelle="Annonce",
    rubrique_label="votre annonce",
    prefixe_lien="annonce",
    #  🔒 La règle d'accès de la rubrique, passée à la fabrique : les trois
    #  routes de réponses la posent, une seule écriture la porte.
    visible_de=annonce_visible,
)


@router.post("/{annonce_id}/photo")
@limiter.limit(LIMITE_TELEVERSEMENT)
def add_photo(
    request: Request,
    annonce_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    annonce = ou_404(session, PetiteAnnonce, annonce_id, "Annonce")
    #  L'auteur SEUL — pas de modération sur ses propres photos, c'est voulu.
    if not est_auteur(annonce, user):
        raise HTTPException(403, "Seul l'auteur peut ajouter des photos")
    photos = json.loads(annonce.photos_json)
    if len(photos) >= MAX_PHOTOS:
        raise HTTPException(400, f"Maximum {MAX_PHOTOS} photos par annonce")
    url = _save_image(file, "annonces", session, user, max_dim=1200)
    photos.append(url)
    annonce.photos_json = json.dumps(photos)
    annonce.mis_a_jour_le = horloge.maintenant()
    session.add(annonce)
    session.commit()
    return {"url": url, "photos": photos}


@router.delete("/{annonce_id}/photo")
def remove_photo(
    annonce_id: int,
    url: str,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    annonce = ou_404(session, PetiteAnnonce, annonce_id, "Annonce")
    #  L'auteur SEUL — même régime que l'ajout ci-dessus.
    if not est_auteur(annonce, user):
        raise HTTPException(403, "Seul l'auteur peut supprimer ses photos")
    photos = [p for p in json.loads(annonce.photos_json) if p != url]
    annonce.photos_json = json.dumps(photos)
    annonce.mis_a_jour_le = horloge.maintenant()
    session.add(annonce)
    session.commit()
    return {"photos": photos}
