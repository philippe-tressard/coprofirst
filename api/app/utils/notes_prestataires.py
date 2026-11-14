"""La note d'un prestataire : la moyenne de ses avis, arrondie au dixième.

## Pourquoi ici (#2507, 04/11/2026)

Elle se calculait à TROIS endroits : `moyenneNotes` (`notations.ts`) pour la carte,
une boucle écrite à la main dans l'onglet Reporting, et `round(…, 1)` dans la
synthèse d'un prestataire — dont l'arrondi n'était pas le même (Python arrondit
4,25 au pair, à 4,2 ; le front à 4,3). L'app iOS, qui ne recopie aucune règle du
site, ne la montrait pas. Le serveur la SERT (`PrestataireRead.note_moyenne`).

🔴 `None` et non `0` sans aucun avis : « pas encore noté » et « noté zéro » sont deux
choses différentes, et `0` ferait afficher zéro étoile sur un prestataire que
personne n'a jugé.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, NamedTuple, Optional

from sqlmodel import Session, func, select

from app.models.prestataires import NotationPrestataire


class NoteDuPrestataire(NamedTuple):
    moyenne: Optional[float]
    nombre: int


SANS_AVIS = NoteDuPrestataire(None, 0)

#  🔴 TROIS ÉTATS depuis le 14/11/2026 (arbitré par l'utilisateur) : Mauvais, Neutre,
#  Excellent. La colonne `note` reste un entier, pour que la moyenne et les seuils
#  existants ne bougent pas : un état NOUVEAU s'écrit 1, 3 ou 5. Les anciennes notes
#  (1 à 5) ne sont PAS réécrites : `etat_de_note` les lit à la volée, 1-2 → Mauvais,
#  3 → Neutre, 4-5 → Excellent. Aucune donnée perdue, et un retour arrière du code
#  relit les mêmes lignes.
ETATS = ("mauvais", "neutre", "excellent")
NOTE_DE_ETAT = {"mauvais": 1, "neutre": 3, "excellent": 5}


def etat_de_note(note: int) -> str:
    """L'état d'une note entière (1 à 5) — la conversion lue, sans réécriture."""
    if note <= 2:
        return "mauvais"
    if note == 3:
        return "neutre"
    return "excellent"


def note_moyenne(somme: int, nombre: int) -> Optional[float]:
    """La moyenne arrondie au dixième, la moitié vers le haut (4,25 → 4,3) — `None` sans avis."""
    if not nombre:
        return None
    exacte = Decimal(somme) / Decimal(nombre)
    return float(exacte.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def notes_des_prestataires(session: Session, ids: Iterable[int]) -> dict[int, NoteDuPrestataire]:
    """La note de chaque prestataire, en UNE requête pour la liste (#1838)."""
    voulus = {i for i in ids if i is not None}
    if not voulus:
        return {}
    lignes = session.exec(
        select(
            NotationPrestataire.prestataire_id,
            func.sum(NotationPrestataire.note),
            func.count(NotationPrestataire.id),
        )
        .where(NotationPrestataire.prestataire_id.in_(voulus))  # type: ignore[union-attr]
        .group_by(NotationPrestataire.prestataire_id)
    ).all()
    return {pid: NoteDuPrestataire(note_moyenne(int(s), int(n)), int(n)) for pid, s, n in lignes}


__all__ = [
    "ETATS",
    "NOTE_DE_ETAT",
    "NoteDuPrestataire",
    "SANS_AVIS",
    "etat_de_note",
    "note_moyenne",
    "notes_des_prestataires",
]
