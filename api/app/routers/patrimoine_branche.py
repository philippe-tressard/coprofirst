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
from app.utils.perimetres import invalider_cache
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


def _verifier_batiment(session: Session, source: Perimetre, batiment_id: Optional[int]) -> None:
    """Le bâtiment de la copie : exigé si la source en a un, refusé sinon."""
    if source.batiment_id is None:
        if batiment_id is not None:
            raise HTTPException(422, "Ce périmètre n'est pas un bâtiment : sa copie non plus.")
        return
    if batiment_id is None:
        raise HTTPException(422, "Choisissez le bâtiment que représente la copie.")
    if session.get(Batiment, batiment_id) is None:
        raise HTTPException(422, "Bâtiment inconnu.")
    deja = session.exec(
        select(Perimetre).where(Perimetre.batiment_id == batiment_id, Perimetre.actif == True)  # noqa: E712
    ).first()
    if deja:
        raise HTTPException(422, f"Ce bâtiment a déjà son périmètre : « {deja.libelle} ».")


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
    _verifier_batiment(session, source, body.batiment_id)

    codes = codes_de_la_copie(source, branche, code)
    existants = {n.code for n in tous}
    pris = [c for c in codes.values() if c in existants]
    if pris:
        raise HTTPException(422, f"Le code « {pris[0]} » est déjà utilisé.")

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
            copie.batiment_id = body.batiment_id
            copie.ordre = max(freres, default=0) + 1
        session.add(copie)
        session.flush()
        copies[n.id] = copie
    session.commit()
    invalider_cache()
    return _un(session, copies[source.id])
