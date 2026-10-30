"""Un objet qu'on va chercher par son identifiant passe par `ou_404`.

## Le constat (#1047, audit du 19/09/2026)

`utils/recuperer.ou_404` existe depuis le 15/09/2026 et compte 86 appels dans 35
fichiers — il est né d'un relevé qui avait trouvé **90 copies** de ces trois
lignes :

    objet = session.get(Modele, objet_id)
    if not objet:
        raise HTTPException(404, "Chose introuvable")

**Trente-huit y ont survécu**, et elles avaient déjà recommencé à diverger sur le
libellé : « Objet introuvable » trois fois, « Import introuvable » trois fois,
« Bail introuvable » deux fois hors du helper. C'est exactement le motif qui avait
fait écrire le helper — la factorisation s'était arrêtée avant la fin.

⚠️ Deux helpers **locaux** portaient en plus une règle d'autorisation :
`bailleur/commun.get_bail_or_404` et `reponses_communaute._cible_visible_ou_404`.
Tous deux ont rejoint `auth/appartenance.py` dans le même lot (#1028) : leur
défaut n'était pas de doubler `ou_404` — ils l'appellent — mais d'écrire une
règle de droits chez un routeur.

## Pourquoi une LISTE et non un plafond (17/10/2026)

Les 404 restants **ne sont pas convertibles**, et chacun pour une raison qui lui
est propre : la visibilité (un 404 qui tait l'existence, `standards/03` §1), une
liste blanche d'accès, une réponse d'un serveur tiers. Ils ont été comptés par
un plafond décroissant de 32 à 4 (#1047, #1564, #1571).

Un plafond compte, il ne nomme pas : un 404 retiré ici et un autre écrit ailleurs
le laissaient vert. Les 404 qui restent se **déclarent** donc un par un dans
`EXCEPTIONS`, avec leur raison, et le contrôle échoue dans les deux sens — un
404 non déclaré, ou une exception qui ne sert plus.

⚠️ Et le plafond ne voyait que `HTTPException(404…)` écrit en toutes lettres :
`registre/routeur.py` levait deux 404 par un alias, `_refus(404, …)`, que le
motif ne reconnaissait pas. Le contrôle lit désormais tout `raise` dont l'appel
porte 404, et `status.HTTP_404_NOT_FOUND` (`_404_dans`, éprouvé par
`test_le_detecteur_voit_chaque_forme`).
"""

import ast
from collections import Counter
from pathlib import Path

from tests.aides_sources import modules_app

RACINE = Path(__file__).resolve().parents[1] / "app"

#: Le module qui porte la question « existe-t-il ? ».
SOURCE = "utils/recuperer.py"

#: Les 404 écrits à la main qui restent, chacun avec sa raison — clé
#: `module::fonction`, un seul 404 par fonction. Liste nominative permanente
#: (la carte #1571 est close : chaque entrée tient à une règle propre).
#:
#: 🔴 Une entrée ne s'ajoute pas pour faire passer le contrôle : aller chercher un
#: objet par son identifiant passe par `utils/recuperer` (`ou_404`,
#: `present_ou_404`…). Une entrée qui ne sert plus fait échouer.
EXCEPTIONS = {
    "auth/appartenance.py::exiger_acces_du_porteur": (
        "visibilité : le badge d'un voisin se lit comme absent (404 et non 403) — "
        "une règle d'accès, qui vit avec les autres"
    ),
    "auth/appartenance.py::exiger_cible_visible": (
        "visibilité : la cible qu'on n'a pas le droit de voir se lit comme absente"
    ),
    "routers/compteurs.py::_servir_fichier_prive": (
        "liste blanche d'ACCÈS aux fichiers de `prive/` : elle décide d'un droit "
        "(`recuperer.connu_ou_404` le refuse en toutes lettres)"
    ),
    "routers/config.py::imap_test": (
        "le dossier IMAP absent est la réponse d'un serveur tiers, pas une ligne de la base"
    ),
}


def _est_404(noeud: ast.AST) -> bool:
    return isinstance(noeud, ast.Constant) and noeud.value == 404


def _nom_appele(appel: ast.Call) -> str:
    f = appel.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


