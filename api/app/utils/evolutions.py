"""Retirer une entrée d'un fil de suivi — **le geste, écrit une seule fois** (#512).

## Pourquoi ce module

Trois objets du site portaient un fil d'évolutions : le **ticket**
(`TicketEvolution`), l'**actualité** (`PublicationEvolution`, supprimée avec sa
table le 30/09/2026 — une actualité EST une affaire, #1177) et l'**événement**
(`EvenementEvolution`). Le geste de suppression n'existait que pour le premier.

Le recopier deux fois aurait été le réflexe évident — et exactement la faute que
`standards/02` interdit. Ce n'est pas une question de lignes : les trois copies
auraient porté chacune leur liste de types effaçables et leur message d'erreur,
et la première divergence serait passée inaperçue, parce qu'un administrateur ne
compare pas le refus d'un écran à celui d'un autre.

⚠️ Le ticket #512 le disait déjà : *« les nouveaux endpoints doivent dire **la
même chose** que lui, ni plus ni moins »*. La seule façon de le garantir est
qu'ils appellent le même code.

## Les deux arbitrages, tranchés le 18/08/2026 et NON rouverts

**Qui** — `require_admin`, jamais `require_cs_or_admin`. Corriger sa propre
entrée (`PATCH`) est un geste ordinaire ; **effacer** fait disparaître une trace
que d'autres ont pu lire et sur laquelle ils ont pu agir. C'est la frontière de
« archiver n'est pas supprimer » : l'irréversible reste à l'administrateur. La
dépendance est posée par chaque endpoint, pas ici — c'est le routeur qui déclare
qui il laisse entrer.

**Quoi** — `commentaire` et `etat` seulement. Une **réponse** appartient à son
auteur, souvent un résident : l'effacer supprimerait la parole de quelqu'un
d'autre, ce qui n'est pas la même chose que retirer une ligne écrite par le
système ou par soi-même.

⚠️ Supprimer une entrée d'état **ne change pas** le statut de l'objet : celui-ci
vit dans sa propre colonne, le fil n'en est que le récit. Le coût est une perte
de traçabilité — on ne saura plus quand l'objet est passé « En cours » —, pas une
incohérence de données. C'est un coût réel : le fil sert de preuve au conseil
syndical face au syndic, et une transition effacée ne se retrouve pas.
"""

from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.auth.deps import peut_editer
from app.utils.recuperer import ou_404

#: Les types d'entrée qu'un humain ÉCRIT — par opposition à celles que le serveur
#: trace lui-même (« Correction : … »).
#:
#: 🔴 C'est LE fait dont dépendent les trois gestes du fil, et il était écrit
#: QUATRE fois (14/09/2026, #779) : ici, dans les deux `PATCH` et dans la
#: création d'une entrée de ticket. Créer, corriger et effacer posent la même
#: question — *cette entrée porte-t-elle le texte de quelqu'un ?* — et une entrée
#: tracée automatiquement répond non aux trois.
#:
#: ⚠️ Le jour où les trois divergeraient — un type créable mais non corrigeable,
#: par exemple — la seconde liste s'écrirait ICI, avec son motif, et non dans une
#: route.
TYPES_SAISIS: tuple[str, ...] = ("commentaire", "etat")

#: Le nom sous lequel la suppression connaît cette liste, et sous lequel le FRONT
#: la tient (`RubriqueHistorique.svelte`).
#:
#: ⚠️ Conservé tel quel : les contextes de build sont `./api` et `./front`, rien
#: de la racine n'entre dans les images — seule la copie est possible, et
#: `test_evolutions_suppression.py` échoue si les deux divergent. Renommer des deux
#: côtés est un lot à part ; le faire en passant casserait le seul lien qui les
#: tient.
TYPES_EFFACABLES: tuple[str, ...] = TYPES_SAISIS

#: Un seul message pour les trois fils. Deux formulations différentes pour le
#: même refus laisseraient croire à deux règles différentes.
REFUS_TYPE = "Cette entrée ne peut pas être supprimée : une réponse appartient à son auteur."


def exiger_saisie_valide(type_saisi: str, nouveau_statut: Any) -> None:
    """Refuse (422) une entrée saisie au fil qui n'est ni un commentaire ni un état,
    ou un changement d'état sans l'état visé.

    Le même refus au fil de l'affaire (`routers/tickets/evolutions`) et à la
    correction de la Suite (`routers/tickets/suite_sections`) — il s'y écrivait
    deux fois, mot pour mot (#2949).
    """
    if type_saisi not in TYPES_SAISIS:
        raise HTTPException(422, "Type invalide (commentaire ou etat)")
    if type_saisi == "etat" and not nouveau_statut:
        raise HTTPException(422, "nouveau_statut requis pour un changement d'état")


def evolution_modifiable(
    session: Session,
    modele: type,
    evol_id: int,
    *,
    champ_parent: str,
    parent_id: int,
    user,
) -> Any:
    """L'entrée, si elle peut être CORRIGÉE par qui la demande — sinon l'erreur.

    🔴 Cette garde était écrite DEUX fois (14/09/2026, #779), dans les deux
    routes `PATCH …/evolutions/{id}` — publications et tickets —, y compris le
    tuple `("commentaire", "etat")` **recopié à la main à deux pas du module qui
    le porte déjà**. Trois copies d'une même liste, dont deux qui s'ignoraient.

    ⚠️ **Pourquoi le même tuple que la suppression**, alors que ce sont deux
    gestes : les deux répondent à la même question de fait — *cette entrée
    porte-t-elle un texte écrit par quelqu'un ?* Une entrée « Correction : … »
    tracée automatiquement ne décrit le geste de personne : on ne la corrige pas
    plus qu'on ne l'efface.

    Le jour où les deux divergeraient — un type modifiable mais non effaçable —
    c'est ICI que la seconde liste s'écrirait, avec son motif, et non dans une
    route.

    ⚠️ Les trois refus dans cet ordre, et il compte : l'appartenance d'abord
    (404 — ne pas révéler l'existence), le type ensuite (422 — la demande est
    recevable mais l'objet s'y refuse), le droit en dernier (403). L'inverse
    dirait « accès refusé » sur une entrée qui n'existe pas.
    """
    evol: Any = ou_404(session, modele, evol_id, "Évolution", sous={champ_parent: parent_id})
    if getattr(evol, "type", None) not in TYPES_SAISIS:
        raise HTTPException(422, "Ce type d'évolution ne peut pas être modifié")
    #  L'auteur ou un admin — `peut_editer`, du module central d'autorisation.
    if not peut_editer(evol, user):
        raise HTTPException(403, "Accès refusé")
    return evol


def supprimer_evolution(
    session: Session,
    modele: type,
    evol_id: int,
    *,
    champ_parent: str,
    parent_id: int,
) -> None:
    """Retire une entrée de fil, ou lève l'exception qui explique pourquoi non.

    `champ_parent` est le nom de la clé étrangère (`ticket_id`,
    `publication_id`, `evenement_id`) : c'est la seule chose qui distingue les
    trois fils. La vérifier n'est pas une formalité — sans elle, un identifiant
    d'entrée valide permettrait d'effacer l'entrée d'un AUTRE objet que celui
    dont on a l'adresse, et le contrôle d'accès de l'URL ne servirait à rien.
    """
    evol: Any = ou_404(session, modele, evol_id, "Entrée", sous={champ_parent: parent_id})
    if getattr(evol, "type", None) not in TYPES_EFFACABLES:
        raise HTTPException(422, REFUS_TYPE)
    session.delete(evol)
    session.commit()
