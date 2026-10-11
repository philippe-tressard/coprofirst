"""Le fil d'activité dit OÙ un document a été ajouté (11/10/2026).

Signalé à l'écran : sous le fichier du règlement, le fil disait « Nouveau
document » — sans dire où le trouver. Ce qui est tenu ici :

- chaque catégorie qui a une rubrique est nommée par son onglet et sa rubrique ;
- une pièce jointe d'affaire, un document de prestataire se disent tels quels,
  le second au conseil et à l'administration seulement — comme son lien ;
- un document rangé ailleurs garde « Nouveau document » ;
- le fichier du règlement mène à l'onglet Règlement, et n'apparaît qu'au fil de
  l'administration.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.utils.documents import RUBRIQUES, endroit_document, lien_document
from app.utils.question_reglement.texte import CODE_CATEGORIE
from tests.aides_reglement import client_admin, client_cs, joindre

LIEN_ONGLET_REGLEMENT = "/residence/reglement"
from tests.aides_reglement import moteur_fixture  # noqa: F401

ADMIN = SimpleNamespace(has_role=lambda *roles: True)
RESIDENT = SimpleNamespace(has_role=lambda *roles: False)


def _doc(code: str | None = None, **champs) -> SimpleNamespace:
    valeurs = {"id": 7, "ticket_id": None, "contrat_id": None}
    valeurs.update(champs)
    return SimpleNamespace(categorie=SimpleNamespace(code=code) if code else None, **valeurs)


@pytest.mark.parametrize(
    "code, attendu",
    [
        ("plan_residence", "Document ajouté dans Résidence › Fiche, rubrique Plans"),
        (
            "reglement_copropriete",
            "Document ajouté dans Résidence › Fiche, rubrique Règlement de copropriété",
        ),
        ("pv_ag", "Document ajouté dans Résidence › Fiche, rubrique Comptes-rendus d'AG"),
        (
            CODE_CATEGORIE,
            "Document ajouté dans Résidence › Règlement, parmi les textes lus par l'assistant",
        ),
        ("autre_categorie", "Nouveau document"),
        (None, "Nouveau document"),
    ],
)
def test_la_rubrique_est_nommee_par_son_onglet(code, attendu):
    assert endroit_document(_doc(code), RESIDENT) == attendu


def test_affaire_et_prestataire_se_disent_tels_quels():
    assert endroit_document(_doc(ticket_id=3), RESIDENT) == "Pièce jointe ajoutée à une affaire"
    contrat = _doc(contrat_id=4)
    assert endroit_document(contrat, ADMIN) == "Document ajouté à la fiche d'un prestataire"
    #  Comme le lien : le résident n'a pas accès à la fiche d'un prestataire.
    assert endroit_document(contrat, RESIDENT) == "Nouveau document"


def test_chaque_rubrique_nommee_a_un_lien():
    """Une phrase qui nomme un endroit sans y mener : le défaut que `lien_document`
    a fermé pour les notifications (`utils/documents`, en tête)."""
    for code in RUBRIQUES:
        assert lien_document(_doc(code), ADMIN, session=None), code
    assert lien_document(_doc(CODE_CATEGORIE), ADMIN, session=None) == LIEN_ONGLET_REGLEMENT


def test_le_fichier_du_reglement_au_fil_de_l_administration_seule(moteur):
    admin = client_admin(moteur)
    joindre(admin, moteur)
    (carte,) = [i for i in admin.get("/flux").json()["items"] if i["type"] == "document"]
    assert carte["detail"].startswith("Document ajouté dans Résidence › Règlement")
    assert carte["lien"] == LIEN_ONGLET_REGLEMENT
    assert [
        i for i in client_cs(moteur).get("/flux").json()["items"] if i["type"] == "document"
    ] == []
