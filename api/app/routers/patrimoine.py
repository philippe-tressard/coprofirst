"""Périmètres — lecture pour tous, écriture pour l'administration.

L'arborescence remplace la table de libellés qui était écrite en dur à deux
endroits, avec deux contenus différents (`utils/perimetres.py` allait jusqu'à
`bat:9`, `front/src/lib/utils.ts` s'arrêtait à `bat:4`). Ce router est ce qui la
rend **éditable** : une autre copropriété n'a ni AFUL, ni quatre bâtiments, ni
forcément de caves, et doit pouvoir tout reconstruire sans livraison.

**Sous session, jamais public.** L'arborescence décrit la copropriété bâtiment par
bâtiment ; rien ici n'a à être lisible sans être connecté. Ce n'est pas dans la
liste blanche de `routers/config.py` et cela n'y entrera pas — l'audit du
26/07/2026 a montré ce que coûte une liste noire à cet endroit.

Trois refus serveur, et ils ne sont pas décoratifs :

1. **Le `code` ne se modifie pas.** C'est lui qui est stocké dans les tickets, les
   actualités et les événements déjà publiés : le changer les orphelinerait en
   silence. Le libellé, lui, se change librement — c'est la raison d'être de l'écran.
2. **Pas de cycle de parenté.** Une boucle rendrait la remontée d'arbre infinie ;
   les lecteurs s'en protègent déjà, mais accepter la donnée serait accepter
   d'écrire un état que rien ne peut interpréter.
3. **Pas de suppression d'un nœud cité par un contenu** — ni d'une branche dont
   un nœud l'est. On propose de le désactiver : il disparaît de la saisie, et les
   contenus publiés gardent leur libellé et leur visibilité. C'est le mécanisme
   retenu pour « la cave relève d'un bâtiment » sans migrer une seule ligne.

Une branche — un nœud et ses descendants — se duplique ou se supprime d'un bloc
(13/10/2026) ; ses règles vivent dans `utils/perimetres/branche.py`.
"""

from app.utils import horloge
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.perimetre import Perimetre
from app.models.core import (
    AnnonceHall,
    Evenement,
    Ticket,
    Utilisateur,
)
from app.utils.lecture import lire_objet
from app.utils.acces_choix import fixer_acces, types_fixes_par_code
from app.utils.perimetres import (
    code_par_defaut,
    invalider_cache,
    parse_json_perimetres,
    parse_perimetres,
)
from app.utils.perimetres.branche import (
    descendants,
    enfants_par_parent,
    refus_copie,
    refus_duplication,
)
from app.utils.perimetres.deplacement import sens_admis
from app.utils.equipements import retirer_liens_du_perimetre
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/perimetres", tags=["perimetres"])


# ── Schémas ───────────────────────────────────────────────────────────────────


class PerimetreRead(BaseModel):
    """Un nœud, tel que le front en a besoin pour afficher ET pour faire choisir."""

    id: int
    code: str
    parent: Optional[str]
    libelle: str
    libelle_court: str
    description: str
    icone: Optional[str]
    batiment_id: Optional[int]
    profondeur: int
    ordre: int
    actif: bool

    #: Le drapeau porté par ce nœud — ce que l'écran édite.
    portee_globale: bool
    #: Le drapeau **effectif**, héritage compris. C'est lui qui répond à « ce contenu
    #: sera-t-il visible de tous les résidents ? », donc lui que l'aide affiche.
    concerne_tous: bool
    #: Un regroupement ne se cible pas, et un nœud retiré de la saisie non plus. Le
    #: front doit tout de même les connaître pour afficher le libellé des contenus
    #: déjà publiés qui les citent — d'où un seul point de lecture et des drapeaux
    #: plutôt que deux listes.
    selectionnable: bool
    privatif: bool
    #: Ce nœud appartient à un tiers (AFUL, voie communale) : ce qui couvre
    #: « toute la copropriété » ne le couvre pas (#943).
    hors_copropriete: bool
    #: Vrai si un contenu cite ce code : l'écran propose alors de désactiver plutôt
    #: que de supprimer, et dit pourquoi.
    utilise: bool
    #: Combien de nœuds la suppression emporterait avec lui — ce que la
    #: confirmation annonce.
    nb_descendants: int = 0
    #: Le serveur accepterait-il de dupliquer cette branche ? Lu sur la même règle
    #: que le geste qui refuse (`refus_duplication`), jamais recopié à l'écran.
    dupliquable: bool = False
    #: …et de le copier sous d'autres parents (`refus_copie`), et lesquelles des
    #: quatre flèches il accepterait (`sens_admis`) : l'écran grise les autres.
    copiable: bool = False
    deplacements: list[str] = []
    #: Les types d'accès (`types_acces.TYPES_ACCES`) qui ouvrent ce nœud d'office,
    #: sans dépendre d'aucun lot — un portillon, un portail (#2060).
    acces_fixes: list[str] = []


