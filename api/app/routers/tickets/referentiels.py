"""Les tables d'une affaire, servies aux clients (#2508) — `GET /tickets/referentiels`.

## Pourquoi cette route

Le contrat ne servait que des CODES : `panne`, `en_cours`, `syndic`. Les libellés,
les pictogrammes, l'ordre de la grille, les colonnes du Kanban vivaient dans le
front ; l'app iOS les GÉNÉRAIT depuis le front de la version publiée, et dépendait
donc du dépôt du site au lieu de l'API (`standards/09` §8, règle 1). Elle les lit
désormais ici, avec les catégories que CE compte peut poser — la règle même qui
refuse la création (`gestes_affaire.categorie_permise`, 403 sinon).

## D'où vient chaque valeur

Aucune table n'est écrite dans ce routeur : chacune vit avec la règle qu'elle sert,
et sa concordance avec le front est tenue par un test.

- catégories : `categories_ticket` (`GRILLE_CATEGORIES`, `LIBELLES_CATEGORIE`),
  `carnet_entretien.est_du_bati`, `nature_affaire.categorie_reservee` —
  🔒 `test_categories_ticket_concordance.py` ;
- états : `tickets/commun.STATUT_LABELS`, `etat_affaire.affaire_close`,
  `kanban_tickets.colonne_du_ticket` — 🔒 `test_statuts_tickets.py` ;
- colonnes du Kanban : `kanban_tickets.COLONNES_KANBAN` — 🔒 `test_kanban_tickets.py` ;
- natures : `nature_affaire.LIBELLES_NATURE` — 🔒 `test_categories_ticket_concordance.py`.

Lecture authentifiée : la grille dépend du compte, et rien ici n'est public.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import get_current_user
from app.auth.gestes_affaire import categorie_permise
from app.models.core import StatutTicket, Utilisateur
from app.models.tickets import STATUTS_TICKET_SANS_CYCLE
from app.utils.carnet_entretien import est_du_bati
from app.utils.etat_affaire import affaire_close
from app.utils.categories_ticket import CATEGORIES_EN_TETE, GRILLE_CATEGORIES, libelle_categorie
from app.utils.kanban_tickets import COLONNES_KANBAN, colonne_du_ticket
from app.utils.nature_affaire import LIBELLES_NATURE, categorie_reservee
from app.utils.saisie_affaire import sections_essentielles
from .commun import STATUT_LABELS

router = APIRouter()


class CategorieServie(BaseModel):
    code: str
    libelle: str
    emoji: str
    description: str
    #: 📒 Une affaire résolue dans cette catégorie entre au carnet d'entretien.
    carnet: bool
    #: Réservée au conseil syndical (403 pour un autre compte).
    reservee: bool
    #: CE compte peut-il la poser ? — la règle de la création, pas une copie.
    permise: bool
    #: Posée en tête de la grille, pleine ligne (« Actualité »).
    en_tete: bool
    #: Les sections que la saisie ESSENTIELLE montre pour cette catégorie (#2595) ;
    #: les autres se rangent dans « Plus de détails ». Identifiants du cadre.
    sections_essentielles: list[str]


class StatutServi(BaseModel):
    code: str
    libelle: str
    #: Résolue ou annulée : l'affaire quitte le suivi.
    clos: bool
    #: La colonne du Kanban, `None` hors tableau.
    colonne_kanban: Optional[str] = None
    #: Offert dans une Suite. `fermé` (historique) et `publie` (une actualité, sans
    #: cycle) s'affichent sans jamais se proposer.
    proposable: bool


class ColonneKanbanServie(BaseModel):
    code: str
    libelle: str
    #: Le mot court de la brique d'accueil.
    libelle_court: str


class NatureServie(BaseModel):
    code: str
    libelle: str


class ReferentielsAffaires(BaseModel):
    categories: list[CategorieServie]
    statuts: list[StatutServi]
    colonnes_kanban: list[ColonneKanbanServie]
    natures: list[NatureServie]


def _proposable(code: str) -> bool:
    """Un état du cycle (`StatutTicket`), hors celui d'une actualité."""
    return code in {s.value for s in StatutTicket} and code not in STATUTS_TICKET_SANS_CYCLE


def referentiels_pour(user: Utilisateur) -> ReferentielsAffaires:
    """Les tables, pour ce compte. PURE au sens de la base : rien n'est lu."""
    return ReferentielsAffaires(
        categories=[
            CategorieServie(
                code=code,
                libelle=libelle_categorie(code),
                emoji=emoji,
                description=description,
                carnet=est_du_bati(code),
                reservee=categorie_reservee(code),
                permise=categorie_permise(code, user),
                en_tete=code in CATEGORIES_EN_TETE,
                sections_essentielles=sections_essentielles(code),
            )
            for code, emoji, description in GRILLE_CATEGORIES
        ],
        statuts=[
            StatutServi(
                code=code,
                libelle=libelle,
                clos=affaire_close(code),
                colonne_kanban=colonne_du_ticket(code),
                proposable=_proposable(code),
            )
            for code, libelle in STATUT_LABELS.items()
        ],
        colonnes_kanban=[
            ColonneKanbanServie(code=code, libelle=libelle, libelle_court=court)
            for code, libelle, court in COLONNES_KANBAN
        ],
        natures=[
            NatureServie(code=code, libelle=libelle) for code, libelle in LIBELLES_NATURE.items()
        ],
    )


@router.get("/referentiels", response_model=ReferentielsAffaires)
def referentiels(user: Utilisateur = Depends(get_current_user)):
    """Catégories (grille, carnet, réserve, permises à ce compte), états, colonnes, natures."""
    return referentiels_pour(user)
