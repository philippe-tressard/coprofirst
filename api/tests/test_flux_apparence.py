"""Garde-fou : toute rubrique du fil a une couleur, un fond et un libellé (08/08/2026).

Le fil d'activité émet quinze types. Les trois tables d'apparence du front n'en
couvraient que **dix** : `prestataire`, `document`, `diagnostic`, `faq` et
`annuaire` — les cinq rubriques ajoutées depuis — retombaient sur les valeurs par
défaut, soit **gris de bordure sur fond gris** (contraste 1,15:1, illisible), avec
le nom technique brut en guise de libellé (« PRESTATAIRE »).

Personne ne l'avait vu, et c'est le point : **une pastille grise ressemble à une
pastille**. Le défaut a été signalé par l'utilisateur, pas par un contrôle — c'est
la question 1 du bilan mémoire (`mep-precheck`, P10), donc le contrôle manquant
est la vraie leçon.

Ce test est **inter-langages**, comme `test_liens_front.py` : le producteur des
types est en Python, leur apparence en TypeScript, et rien ne reliait les deux.
Ajouter une rubrique au fil sans son apparence échoue désormais en CI.
"""

import pathlib
import re

from tests.aides_jetons import jetons_du_theme_clair, resoudre
from tests.aides_sources import modules_app

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_FLUX_TS = _RACINE / "front" / "src" / "lib" / "flux.ts"

#: `type="…"` dans la construction d'un FluxItem — c'est la seule façon dont une
#: rubrique déclare son type, et elle est littérale partout.
_TYPE_EMIS = re.compile(r'type="([a-z_]+)"')


def _types_emis() -> set[str]:
    """Les types que le backend produit réellement — la PORTÉE du contrôle."""
    types = set()
    for module in modules_app("routers/flux", minimum=10):
        types |= set(_TYPE_EMIS.findall(module.source))
    #  Plancher : un motif cassé rendrait un ensemble vide, et toutes les
    #  inclusions ci-dessous seraient vraies à vide (`standards/04` §2, cas zéro).
    assert len(types) >= 12, (
        f"Seulement {len(types)} type(s) détecté(s) : {sorted(types)} — le "
        "détecteur est cassé, ne pas lire ce test comme vert."
    )
    return types


#: Une rubrique et ses attributs : `annonce: { libelle: '…', couleur: '…', … }`,
#: sur une ligne ou sur plusieurs — Prettier les replie depuis que la marque de
#: gouttière (`icone`, `abrege`) s'y est ajoutée (10/10/2026).
_ENTREE = re.compile(r"^	([a-z_]+):\s*\{(.+?)\}", re.M | re.S)
_ATTRIBUT = re.compile(r"([a-z]+):\s*'([^']+)'")

#: Les attributs qu'une rubrique DOIT porter. Écrits ici parce que le test doit
#: pouvoir dire lequel manque ; côté TypeScript, c'est le compilateur qui le
#: refuse (`#lib/table-statuts`), donc ce contrôle-ci ne peut plus échouer sur
#: une entrée incomplète — il reste pour le jour où quelqu'un défera la table.
_ATTENDUS = ("libelle", "couleur", "fond", "icone", "abrege")


def _apparences() -> dict[str, dict[str, str]]:
    """L'apparence de chaque rubrique, lue dans la table UNIQUE de `flux.ts`.

    🔴 Les trois tables parallèles ont fondu en une le 15/09/2026 : un libellé,
    une teinte et un fond par rubrique, déclarés ensemble. L'extracteur lit donc
    une structure et non trois — et la question « les trois tables couvrent-elles
    les mêmes types ? », que ce fichier posait, n'a plus de sens : elles n'en
    font qu'une. Ce qui reste à vérifier est le lien avec le BACKEND, qui lui
    n'a pas changé.
    """
    source = _FLUX_TS.read_text(encoding="utf-8")
    debut = source.index("} = parAttribut({")
    corps = source[debut : source.index("});", debut)]
    apparences = {m.group(1): dict(_ATTRIBUT.findall(m.group(2))) for m in _ENTREE.finditer(corps)}
    #  Cas zéro : un motif cassé rendrait une table vide, et toutes les
    #  inclusions ci-dessous seraient vraies à vide (`standards/04` §2).
    assert len(apparences) >= 12, (
        f"Seulement {len(apparences)} rubrique(s) lue(s) dans flux.ts — le "
        "détecteur est cassé, ne pas lire ce test comme vert."
    )
    return apparences


