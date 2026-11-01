"""Les équipements — la seule porte du serveur (#2442).

La liste vit en base (`models/equipements`), administrée dans
Admin › Copropriété › Équipements. Ce module dit ce qui s'en lit et ce qui
s'y refuse ; aucun routeur ne relit la table de lui-même.

## Ce que le code connaît encore

`CODES_SYSTEME` : `assurance`, `syndic` et `autre`. La fiche de copropriété
désigne SES contrats d'assurance et de syndic par eux, et « autre » est
l'absence de catégorie que le carnet laisse céder devant la spécialité du
prestataire (`carnet_entretien.type_equipement_resolu`). Leur libellé et leur
icône s'administrent ; ils ne se retirent ni ne se suppriment, sinon ces règles
perdraient leur objet en silence.

`HORS_AFFAIRES` : `assurance` et `syndic` classent un CONTRAT, pas un équipement
sur lequel on intervient — une affaire ne les désigne pas (#1097).
"""

from __future__ import annotations

from typing import Iterable, Literal, Optional

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.models.equipements import Equipement, EquipementPerimetre
from app.models.perimetre import Perimetre
from app.models.prestataires import ContratEntretien, Prestataire
from app.models.tickets import Ticket

ASSURANCE = "assurance"
SYNDIC = "syndic"
AUTRE = "autre"

CODES_SYSTEME: frozenset[str] = frozenset({ASSURANCE, SYNDIC, AUTRE})
HORS_AFFAIRES: frozenset[str] = frozenset({ASSURANCE, SYNDIC})

Usage = Literal["contrat", "affaire"]


def tous(session: Session) -> list[Equipement]:
    """Tous les équipements, retirés compris, dans l'ordre de l'administration."""
    return list(
        session.exec(select(Equipement).order_by(Equipement.ordre, Equipement.libelle)).all()
    )


def pour_affaires(code: str) -> bool:
    """Une affaire peut-elle désigner cet équipement ?"""
    return code not in HORS_AFFAIRES


def codes_saisissables(session: Session, pour: Usage) -> set[str]:
    """Les codes qu'un formulaire peut proposer : actifs, et pour une affaire hors contrats."""
    codes = set(session.exec(select(Equipement.code).where(Equipement.actif == True)).all())  # noqa: E712
    return {c for c in codes if pour_affaires(c)} if pour == "affaire" else codes


def exiger_equipement(session: Session, code: Optional[str], pour: Usage) -> None:
    """422 si le code n'est pas proposé à la saisie — inconnu, retiré, ou hors affaires.

    ⚠️ À n'appeler que sur une valeur qui CHANGE : un contrat dont l'équipement
    a été retiré depuis doit rester modifiable sans qu'on lui en choisisse un autre.
    """
    if code and code not in codes_saisissables(session, pour):
        raise HTTPException(422, "Équipement inconnu")


def libelles(session: Session) -> dict[str, str]:
    """`{code: libellé}` — lu une fois pour une liste, jamais par élément."""
    return {e.code: e.libelle for e in tous(session)}


def libelle_dans(table: dict[str, str], code: Optional[str]) -> str:
    """Le libellé d'un code dans une table déjà lue ; un code inconnu, sans ses tirets bas.

    Le repli est celui d'avant la table : un code supprimé, ou le texte libre
    historique d'une spécialité de prestataire, reste lisible.
    """
    if not code:
        return ""
    return table.get(code) or code.replace("_", " ")


def libelle_equipement(session: Session, code: Optional[str]) -> str:
    """Le libellé d'UN code — pour une liste, `libelles` puis `libelle_dans`."""
    if not code:
        return ""
    trouve = session.exec(select(Equipement.libelle).where(Equipement.code == code)).first()
    return trouve or code.replace("_", " ")


def usages(session: Session, code: str) -> dict[str, int]:
    """Ce qui cite ce code : contrats, affaires, fiches de prestataire."""

    def compte(colonne) -> int:
        return session.exec(select(func.count()).where(colonne == code)).one()

    return {
        "contrats": compte(ContratEntretien.type_equipement),
        "affaires": compte(Ticket.equipement),
        "prestataires": compte(Prestataire.specialite),
    }


def perimetres_lies(session: Session, ids: Iterable[int]) -> dict[int, list[str]]:
    """`{equipement_id: [codes de périmètre]}`, dans l'ordre de l'arbre, en une requête."""
    ids = list(ids)
    lies: dict[int, list[str]] = {i: [] for i in ids}
    if not ids:
        return lies
    lignes = session.exec(
        select(EquipementPerimetre.equipement_id, Perimetre.code)
        .join(Perimetre, col(Perimetre.id) == EquipementPerimetre.perimetre_id)
        .where(col(EquipementPerimetre.equipement_id).in_(ids))
        .order_by(Perimetre.ordre, Perimetre.id)
    ).all()
    for equipement_id, code in lignes:
        lies[equipement_id].append(code)
    return lies


def poser_perimetres(session: Session, equipement: Equipement, codes: list[str]) -> None:
    """Remplace les périmètres liés ; 422 sur un code de périmètre inconnu."""
    voulus = list(dict.fromkeys(c for c in codes if c))
    trouves = (
        session.exec(select(Perimetre).where(col(Perimetre.code).in_(voulus))).all()
        if voulus
        else []
    )
    inconnus = set(voulus) - {p.code for p in trouves}
    if inconnus:
        raise HTTPException(422, f"Périmètre inconnu : {', '.join(sorted(inconnus))}")
    for lien in session.exec(
        select(EquipementPerimetre).where(EquipementPerimetre.equipement_id == equipement.id)
    ).all():
        session.delete(lien)
    session.flush()
    for p in trouves:
        session.add(EquipementPerimetre(equipement_id=equipement.id, perimetre_id=p.id))


def retirer_liens_du_perimetre(session: Session, perimetre_id: int) -> None:
    """Un périmètre supprimé emporte ses liens — jamais l'équipement."""
    for lien in session.exec(
        select(EquipementPerimetre).where(EquipementPerimetre.perimetre_id == perimetre_id)
    ).all():
        session.delete(lien)
