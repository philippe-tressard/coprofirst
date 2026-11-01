"""La catégorie d'un contrat se lit de la MÊME façon des deux côtés (10/09/2026).

## L'incident

Signalé à l'écran : *« dans contrat d'entretien le contrat VMC est affecté à
divers, or dans Contrats il est affecté à la catégorie VMC »*.

Deux lectures de la même notion :

| Écran | Lecture |
|---|---|
| onglet **Contrats** | `typeEquipementDuContrat()` — DÉDUIT la catégorie de la spécialité du prestataire quand le contrat porte « autre » |
| **carnet d'entretien** | le champ brut |

Un contrat de VMC enregistré en « autre », confié à un prestataire de spécialité
`vmc`, apparaissait donc dans deux groupes différents selon l'écran. Aucun des
deux n'était en faute pris isolément : c'est l'écart qui l'était, et rien ne
pouvait le voir.

⚠️ **La catégorie « VMC » existait déjà** — la question posée était *faut-il en
ajouter une ?*, et la réponse est non. Ajouter une catégorie aurait laissé le
défaut intact, avec une entrée de plus dans la liste.

## Pourquoi une copie, et pourquoi ce test

Les contextes de build sont `./api` et `./front` : rien de la racine n'entre dans
les images, donc la règle ne peut pas être partagée — seulement copiée. C'est le
même régime que `etage_label` et que le libellé de périmètre, et le même remède :
un test qui refuse que les deux dérivent.
"""

from __future__ import annotations

import re
from pathlib import Path


from app.utils.carnet_entretien import type_equipement_resolu

FRONT = Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "reporting.ts"


class _Contrat:
    def __init__(self, type_equipement):
        self.type_equipement = type_equipement


def test_une_categorie_REELLE_n_est_jamais_remplacee():
    """Un contrat qui dit « toiture » reste « toiture », quel que soit son
    prestataire — une catégorie posée à la main fait foi."""
    assert type_equipement_resolu(_Contrat("toiture"), "plomberie") == "toiture"


def test_AUTRE_laisse_la_specialite_prendre_le_relais():
    """🔴 Le cas signalé : « autre » n'est pas une catégorie, c'est une ABSENCE
    de catégorie."""
    assert type_equipement_resolu(_Contrat("autre"), "vmc") == "vmc"


def test_sans_specialite_on_reste_sur_AUTRE():
    assert type_equipement_resolu(_Contrat("autre"), None) == "autre"
    assert type_equipement_resolu(_Contrat("autre"), "") == "autre"


def test_un_contrat_SANS_type_retombe_sur_la_specialite():
    assert type_equipement_resolu(_Contrat(None), "ascenseur") == "ascenseur"


def test_ni_type_ni_specialite():
    """Le neutre — jamais `None`, qui ferait un groupe sans nom dans le carnet."""
    assert type_equipement_resolu(_Contrat(None), None) == "autre"


def test_le_FRONT_porte_la_meme_regle():
    """Cas zéro compris : si la fonction front change de forme, ce test le dit.

    On ne compare pas deux implémentations ligne à ligne — on vérifie que la
    règle DÉCISIVE y est : « autre » cède, une vraie catégorie non.
    """
    assert FRONT.exists(), (
        f"{FRONT} est introuvable : ce contrôle ne peut plus rien établir. "
        "Ne pas lire son silence comme un succès."
    )
    source = FRONT.read_text(encoding="utf-8")
    assert "typeEquipementDuContrat" in source, "la fonction front a changé de nom"
    #  La condition qui porte toute la règle, aux espaces près.
    condition = re.search(r"if\s*\(\s*propre\s*&&\s*propre\s*!==\s*'autre'\s*\)", source)
    assert condition, (
        "la règle front ne teste plus « propre !== 'autre' » — les deux côtés "
        "vont diverger, et l'écart se verra sur un écran, pas ici."
    )


def test_les_categories_du_produit_survivent():
    """Cas zéro de la liste : si l'amorce se vidait, les tests ci-dessus passeraient
    encore en ne mesurant rien. Depuis #2442 elle vit dans le seed, administrable."""
    from app.seed.equipements import EQUIPEMENTS

    valeurs = {e["code"] for e in EQUIPEMENTS}
    attendues = {"vmc", "ascenseur", "toiture", "plomberie", "autre"}
    assert attendues <= valeurs, (
        f"catégories disparues de l'amorce des équipements : {sorted(attendues - valeurs)}"
    )
