"""Ce qu'est un « compte en attente de validation » — écrit une seule fois.

Trois endroits posaient la question, chacun avec sa propre requête : la liste de
l'écran Admin, sa variante enrichie, et le compteur du tableau de bord. Les trois
écrivaient `Utilisateur.actif == False`, donc les trois donnaient le même chiffre
— et c'est précisément ce qui rendait le défaut indétectable à la relecture : on
vérifie qu'ils sont d'accord, pas qu'ils ont raison (#399).

`actif` répond à « ce compte peut-il se connecter ? ». Il ne répond pas à « reste-t-il
quelque chose à faire dessus ? » : un compte refusé, un compte suspendu et un compte
qui vient de s'inscrire sont tous les trois inactifs, et un seul appelle une action.
C'est `decision_compte_le` qui les sépare — voir la migration 0148 pour ce que le
rétro-remplissage sait, et ce qu'il s'interdit d'inventer.

⚠️ Ne jamais réécrire la condition dans un router. Si un quatrième lecteur apparaît,
il appelle `condition_compte_en_attente()` — c'est le seul moyen pour que la
définition reste unique, et donc corrigible en un seul endroit.
"""

from datetime import datetime
from app.utils import horloge

from sqlalchemy import and_, or_
from sqlmodel import Session, func, select

from app.models.core import StatutUtilisateur, Utilisateur


def condition_compte_en_attente():
    """Clause SQL « ce compte attend une décision de l'administration ».

    À composer dans un `select(...).where(...)` — c'est volontairement une
    condition et non une requête toute faite : les appelants n'ont pas tous
    besoin des mêmes colonnes (une liste, un décompte, une version enrichie).
    """
    return and_(
        Utilisateur.actif == False,  # noqa: E712  (colonne SQL, pas un booléen Python)
        Utilisateur.decision_compte_le.is_(None),
    )


def est_en_attente(user: Utilisateur) -> bool:
    """PURE. La même question que `condition_compte_en_attente`, sur un compte déjà lu.

    🔴 C'est elle que pose le GESTE (`POST /admin/comptes/{id}/traiter`, #2152) :
    la file ne montrait que les comptes en attente, la route acceptait tous les
    autres. Le conseil syndical « validait » ainsi un compte que l'administrateur
    avait désactivé — la liste filtrait, le geste ne refusait rien. Écrite à côté
    de la clause SQL, et 🔒 `test_traiter_compte_en_attente.py` vérifie qu'elles
    répondent pareil dans chaque état.
    """
    return not user.actif and user.decision_compte_le is None


def comptes_en_attente(session: Session) -> list[Utilisateur]:
    """Les comptes qui attendent une décision, du plus ancien au plus récent."""
    return list(
        session.exec(
            select(Utilisateur).where(condition_compte_en_attente()).order_by(Utilisateur.cree_le)
        ).all()
    )


def nb_comptes_en_attente(session: Session) -> int:
    """Combien de comptes attendent une décision."""
    return (
        session.exec(select(func.count(Utilisateur.id)).where(condition_compte_en_attente())).one()
        or 0
    )


def valide_le(user: Utilisateur) -> datetime | None:
    """Quand ce compte OUVERT a été validé — `None` s'il ne l'est pas (#1629).

    La première décision (`decision_compte_le`), qui est la validation pour un
    compte ouvert — sauf le cas rare d'un compte refusé puis validé, qui garde
    la date du refus. À défaut, sa création : la 0148 a rempli les comptes déjà
    ouverts avec `cree_le`, la seule date qu'elle connaissait, et un compte ouvert
    sans décision a été créé ouvert.
    """
    if not user.actif:
        return None
    return user.decision_compte_le or user.cree_le


#: Les deux FERMETURES d'un compte (#1822) — celles dont la purge compte la durée.
REFUS = "refus"
DESACTIVATION = "desactivation"
FERMETURES = (REFUS, DESACTIVATION)


def marquer_decide(
    user: Utilisateur, fermeture: str | None, maintenant: datetime | None = None
) -> None:
    """Acter qu'une décision vient d'être prise sur ce compte.

    À appeler pour les trois issues — validation, refus, désactivation — et pas
    seulement pour celles qui changent `actif`. Le refus n'en changeait aucun :
    c'est pour cela qu'un compte refusé revenait indéfiniment dans la file.

    Idempotent par construction : la date de la **première** décision est celle
    qui compte, la repousser n'apprendrait rien et effacerait un historique.

    `fermeture` — `REFUS`, `DESACTIVATION`, ou `None` pour un compte ouvert
    (validé, réactivé) — dit l'état que la décision laisse, et `compte_ferme_le` depuis
    QUAND : c'est d'elle que la purge compte la durée de conservation (#1822).
    La première date ne le pouvait pas — un compte validé puis désactivé gardait
    la date de sa validation. Une fermeture répétée garde sa date d'origine.
    """
    if fermeture is not None and fermeture not in FERMETURES:
        raise ValueError(f"fermeture inconnue : {fermeture!r}")
    instant = maintenant or horloge.maintenant()
    if user.decision_compte_le is None:
        user.decision_compte_le = instant
    if fermeture is None:
        user.fermeture_compte, user.compte_ferme_le = None, None
    elif user.fermeture_compte != fermeture or user.compte_ferme_le is None:
        user.fermeture_compte, user.compte_ferme_le = fermeture, instant


def est_compte_technique(user: Utilisateur) -> bool:
    """La même question sur un compte déjà lu — voir la clause ci-dessous (#1985)."""
    return user.statut == StatutUtilisateur.admin_technique


def condition_hors_comptes_techniques():
    """Clause SQL « ce compte n'est pas un compte technique » (#1985).

    Les comptes `admin_technique` — l'administrateur et l'opérateur que le seed
    crée — n'habitent pas la résidence : ils n'ont rien à faire dans un choix de
    personne (« Saisi pour », délégation, porteur de badge, locataire d'un bail).
    Sur la démo publique, ils s'y montraient aux visiteurs, adresse comprise.

    `statut` est nullable : un `!=` seul écarterait aussi les comptes sans statut,
    que SQL compare à NULL.
    """
    return or_(
        Utilisateur.statut.is_(None),  # type: ignore[union-attr]
        Utilisateur.statut != StatutUtilisateur.admin_technique,
    )
