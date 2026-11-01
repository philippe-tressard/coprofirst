"""Ce que l'écran NOMME correspond-il à ce que le serveur ACCEPTE ?

C'est la seule question qui vaille sur une table de libellés, et personne ne la
posait. Relevé du 20/08/2026, en instruisant #453 :

| Écran | Ce qu'il montrait |
|---|---|
| Prestataires → Contrats | un libellé, pour **15** des **17** valeurs |
| Reporting → Prestataires | la valeur BRUTE : `chauffage_collectif` |
| Reporting → Renouvellements | la valeur BRUTE, **trois fois** |

🔴 Les deux valeurs manquantes étaient `assurance` et `syndic` — précisément
celles que la fiche de copropriété DÉSIGNE depuis #553. Un contrat d'assurance
s'affichait donc « assurance », en minuscules, à côté de quinze libellés soignés.

Et deux écrans sur trois n'affichaient aucun libellé. Ce n'est pas de
l'inattention : c'est ce que produit une table qui vit dans UN écran — les autres
n'y ont pas accès, alors ils s'en passent.

## Ce fichier ne compare jamais deux copies l'une à l'autre

L'énumération du serveur est **l'unique arbitre** des catégories de prestataire.
Deux listes d'accord entre elles ne prouvent rien : c'était le constat de #415,
où cinq listes de statuts étaient chacune cohérente avec elle-même et aucune juste.

## Les équipements, depuis #2442

Ils ne sont plus une énumération : ils s'administrent (Admin › Copropriété ›
Équipements) et vivent en base. Il n'y a donc plus de table à comparer — ce
fichier refuse qu'une liste soit RÉÉCRITE dans le front, et vérifie que les
équipements de départ ont la forme que la route exige.
"""

from __future__ import annotations

import pathlib
import re

from app.models.prestataires import TypePrestataire

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_FRONT_SRC = _API_DIR.parent / "front" / "src"
_MODULE = _FRONT_SRC / "lib" / "prestataires.ts"


def _valeurs(nom_table: str) -> list[str]:
    """Les `val:` déclarés dans une table du module TypeScript.

    Lecture par motif TEXTUEL et non par analyse : ce module n'est pas exécutable
    depuis Python, et un analyseur TypeScript serait une dépendance de plus pour
    lire quinze lignes. Le motif est ancré sur la déclaration de la table, ce qui
    évite de mélanger deux listes du même fichier.
    """
    source = _MODULE.read_text(encoding="utf-8")
    debut = source.index(f"export const {nom_table}")
    fin = source.index("];", debut)
    return re.findall(r"val:\s*'([^']+)'", source[debut:fin])


def test_le_module_front_existe_et_declare_ses_tables():
    """🔴 Cas zéro. Sans lui, tout ce fichier passerait au vert sur un fichier vide.

    C'est la forme d'échec la plus coûteuse d'un contrôle par motif textuel : il
    ne trouve rien, ne compare rien, et le dit en vert (`standards/04` §2).
    """
    assert _MODULE.is_file(), f"{_MODULE} est introuvable : ce fichier ne mesure plus rien."
    assert len(_valeurs("TYPES_PRESTATAIRE")) >= 3, (
        "la table TYPES_PRESTATAIRE est vide ou illisible"
    )


def test_les_categories_de_prestataire_concordent_aussi():
    """La même table vit à côté, et elle a le même risque.

    Elle est juste aujourd'hui — cinq valeurs des deux côtés depuis #1444. Ce test existe pour
    que cela reste vrai : c'est la recopie qui fabrique la divergence, pas la
    faute d'inattention qui la suit.
    """
    attendues = {e.value for e in TypePrestataire}
    declarees = set(_valeurs("TYPES_PRESTATAIRE"))
    assert declarees == attendues, (
        f"absentes de l'écran : {sorted(attendues - declarees)} · "
        f"inventées par l'écran : {sorted(declarees - attendues)}"
    )


def test_aucun_ecran_ne_recopie_la_liste_des_equipements():
    """🔴 C'est la recopie qu'on empêche, pas la divergence qui en découle.

    Les équipements s'administrent depuis #2442 : ils vivent en base, et l'écran
    les lit par `#lib/equipements`. Une liste réécrite dans un composant ou un
    module serait fausse dès le premier équipement ajouté — c'est ce que faisait
    `EQUIPEMENTS` de `#lib/prestataires`, recopie de l'énumération du serveur.

    Le motif : deux codes de départ cités dans le même fichier du front.
    """
    temoins = ("ascenseur", "chauffage_collectif")
    fautifs = []
    for motif in ("*.svelte", "*.ts"):
        for chemin in _FRONT_SRC.rglob(motif):
            source = chemin.read_text(encoding="utf-8")
            if all(f"'{t}'" in source for t in temoins):
                fautifs.append(str(chemin.relative_to(_FRONT_SRC)).replace("\\", "/"))
    assert not fautifs, (
        f"une liste d'équipements est écrite dans {fautifs} : ils vivent en base "
        "(Admin › Copropriété › Équipements) et se lisent par `#lib/equipements`."
    )


def test_l_amorce_des_equipements_est_saine():
    """Les équipements de départ (`seed/equipements`) : ce que la route exigerait d'eux.

    Cas zéro compris : une amorce vide passerait tous les autres contrôles. Les
    codes système y figurent — la fiche de copropriété et le carnet s'en servent —,
    chaque icône existe au catalogue (`Icon.svelte` remplace un nom inconnu par
    un point d'interrogation), chaque code a la forme qu'accepte la route, et chaque
    abréviation tient dans la gouttière.
    """
    import json

    from app.routers.equipements import _FORME_CODE, ABREVIATION_MAX
    from app.seed.equipements import EQUIPEMENTS
    from app.utils.equipements import CODES_SYSTEME

    catalogue = json.loads(
        (_API_DIR / "app" / "utils" / "icones-svg.json").read_text(encoding="utf-8")
    )
    codes = [e["code"] for e in EQUIPEMENTS]
    assert len(codes) >= 10 and len(set(codes)) == len(codes), codes
    assert CODES_SYSTEME <= set(codes), sorted(CODES_SYSTEME - set(codes))
    assert not [e["icone"] for e in EQUIPEMENTS if e["icone"] not in catalogue]
    assert not [c for c in codes if not _FORME_CODE.match(c)]
    assert not [e["code"] for e in EQUIPEMENTS if len(e["abreviation"]) > ABREVIATION_MAX]


def test_le_plafond_de_l_abreviation_est_le_meme_des_deux_cotes():
    """La route refuse au-delà de `ABREVIATION_MAX` ; l'écran coupe au même nombre."""
    from app.routers.equipements import ABREVIATION_MAX

    source = (_FRONT_SRC / "lib" / "equipements.ts").read_text(encoding="utf-8")
    trouve = re.search(r"export const ABREVIATION_MAX = (\d+);", source)
    assert trouve, (
        "`ABREVIATION_MAX` introuvable dans #lib/equipements : le contrôle ne mesure rien"
    )
    assert int(trouve.group(1)) == ABREVIATION_MAX
