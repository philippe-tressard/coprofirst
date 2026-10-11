"""Supprimer une ligne ET tout ce qui la référence, sans liste tenue à la main.

## Pourquoi ce module existe (#546, 28/08/2026)

`supprimer_utilisateur` nettoyait **onze** familles de dépendances, énumérées à la
main. Le modèle en compte **cinquante-six**, dont trente-sept en `NOT NULL`.
Vingt-six tables n'étaient donc pas nettoyées : publications, tickets, messages,
idées, sondages, signalements, documents… La suppression réussissait quand même,
parce que SQLite tournait avec `foreign_keys=OFF` — et elle laissait en base des
lignes pointant vers un compte qui n'existe plus.

🔴 **Une liste tenue à la main ne peut pas suivre.** Chaque nouvelle table qui
référence un utilisateur devait être ajoutée ici ; vingt-six l'ont été dans le
modèle et pas dans le nettoyage, sans que rien ne le signale. Ce module lit donc
les **métadonnées SQLAlchemy** : il découvre les références au lieu de les
réciter, et une table créée demain est traitée sans qu'on y pense.

## La règle appliquée, et c'est une décision fonctionnelle

| Référence | Traitement |
|---|---|
| `NOT NULL` (la ligne n'existe pas sans son parent) | la ligne est **supprimée**, et ses propres enfants avec |
| nullable (la référence est un détail de la ligne) | la référence est mise à **NULL**, la ligne reste |

Ce module n'arbitre donc rien : c'est le **schéma** qui dit ce qui part avec le
compte. Arbitrage du 28/08/2026 — « le contenu part avec le compte » —, inversé
pour les affaires le 10/10/2026 (#1688) : leur auteur, celui de leur fil et de
leurs messages est facultatif, et un compte supprimé y devient « Ancien
résident ». Ailleurs, la référence obligatoire emporte encore la ligne.

## Ce que ce module ne fait pas

Il ne connaît **aucune règle métier**. Remettre un statut d'import, recalculer un
compteur, retirer une entrée d'un `..._json` : cela reste à l'appelant, et doit se
faire **avant** l'appel. Ce module ramasse ce qui reste.
"""

from sqlalchemy import delete, select, update
from sqlmodel import SQLModel, Session

#  Profondeur maximale de descente. Un cycle de références ferait boucler
#  indéfiniment ; les lignes déjà vues l'empêchent, ce plafond est la seconde
#  barrière — et il rend l'anomalie visible plutôt que silencieuse.
PROFONDEUR_MAX = 12


def references_entrantes(nom_table: str):
    """Les colonnes qui pointent vers `nom_table.id`, lues dans les métadonnées.

    Rend `[(table, colonne, obligatoire)]`. C'est le cœur du module : rien n'est
    récité, tout est découvert.
    """
    trouvees = []
    for table in SQLModel.metadata.tables.values():
        for colonne in table.columns:
            for fk in colonne.foreign_keys:
                if fk.column.table.name == nom_table and fk.column.name == "id":
                    trouvees.append((table, colonne, not colonne.nullable))
    return trouvees


def purger(session: Session, nom_table: str, ligne_id: int, _vues=None, _profondeur=0) -> dict:
    """Supprime la ligne et tout ce qui en dépend. Rend le compte par table.

    ⚠️ Ne fait **pas** de `commit` : l'appelant décide de la transaction, et c'est
    ce qui permet d'annuler l'ensemble si une règle métier échoue ensuite.
    """
    if _vues is None:
        _vues = set()
    cle = (nom_table, ligne_id)
    if cle in _vues:
        return {}
    if _profondeur > PROFONDEUR_MAX:
        raise RuntimeError(
            f"purge : profondeur {PROFONDEUR_MAX} dépassée sur {nom_table}#{ligne_id} — "
            "cycle de références probable dans le modèle."
        )
    _vues.add(cle)
    comptes: dict[str, int] = {}

    for table, colonne, obligatoire in references_entrantes(nom_table):
        if obligatoire:
            #  La ligne n'existe pas sans son parent : elle part, et ses propres
            #  enfants avec elle. On descend AVANT de supprimer, sinon les
            #  petits-enfants deviendraient orphelins à leur tour.
            ids = [r[0] for r in session.exec(select(table.c.id).where(colonne == ligne_id)).all()]
            #  ⚠️ La descente supprime DÉJÀ la ligne (dernière instruction de cette
            #  fonction) : un `delete` groupé ajouté ici la compterait deux fois.
            #  C'est ce que le test a relevé — « assert 2 == 1 » sur une seule
            #  publication. Un compte rendu faux fait douter du reste.
            for enfant_id in ids:
                sous = purger(session, table.name, enfant_id, _vues, _profondeur + 1)
                for k, v in sous.items():
                    comptes[k] = comptes.get(k, 0) + v
        else:
            #  La référence est un détail de la ligne : elle s'efface, la ligne reste.
            res = session.exec(
                update(table).where(colonne == ligne_id).values({colonne.name: None})
            )
            if res.rowcount:
                comptes[f"{table.name} (délié)"] = (
                    comptes.get(f"{table.name} (délié)", 0) + res.rowcount
                )

    table_cible = SQLModel.metadata.tables[nom_table]
    session.exec(delete(table_cible).where(table_cible.c.id == ligne_id))
    comptes[nom_table] = comptes.get(nom_table, 0) + 1
    return comptes
