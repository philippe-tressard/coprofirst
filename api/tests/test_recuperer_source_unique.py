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

## Pourquoi un PLAFOND et non zéro

Le ticket demandait « plafond figé à 0 ». Une partie des `HTTPException(404)`
restants **ne sont pas convertibles** : ils suivent un `select` avec jointure ou
filtre, où il n'y a pas d'identifiant unique à passer au helper — et certains
sont des 404 de **visibilité**, qui relèvent de l'autorisation et doivent rester
là où les droits se lisent (`standards/03` §1).

Le plafond est donc le nombre **réel** constaté, et il ne peut que descendre :
ajouter un 404 brut fait échouer le test. C'est un plafond décroissant, jamais
une tolérance ouverte (`standards/05` §2).

⚠️ **32, et pas 14.** Le ticket annonçait vingt-six écritures convertibles ; à la
mesure, six seulement le sont mécaniquement — les autres portent une condition
**composée** (`if not objet or objet.bail_id != bail_id`), c'est-à-dire deux
questions dans une ligne. Les convertir demande de les séparer une par une, et
c'est le volet 404 de #1047, pas celui-ci. Descendre le plafond en bloc aurait
fait passer une réécriture sémantique pour un remplacement mécanique.
"""

import ast
from pathlib import Path

from tests.aides_sources import modules_app

RACINE = Path(__file__).resolve().parents[1] / "app"

#: Le module qui porte la question « existe-t-il ? ».
SOURCE = "utils/recuperer.py"

#: Ce qui reste, et qui ne peut PAS passer par le helper : un 404 qui suit un
#: `select` (pas d'identifiant unique) ou qui relève de la visibilité.
#:
#: 🔴 Ce nombre ne monte JAMAIS. Il descend quand une de ces écritures devient
#: convertible ; l'augmenter, c'est rouvrir la duplication que `ou_404` a fermée.
#: 08/10/2026 : 11 → 6 — `connu_ou_404` (clé d'un registre, ×2) et
#: `present_ou_404` (résultat `None`, ×3). 13/10/2026 : 6 → 4 — la photo de
#: relevé (condition composée, séparée en `ou_404` puis `present_ou_404`) et la
#: catégorie de FAQ. Restent : la visibilité (`auth/appartenance`, ×2), la liste
#: blanche d'accès des fichiers de compteurs, le dossier IMAP. Carte : #1571.
PLAFOND_404_BRUTS = 4


def _404_bruts() -> list[str]:
    """Tout `HTTPException(404…)` du code applicatif, hors le helper lui-même."""
    trouves = []
    for m in modules_app():
        chemin = m.rel
        if chemin == SOURCE:
            continue
        arbre = m.arbre
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)):
                continue
            if noeud.func.id != "HTTPException":
                continue
            args = list(noeud.args) + [k.value for k in noeud.keywords]
            if any(isinstance(a, ast.Constant) and a.value == 404 for a in args):
                trouves.append(f"app/{chemin}:{noeud.lineno}")
    return trouves


def test_le_plafond_est_a_jour():
    """Un 404 de plus est une copie de plus — le helper existe. Et un plafond
    qui ne colle plus au réel cesse de mesurer.

    L'égalité tient les deux sens : au-dessus, une copie a été ajoutée ; en
    dessous, le plafond autoriserait silencieusement de nouvelles copies jusqu'à
    son niveau — le contrôle serait vert pendant qu'on rouvre la duplication.
    """
    bruts = _404_bruts()
    reels = len(bruts)
    assert reels == PLAFOND_404_BRUTS, (
        f"Le plafond dit {PLAFOND_404_BRUTS}, le dépôt porte {reels} "
        "`HTTPException(404)` écrits à la main :\n"
        + "\n".join(f"  {b}" for b in bruts)
        + (
            "\n\nDescendre le plafond."
            if reels < PLAFOND_404_BRUTS
            else "\n\nAller chercher un objet par son identifiant passe par "
            "`utils/recuperer.ou_404` — le libellé y est composé, donc les messages du "
            "produit disent tous la même chose de la même façon."
        )
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
