"""Les PRESTATAIRES d'une affaire — une liste ordonnée, lue et écrite ici seulement (#2704).

## Pourquoi (12/11/2026, coprofirst-ios#181)

Une affaire n'avait qu'un intervenant (`Ticket.prestataire_id`). Elle en porte
désormais une liste, dans l'ordre de saisie (`ticket_prestataire`, `rang`).
Les dix arbitrages du ticket sont retenus tels quels ; ce module en porte les
règles de liste, `utils/intervenant` celles du conseil et du bâti.

## 🔴 La colonne reste, et elle MÈNE

`Ticket.prestataire_id` est tenu égal au premier de la liste à chaque écriture
(`poser`) : la version précédente du code la lit et l'écrit encore, et revenir à
son image ne demande aucune restauration (#1757). La liste se lit donc par
`liste_effective(colonne, lignes)` : la colonne en tête, les lignes pour la
suite. Si une version antérieure a changé l'intervenant pendant un retour
arrière, sa décision vaut celle d'un client ancien (arbitrage Q2) : elle a
remplacé le PREMIER, les autres restent.

## Un client ancien n'efface personne (Q2)

Il n'envoie que `prestataire_id` : égal au premier, rien ne change ; différent,
il remplace le premier ; `null`, il vide la liste. `prestataire_ids` présent
prime ; les deux présents et incohérents → 422. Un doublon → 422 (Q3).
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.prestataires import Prestataire
from app.models.tickets import TicketPrestataire
from app.utils.archivage import est_archivable
from app.utils.corrections_texte import ajouts_retraits, prestataires as phrases_prestataires
from app.utils.recuperer import ou_404


def liste_effective(premier: Optional[int], lignes: Sequence[int]) -> list[int]:
    """La liste que porte l'affaire : `premier` (la colonne) en tête, puis la suite des lignes.

    C'est aussi ce que fait `prestataire_id` seul, envoyé par un client ancien :
    il remplace le premier et garde les autres (Q2). Une seule écriture.
    """
    if premier is None:
        return []
    return [premier] + [i for i in list(lignes)[1:] if i != premier]


def lignes_par_affaire(session: Session, ticket_ids: Iterable[int]) -> dict[int, list[int]]:
    """Les lignes de `ticket_prestataire`, par affaire et dans l'ordre — UNE requête."""
    ids = [i for i in set(ticket_ids) if i is not None]
    par: dict[int, list[int]] = {}
    if not ids:
        return par
    for ticket_id, prestataire_id in session.exec(
        select(TicketPrestataire.ticket_id, TicketPrestataire.prestataire_id)
        .where(TicketPrestataire.ticket_id.in_(ids))  # type: ignore[union-attr]
        .order_by(TicketPrestataire.ticket_id, TicketPrestataire.rang, TicketPrestataire.id)
    ).all():
        par.setdefault(ticket_id, []).append(prestataire_id)
    return par


def prestataires_de(
    session: Session, ticket: Any, lignes: Optional[Sequence[int]] = None
) -> list[int]:
    """Les prestataires de cette affaire, dans l'ordre. `lignes` : déjà lues par une liste."""
    if lignes is None:
        lignes = lignes_par_affaire(session, [ticket.id]).get(ticket.id, []) if ticket.id else []
    return liste_effective(ticket.prestataire_id, lignes)


def par_affaire(session: Session, tickets: Sequence[Any]) -> dict[int, list[int]]:
    """Les prestataires de chaque affaire d'une liste — sans requête par affaire."""
    lignes = lignes_par_affaire(session, [t.id for t in tickets])
    return {t.id: liste_effective(t.prestataire_id, lignes.get(t.id, [])) for t in tickets}


def presents(session: Session, ids: Sequence[int]) -> list[Prestataire]:
    """Les lignes, dans l'ordre ; une ligne effacée se tait (`session.get`, préchargeable)."""
    return [p for i in ids if (p := session.get(Prestataire, i)) is not None]


def noms(session: Session, ids: Sequence[int]) -> list[str]:
    """Leurs noms, dans l'ordre."""
    return [p.nom for p in presents(session, ids)]


