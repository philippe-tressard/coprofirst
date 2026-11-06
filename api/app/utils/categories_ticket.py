"""Le libellé français d'une catégorie de ticket — côté serveur.

## 🔴 Pourquoi cette table existe, alors qu'elle existe déjà côté front

Signalé le 31/08/2026, capture à l'appui : le courriel envoyé au syndic affichait

    Ticket #TK-079205 · CategorieTicket.panne · Soumis le 31/08/2026

`CategorieTicket` est une `(str, Enum)`, et depuis Python 3.11 son `__str__` rend
`CategorieTicket.panne` et non `panne`. Le gabarit recevait donc l'énumération
brute, et le destinataire lisait un identifiant de code Python.

⚠️ Les libellés vivaient **uniquement dans `front/src/lib/tickets.ts`**. Le
courriel est composé côté serveur : il n'y avait rien à afficher.

## La duplication est INÉVITABLE, et c'est documenté

Les contextes de construction Docker sont `./api` et `./front` : **rien de la
racine n'entre dans les images**. Un module partagé est donc impossible, et le
seul motif viable dans ce dépôt est *copie + test de concordance* — le même que
`perimetre_label` (front et API), verrouillé par `lint:libelle-perimetre`.

🔒 `api/tests/test_categories_ticket_concordance.py` lit la table du front et
exige que les deux disent la même chose. Sans lui, la copie diverge au premier
libellé retouché, et c'est le courriel — que personne ne relit — qui garde
l'ancien.
"""

from __future__ import annotations
from app.utils.valeurs import valeur

#  ⚠️ Les VALEURS sont celles de `CategorieTicket` (`models/tickets.py`), les
#  libellés ceux de `CATEGORIES` (`front/src/lib/tickets.ts`). Les deux sont
#  vérifiés : la première liste par l'énumération, la seconde par le test de
#  concordance.
LIBELLES_CATEGORIE: dict[str, str] = {
    "panne": "Panne",
    "nuisance": "Nuisance & propreté",
    "espaces_verts": "Espaces verts",
    "sinistre": "Sinistre",
    "etude_travaux": "Étude & travaux",
    "entretien": "Entretien",
    "acces_accueil": "Accès & accueil",
    "question": "Question",
    "bug": "Bug",
    "actualite": "Actualité",
}

#: La grille « Nouvelle affaire », servie par `GET /tickets/referentiels` (#2508) —
#: dans l'ORDRE de la grille, qui est une décision (fréquence attendue, arbitrée au
#: front : `CATEGORIES_TICKET`, `tickets-categories.ts`). Chaque entrée : la valeur,
#: son pictogramme, ce qu'elle recouvre. 🔒 `test_categories_ticket_concordance.py`
#: compare ordre, pictogramme et description à la table du front.
GRILLE_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("panne", "🛠️", "Ascenseur, chauffage, éclairage, fuite, porte — à réparer"),
    ("nuisance", "📢", "Bruit, odeurs, stationnement…"),
    ("acces_accueil", "🔑", "Interphone, boîte aux lettres, emménagement"),
    ("espaces_verts", "🌳", "Élagage, haies, arrosage, allées…"),
    ("sinistre", "💧", "Dégât constaté : eau, incendie, vandalisme…"),
    ("etude_travaux", "🏗️", "Diagnostic, sondage, devis, chantier suivi par le conseil"),
    ("entretien", "🧰", "Visite ou maintenance d’un prestataire, récurrente ou non"),
    ("question", "❓", "Information, procédure…"),
    ("bug", "🐛", "Pb technique sur le site"),
    ("actualite", "📰", "Information — suivi optionnel"),
)

#: Les catégories posées EN TÊTE de la grille, pleine ligne : on choisit d'abord
#: entre informer et faire traiter (#1092).
CATEGORIES_EN_TETE: tuple[str, ...] = ("actualite",)


def libelle_categorie(categorie) -> str:
    """« panne » → « Panne ». Rend la valeur telle quelle si elle est inconnue.

    ⚠️ Accepte l'énumération ET la chaîne : le ticket porte l'une ou l'autre
    selon qu'il vient de la base ou d'un brouillon d'aperçu. Passer par
    `getattr(x, "value", x)` évite de le savoir — et c'est justement l'oubli de
    cette nuance qui a fait rendre `CategorieTicket.panne` dans un courriel.

    Une catégorie inconnue rend sa valeur brute plutôt qu'une chaîne vide : mieux
    vaut un mot non traduit qu'une ligne qui disparaît sans rien dire.
    """
    if not categorie:
        return ""
    brute = str(valeur(categorie))
    return LIBELLES_CATEGORIE.get(brute, brute)


#  ══════════════════════════════════════════════════════════════════════════
#  L'URGENCE D'UN TICKET — une seule écriture, des deux côtés (#820)
#
#  🔴 « Ce ticket est urgent » s'écrivait HUIT fois : cinq côté front
#  (`CarteTicket`, `FormulaireTicket`, `VueTickets`, `FluxCard`, `flux.ts`) et
#  trois côté API (`flux/sante.py`, `tickets/apercu.py`, `tickets/courriels.py`).
#  Toutes testaient `categorie == "urgence"`.
#
#  Or `tickets/commun.py` écrivait déjà, en commentaire, la vérité contraire :
#  *« Pas de colonne `urgente` : l'urgence d'un ticket EST sa priorité »* — la
#  case « Urgent » du formulaire pose `priorite = haute` depuis #766. Le produit
#  avait donc DEUX façons de dire qu'un ticket presse, et huit endroits n'en
#  connaissaient qu'une.
#
#  La catégorie « urgence » a été retirée (migration 0177) : elle répondait à la
#  question du DÉLAI dans la liste qui pose celle de la NATURE. Cette fonction
#  est ce qui reste, et il n'y en a qu'une.
#  ══════════════════════════════════════════════════════════════════════════


#: Comment une PRIORITÉ se dit — `PrioriteTicket` (`models/tickets.py`). Le site
#: n'en montre que l'urgence (« ⚡ Urgente », `#lib/tickets.PRIORITE_BREVE`) ;
#: un courriel qui l'écrit en toutes lettres (la relance au syndic) la prend ICI,
#: jamais brute (05/11/2026, `test_enumerations_en_clair`).
LIBELLES_PRIORITE: dict[str, str] = {"basse": "Basse", "normale": "Normale", "haute": "Haute"}


def libelle_priorite(priorite) -> str:
    """« haute » → « Haute ». Une valeur inconnue est rendue telle quelle : elle se voit."""
    cle = str(valeur(priorite) or "")
    return LIBELLES_PRIORITE.get(cle, cle)


def ticket_urgent(ticket) -> bool:
    """Un ticket presse-t-il ? La priorité le dit, et elle seule.

    ⚠️ Accepte l'énumération comme la chaîne, pour la même raison que
    `libelle_categorie` : le ticket porte l'une ou l'autre selon qu'il vient de
    la base ou d'un brouillon d'aperçu, et l'oubli de cette nuance a déjà fait
    rendre `CategorieTicket.panne` dans un courriel.
    """
    if ticket is None:
        return False
    priorite = getattr(ticket, "priorite", None)
    return str(valeur(priorite)) == "haute"