class PerimetreCreate(BaseModel):
    code: str
    libelle: str
    parent: Optional[str] = None
    libelle_court: Optional[str] = None
    description: str = ""
    icone: Optional[str] = None
    batiment_id: Optional[int] = None
    portee_globale: bool = False
    selectionnable: bool = True
    privatif: bool = False
    hors_copropriete: bool = False
    ordre: int = 0


class PerimetreUpdate(BaseModel):
    """Tout est optionnel — sauf `code`, qui n'y figure pas du tout."""

    libelle: Optional[str] = None
    parent: Optional[str] = None
    libelle_court: Optional[str] = None
    description: Optional[str] = None
    icone: Optional[str] = None
    batiment_id: Optional[int] = None
    portee_globale: Optional[bool] = None
    selectionnable: Optional[bool] = None
    privatif: Optional[bool] = None
    hors_copropriete: Optional[bool] = None
    ordre: Optional[int] = None
    actif: Optional[bool] = None
    #: Remplace la liste des types d'accès fixes de ce nœud (#2060).
    acces_fixes: Optional[list[str]] = None


# ── Aides internes ────────────────────────────────────────────────────────────


def _codes_cites(session: Session) -> set[str]:
    """Tous les codes de périmètre cités par un contenu, quel que soit le format.

    Les trois entités qui portent un périmètre utilisent deux formats — JSON pour
    `perimetre_cible`, CSV pour `perimetre`.

    ⚠️ `Publication` n'en fait plus partie (#1091, 23/09/2026) : les actualités
    sont des affaires, la 0210 les a recopiées, et la table subsiste non lue —
    même raisonnement que pour les devis ci-dessous.

    ⚠️ `DevisPrestataire` en faisait partie, et ne le fait plus (#603) : son modèle
    a disparu. Sa table subsiste, non lue — un périmètre cité UNIQUEMENT par un
    devis dormant redevient donc supprimable. C'est voulu : plus rien n'affiche
    ces lignes, et les retenir ferait dépendre l'arborescence d'un contenu que
    personne ne peut plus voir ni corriger. On les analyse avec les mêmes fonctions
    que le reste du produit plutôt qu'avec un `LIKE` sur du JSON, qui donnerait des
    correspondances partielles (« bat:1 » trouvé dans « bat:12 »).
    """
    cites: set[str] = set()
    for modele, champ, json_ in (
        (Ticket, "perimetre_cible", True),
        (AnnonceHall, "perimetre_cible", True),
        (Evenement, "perimetre", False),
    ):
        #  `session.exec(select(<colonne>))` rend des SCALAIRES, pas des tuples à un
        #  élément — contrairement à `session.execute`. La première écriture
        #  dépaquetait `(valeur,)` et levait `ValueError: too many values to unpack`
        #  sur toute chaîne de plus d'un caractère, donc sur *toutes* les valeurs
        #  réelles. `GET /perimetres` répondait 500 en production (12/08/2026), et
        #  aucun test ne couvrait ce router.
        for valeur in session.exec(select(getattr(modele, champ))).all():
            analyse = parse_json_perimetres(valeur) if json_ else parse_perimetres(valeur)
            cites.update(c.strip().lower() for c in analyse if c and c.strip())
    return cites


def _profondeurs(noeuds: list[Perimetre]) -> dict[int, int]:
    par_id = {n.id: n for n in noeuds}
    profondeur: dict[int, int] = {}

    def calculer(noeud: Perimetre) -> int:
        if noeud.id in profondeur:
            return profondeur[noeud.id]
        #  Borné par `vus` : un cycle en base — écrit avant ce router, ou à la main —
        #  ne doit pas suspendre la requête (`standards/04`).
        vus: set[int] = set()
        courant, niveau = noeud, 0
        while courant.parent_id is not None and courant.id not in vus:
            vus.add(courant.id)
            suivant = par_id.get(courant.parent_id)
            if suivant is None:
                break
            niveau += 1
            courant = suivant
        profondeur[noeud.id] = niveau
        return niveau

    for noeud in noeuds:
        calculer(noeud)
    return profondeur


