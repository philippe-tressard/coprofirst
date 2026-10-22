"""La carte des réglages est générée, et elle dit vrai (#2061).

`docs/carte-reglages.md` se déduit du code (`utils/reglages_carte`,
`utils/reglages`, `Settings`). Ce fichier tient, dans les deux sens :
- **le document versionné est ce que le code produit** — un réglage ajouté sans
  régénérer la carte fait échouer la CI ;
- **l'accès déclaré est celui de la route** — lu sur la route MONTÉE (ses
  dépendances d'autorisation), pas sur sa déclaration : le réglage de la sauvegarde
  se montrait à l'opérateur seul et la route acceptait tout administrateur ;
- **rien n'échappe à la carte** — chaque onglet de la liste blanche a sa notion,
  chaque variable de `Settings` son thème, et un écart déclaré qui cesse d'être
  vrai fait échouer (il se retire alors du registre).

Les contrôles sont éprouvés par un cas fautif (le « témoin ») : un contrôle vert
qui ne verrait rien, parce que sa portée est vide, rassurerait à tort.
"""

from __future__ import annotations

import importlib
import pathlib
import re
from dataclasses import replace

from app.config import Settings
from app.main import app
from app.utils import reglages
from app.utils.llm_usages import CHAMPS_USAGE
from app.utils.reglages_carte import (
    NOTIONS,
    SECRETS_ENV,
    THEMES_ENV,
    TYPES,
    TYPES_CHAMP_USAGE,
    Acces,
    ecarts_d_acces,
)
from app.utils.reglages_carte_rendu import rendre_document
from tests.aides_sources import operations_montees

_DOCUMENT = pathlib.Path(__file__).resolve().parents[2] / "docs" / "carte-reglages.md"
_AUTORISATIONS = {
    "require_operateur",
    "require_admin",
    "require_cs_or_admin",
    "require_proprietaire",
    "require_questions_reglement",
}