def libelle(session: Session, ids: Sequence[int]) -> str:
    """« Otis, Schindler » — ce que la synthèse, l'archive et la recherche nomment."""
    return ", ".join(noms(session, ids))


def _envoye(body: Any, champ: str) -> bool:
    return champ in getattr(body, "model_fields_set", set())


def liste_demandee(body: Any, actuelle: Sequence[int]) -> Optional[list[int]]:
    """La liste que le corps demande, ou `None` s'il ne dit rien des prestataires (Q2, Q3)."""
    if _envoye(body, "prestataire_ids"):
        ids = list(getattr(body, "prestataire_ids", None) or [])
        if len(set(ids)) != len(ids):
            raise HTTPException(422, "Un prestataire figure deux fois dans la liste")
        premier = ids[0] if ids else None
        if _envoye(body, "prestataire_id") and body.prestataire_id != premier:
            raise HTTPException(
                422, "prestataire_id doit être le premier de prestataire_ids, ou absent"
            )
        return ids
    if _envoye(body, "prestataire_id"):
        return liste_effective(body.prestataire_id, actuelle)
    return None


def exiger_prestataires(session: Session, ids: Sequence[int], actuelle: Sequence[int]) -> None:
    """Chacun existe (404) ; un prestataire archivé ne s'AJOUTE pas, il reste s'il y était (Q3)."""
    for i in ids:
        p = ou_404(session, Prestataire, i, "Prestataire")
        if i not in actuelle and est_archivable("prestataire", p):
            raise HTTPException(422, f"Le prestataire « {p.nom} » est archivé")


def historique(session: Session, avant: Sequence[int], apres: Sequence[int]) -> list[str]:
    """« Prestataire ajouté : Otis » · « Prestataire retiré : Schindler » (Q5)."""
    ajoutes, retires = ajouts_retraits(avant, apres)
    return phrases_prestataires(
        noms(session, ajoutes), noms(session, retires), list(avant) != list(apres)
    )


def poser(session: Session, ticket: Any, ids: Sequence[int]) -> None:
    """Écrit la liste : les lignes ET la colonne, égale au premier. Sans `commit`.

    En place, jamais « tout retirer puis tout remettre » : l'unité de travail
    émet les INSERT avant les DELETE, et la contrainte d'unicité refuserait de
    reposer une ligne qu'on vient de retirer.
    """
    ticket.prestataire_id = ids[0] if ids else None
    existantes = {
        lg.prestataire_id: lg
        for lg in session.exec(
            select(TicketPrestataire).where(TicketPrestataire.ticket_id == ticket.id)
        ).all()
    }
    for prestataire_id, ligne in existantes.items():
        if prestataire_id not in ids:
            session.delete(ligne)
    for rang, prestataire_id in enumerate(ids):
        ligne = existantes.get(prestataire_id)
        if ligne is None:
            #  Une colonne héritée peut nommer un prestataire disparu : la colonne
            #  le garde (la lecture se tait), la clé étrangère refuserait la ligne.
            if session.get(Prestataire, prestataire_id) is None:
                continue
            session.add(
                TicketPrestataire(ticket_id=ticket.id, prestataire_id=prestataire_id, rang=rang)
            )
        elif ligne.rang != rang:
            ligne.rang = rang
            session.add(ligne)
    session.add(ticket)


def supprimer_de(session: Session, ticket_id: int) -> int:
    """Une affaire supprimée ne laisse aucune ligne. Sans `commit` ; rend le nombre."""
    lignes = session.exec(
        select(TicketPrestataire).where(TicketPrestataire.ticket_id == ticket_id)
    ).all()
    for lg in lignes:
        session.delete(lg)
    return len(lignes)


__all__ = [
    "exiger_prestataires",
    "historique",
    "libelle",
    "liste_demandee",
    "liste_effective",
    "lignes_par_affaire",
    "noms",
    "par_affaire",
    "poser",
    "presents",
    "prestataires_de",
    "supprimer_de",
]