def _404_dans(arbre: ast.AST) -> list[tuple[str, int]]:
    """Les 404 levés à la main dans un arbre : `(fonction englobante, ligne)`.

    Trois formes : `HTTPException(…404…)` quel que soit son chemin d'import,
    tout `raise f(…404…)` — un alias qui fabrique l'exception —, et
    `status.HTTP_404_NOT_FOUND`.
    """
    trouves: dict[int, str] = {}

    def visiter(noeud: ast.AST, fonction: str) -> None:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fonction = noeud.name
        appel = noeud.exc if isinstance(noeud, ast.Raise) else noeud
        if isinstance(appel, ast.Call):
            args = list(appel.args) + [k.value for k in appel.keywords]
            if any(map(_est_404, args)) and (
                isinstance(noeud, ast.Raise) or _nom_appele(appel) == "HTTPException"
            ):
                trouves.setdefault(appel.lineno, fonction)
        if isinstance(noeud, ast.Attribute) and noeud.attr == "HTTP_404_NOT_FOUND":
            trouves.setdefault(noeud.lineno, fonction)
        for enfant in ast.iter_child_nodes(noeud):
            visiter(enfant, fonction)

    visiter(arbre, "<module>")
    return sorted((f, ligne) for ligne, f in trouves.items())


def _404_bruts() -> list[tuple[str, str]]:
    """Tout 404 levé à la main dans `app/`, hors le helper : `(clé, emplacement)`."""
    return [
        (f"{m.rel}::{fonction}", f"app/{m.rel}:{ligne}")
        for m in modules_app()
        if m.rel != SOURCE
        for fonction, ligne in _404_dans(m.arbre)
    ]


def test_le_detecteur_voit_chaque_forme():
    """Un contrôle qui ne voit pas la forme fautive est vert sur elle : cas fautifs
    d'abord, et ce qui n'est pas un 404 levé ne compte pas."""
    source = """
import fastapi
from fastapi import status

def a(): raise HTTPException(404, "x")
def b(): raise HTTPException(status_code=404)
def c(): raise fastapi.HTTPException(404)
def d(): raise _refus(404, "x")
def e(): raise HTTPException(status.HTTP_404_NOT_FOUND)
def f(): erreur = HTTPException(404)
def g(): raise HTTPException(403, "x")
def h(): dessin.rectangle((404, 92, 538, 548))
def i(): return 404
"""
    vus = {f for f, _ in _404_dans(ast.parse(source))}
    assert vus == {"a", "b", "c", "d", "e", "f"}, vus


def test_chaque_404_ecrit_a_la_main_est_declare():
    """Un 404 non déclaré est une copie de plus — le helper existe. Une exception
    qui ne sert plus ferme une question qui ne se pose plus."""
    bruts = _404_bruts()
    comptes = Counter(cle for cle, _ in bruts)
    inconnus = [lieu for cle, lieu in bruts if cle not in EXCEPTIONS]
    multiples = sorted(cle for cle, n in comptes.items() if n > 1 and cle in EXCEPTIONS)
    inutiles = sorted(set(EXCEPTIONS) - set(comptes))
    assert not inconnus, (
        "404 écrit(s) à la main hors de `utils/recuperer` : "
        + ", ".join(inconnus)
        + ". Aller chercher un objet par son identifiant passe par `ou_404`, un "
        "résultat `None` par `present_ou_404` — le libellé y est composé."
    )
    assert not multiples, f"Exception(s) qui porte(nt) plus d'un 404 : {multiples}"
    assert not inutiles, (
        f"Exception(s) qui ne serve(nt) plus — à retirer d'`EXCEPTIONS` : {inutiles}"
    )


def test_aucun_helper_local_ne_double_le_helper_partage():
    """Un second nom pour la même question, c'est deux notions apparentes.

    `get_bail_or_404` était une copie exacte ; `_cible_visible_ou_404` mêlait
    « existe-t-il ? » et « puis-je le voir ? », ce que `recuperer.py` refuse de
    faire en toutes lettres.
    """
    fautes = []
    for m in modules_app():
        chemin = m.rel
        if chemin == SOURCE:
            continue
        arbre = m.arbre
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if "404" not in noeud.name:
                continue
            fautes.append(f"app/{chemin}::{noeud.name}")
    assert not fautes, (
        "Helper(s) local(aux) qui doublent `ou_404` :\n"
        + "\n".join(f"  {f}" for f in fautes)
        + "\n\nUn helper dont le nom porte « 404 » répond à la même question que "
        "`utils/recuperer.ou_404` : l'appeler, ou dire ici pourquoi il est différent."
    )
