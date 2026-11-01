"""Les gestes d'une branche de l'arborescence — la dupliquer, la copier sous
d'autres parents, la déplacer d'un rang ou d'un niveau.

Demandé le 13/10/2026 : « Bâtiment 1 » porte ses espaces (hall, cave, toit…) ;
ajouter un bâtiment, c'était les recréer un par un. La copie reçoit de
l'administrateur son nom, son code et sa description ; ses descendants gardent
les leurs, et toutes leurs caractéristiques.

Module à part de `patrimoine.py` pour le tenir sous 500 lignes (`standards/02`
§6) ; même préfixe, et il en réutilise la lecture (`_un`) plutôt que de la
recopier. Les règles de la branche vivent dans `utils/perimetres/branche.py`.

🔴 **Le bâtiment ne se recopie pas.** `batiment_id` décide QUI LIT un contenu
ciblé (`batiments_cibles`) : une copie de « Bâtiment 1 » qui le garderait ferait
lire aux résidents du bâtiment 1 ce qui est publié pour le nouveau. Quand la
source est un bâtiment, la copie en exige un autre ; sinon elle n'en porte pas.

**…et elle peut le créer** (#1945, arbitré le 14/10/2026) : aucun écran ne crée
de bâtiment, donc « Bâtiment 1 → Bâtiment 5 » n'aboutissait jamais. La copie
reçoit soit un bâtiment existant qui n'a pas encore de périmètre, soit le
numéro d'un bâtiment NEUF — créé dans la même transaction, avec la copropriété
et les caractéristiques du bâtiment copié, sans aucun lot (un lot est un bien,
il ne se recopie pas).

**Copier sous d'autres parents** (01/11/2026) : *« dupliquer un périmètre sur
plusieurs autres catégories, avec les mêmes paramètres »*. La copie garde nom,
caractéristiques et accès fixes ; seul son code change, dérivé de chaque parent.
Tout ou rien : un code déjà pris refuse le geste entier.

**Déplacer** (01/11/2026) : les quatre flèches d'un nœud, règles dans
`utils/perimetres/deplacement.py`.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import Batiment, Utilisateur
from app.models.perimetre import Perimetre
from app.routers.patrimoine import PerimetreRead, _noeud, _un
from app.utils import horloge
from app.utils.acces_choix import fixer_acces, types_fixes_par_code
from app.utils.perimetres import code_par_defaut, invalider_cache, perimetre_du_batiment
from app.utils.perimetres.branche import (
    CHAMPS_RECOPIES,
    code_copie,
    codes_de_la_copie,
    descendants,
    fratrie_de_la_copie,
    refus_copie,
    refus_duplication,
)
from app.utils.perimetres.deplacement import deplacement, refus_deplacement

router = APIRouter(prefix="/perimetres", tags=["perimetres"])


class PerimetreDuplication(BaseModel):
    """Ce que l'administrateur décide pour la COPIE — le reste vient de la source."""

    code: str
    libelle: str
    description: str = ""
    batiment_id: Optional[int] = None
    #: Le NUMÉRO d'un bâtiment à créer pour la copie (« 5 », « E ») — l'autre
    #: façon de répondre, exclusive de `batiment_id`.
    nouveau_batiment: Optional[str] = None


class PerimetreCopie(BaseModel):
    """Les parents sous lesquels poser une copie du nœud — par leur code."""

    parents: list[str]


class PerimetreDeplacement(BaseModel):
    """Une des quatre flèches : `haut`, `bas`, `gauche`, `droite`."""

    sens: str


#: Ce que le bâtiment créé reprend du bâtiment copié : sa description physique.
#: Ni l'identifiant, ni le numéro (saisi), ni les lots.
CARACTERISTIQUES_BATIMENT = (
    "copropriete_id",
    "nb_etages",
    "sous_sol",
    "specificites",
    "nb_appartements",
    "nb_caves",
    "nb_parkings",
    "nb_locaux_commerciaux",
)


