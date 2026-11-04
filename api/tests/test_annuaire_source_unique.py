"""La composition du conseil et du syndic ne s'écrit qu'à UN endroit (09/09/2026).

## Le défaut

`routers/admin/annuaire.py` (l'écran) et `routers/admin/arrivants.py` (la fiche
d'accueil remise aux nouveaux résidents) construisaient la même liste, avec le
même tri, les mêmes caches et les mêmes clés — **trente et une lignes identiques
au caractère près**. Le second l'annonçait : *« même logique que
GET /admin/annuaire »*, ce qui est la signature d'une copie qui se sait copie et
que personne ne rapproche.

Elles avaient déjà divergé :

* `est_gestionnaire_site` s'écrivait `site_manager_user_id is not None and …` d'un
  côté, `site_manager_user_id and …` de l'autre — deux réponses différentes pour
  l'identifiant `0` ;
* l'une rendait `id`, l'autre `batiment_id`.

C'est la forme la plus coûteuse de duplication d'un **rendu** : les deux sorties
décrivent le même objet — le conseil syndical — et personne ne les compare, parce
qu'elles vivent sur deux écrans différents (`standards/11` §14).

## Ce que ce fichier verrouille

Le **tri** et la composition, par leur marqueur le plus distinctif : l'ordre des
civilités (« Mme », puis « Mlle »), écrit en dictionnaire. Un fichier qui le
réécrit vient de recopier le tri, et le tri est la moitié de la composition.
Jusqu'au 04/11/2026 c'était la sentinelle `9999` des membres sans bâtiment : le
tri suit depuis le NUMÉRO du bâtiment, la règle de l'écran (#2505), et n'en a
plus besoin. L'autre
moitié est le **dictionnaire de membre** : un balayage unique de `app/` cherche
les deux formes, et ne les tolère que dans la source.
"""

from __future__ import annotations

import ast

from tests.aides_sources import module_app, modules_app

SOURCE = "utils/annuaire.py"

#: Le marqueur du tri : un dictionnaire qui ordonne ces civilités.
CIVILITES_ORDONNEES = {"Mme", "Mlle"}


def _ordonne_les_civilites(source: str) -> bool:
    """Cherche un DICTIONNAIRE dans le code, jamais le texte : la prose le cite."""
    return any(
        isinstance(n, ast.Dict)
        and CIVILITES_ORDONNEES
        <= {c.value for c in n.keys if isinstance(c, ast.Constant) and isinstance(c.value, str)}
        for n in ast.walk(ast.parse(source))
    )


def test_les_deux_ecrans_rendent_la_MEME_composition():
    """Le fait, pas la forme : les deux appelants passent-ils par la source ?

    Un test qui ne regarderait que l'ordre des civilités resterait vert si l'un des deux
    reconstituait la liste autrement — mêmes clés, autre tri.
    """
    import inspect

    from app.routers.admin import annuaire, arrivants

    #  🔴 QUATRE appelants, pas deux (18/09/2026, #779). Les deux écrans
    #  d'administration ne figuraient pas dans cette liste — et c'est exactement
    #  eux qui refaisaient le dictionnaire, dans le fichier qui importe la
    #  fonction. Chacun déclare ce qu'il DOIT employer : les écrans
    #  d'administration ne rendent qu'une des deux compositions. Une liste
    #  d'appelants se périme au suivant ; le balayage qui vient après décrit la
    #  NOTION, et n'a pas ce défaut.
    attendus = (
        (annuaire, "annuaire", ("membres_du_conseil", "membres_du_syndic")),
        (annuaire, "get_composition_cs", ("membres_du_conseil",)),
        (annuaire, "get_syndic_info", ("membres_du_syndic",)),
        (arrivants, "get_fiche_arrivant", ("membres_du_conseil", "membres_du_syndic")),
    )
    for module, fonction, sources in attendus:
        source = inspect.getsource(getattr(module, fonction))
        for attendue in sources:
            assert attendue in source, (
                f"`{module.__name__}.{fonction}` ne passe plus par `{attendue}` : "
                "il a repris sa propre composition."
            )


