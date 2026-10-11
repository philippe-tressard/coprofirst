"""Toute référence vers un compte est CLASSÉE : gardée sans nom, ou personnelle (#1821).

Ce qu'un compte supprimé emporte ne se décide pas dans `supprimer_compte` : la
purge référentielle supprime toute ligne dont la référence au compte est
OBLIGATOIRE, et délie une référence facultative. Une table ajoutée avec un
`auteur_id` obligatoire partait donc avec le compte sans que personne l'ait
décidé — c'est ce qui était arrivé aux affaires (#1688), aux documents et aux
règles de la résidence (#1821).

Désormais chaque référence obligatoire se range dans `CONTENUS_PERSONNELS`, avec
sa raison, et chaque contenu gardé dans `CONTENUS_GARDES`, avec une référence
facultative. Les deux listes se lisent contre le modèle, dans les deux sens.
"""

from __future__ import annotations

from app.utils.purge_referentielle import references_entrantes
from app.utils.suppression_compte import CONTENUS_GARDES, CONTENUS_PERSONNELS


def _references() -> dict[tuple[str, str], bool]:
    refs = {
        (t.name, c.name): obligatoire for t, c, obligatoire in references_entrantes("utilisateur")
    }
    #  Cas zéro : une lecture des métadonnées cassée rendrait tout vert.
    assert len(refs) > 40, f"seulement {len(refs)} références lues"
    return refs


def test_toute_reference_obligatoire_est_declaree_personnelle():
    refs = _references()
    non_classees = sorted(k for k, oblig in refs.items() if oblig and k not in CONTENUS_PERSONNELS)
    assert not non_classees, (
        "Référence OBLIGATOIRE vers un compte que personne n'a classée — supprimer le "
        "compte supprimerait la ligne. La ranger dans CONTENUS_PERSONNELS (elle part) ou "
        f"la rendre facultative et la ranger dans CONTENUS_GARDES : {non_classees}"
    )


def test_un_contenu_garde_a_une_reference_facultative():
    refs = _references()
    for cle, raison in CONTENUS_GARDES.items():
        assert cle in refs, f"{cle} n'existe plus dans le modèle — à retirer de CONTENUS_GARDES"
        assert not refs[cle], f"{cle} ({raison}) est déclaré gardé mais reste obligatoire"


def test_un_contenu_personnel_existe_et_reste_obligatoire():
    refs = _references()
    for cle in CONTENUS_PERSONNELS:
        assert cle in refs, f"{cle} n'existe plus dans le modèle — à retirer de CONTENUS_PERSONNELS"
        assert refs[cle], f"{cle} est facultatif : il ne part plus avec le compte, le reclasser"


def test_aucune_reference_n_est_dans_les_deux_listes():
    assert not (CONTENUS_GARDES.keys() & CONTENUS_PERSONNELS.keys())


def test_un_auteur_garde_se_lit_par_ou_rien():
    """`session.get(Utilisateur, x.auteur_id)` sur une référence gardée — désormais vide
    pour un compte supprimé — avertit que la clé vide « pourra lever une erreur ». Elle
    se lit par `utils/recuperer.ou_rien`, qui ne demande rien quand la clé est vide."""
    import re

    from tests.aides_sources import modules_app

    #  `user_id` (les votes) est écarté : le nom est trop commun — jetons, liens de
    #  lot, tous obligatoires —, et aucun écran ne lit l'auteur d'un vote.
    colonnes = "|".join(sorted({col for _, col in CONTENUS_GARDES} - {"user_id"}))
    motif = re.compile(rf"session\.get\(\s*Utilisateur\s*,\s*[\w.]+\.({colonnes})\s*\)")
    #  `annonces.py` lit l'auteur d'une petite annonce : référence PERSONNELLE, jamais vide.
    fautes = [
        f"{m.rel}:{n}"
        for m in modules_app()
        if m.rel != "routers/annonces.py"
        for n, ligne in enumerate(m.source.splitlines(), 1)
        if motif.search(ligne)
    ]
    assert not fautes, f"lire par `ou_rien(session, Utilisateur, …)` : {fautes}"