def _verifier_batiment(
    session: Session, source: Perimetre, body: PerimetreDuplication
) -> Optional[str]:
    """Le bâtiment de la copie : exigé si la source en a un, refusé sinon.

    Rend le numéro du bâtiment à créer, ou `None` quand la copie en reprend un
    qui existe. Ne crée RIEN : la création attend que la copie entière soit
    acceptée — un code pris ne doit pas laisser un bâtiment orphelin.
    """
    numero = (body.nouveau_batiment or "").strip() or None
    if source.batiment_id is None:
        if body.batiment_id is not None or numero is not None:
            raise HTTPException(422, "Ce périmètre n'est pas un bâtiment : sa copie non plus.")
        return None
    if body.batiment_id is not None and numero is not None:
        raise HTTPException(422, "Un bâtiment existant ou un nouveau : l'un ou l'autre.")
    if numero is not None:
        existants = session.exec(select(Batiment.numero)).all()
        if numero.casefold() in {n.strip().casefold() for n in existants}:
            raise HTTPException(422, f"Le bâtiment « {numero} » existe déjà.")
        return numero
    if body.batiment_id is None:
        raise HTTPException(422, "Choisissez le bâtiment que représente la copie.")
    if session.get(Batiment, body.batiment_id) is None:
        raise HTTPException(422, "Bâtiment inconnu.")
    #  La question « ce bâtiment a-t-il son périmètre ? » est celle de l'arbre —
    #  et celle que la boîte pose pour ne proposer que les bâtiments libres.
    deja = perimetre_du_batiment(body.batiment_id)
    if deja:
        raise HTTPException(422, f"Ce bâtiment a déjà son périmètre : « {deja.libelle} ».")
    return None


def _creer_batiment(session: Session, source: Perimetre, numero: str) -> int:
    """Le bâtiment neuf de la copie, à l'image de celui de la source."""
    modele = session.get(Batiment, source.batiment_id)
    if modele is None:
        raise HTTPException(422, "Le bâtiment du périmètre copié n'existe plus.")
    batiment = Batiment(
        numero=numero, **{champ: getattr(modele, champ) for champ in CARACTERISTIQUES_BATIMENT}
    )
    session.add(batiment)
    session.flush()
    return batiment.id


