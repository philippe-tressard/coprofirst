"""Ce qu'un nœud de l'arbre PORTE, sa lecture le REND — `PerimetreRead` (#1563).

Sorti de `test_lectures_rendent_le_modele.py` le 01/11/2026 (#2450), qui en dit
le pourquoi : une lecture recopiée colonne par colonne perd sans un mot ce
qu'elle oublie. Ici, l'arbre et l'orphelin — les deux écritures d'avant —, la
sortie JSON entière, champ par champ.
"""

from __future__ import annotations

from app.models.perimetre import Perimetre

# ── patrimoine : PerimetreRead (deux écritures, dont l'orphelin) ──────────────


def test_perimetre_read_arbre_et_orphelin():
    from app.routers.patrimoine import _en_lecture

    racine = Perimetre(
        id=1,
        code="residence",
        libelle="Résidence",
        libelle_court="Rés.",
        description="Tout",
        icone="maison",
        portee_globale=True,
        selectionnable=False,
        ordre=0,
    )
    enfant = Perimetre(
        id=2,
        code="Bat-A",
        parent_id=1,
        libelle="Bâtiment A",
        libelle_court=None,
        description=None,
        batiment_id=7,
        privatif=True,
        hors_copropriete=True,
        actif=False,
        ordre=3,
    )
    orphelin = Perimetre(
        id=3, code="perdu", parent_id=999, libelle="Perdu", description="", portee_globale=True
    )
    lus = [lu.model_dump(mode="json") for lu in _en_lecture([racine, enfant, orphelin], {"bat-a"})]
    assert lus == ATTENDU_PERIMETRES, lus


# ── Les sorties attendues ─────────────────────────────────────────────────────

_NOEUD = {
    "parent": None,
    "icone": None,
    "batiment_id": None,
    "profondeur": 0,
    "ordre": 0,
    "actif": True,
    "portee_globale": False,
    "concerne_tous": False,
    "selectionnable": True,
    "privatif": False,
    "hors_copropriete": False,
    "utilise": False,
    #  Ajoutés le 13/10/2026 (dupliquer, supprimer une branche) : lus sur
    #  `utils/perimetres/branche`, pas sur une colonne.
    "nb_descendants": 0,
    "dupliquable": False,
    #  Ajouté le 17/10/2026 (#2060) : lu dans la configuration des accès fixes.
    "acces_fixes": [],
    #  Ajoutés le 01/11/2026 (copier ailleurs, les quatre flèches) : lus sur
    #  `utils/perimetres/branche` et `deplacement`.
    "copiable": True,
    "deplacements": [],
}
ATTENDU_PERIMETRES = [
    {
        **_NOEUD,
        "id": 1,
        "code": "residence",
        "libelle": "Résidence",
        "libelle_court": "Rés.",
        "description": "Tout",
        "icone": "maison",
        "portee_globale": True,
        "concerne_tous": True,
        "selectionnable": False,
        #  Sa branche porte un bâtiment (Bat-A) : elle ne se duplique pas d'un bloc,
        #  ni ne se copie ailleurs. Seule à la racine : aucune flèche.
        "nb_descendants": 1,
        "copiable": False,
    },
    {
        **_NOEUD,
        "id": 2,
        "code": "Bat-A",
        "parent": "residence",
        "libelle": "Bâtiment A",
        #  Les deux replis : un libellé court absent prend le libellé, une
        #  description absente sort en chaîne vide.
        "libelle_court": "Bâtiment A",
        "description": "",
        "batiment_id": 7,
        "profondeur": 1,
        "ordre": 3,
        "actif": False,
        "concerne_tous": True,  # hérité de la racine
        "privatif": True,
        "hors_copropriete": True,
        "utilise": True,  # cité ; la casse du code n'y fait rien
        "copiable": False,  # un bâtiment
        "deplacements": ["gauche"],  # fils unique : il ne peut que sortir
    },
    {
        #  L'orphelin : rendu quand même, sans parent ni profondeur.
        **_NOEUD,
        "id": 3,
        "code": "perdu",
        "libelle": "Perdu",
        "libelle_court": "Perdu",
        "description": "",
        "portee_globale": True,
        "concerne_tous": True,
    },
]
