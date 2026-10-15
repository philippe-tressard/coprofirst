"""« Remplacer » n'efface pas les décisions de l'administration (#824).

## Le défaut

Les trois imports Excel exposent le même paramètre `remplacer` sous le même
libellé, dans trois écrans d'administration. Le geste de purge était recopié
**trois fois**, et les trois copies ne purgeaient pas la même chose :

    télécommandes   statut == en_attente   le non-traité
    vigiks          statut == en_attente   le non-traité
    lots            statut != resolu       le non-traité ET le mis de côté

Aucune ne portait de commentaire : rien ne disait si la divergence était voulue
ou recopiée de travers. Et **aucun test n'exerçait `remplacer=True`** — les
trois cas de `test_import_xlsx.py` passent `False`.

## Ce que ce fichier verrouille

`ignore` veut dire *« l'admin a choisi d'écarter cette ligne »*. Réimporter le
même fichier avec « Remplacer » la ressuscitait, en silence : la forme exacte du
seed des périmètres qui annulait les suppressions de l'administration
(13/08/2026). Une décision d'administration n'est pas une donnée d'import.

⚠️ Ces tests visent le **comportement observable** — ce que contient la table
après un réimport — et non le prédicat. Vérifier `_PURGES_PAR_REMPLACER` aurait
recopié la décision au lieu de la constater (`standards/04` §14).
"""

import io

import pytest
from sqlmodel import select

from app.models.core import (
    LotImport,
    StatutImport,
    StatutLotImport,
    TelecommandeImport,
    VigikImport,
)
from app.utils import import_lots, import_telecommandes, import_vigiks

openpyxl = pytest.importorskip(
    "openpyxl",
    reason="openpyxl est une dépendance de production ; son absence rend ces "
    "tests INCONNUS, pas verts",
)


