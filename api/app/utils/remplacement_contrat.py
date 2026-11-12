"""Un contrat résilié, remplacé par celui d'un autre prestataire — UNE règle, pour tout le monde.

## La demande (12/11/2026, à l'écran)

*« Comment préciser qu'un prestataire est remplacé par un autre ? Après vérification,
la résiliation de SPEM est effective au 17 novembre : lancez votre contrat au 18
novembre (BOUVIER). »*

## Ce que le modèle porte, et ce qu'il ne porte pas

Deux colonnes sur l'ANCIEN contrat : `resilie_le` (le dernier jour où il court) et
`remplace_par_id` (celui qui prend la suite). Le sens inverse — « ce contrat remplace
SPEM » — se DÉDUIT ici, à la lecture : une colonne sur le nouveau contrat ferait deux
vérités libres de se contredire (A dit « remplacé par B », B dit « remplace C »).

🔴 Le renvoi ne vaut que **daté** : « remplacé par » sans « résilié le » ne dirait pas
quand la suite commence, et l'échéance de l'ancien resterait celle d'un contrat qui se
reconduit. `verifier_remplacement` l'exige.

⚠️ Rien ne l'archive : l'archivage d'un contrat reste une décision du conseil
(`utils/archivage.REGLES["contrat"]` — « un contrat se clôt par décision »). Une fois
la résiliation passée, l'ancien contrat cesse de relancer (visite, préavis) et se
lit « résilié » ; c'est le conseil qui l'envoie aux Archives.
"""

from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.prestataires import ContratEntretien
from app.utils.echeance_contrat import resiliation_effective
from app.utils.recuperer import ou_404

#: Garde-fou d'une chaîne A → B → C : la vérification des cycles l'empêche d'être
#: infinie, cette borne empêche qu'une base abîmée fasse tourner la lecture.
PROFONDEUR_MAX = 20


def verifier_remplacement(
    session: Session,
    contrat: ContratEntretien,
    resilie_le: Optional[date],
    remplace_par_id: Optional[int],
) -> None:
    """Refuse (400) ce qui ne tient pas — avant toute écriture.

    `contrat` est le contrat tel qu'il est AVANT la modification (ou, à la création,
    tel qu'il sera : `id` vide) ; `resilie_le` et `remplace_par_id` sont les valeurs
    qu'il aura APRÈS.
    """
    if resilie_le is not None and resilie_le < contrat.date_debut:
        raise HTTPException(400, "La résiliation ne peut pas précéder le début du contrat.")
    if remplace_par_id is None:
        return
    if resilie_le is None:
        raise HTTPException(
            400,
            "Précisez la date de résiliation : un contrat remplacé s'arrête un jour donné.",
        )
    if contrat.id is not None and remplace_par_id == contrat.id:
        raise HTTPException(400, "Un contrat ne peut pas se remplacer lui-même.")
    suivant = ou_404(session, ContratEntretien, remplace_par_id, "Contrat remplaçant")
    if suivant.copropriete_id != contrat.copropriete_id:
        raise HTTPException(400, "Le contrat remplaçant doit être celui de la même copropriété.")
    #  Un cycle (A → B → A) ferait suivre la chaîne sans fin : on remonte la chaîne du
    #  remplaçant, elle ne doit jamais revenir à ce contrat.
    courant: Optional[ContratEntretien] = suivant
    for _ in range(PROFONDEUR_MAX):
        if courant is None or courant.remplace_par_id is None:
            return
        if contrat.id is not None and courant.remplace_par_id == contrat.id:
            raise HTTPException(
                400, "Ce remplacement boucle : le remplaçant est déjà remplacé par ce contrat."
            )
        courant = session.get(ContratEntretien, courant.remplace_par_id)


def successeur_en_vigueur(
    session: Session, contrat: ContratEntretien, aujourdhui: Optional[date] = None
) -> ContratEntretien:
    """Le contrat qui FAIT FOI aujourd'hui : celui-ci, ou son successeur s'il est résilié.

    La fiche de la copropriété désigne un contrat d'assurance ou de syndic ; quand
    l'assureur change, elle doit montrer le nouveau dès que l'ancien a cessé, sans
    qu'on pense à la rediriger à la main.
    """
    courant = contrat
    for _ in range(PROFONDEUR_MAX):
        if not (courant.remplace_par_id and resiliation_effective(courant, aujourdhui)):
            break
        suivant = session.get(ContratEntretien, courant.remplace_par_id)
        if suivant is None:
            break
        courant = suivant
    return courant


def contrats_lies(
    session: Session, contrats: list[ContratEntretien]
) -> tuple[dict[int, ContratEntretien], dict[int, list[ContratEntretien]]]:
    """Pour une liste de contrats : leur remplaçant, et ceux qu'ils remplacent.

    Lu en deux requêtes pour toute la liste, pas une par ligne (#1838). Rend
    `(remplacants, remplaces)` : `remplacants[id_ancien]` est le contrat qui prend sa
    suite ; `remplaces[id_nouveau]` la liste de ceux qu'il remplace (un assureur peut
    reprendre deux contrats), du plus ancien au plus récent.
    """
    ids = {c.id for c in contrats}
    suivants = {c.remplace_par_id for c in contrats if c.remplace_par_id}
    suivants_lus = (
        {
            c.id: c
            for c in session.exec(
                select(ContratEntretien).where(ContratEntretien.id.in_(suivants))  # type: ignore[union-attr]
            ).all()
        }
        if suivants
        else {}
    )
    anciens = (
        session.exec(
            select(ContratEntretien).where(ContratEntretien.remplace_par_id.in_(ids))
        ).all()  # type: ignore[union-attr]
        if ids
        else []
    )
    remplaces: dict[int, list[ContratEntretien]] = {}
    for ancien in sorted(anciens, key=lambda a: (a.resilie_le or date.max, a.id)):
        remplaces.setdefault(ancien.remplace_par_id, []).append(ancien)
    remplacants = {
        c.id: suivants_lus[c.remplace_par_id] for c in contrats if c.remplace_par_id in suivants_lus
    }
    return remplacants, remplaces