@router.post("/{perimetre_id}/dupliquer", response_model=PerimetreRead, status_code=201)
def dupliquer_perimetre(
    perimetre_id: int,
    body: PerimetreDuplication,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    source = _noeud(session, perimetre_id)
    tous = list(session.exec(select(Perimetre)).all())
    branche = descendants(source, tous)
    refus = refus_duplication(branche)
    if refus:
        raise HTTPException(422, refus)

    code = body.code.strip()
    libelle = body.libelle.strip()
    if not code or not libelle:
        raise HTTPException(422, "Le libellé et le code sont obligatoires.")
    numero_neuf = _verifier_batiment(session, source, body)

    codes = codes_de_la_copie(source, branche, code)
    existants = {n.code for n in tous}
    pris = [c for c in codes.values() if c in existants]
    if pris:
        raise HTTPException(422, f"Le code « {pris[0]} » est déjà utilisé.")

    batiment_id = _creer_batiment(session, source, numero_neuf) if numero_neuf else body.batiment_id
    tete = _recopier(session, admin, tous, source, branche, codes, source.parent_id)
    #  La tête prend ce que l'administrateur a saisi. Son abrégé n'est pas
    #  repris : « Bât. 1 » ne nomme pas « Bâtiment 5 », et vide, il retombe sur
    #  le libellé.
    tete.libelle = libelle
    tete.libelle_court = None
    tete.description = body.description
    tete.batiment_id = batiment_id
    session.add(tete)
    session.commit()
    invalider_cache()
    return _un(session, tete)


def _recopier(
    session: Session,
    admin: Utilisateur,
    tous: list[Perimetre],
    source: Perimetre,
    branche: list[Perimetre],
    codes: dict[int, str],
    parent_id: Optional[int],
) -> Perimetre:
    """Pose sous `parent_id` une copie de `source` et de sa branche ; rend la tête.

    Chaque nœud reprend `CHAMPS_RECOPIES` et ses accès fixes ; la tête se range
    en dernier parmi ses nouveaux frères (la copie la replace ensuite, #2450). Ne valide pas la transaction : le
    geste appelant décide du reste, puis du `commit`.
    """
    maintenant = horloge.maintenant()
    fixes = types_fixes_par_code(session)
    freres = [n.ordre for n in tous if n.parent_id == parent_id]
    copies: dict[int, Perimetre] = {}
    for n in (source, *branche):
        copie = Perimetre(
            **{champ: getattr(n, champ) for champ in CHAMPS_RECOPIES},
            code=codes[n.id],
            parent_id=parent_id if n is source else copies[n.parent_id].id,
            modifie_par_id=admin.id,
            modifie_le=maintenant,
        )
        if n is source:
            copie.ordre = max(freres, default=0) + 1
        session.add(copie)
        session.flush()
        copies[n.id] = copie
        if fixes.get(n.code):
            fixer_acces(session, copie.code, fixes[n.code])
    return copies[source.id]


@router.post("/{perimetre_id}/copier", response_model=list[PerimetreRead], status_code=201)
def copier_perimetre(
    perimetre_id: int,
    body: PerimetreCopie,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Pose une copie du nœud — et de sa branche — sous chacun des `parents`."""
    source = _noeud(session, perimetre_id)
    tous = list(session.exec(select(Perimetre)).all())
    branche = descendants(source, tous)
    refus = refus_copie(source, branche)
    if refus:
        raise HTTPException(422, refus)

    par_code = {n.code: n for n in tous}
    exclus = {source.id, source.parent_id, *(n.id for n in branche)}
    parents: list[Perimetre] = []
    for code in dict.fromkeys(c.strip() for c in body.parents if c.strip()):
        parent = par_code.get(code)
        if parent is None:
            raise HTTPException(422, f"Périmètre parent inconnu : {code}")
        if parent.id in exclus:
            raise HTTPException(
                422, f"« {parent.libelle} » ne peut pas recevoir une copie de ce périmètre."
            )
        parents.append(parent)
    if not parents:
        raise HTTPException(422, "Choisissez au moins un périmètre où poser la copie.")

    #  Tous les codes d'abord, puis l'écriture : un code pris refuse le geste
    #  ENTIER, plutôt que de laisser la moitié des copies posées.
    parent_source = next((n for n in tous if n.id == source.parent_id), None)
    plan: list[tuple[Perimetre, dict[int, str]]] = []
    pris = {n.code for n in tous}
    for parent in parents:
        tete = code_copie(parent_source.code if parent_source else "", parent.code, source.code)
        codes = codes_de_la_copie(source, branche, tete)
        deja = [c for c in codes.values() if c in pris]
        if deja:
            raise HTTPException(
                422,
                f"« {parent.libelle} » contient déjà le code « {deja[0]} » : rien n'a été copié.",
            )
        pris.update(codes.values())
        plan.append((parent, codes))

    tetes = [_recopier(session, admin, tous, source, branche, codes, p.id) for p, codes in plan]
    #  Chaque copie prend la place de la source parmi ses nouveaux frères (#2450).
    for (parent, _), tete in zip(plan, tetes):
        _renumeroter(session, admin, fratrie_de_la_copie(source, tous, parent.id, tete))
    session.commit()
    invalider_cache()
    return [_un(session, t) for t in tetes]


@router.post("/{perimetre_id}/deplacer", response_model=PerimetreRead)
def deplacer_perimetre(
    perimetre_id: int,
    body: PerimetreDeplacement,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Une des quatre flèches d'un nœud : d'un rang (haut, bas) ou d'un niveau
    (gauche : hors de son parent ; droite : dans le frère qui le précède)."""
    noeud = _noeud(session, perimetre_id)
    tous = list(session.exec(select(Perimetre)).all())
    racine = code_par_defaut()
    arrivee = deplacement(noeud, tous, body.sens, racine)
    if arrivee is None:
        raise HTTPException(422, refus_deplacement(noeud, tous, body.sens, racine))

    noeud.parent_id = arrivee.parent_id
    noeud.modifie_par_id = admin.id
    noeud.modifie_le = horloge.maintenant()
    session.add(noeud)
    _renumeroter(session, admin, arrivee.fratrie)
    session.commit()
    invalider_cache()
    return _un(session, noeud)


def _renumeroter(session: Session, admin: Utilisateur, fratrie: list[Perimetre]) -> None:
    """Donne à chaque frère son rang (0, 1, 2…) dans l'ordre voulu.

    Deux frères à rang égal ne s'échangeraient pas : le tri les départage par
    leur code. Seuls les nœuds dont le rang change sont réécrits.
    """
    maintenant = horloge.maintenant()
    for rang, n in enumerate(fratrie):
        if n.ordre != rang:
            n.ordre = rang
            n.modifie_par_id = admin.id
            n.modifie_le = maintenant
            session.add(n)
