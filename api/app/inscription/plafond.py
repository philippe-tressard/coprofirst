"""Le plafond du MODE LIMITÉ : 5 comptes actifs au plus (D18, §4.11 règle 2 — R6 #1882).

## Les règles

1. **Le sixième compte est refusé ; aucun compte existant n'est touché.** Le
   plafond ne désactive, ne masque ni n'efface rien : une installation qui en
   comptait déjà davantage les garde tous, et refuse seulement d'en OUVRIR un de
   plus — y compris de rouvrir un compte qu'elle vient de désactiver.
2. **Une seule porte, au niveau de la base** : un compte devient actif par
   plusieurs routes — la validation d'une inscription (`POST
   /admin/comptes/{id}/traiter`), la fiche de l'administrateur (`PATCH
   /admin/utilisateurs/{id}`, qui recopie ses champs) —, et la prochaine en serait
   une de plus. La règle se pose donc sur l'ÉCRITURE : avant chaque flush, tout
   `Utilisateur` qui devient actif est compté (`_avant_flush`). Aucune route ne la
   recopie, aucune ne peut l'oublier.
3. **Ce qui compte** : les comptes actifs de TOUTE l'installation (une
   installation commune additionne ses copropriétés), hors comptes techniques —
   l'administrateur et l'opérateur que le seed crée n'habitent pas la résidence
   (`utils/comptes.condition_hors_comptes_techniques`).
4. **Qui y échappe** (`regime.plafond_applique`) : la référence, une installation
   d'essai, un rôle inconnu, une installation active ou suspendue, la démo, et le
   retour au constat (`REGISTRE_CONSTAT`). La restauration d'une archive
   (`utils/import_copropriete`) écrit par des insertions directes, sans flush
   d'objets : elle rend les comptes tels qu'ils étaient.
5. **Les courriels de sécurité restent** (§4.8) : le plafond ne touche aucun envoi.

🔒 `tests/test_registre_plafond.py`.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import event, func, inspect, select
from sqlalchemy.orm import Session as SessionOrm

from app import contexte
from app.inscription.regime import PLAFOND_COMPTES_ACTIFS, plafond_applique
from app.models.core import StatutUtilisateur, Utilisateur
from app.utils.comptes import condition_hors_comptes_techniques, est_compte_technique

#: Le refus, pour l'administrateur : ce qui se passe, ce qui ne se passe pas, quoi faire.
MESSAGE = (
    f"Mode limité : cette installation compte déjà {PLAFOND_COMPTES_ACTIFS} comptes actifs, "
    "le plafond tant qu'elle n'a pas de bail actif de la référence CoproFirst. Aucun compte "
    "existant n'est touché. Pour ouvrir celui-ci, désactivez d'abord un autre compte "
    "(Administration › Utilisateurs), ou demandez à l'opérateur de l'installation de "
    "l'inscrire au registre (Administration › Installation)."
)


class PlafondAtteint(HTTPException):
    """Le sixième compte actif — 409, et ce qu'il faut faire."""

    def __init__(self) -> None:
        super().__init__(409, MESSAGE)


def _avant(session, user: Utilisateur, champ: str):
    """La valeur EN BASE de ce champ avant ce flush — `None` s'il n'a pas changé.

    L'historique la donne quand le champ a été lu avant d'être écrit ; après un
    commit, l'objet expire, et `user.actif = True` écrit sans lecture n'a pas
    d'« avant » : la base le dit. Sans cela, ce compte passerait sans être compté.
    """
    historique = getattr(inspect(user).attrs, champ).history
    if not historique.added:
        return None
    if historique.deleted:
        return historique.deleted[0]
    colonne = getattr(Utilisateur, champ)
    return session.scalar(select(colonne).where(Utilisateur.id == user.id))


def _devient_actif(session, user: Utilisateur) -> bool:
    """Ce compte, écrit dans ce flush, OUVRE-t-il une place de plus ? (règle 1)"""
    if not user.actif or est_compte_technique(user):
        return False
    etat = inspect(user)
    if etat.pending or etat.transient:
        return True
    if _avant(session, user, "actif") is False:
        return True
    #  Un compte actif qui cesse d'être technique compte désormais.
    return _avant(session, user, "statut") == StatutUtilisateur.admin_technique


def _compter(session) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Utilisateur)
        .where(Utilisateur.actif == True)  # noqa: E712  (colonne SQL)
        .where(condition_hors_comptes_techniques())
    )


def comptes_actifs(session) -> int:
    """Les comptes actifs de l'INSTALLATION, comptes techniques exclus (règle 3).

    Ceux de la base de `session`, plus ceux des autres copropriétés d'une
    installation commune, chacune dans son contexte. Ne rend qu'un nombre.
    """
    total = _compter(session)
    if not contexte.est_commune():
        return total
    try:
        courante = contexte.courante().identifiant
    except contexte.HorsCopropriete:
        courante = None
    for copro in contexte.coproprietes():
        if copro.identifiant == courante:
            continue
        with contexte.dans(copro), contexte.nouvelle_session() as autre:
            total += _compter(autre)
    return total


def _avant_flush(session, _contexte_flush, _instances) -> None:
    """La porte (règle 2) : refuse le flush qui ouvrirait un compte au-delà du plafond."""
    comptes = [o for o in (*session.new, *session.dirty) if isinstance(o, Utilisateur)]
    if not comptes:
        return
    with session.no_autoflush:
        ouverts = sum(1 for user in comptes if _devient_actif(session, user))
        if not ouverts or plafond_applique() is None:
            return
        if comptes_actifs(session) + ouverts > PLAFOND_COMPTES_ACTIFS:
            raise PlafondAtteint()


def installer() -> None:
    """Pose la porte sur toute session de l'application — une fois."""
    if not event.contains(SessionOrm, "before_flush", _avant_flush):
        event.listen(SessionOrm, "before_flush", _avant_flush)


installer()
