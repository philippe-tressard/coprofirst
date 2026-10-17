"""Les ressources d'une copropriété ne se demandent qu'au module `contexte` (#1744).

Chantier multi-copropriétés, spec §4.1 règle 3 : *aucune ressource ne se construit
depuis la configuration globale*. La base, la racine des fichiers, le secret de
signature et l'expéditeur des courriels appartiennent à UNE copropriété. Tant
qu'il n'y en a qu'une, `app/contexte.py` les lit dans `settings` ; le jour où il
y en aura deux, seul ce module changera — à condition que personne d'autre ne
les lise directement.

Relevé du 08/10/2026 : `engine` importé dans quinze modules, `Session(engine)`
dix-sept fois, et les quatre réglages lus à quatorze endroits. Ce contrôle refuse
le suivant, sur l'AST — un commentaire qui en parle n'est pas un accès.
"""

from __future__ import annotations

import ast

from tests.aides_sources import module_app, modules_app

#: Le module qui sert les ressources, et celui qui construit le moteur.
CONTEXTE = "contexte.py"
CONSTRUCTEUR = "database.py"
#: Le seul module qui DÉCLARE les réglages.
CONFIGURATION = "config.py"

#: Ce que `app.database` construit et que seul le contexte distribue.
NOMS_DE_LA_BASE = frozenset({"engine", "SessionLocal"})
#: Les réglages propres à une copropriété — `backup_dir` depuis #2053 : sur une
#: installation commune, le volume des sauvegardes est partagé, et chaque copropriété
#: a son dossier (`contexte.dossier_des_sauvegardes`).
REGLAGES_DE_COPROPRIETE = frozenset(
    {"database_url", "secret_key", "uploads_dir", "mail_from", "mail_from_name", "backup_dir"}
)
#: Les modules qui lisent un de ces réglages pour la PLATEFORME, avec leur raison.
LECTEURS_DE_LA_PLATEFORME = {
    "registre/sauvegarde.py": "la base `plateforme` a son dossier, `plateforme/`, hors "
    "de toute copropriété (§4.9)",
}


def acces_directs(arbre: ast.AST, *, lit_la_base: bool, lit_les_reglages: bool) -> list:
    """Les accès directs d'un arbre : `(ligne, forme)`."""
    trouves = []
    for n in ast.walk(arbre):
        if lit_la_base and isinstance(n, ast.ImportFrom) and n.module == "app.database":
            trouves += [
                (n.lineno, f"from app.database import {a.name}")
                for a in n.names
                if a.name in NOMS_DE_LA_BASE
            ]
        elif isinstance(n, ast.Attribute):
            if lit_la_base and n.attr in NOMS_DE_LA_BASE and _nomme(n.value, "database"):
                trouves.append((n.lineno, f"database.{n.attr}"))
            elif lit_les_reglages and n.attr in REGLAGES_DE_COPROPRIETE:
                trouves.append((n.lineno, f".{n.attr}"))
    return sorted(trouves)


def _nomme(noeud: ast.AST, nom: str) -> bool:
    return (isinstance(noeud, ast.Name) and noeud.id == nom) or (
        isinstance(noeud, ast.Attribute) and noeud.attr == nom
    )


def test_aucune_ressource_de_copropriete_lue_hors_du_contexte():
    fautes = {}
    for m in modules_app(minimum=300):
        if m.rel == CONTEXTE:
            continue
        a = acces_directs(
            m.arbre,
            lit_la_base=m.rel != CONSTRUCTEUR,
            lit_les_reglages=m.rel not in (CONFIGURATION, *LECTEURS_DE_LA_PLATEFORME),
        )
        if a:
            fautes[m.rel] = a
    assert not fautes, (
        "Ressource d'une copropriété lue hors de `app/contexte.py` (#1744, spec §4.1 "
        "règle 3) — la demander au contexte : `contexte.moteur()`, "
        "`contexte.nouvelle_session()`, `contexte.courante().url_base | racine_fichiers "
        "| secret | expediteur | nom_expediteur` :\n"
        + "\n".join(
            f"  app/{rel}:{ligne} — {forme}" for rel, a in fautes.items() for ligne, forme in a
        )
    )


def test_le_contexte_porte_ce_que_le_releve_cherche():
    """Le cas zéro : si le contexte n'était plus vu, le relevé ne mesurerait plus rien."""
    formes = {
        f
        for _, f in acces_directs(
            module_app(CONTEXTE).arbre, lit_la_base=True, lit_les_reglages=True
        )
    }
    attendues = {"database.engine"} | {f".{r}" for r in REGLAGES_DE_COPROPRIETE}
    assert attendues <= formes, f"le relevé ne voit plus dans le contexte : {attendues - formes}"


_EXEMPLE = '''
"""Docstring : from app.database import engine, settings.secret_key — racontés."""
from app.database import engine, get_session
from app.database import SessionLocal as S
from app import database
from app.config import get_settings

# commentaire : settings.uploads_dir
a = get_settings().database_url
b = settings.secret_key
c = database.engine
d = app.database.SessionLocal()
e = get_settings().origin
f = moteur.url
'''


def test_chaque_forme_est_reperee_et_le_reste_ne_l_est_pas():
    formes = [
        f for _, f in acces_directs(ast.parse(_EXEMPLE), lit_la_base=True, lit_les_reglages=True)
    ]
    assert formes == [
        "from app.database import engine",
        "from app.database import SessionLocal",
        ".database_url",
        ".secret_key",
        "database.engine",
        "database.SessionLocal",
    ]
