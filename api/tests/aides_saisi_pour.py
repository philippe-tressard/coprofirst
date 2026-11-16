"""Le « Saisi pour » éprouvé sur la règle, pas sur la table — écrit une fois (#1495).

`test_proprietaire_ticket.py` (`copie_auteur.proprietaire`) et
`test_proprietaire_expose.py` (`saisi_pour.noms_derives`) portaient chacun la
même classe d'objet factice et la même base à deux comptes, à l'identique.
Deux copies d'un même décor divergent au premier cas qu'on n'ajoute qu'à l'une.
"""

from __future__ import annotations

from sqlmodel import Session

from tests.aides_base import compte


class ObjetSaisiPour:
    """Un porteur des seuls champs que la règle regarde — pas le modèle.

    ⚠️ Volontairement PAS le modèle SQLModel : ces tests portent sur la règle,
    pas sur la table. Un objet nu montre exactement de quoi la fonction dépend —
    et il échouerait si elle se mettait à lire autre chose.
    """

    def __init__(self, auteur_id=None, sp_user=None, sp_nom=None, sp_email=None):
        self.auteur_id = auteur_id
        self.saisi_pour_user_id = sp_user
        self.saisi_pour_nom = sp_nom
        self.saisi_pour_email = sp_email


def alice_et_bruno(session: Session) -> None:
    """Alice (CS, id 1) saisit ; Bruno (id 2) est le résident inscrit pour qui."""
    compte(
        session,
        id=1,
        prenom="Alice",
        nom="Martin",
        email="alice@x.test",
        role="conseil_syndical",
    )
    compte(
        session,
        id=2,
        prenom="Bruno",
        nom="Dupont",
        email="bruno@x.test",
        role="propriétaire",
    )