def _table(nom: str) -> set[str]:
    """Les clés portant l'attribut `nom` — l'ancienne question, même réponse."""
    return {t for t, a in _apparences().items() if nom in a}


def test_chaque_type_emis_a_une_couleur_un_fond_et_un_libelle():
    emis = _types_emis()
    manques = {}
    for nom in _ATTENDUS:
        absents = emis - _table(nom)
        if absents:
            manques[nom] = sorted(absents)
    assert not manques, (
        "Des rubriques du fil n'ont pas d'apparence déclarée dans "
        f"front/src/lib/flux.ts : {manques}.\n"
        "Sans elles, la pastille s'affiche en gris sur fond gris (illisible) et "
        "porte le nom technique brut. Ajouter les trois entrées — couleur, fond "
        "et libellé — en vérifiant le contraste (AA = 4.5:1)."
    )


def test_aucune_apparence_orpheline():
    """Vérification EN SENS INVERSE : une entrée pour un type qui n'existe plus.

    Sans elle, les tables grossissent à chaque rubrique retirée et personne ne le
    sait — c'est la même exigence que la liste d'exceptions de
    `test_endpoints_orphelins` (`standards/02` §5).
    """
    emis = _types_emis()
    for nom in _ATTENDUS:
        orphelines = _table(nom) - emis
        assert not orphelines, (
            f"{nom} déclare l'apparence de {sorted(orphelines)}, que le backend "
            "n'émet plus. Retirer ces entrées — ou la rubrique a-t-elle été "
            "supprimée sans nettoyer son apparence ?"
        )


def _contraste(avant_plan: str, arriere_plan: str) -> float:
    def luminance(hexa: str) -> float:
        hexa = hexa.lstrip("#")
        canaux = [int(hexa[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canaux]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    a, b = luminance(avant_plan), luminance(arriere_plan)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _valeurs(nom: str) -> dict[str, str]:
    """La valeur d'un attribut pour chaque rubrique."""
    return {t: a[nom] for t, a in _apparences().items() if nom in a}


def test_chaque_pastille_est_lisible():
    """Contraste texte/fond au niveau AA — c'est la plainte d'origine.

    Six des sept couleurs historiques échouaient : l'ambre à 2,07, l'émeraude à
    2,41. Un contrôle sur la seule PRÉSENCE des entrées aurait laissé passer une
    pastille jaune pâle sur blanc cassé, tout aussi illisible que le gris.
    """
    couleurs, fonds = _valeurs("couleur"), _valeurs("fond")
    assert len(couleurs) >= 12, f"Seulement {len(couleurs)} teinte(s) lue(s) — détecteur cassé"

    jetons = jetons_du_theme_clair()
    trop_pales = []
    for type_, couleur in couleurs.items():
        #  Les teintes sont des jetons (`var(--fil-rouge)`, #2174 S2) : mesurées sur
        #  leur valeur RÉSOLUE dans `socle.css`. Aucune n'est écartée — une entrée
        #  non littérale qui échapperait au contrôle est le trou qui laisse passer
        #  un défaut.
        fond = fonds.get(type_)
        assert fond, f"{type_} : pas de fond déclaré"
        couleur, fond = resoudre(couleur, jetons), resoudre(fond, jetons)
        assert couleur.startswith("#") and fond.startswith("#"), (type_, couleur, fond)
        rapport = _contraste(couleur, fond)
        if rapport < 4.5:
            trop_pales.append(f"{type_} : {couleur} sur {fond} = {rapport:.2f}:1")

    assert not trop_pales, (
        "Pastilles sous le seuil de lisibilité AA (4.5:1) :\n  "
        + "\n  ".join(trop_pales)
        + "\nUtiliser une teinte foncée (700/800) sur un fond clair (50)."
    )
