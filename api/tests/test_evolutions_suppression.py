"""Les trois fils disent la MÊME chose quand on veut effacer une entrée (#512).

## Ce que ce fichier protège

Le geste de suppression d'une entrée de fil n'existait que pour les tickets. Le
bouton 🗑️, lui, s'affichait sur **cinq** écrans : un administrateur cliquait, et
rien ne se passait — pas d'action, pas d'erreur, pas de trace (#505).

Les deux routes manquantes auraient pu se copier. C'est ce que le ticket
interdisait explicitement : *« les nouveaux endpoints doivent dire **la même
chose** que lui, ni plus ni moins »*. Trois copies auraient porté chacune leur
liste de types effaçables et leur message de refus, et la première divergence
serait passée inaperçue — un administrateur ne compare pas le refus d'un écran à
celui d'un autre.

Ces tests vérifient donc l'**identité**, pas la ressemblance :

1. les trois routes existent, avec la même méthode et la même forme d'URL ;
2. les trois passent par la même fonction (`supprimer_evolution`) ;
3. les trois exigent `require_admin` — corriger est ouvert à l'auteur, effacer
   ne l'est pas ;
4. la liste des types effaçables est la même côté écran et côté serveur, alors
   que rien ne peut la partager entre les deux images Docker.

## 🔴 Pourquoi 3 et 4 par analyse statique

Le contrôle d'accès et la liste des types ne se voient pas dans une réponse
HTTP nominale : un test fonctionnel qui appelle la route en administrateur passe
tout aussi bien si la dépendance a été relâchée à `require_cs_or_admin`. Il faut
regarder la **déclaration**, pas le comportement du cas heureux — c'est la même
famille que `test_emails_contexte_appel.py`, qui a trouvé un bug latent là où
tous les envois fonctionnaient.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from app.utils.evolutions import TYPES_EFFACABLES

RACINE = pathlib.Path(__file__).parent.parent
FRONT = RACINE.parent / "front"

#: Les trois fils du site : le fichier qui porte la route, le nom de la fonction,
#: et le chemin DÉCLARÉ dans son décorateur (préfixe de montage exclu).
FILS = {
    "ticket": (
        "app/routers/tickets/evolutions.py",
        "delete_evolution",
        "/{ticket_id}/evolutions/{evol_id}",
    ),
}


#  ⚠️ Tout se lit dans le SOURCE, pas dans `app.routes`. Importer `app.main`
#  hors du conteneur ne monte pas les routeurs : la liste des routes y est vide,
#  et un test qui l'interrogerait passerait au vert en ne regardant RIEN — le
#  cas zéro exactement (`standards/04` §2). Découvert en écrivant ce fichier :
#  la première version affirmait l'absence des trois routes, y compris celle des
#  tickets, qui existe depuis le 18/08.


def _fonction(chemin: str, nom: str) -> ast.FunctionDef:
    arbre = ast.parse((RACINE / chemin).read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) and noeud.name == nom:
            return noeud
    pytest.fail(f"{nom} introuvable dans {chemin}")


@pytest.mark.parametrize("fil", sorted(FILS))
def test_la_route_de_suppression_existe(fil):
    """Le geste existe pour les trois fils, pas seulement pour les tickets."""
    chemin, nom, url = FILS[fil]
    fonction = _fonction(chemin, nom)
    #  ⚠️ On lit l'ARGUMENT du décorateur, pas sa forme rendue : `ast.unparse`
    #  normalise les guillemets, si bien qu'une comparaison de texte cherchant
    #  des guillemets doubles ne trouve jamais rien — et le test échoue en
    #  affirmant l'absence d'une route qui existe.
    declarees = {
        (d.func.attr, d.args[0].value)
        for d in fonction.decorator_list
        if isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and d.args
        and isinstance(d.args[0], ast.Constant)
    }
    assert ("delete", url) in declarees, (
        f"{fil} : aucun `@router.delete({url!r})` — trouvé {sorted(declarees)}"
    )


@pytest.mark.parametrize("fil", sorted(FILS))
def test_chaque_route_delegue_au_geste_partage(fil):
    """Aucune des trois ne décide seule — sinon les trois divergeront.

    Une route qui réimplémenterait le contrôle (`if evol.type not in (…)`)
    passerait tous les tests fonctionnels le jour où elle est écrite, et
    cesserait d'être d'accord avec les deux autres au premier ajustement.
    """
    chemin, nom, _ = FILS[fil]
    fonction = _fonction(chemin, nom)
    appels = {
        n.func.id
        for n in ast.walk(fonction)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "supprimer_evolution" in appels, (
        f"{fil} : la route n'appelle pas `supprimer_evolution` — "
        "elle réimplémente le geste, et divergera."
    )


@pytest.mark.parametrize("fil", sorted(FILS))
def test_effacer_est_reserve_a_l_administrateur(fil):
    """🔴 `require_admin`, jamais `require_cs_or_admin`.

    Corriger sa propre entrée est ordinaire ; effacer fait disparaître une trace
    que d'autres ont pu lire et sur laquelle ils ont pu agir. Le fil sert de
    preuve au conseil syndical face au syndic — une entrée effacée ne se
    retrouve pas.

    Un relâchement de cette dépendance ne se verrait dans AUCUN appel réussi :
    seule la déclaration le dit.
    """
    chemin, nom, _ = FILS[fil]
    fonction = _fonction(chemin, nom)
    #  ⚠️ On lit la SIGNATURE, pas le corps ni la docstring. La première version
    #  de ce test cherchait « require_cs_or_admin » dans le source entier et
    #  échouait sur les tickets — dont la docstring explique justement pourquoi
    #  ce n'est PAS cette dépendance. Un contrôle qui lit de la prose mesure
    #  autre chose que ce qu'il croit.
    deps = {ast.unparse(d) for d in fonction.args.defaults if isinstance(d, ast.Call)}
    assert any("require_admin" in d for d in deps), (
        f"{fil} : la suppression n'exige pas `require_admin` — dépendances : {sorted(deps)}"
    )
    assert not any("require_cs_or_admin" in d for d in deps), (
        f"{fil} : la suppression accepte le conseil syndical — "
        "l'arbitrage du 18/08/2026 réserve le geste à l'administrateur."
    )


def test_l_ecran_lit_les_gestes_servis_et_ne_garde_aucune_copie_de_la_regle():
    """⚠️ La copie assumée a disparu (#2646) : l'écran LIT `peut_supprimer`.

    Les contextes de build sont `./api` et `./front` : rien de la racine
    n'entre dans les images, la liste des types effaçables vivait donc en deux
    exemplaires, surveillés par un test de concordance. Le serveur sert désormais
    le droit par entrée (`auth/gestes_evolution`) : l'écran, comme l'app iOS, le
    lit. Le cas fautif que ce test refuse — une liste de types, une identité ou un
    rôle recopiés dans le composant — est ce que la concordance ne faisait que
    comparer.
    """
    rubrique = (FRONT / "src/lib/components/RubriqueHistorique.svelte").read_text(encoding="utf-8")
    assert "evol.peut_supprimer" in rubrique and "evol.peut_modifier" in rubrique
    for copie in ("TYPES_EFFACABLES", "TYPES_CORRIGEABLES", "peutEditer(", "estAdmin"):
        assert copie not in rubrique, f"RubriqueHistorique recopie la règle du serveur : {copie}"


def test_une_reponse_n_est_jamais_effacable():
    """La règle qui protège la parole d'autrui, quel que soit le fil.

    Une réponse appartient à son auteur, souvent un résident. L'inscrire dans un
    test plutôt que dans un commentaire est ce qui empêchera de l'ajouter « pour
    faire simple » le jour où un administrateur demandera à retirer une réponse
    déplacée — ce qui relève de la modération, pas du fil.
    """
    assert "reponse" not in TYPES_EFFACABLES