def _classeur(lignes: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    for ligne in lignes:
        wb.active.append(ligne)
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


#:  Les trois imports, avec de quoi les exercer : (nom, module, modèle,
#:  classeur, fabrique d'une ligne ABSENTE du classeur, statut « en attente »).
#:
#:  ⚠️ La ligne témoin est absente du classeur À DESSEIN. Reprendre une ligne
#:  qu'il contient ne prouverait rien : l'identifiant libéré peut revenir, et une
#:  purge suivie d'un réimport rend exactement le même identifiant qu'une purge
#:  qui n'aurait rien fait.
#:
#:  🔴 Le relevé est écrit à la main, et `test_les_trois_imports_sont_couverts`
#:  le confronte au code : un quatrième import apparaîtrait sinon sans que rien
#:  ne le signale, et cette question-ci ne lui serait jamais posée.
_IMPORTS = [
    (
        "lots",
        import_lots,
        LotImport,
        [["Bât", "Lot", "Nom", "Type"], [1, "A101", "DUPONT Jean", "Appartement"]],
        lambda statut: LotImport(
            numero="ABSENT-DU-CLASSEUR",
            batiment_id=9,
            type_raw="AP",
            nom_coproprietaire="MIS DE COTE",
            statut=statut,
        ),
        StatutLotImport.en_attente,
    ),
    (
        "telecommandes",
        import_telecommandes,
        TelecommandeImport,
        [["Copropriétaire", "Locataire", "Réf"], ["DUPONT Jean", "", "TC-001"]],
        lambda statut: TelecommandeImport(
            nom_proprietaire="MIS DE COTE",
            reference="TC-ABSENTE",
            statut=statut,
        ),
        StatutImport.en_attente,
    ),
    (
        "vigiks",
        import_vigiks,
        VigikImport,
        [["Bât", "Appt", "Prop", "Loc", "Code"], [1, "101", "DUPONT Jean", "", "V-001"]],
        lambda statut: VigikImport(
            nom_proprietaire="MIS DE COTE",
            code="V-ABSENT",
            statut=statut,
        ),
        StatutImport.en_attente,
    ),
]

_IDS = [c[0] for c in _IMPORTS]


@pytest.mark.parametrize("nom,module,modele,lignes,ligne,en_attente", _IMPORTS, ids=_IDS)
def test_remplacer_PRESERVE_une_ligne_ecartee_par_l_admin(
    session, nom, module, modele, lignes, ligne, en_attente
):
    """🔴 Le cas qui motive tout : la ligne mise de côté survit au réimport.

    Sans quoi l'admin qui reverse un classeur corrigé retrouve, sans un mot, les
    lignes qu'il avait délibérément écartées — et doit refaire le travail à
    chaque import, en croyant que le logiciel ne l'a pas enregistré.
    """
    ecartee = ligne(type(en_attente).ignore)
    session.add(ecartee)
    session.commit()

    module.importer_depuis_bytes(_classeur(lignes), session, True)

    restantes = session.exec(select(modele)).all()
    ecartees = [ligne for ligne in restantes if ligne.statut.value == "ignore"]
    assert len(ecartees) == 1, (
        f"[{nom}] « Remplacer » a effacé une ligne que l'admin avait écartée. "
        "Un réimport ressuscite alors les lignes mises de côté, sans rien dire."
    )


@pytest.mark.parametrize("nom,module,modele,lignes,ligne,en_attente", _IMPORTS, ids=_IDS)
def test_remplacer_efface_BIEN_le_non_traite(
    session, nom, module, modele, lignes, ligne, en_attente
):
    """Le pendant : sans lui, « préserver » deviendrait « ne rien purger ».

    Un contrôle qui n'exige que la conservation est satisfait par une purge qui
    ne fait rien du tout — et le paramètre `remplacer` deviendrait décoratif.
    """
    temoin = ligne(en_attente)
    session.add(temoin)
    session.commit()

    module.importer_depuis_bytes(_classeur(lignes), session, True)

    #  ⚠️ Le DÉCOMPTE tranche, pas l'identifiant : un identifiant ne dit pas
    #  si la ligne a été remplacée. Comparer les `id` jugerait à côté.
    #  Avant : 1 témoin. Après : 1 ligne, celle du classeur. Sans purge : 2.
    restantes = session.exec(select(modele)).all()
    assert len(restantes) == 1, (
        f"[{nom}] {len(restantes)} lignes après un « Remplacer » : la ligne en "
        "attente n'a pas été purgée, et le paramètre est décoratif."
    )


def test_sans_remplacer_rien_n_est_purge(session):
    """Cas zéro du geste : la purge ne doit se produire QUE sur demande."""
    session.add(
        TelecommandeImport(
            nom_proprietaire="DEJA LA",
            reference="TC-000",
            statut=StatutImport.en_attente,
        )
    )
    session.commit()

    import_telecommandes.importer_depuis_bytes(
        _classeur([["Copro", "Loc", "Réf"], ["DUPONT Jean", "", "TC-001"]]), session, False
    )

    refs = {ligne.reference for ligne in session.exec(select(TelecommandeImport)).all()}
    assert refs == {"TC-000", "TC-001"}, (
        "Un import sans « Remplacer » a effacé des lignes existantes."
    )


def test_les_trois_imports_sont_couverts():
    """Un quatrième module d'import ne doit pas échapper à cette question.

    Le relevé `_IMPORTS` est écrit à la main ; ce test le confronte au code, pour
    qu'un import ajouté soit examiné ici plutôt que découvert au prochain audit.
    """
    import pathlib
    import re

    utils = pathlib.Path(__file__).resolve().parents[1] / "app" / "utils"
    modules = {
        f.stem
        for f in utils.glob("import_*.py")
        if f.stem != "import_xlsx"
        and re.search(r"def _traiter_rows", f.read_text(encoding="utf-8"))
    }
    couverts = {f"import_{nom}" for nom in _IDS}
    assert modules <= couverts, (
        f"import(s) hors du relevé : {sorted(modules - couverts)}. Les ajouter à "
        "`_IMPORTS` après avoir décidé de ce que leur « Remplacer » efface."
    )
