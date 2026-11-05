"""Ce qu'une affaire EST — actualité, affaire suivie, événement — dérivé, jamais saisi.

## Pourquoi un module (#1091, 23/09/2026)

Depuis l'arbitrage du 22/09, il n'y a plus qu'un objet : l'Affaire. « Actualité »
est une catégorie, réservée au conseil, sans cycle de vie. Trois questions en
découlent, et chacune ne s'écrit qu'ici :

| Question | Fonction |
|---|---|
| est-ce une actualité ? | `est_actualite` |
| sous quels filtres paraît-elle ? | `natures` |
| dans quel état naît-elle, ou passe-t-elle en changeant de catégorie ? | `statut_pour` |

## La règle du filtre, telle que l'utilisateur l'a posée (22 puis 23/09)

> « Actualité : si catégorie Actualité ; Calendrier : si une date est
>   définie ; Activité : le reste »

Les libellés du 22/09 (« Affaires », « Évènement ») ont été remplacés le
23/09 (#1092), quand les pages Actualités et Calendrier ont disparu au profit
de la seule vue Affaires. Ce n'est pas une partition : une actualité datée
paraît sous « Actualité » ET sous « Calendrier ». `natures` rend donc une LISTE, que l'écran interroge — il ne
redérive rien, sinon la règle divergerait au premier cas limite (le motif « deux
copies divergent sur le cas limite », vécu trois fois dans ce dépôt).
"""

from __future__ import annotations

from typing import Any, Optional

from app.models.tickets import CATEGORIES_RESERVEES_AU_CS, CategorieTicket, StatutTicket
from app.utils.perimetres import perimetre_cible_json
from app.utils.valeurs import valeur

ACTUALITE = CategorieTicket.actualite.value


def est_actualite(objet: Any) -> bool:
    """Cet objet est-il une affaire de catégorie « Actualité » ?"""
    return valeur(getattr(objet, "categorie", None)) == ACTUALITE


#: Les trois natures et leur libellé — le filtre de la vue Affaires, dans son
#: ordre. Servies par `GET /tickets/referentiels` (#2508) ; 🔒
#: `test_categories_ticket_concordance.py` les compare à `NATURES` (front).
LIBELLES_NATURE: dict[str, str] = {
    "actualite": "Actualité",
    "calendrier": "Calendrier",
    "activite": "Affaire",
}


def natures(ticket: Any) -> list[str]:
    """Les filtres sous lesquels l'affaire paraît : `actualite`, `calendrier`, `activite`."""
    datee = getattr(ticket, "debut", None) is not None
    if est_actualite(ticket):
        return ["actualite", "calendrier"] if datee else ["actualite"]
    return ["calendrier"] if datee else ["activite"]


def change_de_nature(ticket: Any, nouvelle_categorie: Any) -> bool:
    """La nouvelle catégorie fait-elle passer l'affaire d'actualité à suivie, ou l'inverse ?

    ⚠️ Écrite sur `ACTUALITE`, jamais sur les catégories réservées : Étude &
    travaux et Entretien le sont aussi depuis le 23/09/2026, sans rien changer
    à la nature de l'affaire.
    """
    if nouvelle_categorie is None:
        return False
    return (valeur(nouvelle_categorie) == ACTUALITE) != est_actualite(ticket)


def perimetre_bug() -> str:
    """Le périmètre d'un BOGUE : il n'en a pas — il concerne le site, pas un lieu.

    Le défaut de l'arbre, lu à l'écriture : c'était la constante `PERIMETRE_BUG`,
    qui recopiait le code de la racine (#1567). La règle garde son nom — deux
    gestes l'appliquent (création, correction), et c'est elle qu'ils citent.
    """
    return perimetre_cible_json()


def est_bug(categorie: Any) -> bool:
    """Un bogue du site (#1191, 24/09/2026) — arbitré par l'utilisateur :

    « tout le monde peut en détecter un et donc en ouvrir un, mais seul le
    gestionnaire est notifié, et la rubrique Périmètre n'a pas de sens et doit
    être verrouillée ». Ni diffusion, ni conseil syndical, ni mise en avant.
    """
    return valeur(categorie) == CategorieTicket.bug.value


def categorie_reservee(categorie: Any) -> bool:
    """Un résident ne pose pas cette catégorie (création comme correction)."""
    return valeur(categorie) in CATEGORIES_RESERVEES_AU_CS


def statut_pour(categorie: Any, demande: Optional[str] = None, *, est_cs: bool = False) -> str:
    """L'état d'une affaire de cette catégorie, à la création ou quand elle en change.

    - une actualité est `publie`, toujours : elle n'a pas de cycle, et aucun
      état demandé ne l'y fait entrer ;
    - une affaire suivie est `ouvert`, sauf état demandé par le conseil — dans
      la liste blanche des états PROPOSABLES : `publie` n'en fait pas partie.
    """
    if valeur(categorie) == ACTUALITE:
        return StatutTicket.publie.value
    proposables = {s.value for s in StatutTicket} - {StatutTicket.publie.value}
    if est_cs and demande in proposables:
        return demande
    return StatutTicket.ouvert.value


__all__ = [
    "ACTUALITE",
    "LIBELLES_NATURE",
    "categorie_reservee",
    "change_de_nature",
    "est_actualite",
    "natures",
    "statut_pour",
]
