"""Chaque type qu'émet la cloche a son pictogramme et son libellé publiés (#2802).

Lit sur l'arbre syntaxique de `app/` chaque appel à `sonner` / `sonner_systeme`
(`utils/cloche`, la seule porte des notifications) et son argument `type=` :
- une constante doit être une clé de `TYPES_NOTIFICATION` ;
- une expression se déclare dans `DYNAMIQUES`, avec sa raison (l'app lui donne
  `TYPE_PAR_DEFAUT`) — une déclaration qui ne sert plus échoue ;
- chaque clé de la table est émise quelque part (pas d'entrée morte) ;
- chaque pictogramme est au catalogue `icones-svg.json`, dont les apps reçoivent les tracés.
"""

from __future__ import annotations

import ast
import json
import pathlib

from app.utils.types_notification import TYPE_PAR_DEFAUT, TYPES_NOTIFICATION

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
CATALOGUE = APP / "utils" / "icones-svg.json"
PORTES = {"sonner", "sonner_systeme"}

#: `fichier:expression` → raison. L'app leur donne `TYPE_PAR_DEFAUT`.
DYNAMIQUES = {
    "utils/acces_gestes.py:type_acces.cle": "un type d'accès ADMINISTRABLE (vigik, télécommande…) "
    "posé en base : la table ne peut pas l'énumérer",
}


def types_emis(source: str) -> list[tuple[str, int]]:
    """PURE. Les `type=` passés à la cloche : (constante ou `<expression>`, ligne)."""
    sortie = []
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.Call):
            continue
        f = noeud.func
        nom = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        if nom not in PORTES:
            continue
        for k in noeud.keywords:
            if k.arg == "type":
                v = k.value
                valeur = v.value if isinstance(v, ast.Constant) else f"<{ast.unparse(v)}>"
                sortie.append((valeur, noeud.lineno))
    return sortie


def _releve() -> dict[str, list[str]]:
    releve: dict[str, list[str]] = {}
    fichiers = sorted(APP.rglob("*.py"))
    assert len(fichiers) > 300, "lecture de app/ cassée — cas zéro"
    for chemin in fichiers:
        rel = chemin.relative_to(APP).as_posix()
        for valeur, ligne in types_emis(chemin.read_text(encoding="utf-8")):
            cle = f"{rel}:{valeur[1:-1]}" if valeur.startswith("<") else valeur
            releve.setdefault(cle, []).append(f"{rel}:{ligne}")
    return releve


def test_chaque_forme_est_reperee():
    source = (
        "sonner(s, destinataire_id=1, type='sondage')\n"
        "cloche.sonner_systeme(s, 'compte', destinataire_id=1, type=t.cle)\n"
        "autre(type='x')\n"
    )
    assert types_emis(source) == [("sondage", 1), ("<t.cle>", 2)]


def test_chaque_type_emis_a_son_pictogramme():
    releve = _releve()
    assert len(releve) >= 5, f"{len(releve)} type(s) relevé(s) — cas zéro"
    inconnus = {
        cle: ou
        for cle, ou in releve.items()
        if cle not in TYPES_NOTIFICATION and cle not in DYNAMIQUES
    }
    assert not inconnus, (
        "type(s) de notification sans entrée dans utils/types_notification.TYPES_NOTIFICATION "
        f"(ou, pour une expression, dans DYNAMIQUES) : {inconnus}"
    )


def test_aucune_entree_ni_declaration_morte():
    releve = _releve()
    mortes = sorted(set(TYPES_NOTIFICATION) - set(releve))
    assert not mortes, f"type(s) que plus rien n'émet, à retirer de la table : {mortes}"
    perimees = sorted(set(DYNAMIQUES) - set(releve))
    assert not perimees, f"déclaration(s) de DYNAMIQUES qui ne servent plus : {perimees}"


def test_chaque_pictogramme_est_au_catalogue():
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    for type_, entree in {**TYPES_NOTIFICATION, "<défaut>": TYPE_PAR_DEFAUT}.items():
        assert set(entree) == {"pictogramme", "libelle"}, type_
        assert entree["pictogramme"] in catalogue, (
            f"{type_} : « {entree['pictogramme']} » absent du catalogue"
        )
        assert entree["libelle"].strip(), type_