def _concerne_tous(noeud: Perimetre, par_id: dict[int, Perimetre]) -> bool:
    vus: set[int] = set()
    courant: Optional[Perimetre] = noeud
    while courant is not None and courant.id not in vus:
        if courant.portee_globale:
            return True
        vus.add(courant.id)
        courant = par_id.get(courant.parent_id)
    return False


def _lu(
    noeud: Perimetre,
    cites: set[str],
    parent: Optional[str],
    profondeur: int,
    concerne_tous: bool,
    branche: list[Perimetre],
    fixes: dict[str, list[str]],
    deplacements: list[str],
) -> PerimetreRead:
    """Un nœud lu sur le modèle, avec ce que l'arbre seul sait dire.

    🔴 Ce `PerimetreRead` était écrit DEUX FOIS, colonne par colonne, ici même —
    l'arbre et l'orphelin, qui ne diffèrent que par les trois valeurs passées en
    paramètre (#1563). Un champ ajouté au schéma devait l'être aux deux.
    """
    return lire_objet(
        PerimetreRead,
        noeud,
        parent=parent,
        profondeur=profondeur,
        concerne_tous=concerne_tous,
        libelle_court=noeud.libelle_court or noeud.libelle,
        description=noeud.description or "",
        utilise=noeud.code.lower() in cites,
        nb_descendants=len(branche),
        dupliquable=refus_duplication(branche) is None,
        copiable=refus_copie(noeud, branche) is None,
        deplacements=deplacements,
        acces_fixes=fixes.get(noeud.code, []),
    )


def _en_lecture(
    noeuds: list[Perimetre],
    cites: set[str],
    fixes: Optional[dict[str, list[str]]] = None,
    racine: Optional[str] = None,
) -> list[PerimetreRead]:
    """L'arborescence à plat, en ordre d'affichage (parcours en profondeur).

    L'ordre est calculé ici plutôt que côté front : c'est la même question pour
    toutes les rubriques, et deux tris divergents sont un tri de trop. `racine` :
    le périmètre par défaut (`code_par_defaut`), qui ne change pas de niveau.
    """
    fixes = fixes or {}
    par_id = {n.id: n for n in noeuds}
    profondeur = _profondeurs(noeuds)

    enfants = enfants_par_parent(noeuds)

    sortie: list[PerimetreRead] = []
    vus: set[int] = set()

    def descendre(parent_id: Optional[int]) -> None:
        for noeud in enfants.get(parent_id, []):
            if noeud.id in vus:
                continue
            vus.add(noeud.id)
            parent = par_id[noeud.parent_id].code if noeud.parent_id in par_id else None
            sortie.append(
                _lu(
                    noeud,
                    cites,
                    parent,
                    profondeur.get(noeud.id, 0),
                    _concerne_tous(noeud, par_id),
                    descendants(noeud, noeuds),
                    fixes,
                    sens_admis(noeud, noeuds, racine),
                )
            )
            descendre(noeud.id)

    descendre(None)
    #  Un nœud dont le parent a disparu n'apparaîtrait dans aucune branche : on le
    #  rend quand même, sinon l'écran ne permettrait pas de le réparer.
    for noeud in noeuds:
        if noeud.id not in vus:
            sortie.append(
                _lu(
                    noeud,
                    cites,
                    None,
                    0,
                    noeud.portee_globale,
                    descendants(noeud, noeuds),
                    fixes,
                    [],
                )
            )
    return sortie


def _un(session: Session, noeud: Perimetre) -> PerimetreRead:
    """Un nœud rendu **dans le contexte de l'arbre entier**.

    Le calculer isolément donnerait un `parent` toujours nul et une `profondeur`
    toujours à zéro : ces deux valeurs ne se déduisent pas d'une ligne seule.
    """
    tous = list(session.exec(select(Perimetre)).all())
    lus = _en_lecture(tous, _codes_cites(session), types_fixes_par_code(session), code_par_defaut())
    for lu in lus:
        if lu.id == noeud.id:
            return lu
    raise HTTPException(500, "Périmètre introuvable après écriture.")


def _noeud(session: Session, perimetre_id: int) -> Perimetre:
    noeud = ou_404(session, Perimetre, perimetre_id, "Périmètre")
    return noeud


def _resoudre_parent(session: Session, code_parent: Optional[str]) -> Optional[int]:
    if not code_parent:
        return None
    parent = session.exec(select(Perimetre).where(Perimetre.code == code_parent)).first()
    if not parent:
        raise HTTPException(422, f"Périmètre parent inconnu : {code_parent}")
    return parent.id