def _sans_nom(chemin: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", chemin)


def _dependances_des_routes() -> dict[tuple[str, str], frozenset[str]]:
    """(méthode, chemin monté) → les dépendances d'autorisation que la route PREND."""

    def parcourir(dependant, trouvees: set[str]) -> None:
        for sous in dependant.dependencies:
            nom = getattr(getattr(sous, "call", None), "__name__", "")
            if nom in _AUTORISATIONS:
                trouvees.add(nom)
            parcourir(sous, trouvees)

    resultat = {}
    for methode, chemin, route in operations_montees(app):
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        trouvees: set[str] = set()
        parcourir(dependant, trouvees)
        resultat[(methode, chemin)] = frozenset(trouvees)
    return resultat


# ── Le document ─────────────────────────────────────────────────────────────────


def test_la_carte_versionnee_est_ce_que_le_code_produit():
    attendu = rendre_document()
    actuel = _DOCUMENT.read_bytes().decode("utf-8") if _DOCUMENT.exists() else ""
    assert actuel == attendu, (
        "docs/carte-reglages.md diffère du code : "
        "python scripts/ci/carte_reglages.py --ecrire, puis relire la différence."
    )


def test_la_carte_n_est_pas_vide_et_un_changement_la_modifie():
    """Cas zéro et témoin : le rendu porte la matière, et suit le registre."""
    document = rendre_document()
    assert len(NOTIONS) >= 20 and "```mermaid" in document
    assert document.count("\n| `") > 100  # les clés de config_site et l'environnement
    modifiees = tuple(
        replace(n, ecran="ÉCRAN-TÉMOIN") if n.code == "sauvegarde" else n for n in NOTIONS
    )
    assert "ÉCRAN-TÉMOIN" in rendre_document(modifiees)
    assert "ÉCRAN-TÉMOIN" not in document


# ── L'accès déclaré est celui de la route ───────────────────────────────────────


def test_l_acces_declare_est_la_dependance_que_la_route_prend():
    assert ecarts_d_acces(NOTIONS, _dependances_des_routes()) == []


def test_le_controle_d_acces_voit_un_ecart_et_une_route_disparue():
    """Témoin : le contrôle refuse un accès faux et une route qui n'existe pas."""
    routes = _dependances_des_routes()
    sauvegarde = next(n for n in NOTIONS if n.code == "sauvegarde")
    fausse = replace(sauvegarde, acces=Acces.ADMIN)
    assert ecarts_d_acces((fausse,), routes)
    disparue = replace(sauvegarde, route=("PUT", "/admin/route-qui-nexiste-pas"))
    assert ecarts_d_acces((disparue,), routes)


def test_un_ecart_connu_porte_son_ticket():
    """Un écart entre un écran et sa route se suit : sans ticket, il serait un oubli."""
    avec_ecart = [n for n in NOTIONS if n.ecart]
    for n in avec_ecart:
        assert re.search(r"#\d{3,}", n.ecart), f"{n.code} : l'écart ne cite aucun ticket"
    assert re.search(r"#\d{3,}", "écart (#2096)")  # cas zéro : le motif lit un numéro


def test_les_notions_se_declarent_proprement():
    codes = [n.code for n in NOTIONS]
    assert len(codes) == len(set(codes))
    for n in NOTIONS:
        if n.acces in (Acces.EXPLOITANT, Acces.PERSONNE):
            assert n.route is None, n.code
        else:
            assert n.route is not None, f"{n.code} : un accès par route sans route"
        for constante in n.constantes:
            module, nom = constante.split(":")
            assert hasattr(importlib.import_module(module), nom), constante


def test_les_routes_citees_par_un_refus_existent():
    """Un refus qui renvoie vers une route doit nommer une route qui existe."""
    #  Le nom d'un paramètre de chemin n'est pas la route : `{id}` vaut `{perimetre_id}`.
    routes = {(m, _sans_nom(c)) for m, c in _dependances_des_routes()}
    motif = re.compile(r"\b(GET|PUT|PATCH|POST) (/[\w/{}\-]+)")
    cites = 0
    for cle, message in reglages.REFUSEES.items():
        m = motif.search(message)
        if m:
            cites += 1
            assert (m.group(1), _sans_nom(m.group(2))) in routes, f"{cle} : {m.group(0)}"
    assert cites >= 3  # cas zéro : le motif lit bien les messages


# ── L'écran déclaré est celui que le front range ───────────────────────────────

_PAGES_ROLES = (
    pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "pages-roles.ts"
)
_ONGLET_RANGE = re.compile(r"label: '([^']+)',\s*groupe: '([^']+)'")


def _onglets_ranges() -> set[tuple[str, str]]:
    """(groupe, onglet) de chaque onglet d'Admin tel que `pages-roles.ts` le range."""
    source = _PAGES_ROLES.read_text(encoding="utf-8")
    return {(groupe, label) for label, groupe in _ONGLET_RANGE.findall(source)}


def ecrans_d_admin_inconnus(notions, ranges: set[tuple[str, str]]) -> list[str]:
    """PURE. Les écrans « Admin › groupe › onglet » que le front ne range pas."""
    inconnus = []
    for n in notions:
        premier = n.ecran.split(" ; ")[0]
        if not premier.startswith("Admin › "):
            continue
        morceaux = premier.removeprefix("Admin › ").split(" › ")
        if len(morceaux) != 2 or (morceaux[0], morceaux[1]) not in ranges:
            inconnus.append(
                f"{n.code} : « {premier} » n'est pas un onglet rangé par pages-roles.ts"
            )
    return inconnus


def test_chaque_ecran_d_admin_est_un_onglet_que_le_front_range():
    ranges = _onglets_ranges()
    assert len(ranges) >= 18  # cas zéro : le relevé lit bien les onglets d'Admin
    assert ecrans_d_admin_inconnus(NOTIONS, ranges) == []


def test_le_controle_d_ecran_voit_un_onglet_qui_n_existe_pas():
    """Témoin : un écran inventé, et un ancien libellé (« Paramétrage site »), sont refusés."""
    ranges = _onglets_ranges()
    sauvegarde = next(n for n in NOTIONS if n.code == "sauvegarde")
    for faux in ("Admin › 🛠 Exploitation › Inventé", "Admin › Paramétrage site"):
        assert ecrans_d_admin_inconnus((replace(sauvegarde, ecran=faux),), ranges)


# ── Rien n'échappe à la carte ───────────────────────────────────────────────────


def test_chaque_onglet_de_la_liste_blanche_a_sa_notion():
    onglets = [n.onglet for n in NOTIONS if n.onglet]
    assert sorted(onglets) == sorted(reglages.PAR_ONGLET), "un onglet sans notion, ou deux notions"


def test_les_types_declares_visent_des_cles_ecrivables():
    assert set(TYPES) <= reglages.ECRIVABLES, sorted(set(TYPES) - reglages.ECRIVABLES)
    assert set(TYPES_CHAMP_USAGE) <= set(CHAMPS_USAGE) | {"coproprietaires"}


def test_chaque_variable_d_environnement_a_son_theme():
    champs = set(Settings.model_fields)
    themes = [nom for noms in THEMES_ENV.values() for nom in noms]
    assert len(themes) == len(set(themes)), "une variable rangée sous deux thèmes"
    assert set(themes) == champs, (
        f"sans thème : {sorted(champs - set(themes))} · "
        f"thème sans champ : {sorted(set(themes) - champs)}"
    )
    assert SECRETS_ENV <= champs
