"""Rien ne part sur le groupe de la résidence hors d'une porte déclarée (22/10/2026).

## Pourquoi

Le groupe est lu par TOUS les résidents. Ce qui peut y partir se décide sur
l'OBJET — sa réserve, son public —, à une porte par nature d'objet
(`standards/03` §2 bis). Deux fuites le même jour : trois envois d'affaire dont
un seul transmettait la réserve (un code d'ascenseur), puis le sondage, qui ne
transmettait rien. Le premier contrôle ne regardait que `routers/tickets/` : le
sondage était hors de sa portée (`standards/05` §9).

Ici, la portée est tout `api/app/`, et la liste des portes se lit dans `PORTES`.
Une porte neuve s'y ajoute — avec la règle qu'elle lit sur l'objet.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

#: Les seuls appelants de `diffuser`, et la règle que chacun lit sur l'objet.
#: Le registre lui-même (`utils/diffusion.py`) définit le geste, il ne l'appelle pas.
PORTES: dict[str, tuple[str, str]] = {
    "routers/tickets/groupe.py": ("diffuser_l_affaire", "contenu_hors_du_groupe("),
    "routers/sondages/groupe.py": ("diffuser_le_sondage", "sondage_hors_du_groupe("),
    #  Une affiche est faite pour le hall ; tirée d'une affaire, elle en lit la réserve.
    "routers/annonces_hall_courriels.py": ("_partager_sur_le_groupe", "contenu_hors_du_groupe("),
}


def appels_directs(racine: Path) -> list[tuple[str, str]]:
    """(fichier relatif, fonction englobante) de chaque appel à `diffuser`."""
    trouves = []
    for chemin in sorted(racine.rglob("*.py")):
        rel = chemin.relative_to(racine).as_posix()
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for fonction in ast.walk(arbre):
            if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for noeud in ast.walk(fonction):
                if isinstance(noeud, ast.Call):
                    nom = getattr(noeud.func, "id", None) or getattr(noeud.func, "attr", None)
                    if nom == "diffuser":
                        trouves.append((rel, fonction.name))
        #  Un appel au niveau du module n'a pas de fonction englobante.
        for noeud in arbre.body:
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for n in ast.walk(noeud):
                    if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "diffuser":
                        trouves.append((rel, "<module>"))
    return trouves


def test_le_groupe_ne_se_diffuse_que_par_une_porte_declaree():
    fautifs = [
        f"{rel} ({fonction})"
        for rel, fonction in appels_directs(APP)
        if PORTES.get(rel, (None,))[0] != fonction
    ]
    assert not fautifs, (
        "Un appel direct à `diffuser` oublie la réserve de l'objet : passer par sa "
        f"porte (`PORTES`), ou en déclarer une qui lit la réserve : {fautifs}"
    )


def test_chaque_porte_sert_et_lit_la_reserve():
    """Témoin : une porte déclarée appelle `diffuser` ET lit la règle sur l'objet."""
    appels = set(appels_directs(APP))
    for rel, (fonction, regle) in PORTES.items():
        assert (rel, fonction) in appels, f"porte déclarée qui ne sert plus : {rel} ({fonction})"
        source = (APP / rel).read_text(encoding="utf-8")
        assert regle in source, f"{rel} ne lit plus la réserve sur l'objet ({regle})"


def test_le_controle_attrape_un_appel_direct(tmp_path):
    """Le cas zéro : un appelant hors porte est bien vu, sous ses deux formes."""
    (tmp_path / "fuite.py").write_text(
        "from app.utils import diffusion\n"
        "from app.utils.diffusion import diffuser\n"
        "def partager(t, c, s):\n"
        "    diffuser(t, c, s.titre, s.description)\n"
        "def partager_bis(t, c, s):\n"
        "    diffusion.diffuser(t, c, s.titre, s.description)\n",
        encoding="utf-8",
    )
    assert appels_directs(tmp_path) == [("fuite.py", "partager"), ("fuite.py", "partager_bis")]
