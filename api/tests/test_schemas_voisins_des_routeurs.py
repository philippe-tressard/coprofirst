"""Les schémas rangés à côté de leur routeur gardent leur comportement (#1566).

`DocumentRead`, `NotificationRead`, `CommandeAccesCreate` et `CommandeAccesRead` ont
quitté `app/schemas.py` pour `routers/documents_schemas.py`,
`routers/notifications_schemas.py` et `routers/acces/resident_schemas.py`. Le
déplacement ne devait changer ni un champ ni une règle : ce fichier le dit. Il
nommait les trois modules pour `test_routeurs_nommes_par_un_test`, qui ne juge plus,
depuis #2914, que les modules portant une route : un module de schémas en est hors.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.routers.acces.resident_schemas import CommandeAccesCreate, CommandeAccesRead
from app.routers.documents_schemas import DocumentRead
from app.routers.notifications_schemas import NotificationRead

MAINTENANT = datetime(2026, 10, 2, 9, 30)


def _document(**champs) -> SimpleNamespace:
    base = dict(
        id=1,
        titre="Règlement",
        fichier_nom="reglement.pdf",
        mime_type="application/pdf",
        perimetre="résidence",
        publie_le=MAINTENANT,
    )
    return SimpleNamespace(**{**base, **champs})


@pytest.mark.parametrize(
    ("stocke", "attendu"),
    [
        ('["batiment_a"]', ["batiment_a"]),
        (["batiment_a"], ["batiment_a"]),
        (None, None),
        ("pas du json", None),
        ('"une chaîne"', None),
        ('{"a": 1}', None),
    ],
)
def test_le_perimetre_d_un_document_sort_en_liste_ou_rien(stocke, attendu):
    """Une valeur abîmée rend `None` : la bibliothèque reste lisible, sans badge."""
    lu = DocumentRead.model_validate(_document(perimetre_cible=stocke))

    assert lu.perimetre_cible == attendu
    assert lu.description == ""  # défaut, pas Optional


def test_une_notification_se_lit_depuis_l_objet_de_la_base():
    lue = NotificationRead.model_validate(
        SimpleNamespace(
            id=7,
            type="info",
            titre="Titre",
            corps="Corps",
            lien=None,
            lue=False,
            urgente=True,
            cree_le=MAINTENANT,
        )
    )

    assert (lue.id, lue.lue, lue.urgente, lue.lien) == (7, False, True, None)


def test_une_commande_d_acces_vaut_une_unite_par_defaut():
    commande = CommandeAccesCreate(lot_id=3, type="vigik")

    assert (commande.quantite, commande.motif) == (1, None)


def test_une_commande_d_acces_se_lit_depuis_l_objet_de_la_base():
    lue = CommandeAccesRead.model_validate(
        SimpleNamespace(
            id=1,
            user_id=2,
            lot_id=3,
            type="telecommande",
            quantite=2,
            motif=None,
            statut="en_attente",
            cree_le=MAINTENANT,
        )
    )

    assert (lue.lot_id, lue.type, lue.quantite) == (3, "telecommande", 2)
