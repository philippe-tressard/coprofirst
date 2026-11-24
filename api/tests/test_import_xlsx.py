"""Les trois imports Excel, exercés sur un vrai classeur (08/08/2026).

**Aucun test n'exerçait `importer_depuis_bytes`.** C'est apparu en factorisant la
mécanique commune aux trois modules d'import (lots, télécommandes, vigiks) :
309 tests passaient au vert et ne disaient strictement rien de la réécriture. Le
comportement a donc été comparé à la main, avant/après, sur un classeur construit
pour l'occasion — puis ce harnais est devenu ce fichier, parce qu'une
vérification ponctuelle ne protège que le jour où on la fait
(`standards/05-tests-et-garde-fous.md` §1).

Ce que ces tests couvrent — le chemin du **téléversement**, celui qu'emprunte
l'interface d'administration : ouverture du classeur, en-tête ignorée, lignes
vides, doublons, noms exclus, accents, et la transaction validée.
"""

import pytest
from sqlmodel import select

from app.models.core import LotImport, TelecommandeImport, VigikImport
from app.utils import import_lots, import_telecommandes, import_vigiks
from app.utils.import_xlsx import normaliser
from tests.aides_xlsx import classeur


# ── normaliser : la fonction que les trois modules partagent ─────────────────


@pytest.mark.parametrize(
    "entree,attendu",
    [
        ("  Élodie   MARTIN ", "ELODIE MARTIN"),  # accents, espaces multiples, bords
        ("DUPONT-martin", "DUPONT-MARTIN"),  # le tiret est signifiant, il reste
        ("ÀÉÎÕÜ", "AEIOU"),
        ("Ça va", "CA VA"),
        (None, ""),
        ("", ""),
    ],
)
def test_normaliser_aplatit_casse_et_accents(entree, attendu):
    """C'est de cette normalisation que dépend l'appariement des accès.

    Un écart ici ne casse rien visiblement : il fait simplement échouer des
    rapprochements nom↔lot, en silence.
    """
    assert normaliser(entree) == attendu


def test_les_trois_modules_exposent_la_meme_normalisation():
    """Ils la ré-exportent ; qu'un seul reparte sur sa copie se verrait ici."""
    for module in (import_lots, import_telecommandes, import_vigiks):
        assert module.normaliser is normaliser, (
            f"{module.__name__} n'utilise plus la normalisation partagée — "
            "l'appariement des accès divergerait entre les trois imports."
        )


# ── Le chemin réel du téléversement ──────────────────────────────────────────


def test_import_telecommandes_compte_doublons_ignores_et_importes(session):
    contenu = classeur(
        [
            ["Copropriétaire", "Locataire", "Référence"],  # en-tête, ignorée
            ["DUPONT Jean", "", "TC-001"],
            ["dupont  jean", "", "TC-002"],  # même personne, autre casse
            ["Élodie MARTIN", "LOCATAIRE X", "TC-003"],
            ["DUPONT Jean", "", "TC-001"],  # doublon exact
            ["ATPE", "", "TC-900"],  # nom exclu (hors résidents)
            [None, None, None],  # ligne vide
        ]
    )
    stats = import_telecommandes.importer_depuis_bytes(contenu, session, False)

    assert stats["importes"] == 3
    assert stats["doublons"] == 1
    assert stats["ignores"] == 1
    assert stats["erreurs"] == []

    lignes = session.exec(select(TelecommandeImport)).all()
    assert len(lignes) == 4  # 3 importées + 1 marquée « ignoré »
    exclue = next(ligne for ligne in lignes if ligne.reference == "TC-900")
    assert exclue.statut.value == "ignore"
    assert "ligne Excel 6" in (exclue.notes_admin or ""), (
        "Le numéro de ligne doit désigner la ligne du FICHIER, en-tête comprise — "
        "c'est ce que l'utilisateur a sous les yeux quand il corrige son classeur."
    )


def test_import_lots_signale_un_batiment_illisible_sans_interrompre(session):
    """Une ligne fautive est rapportée, les autres passent quand même.

    Un import qui s'arrête à la première erreur oblige à recommencer autant de
    fois qu'il y a de fautes de frappe dans le classeur.
    """
    contenu = classeur(
        [
            ["Bât", "Lot", "Nom", "Type"],
            [1, "A101", "DUPONT Jean", "Appartement"],
            ["P", "P12", "DUPONT Jean", "Parking"],  # 'P' n'est pas un bâtiment
            [2, "B201", "Élodie MARTIN", "Appartement"],
            [None, None, None, None],
        ]
    )
    stats = import_lots.importer_depuis_bytes(contenu, session, False)

    assert stats["importes"] == 2
    assert len(stats["erreurs"]) == 1
    assert "P12" in stats["erreurs"][0]
    assert {lot.numero for lot in session.exec(select(LotImport)).all()} == {"A101", "B201"}


def test_un_classeur_sans_donnee_ne_casse_pas(session):
    """Cas zéro : un fichier vide ou réduit à son en-tête n'écrit rien, sans lever."""
    for lignes in ([], [["Nom", "Bât", "Réf"]]):
        stats = import_vigiks.importer_depuis_bytes(classeur(lignes), session, False)
        assert stats["importes"] == 0
        assert stats["erreurs"] == []
    assert session.exec(select(VigikImport)).all() == []


def test_un_fichier_qui_n_est_pas_un_classeur_est_refuse(session):
    """Un PDF renommé en .xlsx doit lever, pas écrire des lignes fantaisistes."""
    with pytest.raises(Exception):
        import_vigiks.importer_depuis_bytes(b"ceci n'est pas un classeur", session, False)
