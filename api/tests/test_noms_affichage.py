"""« Prénom NOM » — la règle d'affichage d'une personne, servie aux deux clients.

## Pourquoi ce test (31/08/2026)

Le fil affichait « Jean-Baptiste ForT » : la casse telle qu'elle avait été
tapée. Arbitré à l'écran — *« l'affichage devrait être Prénom NOM => Nom en
majuscule »*.

La règle n'est écrite qu'**ici**, côté serveur (`app/utils/noms.py`) : le site et
l'app iOS LISENT le nom servi (`nom_affiche`, `schemas_nom_servi.NomServi`), et
une personne en cours de saisie est nommée par `POST /noms/affiche` (#2633). Le
jumeau du front (`nomAffiche`) et sa concordance exécutée sont retirés avec lui.
"""

from __future__ import annotations

from app.utils.noms import nom_affiche

from tests.aides_noms import CAS


def test_le_nom_passe_en_capitales_le_prenom_non():
    """Le cas signalé à l'écran, et ses voisins."""
    for prenom, nom, attendu in CAS:
        assert nom_affiche(prenom, nom) == attendu, (
            f"nom_affiche({prenom!r}, {nom!r}) rend "
            f"{nom_affiche(prenom, nom)!r} au lieu de {attendu!r}"
        )


def test_l_absence_ne_produit_JAMAIS_None_ni_espace_orphelin():
    """Une personne à demi connue s'affiche quand même, et proprement.

    C'est le cas qui se perd : `f"{prenom} {nom}"` sur un nom vide laisse un
    espace en fin de chaîne, invisible dans le code et visible dans une liste
    triée ou une comparaison.
    """
    assert nom_affiche(None, None) == ""
    assert nom_affiche(None, "Martin") == "MARTIN"
    assert nom_affiche("Anne", None) == "Anne"
    for prenom, nom, _ in CAS:
        assert nom_affiche(prenom, nom) == nom_affiche(prenom, nom).strip()


def test_la_regle_INVERSE_existe_toujours_et_reste_distincte():
    """⚠️ `_nom_presentable` fait l'inverse, et les confondre casse les courriels.

    « DUPONT » → « Dupont » sert à s'ADRESSER à quelqu'un ; `nom_affiche` sert à
    l'IDENTIFIER dans une liste. Si l'une venait à déléguer à l'autre, les
    courriels se mettraient à hurler — ce test le refuse.
    """
    from app.utils.destinataires import _nom_presentable

    assert _nom_presentable("DUPONT") == "Dupont"
    assert nom_affiche("Jean", "dupont") == "Jean DUPONT"
