"""Un ticket « Étude & travaux » dans le kanban — la correspondance, écrite une fois.

## Ce que ça fait (#833, 08/09/2026)

Les tickets de la catégorie **Étude & travaux** décrivent un chantier suivi par
le conseil : une étude d'étanchéité, un devis, des travaux. Ils vivaient dans la
liste des tickets pendant que le kanban, lui, ne connaissait que les
**événements** du calendrier — deux endroits pour suivre la même chose.

Le statut du ticket **EST** sa colonne :

=========  ======================  =========================================
Ticket     Colonne                 Ce que ça dit
=========  ======================  =========================================
ouvert     ``cs``                  le conseil instruit
en_ag      ``ag``                  soumis au vote de l'AG
en_cours   ``syndic``              c'est passé au syndic
chez_pres… ``fournisseur``         chez le prestataire
résolu     ``termine``             le chantier est fait
annulé     ``annule``              abandonné
=========  ======================  =========================================

## 🔴 Aucun second champ d'état — arbitrage de Philippe (08/09/2026)

Le kanban **lit** les tickets ; il n'en crée pas de copie. C'est la voie choisie
contre « un événement créé pour chaque ticket », et pour une raison précise :
deux objets décrivant la même affaire divergent au premier geste. Déplacer une
carte changerait alors le statut de l'un et pas de l'autre, et il faudrait
décider lequel fait foi.

C'est déjà la règle des événements, écrite dans `#lib/kanban.ts` :

    « Aucun second champ d'état n'a été créé — deux notions de suivi sur le
      même objet se contredisent au premier écart. »

✅ **Les six colonnes sont atteignables** depuis le 23/09/2026 (#1092, lot 5) :
`fournisseur` et `ag` étaient inatteignables faute d'état, et c'était un
constat, pas un oubli. Les états `en_ag` et `chez_prestataire` sont nés quand
les événements du calendrier sont devenus des affaires.

## Le pendant côté front

`front/src/lib/kanban.ts` porte la même table. Les contextes de build sont
`./api` et `./front` : le partage d'un fichier est impossible, seule la copie
l'est — exactement comme `KANBAN_LABELS` de `calendrier_historique.py`.
`api/tests/test_kanban_tickets.py` échoue si les deux dérivent.
"""

from __future__ import annotations

from typing import Optional
from app.utils.valeurs import valeur

#: La catégorie dont les tickets entrent au kanban. Une seule pour l'instant, et
#: le nommer plutôt que le coder en dur permet d'en ajouter sans chercher.
CATEGORIES_SUIVIES: tuple[str, ...] = ("etude_travaux", "entretien")

#: Statut du ticket → colonne du kanban. **La source unique.**
COLONNE_PAR_STATUT: dict[str, str] = {
    "ouvert": "cs",
    "en_ag": "ag",
    "en_cours": "syndic",
    "chez_prestataire": "fournisseur",
    "résolu": "termine",
    "annulé": "annule",
}


def colonne_du_ticket(statut: Optional[str]) -> Optional[str]:
    """La colonne d'un ticket, ou `None` si son statut n'en désigne aucune.

    ⚠️ `None` plutôt qu'un repli sur `cs` : un statut inconnu doit **sortir** le
    ticket du tableau, pas l'y ranger arbitrairement. Une carte posée dans la
    mauvaise colonne se lit comme une information, et personne ne la remet en
    cause.
    """
    if not statut:
        return None
    return COLONNE_PAR_STATUT.get(str(valeur(statut)))


def suivi_par_defaut(categorie: Optional[str]) -> bool:
    """Vrai si un ticket de cette catégorie entre au kanban à sa création.

    Le conseil peut décocher à la création comme après : c'est une case du
    formulaire, pas une fatalité de la catégorie.
    """
    #  `valeur` : la création passe l'ÉNUMÉRATION, dont `str()` rend
    #  « CategorieTicket.etude_travaux » — le défaut ne se posait jamais (#1092).
    return str(valeur(categorie)) in CATEGORIES_SUIVIES


__all__ = [
    "CATEGORIES_SUIVIES",
    "COLONNE_PAR_STATUT",
    "colonne_du_ticket",
    "suivi_par_defaut",
]
