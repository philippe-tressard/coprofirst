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

`TypeEquipement` est **l'unique arbitre**. Deux listes d'accord entre elles ne
prouvent rien : c'était le constat de #415, où cinq listes de statuts étaient
chacune cohérente avec elle-même et aucune juste.

Même forme, donc, que `test_statuts_tickets.py`.
"""

from __future__ import annotations

import pathlib
import re

from app.models.prestataires import TypeEquipement, TypePrestataire

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
    assert len(_valeurs("EQUIPEMENTS")) >= 10, "la table EQUIPEMENTS est vide ou illisible"
    assert len(_valeurs("TYPES_PRESTATAIRE")) >= 3, (
        "la table TYPES_PRESTATAIRE est vide ou illisible"
    )


def test_l_ecran_nomme_TOUS_les_types_d_equipement():
    """Une valeur que le serveur accepte et que l'écran ne nomme pas s'affiche BRUTE.

    C'est le défaut trouvé : `assurance` et `syndic` manquaient, et l'écran les
    rendait en minuscules au milieu de libellés soignés.
    """
    attendues = {e.value for e in TypeEquipement}
    declarees = set(_valeurs("EQUIPEMENTS"))
    manquantes = attendues - declarees
    assert not manquantes, (
        f"{sorted(manquantes)} sont acceptées par le serveur et NON nommées par "
        "l'écran : elles s'afficheront en valeur brute."
    )


def test_l_ecran_ne_nomme_RIEN_que_le_serveur_refuse():
    """⚠️ L'autre sens de la rupture, et il est plus grave.

    Une valeur proposée que le serveur refuse produit un 422 sur un geste que
    l'interface a elle-même offert. Une relation a deux sens de rupture, et un
    contrôle qui n'en garde qu'un laisse passer l'autre (`standards/05` §9 bis).
    """
    acceptees = {e.value for e in TypeEquipement}
    inventees = set(_valeurs("EQUIPEMENTS")) - acceptees
    assert not inventees, (
        f"{sorted(inventees)} sont proposées par l'écran et REFUSÉES par le "
        "serveur : le geste produira un 422."
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


def test_aucun_ecran_ne_recopie_la_table():
    """🔴 C'est la recopie qu'on empêche, pas la divergence qui en découle.

    Interdire la divergence sans interdire la recopie revient à corriger le
    symptôme : la table réapparaîtrait ailleurs, juste au moment de sa copie, et
    fausse trois mois plus tard.

    Le motif cherche une liste d'options d'équipement écrite dans un composant :
    deux valeurs de l'énumération citées dans le même fichier, hors du module qui
    les porte.
    """
    temoins = ("ascenseur", "chauffage_collectif")
    fautifs = []
    for chemin in _FRONT_SRC.rglob("*.svelte"):
        source = chemin.read_text(encoding="utf-8")
        if all(f"'{t}'" in source for t in temoins):
            fautifs.append(str(chemin.relative_to(_FRONT_SRC)).replace("\\", "/"))
    assert not fautifs, (
        f"la table des équipements est recopiée dans {fautifs} : elle vit dans "
        "`#lib/prestataires.ts`, et nulle part ailleurs."
    )


def test_ce_qui_n_est_pas_un_equipement_est_le_meme_des_deux_cotes():
    """#1097 : une affaire désigne un équipement, jamais `assurance` ni `syndic`.

    L'écran dérive `EQUIPEMENTS_AFFAIRE` de `HORS_EQUIPEMENT` ; le serveur refuse
    en 422 ce que sa propre liste exclut. Deux listes, donc une comparaison — et
    le cas zéro : vides des deux côtés, elles seraient d'accord sans rien exclure.
    """
    from app.utils.intervenant import HORS_EQUIPEMENT

    source = _MODULE.read_text(encoding="utf-8")
    debut = source.index("export const HORS_EQUIPEMENT")
    ecran = set(re.findall(r"'([^']+)'", source[debut : source.index(";", debut)]))
    assert ecran == set(HORS_EQUIPEMENT) and ecran, (ecran, HORS_EQUIPEMENT)
