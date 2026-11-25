"""Le fil affiche le LIBELLÉ d'une catégorie, jamais son code (#1310).

Signalé le 25/09/2026, capture à l'appui : une affaire portait dans le fil
d'actualité le badge `acces_accueil`. `badges_ticket` y posait la valeur de
l'énumération, alors que la table des libellés existait côté serveur
(`utils/categories_ticket.libelle_categorie`) et servait déjà aux courriels.

Deux contrôles :

- le comportement : pour CHAQUE valeur de `CategorieTicket`, le badge est le
  libellé de la table ;
- la récidive : aucun routeur du fil ne pose un `.categorie` brut dans une liste
  de badges. La FAQ en est exemptée, et c'est déclaré : sa catégorie est un
  libellé libre saisi par le conseil (« 🗑️ Tri des déchets »), pas un code.
"""

from __future__ import annotations

import ast
import pathlib
from types import SimpleNamespace

from app.models.tickets import CategorieTicket
from app.routers.flux.commun import badges_ticket
from app.utils.categories_ticket import LIBELLES_CATEGORIE

_FLUX = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "flux"

#: Les fichiers où une catégorie brute est un libellé, avec leur raison.
#: Une exception qui ne sert plus fait échouer le test.
EXCEPTIONS = {
    "ressources.py": "FAQ : `Faq.categorie` est un libellé libre, saisi tel qu'affiché",
}


def categories_brutes(source: str) -> list[int]:
    """Les lignes où un `.categorie` est posé tel quel comme ÉLÉMENT d'une liste.

    Lu dans l'AST et non dans le texte : une docstring qui RACONTE l'ancienne
    forme n'est pas du code. Passé à une fonction (`libelle_categorie(x.categorie)`),
    l'attribut n'est plus un élément de la liste, et il n'est pas relevé.
    """
    return sorted(
        elt.lineno
        for noeud in ast.walk(ast.parse(source))
        if isinstance(noeud, ast.List)
        for elt in noeud.elts
        if isinstance(elt, ast.Attribute) and elt.attr == "categorie"
    )


def _ticket(categorie) -> SimpleNamespace:
    return SimpleNamespace(numero="TK-000001", categorie=categorie, priorite=None)


def test_chaque_categorie_s_affiche_par_son_libelle():
    for cat in CategorieTicket:
        badges = badges_ticket(_ticket(cat))
        assert LIBELLES_CATEGORIE[cat.value] in badges, (
            f"{cat.value} : le fil affiche {badges}, et non « {LIBELLES_CATEGORIE[cat.value]} »"
        )
        assert cat.value not in badges or cat.value == LIBELLES_CATEGORIE[cat.value]


def test_aucun_routeur_du_fil_ne_pose_une_categorie_brute():
    fichiers = sorted(_FLUX.glob("*.py"))
    assert fichiers, f"aucun routeur du fil sous {_FLUX} — le contrôle ne mesure rien"
    fautifs, vues = [], set()
    for f in fichiers:
        lignes = categories_brutes(f.read_text(encoding="utf-8"))
        if lignes and f.name in EXCEPTIONS:
            vues.add(f.name)
            continue
        fautifs += [f"{f.name}:{n}" for n in lignes]
    assert not fautifs, (
        "Catégorie posée brute dans un badge du fil — passer par "
        "`libelle_categorie` :\n" + "\n".join(fautifs)
    )
    perimees = set(EXCEPTIONS) - vues
    assert not perimees, f"Exceptions qui ne servent plus, à retirer : {sorted(perimees)}"


def test_le_controle_reconnait_la_forme_fautive():
    """Le contrôle s'éprouve lui-même : la ligne d'avant #1310 est refusée, la
    forme corrigée et une docstring qui cite l'ancienne passent."""
    assert categories_brutes('badges = [f"#{ticket.numero}", ticket.categorie]') == [1]
    assert categories_brutes("badges = [t.numero, libelle_categorie(t.categorie)]") == []
    assert categories_brutes('"""forme `[tk.numero, tk.categorie]`"""') == []