def _refuser_cycle(session: Session, noeud_id: int, parent_id: Optional[int]) -> None:
    """Un nœud ne peut pas devenir son propre ancêtre."""
    courant_id = parent_id
    vus: set[int] = set()
    while courant_id is not None and courant_id not in vus:
        if courant_id == noeud_id:
            raise HTTPException(422, "Ce déplacement ferait d'un périmètre son propre ancêtre.")
        vus.add(courant_id)
        parent = session.get(Perimetre, courant_id)
        courant_id = parent.parent_id if parent else None


# ── Lecture ───────────────────────────────────────────────────────────────────


@router.get("", response_model=list[PerimetreRead])
def lister_perimetres(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    noeuds = session.exec(select(Perimetre)).all()
    return _en_lecture(
        list(noeuds), _codes_cites(session), types_fixes_par_code(session), code_par_defaut()
    )


# ── Écriture (administration) ─────────────────────────────────────────────────


@router.post("", response_model=PerimetreRead, status_code=201)
def creer_perimetre(
    body: PerimetreCreate,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    code = body.code.strip()
    if not code:
        raise HTTPException(422, "Le code est obligatoire.")
    if session.exec(select(Perimetre).where(Perimetre.code == code)).first():
        raise HTTPException(422, f"Le code « {code} » est déjà utilisé.")

    noeud = Perimetre(
        code=code,
        parent_id=_resoudre_parent(session, body.parent),
        libelle=body.libelle,
        libelle_court=body.libelle_court,
        description=body.description,
        icone=body.icone,
        batiment_id=body.batiment_id,
        portee_globale=body.portee_globale,
        selectionnable=body.selectionnable,
        privatif=body.privatif,
        hors_copropriete=body.hors_copropriete,
        ordre=body.ordre,
        modifie_par_id=admin.id,
        modifie_le=horloge.maintenant(),
    )
    session.add(noeud)
    session.commit()
    invalider_cache()
    return _un(session, noeud)


@router.patch("/{perimetre_id}", response_model=PerimetreRead)
def modifier_perimetre(
    perimetre_id: int,
    body: PerimetreUpdate,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    noeud = _noeud(session, perimetre_id)
    donnees = body.dict(exclude_unset=True)

    if "parent" in donnees:
        parent_id = _resoudre_parent(session, donnees.pop("parent"))
        _refuser_cycle(session, noeud.id, parent_id)
        noeud.parent_id = parent_id
    if "acces_fixes" in donnees:
        fixer_acces(session, noeud.code, donnees.pop("acces_fixes") or [])

    for champ, valeur in donnees.items():
        setattr(noeud, champ, valeur)

    noeud.modifie_par_id = admin.id
    noeud.modifie_le = horloge.maintenant()
    session.add(noeud)
    session.commit()
    invalider_cache()
    return _un(session, noeud)


@router.delete("/{perimetre_id}", status_code=204)
def supprimer_perimetre(
    perimetre_id: int,
    avec_descendants: bool = False,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Supprime un nœud — et sa branche si `avec_descendants`, que l'écran ne pose
    qu'après une confirmation qui les compte.

    🔴 Le drapeau est EXPLICITE : un client resté en cache, qui ignore la
    cascade, rencontre le refus d'avant au lieu d'emporter une branche en silence.
    Refusé dès qu'UN nœud de la branche est cité par un contenu : on désactive.
    """
    noeud = _noeud(session, perimetre_id)
    branche = descendants(noeud, list(session.exec(select(Perimetre)).all()))

    if branche and not avec_descendants:
        raise HTTPException(
            409,
            f"« {noeud.libelle} » contient {len(branche)} sous-périmètre(s). "
            "Confirmez leur suppression, ou déplacez-les d'abord.",
        )

    cites = _codes_cites(session)
    for n in (noeud, *branche):
        if n.code.lower() in cites:
            raise HTTPException(
                409,
                f"« {n.libelle} » est utilisé par des contenus déjà publiés. "
                "Désactivez-le : il disparaîtra de la saisie, et ces contenus garderont "
                "leur libellé et leur visibilité.",
            )

    #  Les enfants avant leurs parents : la clé `parent_id` ne doit jamais
    #  désigner une ligne déjà retirée.
    for n in (*reversed(branche), noeud):
        #  Un équipement qui s'y trouvait le perd, il ne disparaît pas (#2442).
        retirer_liens_du_perimetre(session, n.id)
        session.delete(n)
        session.flush()
    session.commit()
    invalider_cache()
