"""Supprimer les enfants d'un objet avant l'objet — et dans le bon ORDRE.

## Pourquoi ce module (#546, 30/08/2026)

Deux endpoints se sont retrouvés à écrire la même chose le même jour — retirer
les documents d'un ticket, puis ceux d'un événement. La troisième occurrence
était en vue (`publication`), et une cascade recopiée diverge comme n'importe
quel autre code : c'est ce qui a produit les deux défauts ci-dessous.

## 🔴 CE QUE CE MODULE PORTE, ET QU'ON NE DEVINE PAS

**SQLAlchemy n'ordonne les `DELETE` d'un même `commit()` que selon les
`Relationship` DÉCLARÉES.** Une clé étrangère seule ne suffit pas.

`Document` ne porte pas de `Relationship` vers `Ticket` ni vers `Evenement` — il
n'a qu'une colonne `ticket_id` / `evenement_id`. L'unité de travail n'a donc
aucune raison d'ordonner les deux suppressions, et elle a émis :

    DELETE FROM ticket WHERE ticket.id = ?      ← en PREMIER

d'où `FOREIGN KEY constraint failed`, **alors que le document était bien marqué
pour suppression**. Tracé sur le SQL réellement émis, pas déduit.

Le `flush()` force l'émission des DELETE enfants avant celui du parent. Il n'est
donc pas défensif : sans lui, la suppression échoue sous `foreign_keys=ON`.

⚠️ Relevé automatique du 30/08/2026 : **13 relations** du schéma sont dans ce cas
— une FK vers une table que le code supprime, sans `Relationship` pour l'ordonner.
Toutes celles qui ne sont pas encore éprouvées par un test le sont dans #546.

## Ce que le régime actuel cache

Jusqu'au 30/08/2026, la production tournait à `foreign_keys=OFF` (l'application
les active depuis, `app/database.py`). Ces suppressions **réussissaient** donc —
en laissant des lignes orphelines qui pointent vers un parent
disparu. Quand la colonne est `NOT NULL` (l'historique d'un événement), ces
lignes sont même irrécupérables : on ne peut pas les rattacher ailleurs.

C'est le vrai coût de #546, et il est déjà payé : activer les clés ne créera pas
le problème, il le rendra visible.
"""

from sqlmodel import Session, select

from app.models.documents import Document
from app.utils.stockage import stockage


def supprimer_documents_de(session: Session, colonne: str, valeur: int) -> int:
    """Retirer les documents rattachés à un porteur, fichier compris.

    `colonne` est le nom de la clé étrangère (`ticket_id`, `evenement_id`…).
    Rend le nombre de documents supprimés — l'appelant peut ainsi décider s'il
    doit `flush()` (cf. `flush_si_necessaire`).

    ⚠️ **Le FICHIER part avec la ligne**, comme dans `delete_document`. Ne
    supprimer que la ligne laisserait sur le disque un fichier que plus aucune
    ligne ne désigne : invisible pour l'application, et donc indestructible.

    ⚠️ **N'appelle ni `flush()` ni `commit()`** : l'appelant reste maître de sa
    transaction, ce qui lui permet d'annuler l'ensemble si une règle métier
    échoue ensuite. C'est la convention de `purge_referentielle.purger()`.
    """
    champ = getattr(Document, colonne)
    documents = session.exec(select(Document).where(champ == valeur)).all()
    for doc in documents:
        stockage().supprimer_de(doc)
        session.delete(doc)
    return len(documents)


def supprimer_lignes_liees(session: Session, *collections) -> int:
    """Marquer pour suppression tout ce que portent ces collections.

    Sert aux enfants déjà atteignables par une `Relationship` (`ticket.evolutions`,
    `ticket.messages`) : la boucle était écrite une fois par collection, et la
    troisième était en vue.

    ⚠️ Chaque collection est matérialisée par `list()` **avant** d'être parcourue :
    supprimer en itérant sur une collection liée la modifie pendant l'itération,
    et SQLAlchemy en saute alors un élément sur deux.

    Rend le nombre total de lignes marquées — de quoi décider du `flush()`.
    """
    total = 0
    for collection in collections:
        for ligne in list(collection):
            session.delete(ligne)
            total += 1
    return total


def flush_si_necessaire(session: Session, *comptes: int) -> None:
    """Émettre les DELETE enfants **avant** celui du parent, si des enfants partent.

    À appeler entre la suppression des enfants et celle du parent. Voir l'en-tête
    de ce module : ce n'est pas une précaution, c'est la seule chose qui garantit
    l'ordre quand la relation n'est portée que par une clé étrangère.

    Le `if` évite un aller-retour inutile quand il n'y avait rien à supprimer —
    et il documente que le `flush()` répond aux enfants, pas au parent.
    """
    if any(comptes):
        session.flush()
