"""La récidive d'un équipement — « la énième réparation » (#1647).

À la production de la synthèse d'une affaire close, le conseil doit voir
d'un coup d'œil qu'elle n'est pas la première sur ce **même équipement** : c'est
la récidive qui justifie un remplacement plutôt qu'une réparation de plus.

## Ce qui est arbitré (03/10/2026)

- **Seuil** : au moins **2 autres** affaires (3 au total) — une seule autre est un
  hasard ;
- **Même équipement ET même périmètre** : deux ascenseurs de bâtiments différents
  portent le même libellé d'équipement sans être le même appareil ;
- **Où** : un bloc « Récidive » dans la Suite de synthèse, avec les liens vers les
  affaires — et nommé dans le message envoyé à l'assistant. **Aucune notification**
  de plus.

## Ce qui compte

Les autres affaires **résolues** (une annulée n'est pas une intervention) dont la
clôture tombe dans les **24 mois** qui précèdent celle-ci. Le relevé est **figé**
avec les métriques à la production : une affaire close plus tard ne s'y ajoute
pas, et un équipement posé APRÈS la production ne la rejoue pas — « Relancer »
recalcule.

## Qui le lit

Le **conseil syndical** seul (`lecture.synthese_lue`) : la synthèse validée est lue
par les copropriétaires, et ce bloc nomme d'AUTRES affaires dont ils n'ont pas à
connaître l'existence. Le serveur retire la clé ; l'écran n'a rien à décider.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, col, select

from app.models.core import Ticket
from app.models.tickets import StatutTicket
from app.utils.affaire_absorbee import pas_absorbee
from app.utils.echeance_contrat import ajouter_mois
from app.utils.perimetres import parse_json_perimetres

#: Le nombre d'AUTRES affaires à partir duquel on parle de récidive.
SEUIL_AUTRES = 2
#: La fenêtre, en mois civils avant la clôture.
FENETRE_MOIS = 24
#: La clé du relevé dans `metriques_json`.
CLE = "recidive"


def perimetre_de(ticket: Ticket) -> tuple[str, ...]:
    """Le périmètre d'une affaire, comparable : les codes triés et dédoublonnés."""
    return tuple(sorted(set(parse_json_perimetres(ticket.perimetre_cible))))


def recidive_de(session: Session, ticket: Ticket, cloture_le: datetime) -> Optional[dict]:
    """Le relevé de récidive de l'affaire, ou `None` sous le seuil (ou sans équipement)."""
    if not ticket.equipement:
        return None
    candidates = session.exec(
        select(Ticket)
        .where(
            Ticket.id != ticket.id,
            Ticket.equipement == ticket.equipement,
            col(Ticket.statut).in_([StatutTicket.résolu.value]),
            col(Ticket.ferme_le) >= ajouter_mois(cloture_le, -FENETRE_MOIS),
            col(Ticket.ferme_le) <= cloture_le,
            pas_absorbee(),  # comptée dans sa principale (#1704)
        )
        .order_by(col(Ticket.ferme_le).desc())
    ).all()
    perimetre = perimetre_de(ticket)
    autres = [t for t in candidates if perimetre_de(t) == perimetre]
    if len(autres) < SEUIL_AUTRES:
        return None
    return {
        "equipement": ticket.equipement,
        "mois": FENETRE_MOIS,
        "autres": [
            {
                "id": t.id,
                "numero": t.numero,
                "titre": t.titre,
                "ferme_le": t.ferme_le.isoformat(),
            }
            for t in autres
        ],
    }


__all__ = ["CLE", "FENETRE_MOIS", "SEUIL_AUTRES", "perimetre_de", "recidive_de"]
