"""Dupliquer une branche de l'arborescence — un nœud et tous ses descendants.

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
from app.utils.perimetres import invalider_cache, perimetre_du_batiment
from app.utils.perimetres.branche import (
    CHAMPS_RECOPIES,
    codes_de_la_copie,
    descendants,
    refus_duplication,
)

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
    maintenant = horloge.maintenant()
    freres = [n.ordre for n in tous if n.parent_id == source.parent_id]
    copies: dict[int, Perimetre] = {}
    for n in (source, *branche):
        copie = Perimetre(
            **{champ: getattr(n, champ) for champ in CHAMPS_RECOPIES},
            code=codes[n.id],
            parent_id=source.parent_id if n is source else copies[n.parent_id].id,
            modifie_par_id=admin.id,
            modifie_le=maintenant,
        )
        if n is source:
            #  La tête prend ce que l'administrateur a saisi, et se range en
            #  dernier parmi ses frères. Son abrégé n'est pas repris : « Bât. 1 »
            #  ne nomme pas « Bâtiment 5 », et vide, il retombe sur le libellé.
            copie.libelle = libelle
            copie.libelle_court = None
            copie.description = body.description
            copie.batiment_id = batiment_id
            copie.ordre = max(freres, default=0) + 1
        session.add(copie)
        session.flush()
        copies[n.id] = copie
    session.commit()
    invalider_cache()
    return _un(session, copies[source.id])
