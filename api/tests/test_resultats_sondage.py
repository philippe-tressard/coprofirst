"""Les résultats d'un sondage ne quittent le serveur que s'ils sont lisibles.

Écrit le 17/08/2026 en instruisant #397. Le ticket demandait de reformuler un
libellé — « Résultats visibles avant clôture », qui ne disait pas *à qui*. En
vérifiant ce que le serveur appliquait, il est apparu qu'il n'appliquait **rien** :

    GET /sondages/{id} calculait et renvoyait, pour chaque option,
    `nb_votes` et `reponses_libres` sans aucune condition — ni sur
    `resultats_publics`, ni sur la clôture, ni sur le fait d'avoir voté.

Décocher la case ne cachait donc rien. Les décomptes **et les réponses en texte
libre** partaient dans la réponse réseau, lisibles par n'importe quel destinataire
du sondage avant son vote — alors que la case existe précisément pour qu'un vote
en cours n'influence pas les suivants.

Ce fichier couvre les deux moitiés, parce que couvrir la première seule ne
protège de rien :

  1. **La décision** — `resultats_sondage_visibles`, fonction pure, sa table de
     vérité complète.
  2. **Le point d'appel** — que `get_sondage` produise bel et bien `nb_votes`
     SOUS cette décision, et non à côté.

Le second point est la leçon du 11/08 (cf. `check-reliability.sh`) : je testais la
décision, pas le tuyau qui la nourrit. Une fonction pure parfaite qu'un routeur
n'appelle pas laisse le défaut intact, et le test reste vert.
"""

import ast
from pathlib import Path

import pytest

from app.utils.visibility import resultats_sondage_visibles

#  `sondages.py` est devenu le paquet `sondages/` le 17/08/2026 (le garde-fou de
#  modularité a refusé qu'il grossisse au-delà de 514 lignes). Le cas zéro
#  ci-dessous a signalé le déplacement en ÉCHOUANT — c'est exactement ce qu'on
#  attend : sans lui, ce fichier aurait analysé un chemin inexistant et conclu
#  au vert sur zéro ligne.
ROUTER = Path(__file__).resolve().parents[1] / "app" / "routers" / "sondages" / "crud.py"


# ── 1. La décision ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "resultats_publics, cloture, attendu, pourquoi",
    [
        (True, False, True, "case cochée, sondage ouvert : c'est le cas nominal"),
        (True, True, True, "case cochée, sondage clos : visibles a fortiori"),
        (
            False,
            True,
            True,
            "case DÉCOCHÉE mais sondage CLOS — « avant clôture » "
            "ne veut pas dire « jamais » : c'est le cas que le front "
            "rendait impossible en écrasant sa propre condition",
        ),
        (
            False,
            False,
            False,
            "case décochée, sondage ouvert : LE seul cas à masquer, et celui qui ne l'était pas",
        ),
    ],
)
def test_table_de_verite(resultats_publics, cloture, attendu, pourquoi):
    assert resultats_sondage_visibles(resultats_publics, cloture) is attendu, pourquoi


def test_aucune_exception_pour_personne():
    """La signature ne prend PAS d'utilisateur — donc pas de passe-droit possible.

    Décision assumée (#397) : ni l'auteur ni le conseil syndical ne voient la
    participation avant la clôture quand la case est décochée. Si un jour on veut
    l'inverse, il faudra changer cette signature — et ce test échouera, ce qui est
    exactement le moment où la question doit être reposée.
    """
    import inspect

    params = list(inspect.signature(resultats_sondage_visibles).parameters)
    assert params == ["resultats_publics", "cloture"], (
        "La règle a gagné un paramètre : si c'est un utilisateur, c'est un "
        "passe-droit, et il doit être décidé explicitement, pas glissé ici."
    )


# ── 2. Le point d'appel ───────────────────────────────────────────────────────


def _arbre_et_parents():
    arbre = ast.parse(ROUTER.read_text(encoding="utf-8"))
    parents = {}
    for noeud in ast.walk(arbre):
        for enfant in ast.iter_child_nodes(noeud):
            parents[enfant] = noeud
    return arbre, parents


def _fonction(arbre, nom):
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == nom:
            return noeud
    return None


def test_cas_zero_le_routeur_est_analysable():
    """Sans cette garde, un renommage rendrait les tests suivants vides et verts."""
    assert ROUTER.exists(), f"{ROUTER} introuvable — ce contrôle ne peut pas conclure."
    arbre, _ = _arbre_et_parents()
    assert _fonction(arbre, "get_sondage") is not None, (
        "get_sondage a disparu ou a été renommée : les contrôles ci-dessous "
        "porteraient sur rien et passeraient au vert."
    )


def test_le_routeur_appelle_la_regle_partagee():
    arbre, _ = _arbre_et_parents()
    appels = [
        n
        for n in ast.walk(arbre)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "resultats_sondage_visibles"
    ]
    assert appels, (
        "routers/sondages.py n'appelle plus `resultats_sondage_visibles`. "
        "Si la condition a été réécrite sur place, elle est libre de diverger "
        "de la règle testée ci-dessus — c'est exactement ce qui s'était produit "
        "entre le front et l'API (#397)."
    )


def test_nb_votes_est_produit_sous_la_decision():
    """`nb_votes` ne doit exister que dans une branche gardée par la décision.

    C'est le contrôle qui aurait attrapé le défaut d'origine : la fonction pure
    n'existait pas, mais si elle avait existé sans être branchée, tout le reste
    de ce fichier serait resté vert.
    """
    arbre, parents = _arbre_et_parents()
    get_sondage = _fonction(arbre, "get_sondage")

    mentions = [
        n
        for n in ast.walk(get_sondage)
        if isinstance(n, ast.Constant) and n.value in ("nb_votes", "part", "reponses_libres")
    ]
    assert mentions, (
        "Ni `nb_votes` ni `reponses_libres` ne sont produits par get_sondage — "
        "la forme de la réponse a changé, ce contrôle ne sait plus quoi vérifier."
    )

    for mention in mentions:
        garde = False
        courant = mention
        while courant in parents:
            courant = parents[courant]
            if courant is get_sondage:
                break
            if isinstance(courant, ast.If):
                noms = {n.id for n in ast.walk(courant.test) if isinstance(n, ast.Name)}
                if "resultats_visibles" in noms:
                    garde = True
                    break
        assert garde, (
            f"« {mention.value} » (ligne {mention.lineno}) est produit HORS de la "
            "branche gardée par `resultats_visibles`. Les décomptes partiraient "
            "dans la réponse réseau quelle que soit la case cochée — le défaut "
            "d'origine de #397, qu'aucun masquage côté front ne corrige."
        )