#: Les clés qui, ENSEMBLE, font reconnaître un dictionnaire de membre. Deux jeux,
#: un par table — le président est propre au conseil, le principal au syndic.
MARQUEURS = (
    ("conseil", {"prenom", "est_president"}),
    ("syndic", {"prenom", "est_principal"}),
)


def _dictionnaires_de_membre(source: str) -> list[str]:
    """Les littéraux de dictionnaire qui décrivent un membre, quel qu'en soit l'auteur."""
    trouves = []
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.Dict):
            continue
        cles = {
            c.value for c in noeud.keys if isinstance(c, ast.Constant) and isinstance(c.value, str)
        }
        for nom, marqueurs in MARQUEURS:
            if marqueurs <= cles:
                trouves.append(nom)
    return trouves


FORME_TRI = "tri (ordre des civilités)"


def _forme_dictionnaire(nom: str) -> str:
    return f"dictionnaire de membre du {nom}"


def _formes_recopiees(source: str) -> list[str]:
    """Les deux moitiés de la composition qu'un module aurait recopiées."""
    formes = [FORME_TRI] if _ordonne_les_civilites(source) else []
    return formes + [
        _forme_dictionnaire(nom) for nom in sorted(set(_dictionnaires_de_membre(source)))
    ]


def test_aucun_module_ne_recopie_la_composition_du_conseil():
    """🔴 La portée décrit la notion, pas la liste des appelants connus.

    Le test précédent énumère les appelants : il ne peut rien dire du cinquième.
    Celui-ci cherche les deux FORMES de la composition — l'ordre des civilités, et
    un littéral de dictionnaire portant les clés d'un membre — partout dans
    `app/`, et ne les tolère que dans la source.

    C'est ce qui a manqué le 18/09/2026 : `routers/admin/annuaire.py` refaisait
    la composition pour ses deux écrans, avec son propre cache de bâtiments et
    sa propre écriture de la règle du gestionnaire de site, dans le fichier même
    qui importe `membres_du_conseil`. Aucun contrôle ne le voyait, parce que le
    seul qui parlait du sujet regardait deux fonctions nommées à la main
    (`standards/04` §40).
    """
    fautifs = {}
    for m in modules_app():
        rel = m.rel
        if rel == SOURCE:
            continue
        formes = _formes_recopiees(m.source)
        if formes:
            fautifs[rel] = formes

    assert not fautifs, (
        "Ces modules recopient la composition du conseil ou du syndic :\n"
        + "\n".join(f"  {f} : {', '.join(q)}" for f, q in sorted(fautifs.items()))
        + "\nEmployer `membres_du_conseil` / `membres_du_syndic` de "
        "`app.utils.annuaire`, en passant `pour_administration=True` si les "
        "champs de gestion manquent — une méthode trop pauvre ne fait pas "
        "contourner un peu, elle fait recopier en entier. Deux tris d'une même "
        "liste finissent par se contredire, et sur deux écrans que personne ne "
        "compare."
    )


def test_cas_zero_la_source_porte_bien_les_formes_cherchees():
    """🔴 Sans elles, le balayage ne cherche plus rien et reste vert.

    C'est le cas zéro de `standards/04` §2 : un contrôle dont le motif ne
    correspond plus à rien ne refuse plus rien, et il ne le dit pas.
    """
    formes = _formes_recopiees(module_app(SOURCE).source)
    attendues = [FORME_TRI] + sorted(_forme_dictionnaire(nom) for nom, _ in MARQUEURS)
    assert formes == attendues, (
        f"`{SOURCE}` ne porte plus toutes les formes reconnues ({formes}) : ce "
        "contrôle laisserait passer une copie sans le dire."
    )
    assert len(modules_app()) > 50, "le parcours ne décrit plus `app/`."
